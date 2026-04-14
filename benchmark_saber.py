"""Scaffold for benchmarking SABER KEM variants via an external executable."""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark_schema import (
    SABER_RESULTS_PATH,
    build_algorithm_metadata,
    build_result_entry,
    build_results_document,
    configure_logging,
    empty_operation_stats,
    write_json_document,
)

DEFAULT_OUTPUT_PATH = SABER_RESULTS_PATH
DEFAULT_EXECUTABLE = None
SABER_VARIANTS = [
    "LightSABER",
    "SABER",
    "FireSABER",
]

LOGGER = logging.getLogger(__name__)


def resolve_executable(explicit_path: str | None = None) -> str | None:
    """Resolve the SABER benchmark executable if it is available."""
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists():
            return str(candidate)
        return None

    # TODO: Replace this with the path or discovery logic for the official SABER benchmark executable.
    guessed_names = [
        "saber_bench",
        "PQCgenKAT_kem",
    ]
    for name in guessed_names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return DEFAULT_EXECUTABLE


def run_external_command(
    command: list[str],
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run an external benchmark command and capture text output."""
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def extract_float(pattern: str, text: str) -> float | None:
    """Extract the first floating-point value matched by a regular expression."""
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def parse_timing_output(stdout: str, stderr: str = "") -> dict[str, Any]:
    """Parse benchmark timing output from the external SABER implementation."""
    combined_output = "\n".join(part for part in [stdout, stderr] if part)

    # TODO: Replace these placeholder patterns with parsing rules from the official SABER benchmark output.
    keygen_mean_ms = extract_float(r"key(?:\s+)?gen(?:eration)?(?:\s+mean)?\s*[:=]\s*([0-9.]+)", combined_output)
    encaps_mean_ms = extract_float(r"encap(?:sulation)?(?:\s+mean)?\s*[:=]\s*([0-9.]+)", combined_output)
    decaps_mean_ms = extract_float(r"decap(?:sulation)?(?:\s+mean)?\s*[:=]\s*([0-9.]+)", combined_output)

    if keygen_mean_ms is None and encaps_mean_ms is None and decaps_mean_ms is None:
        return {
            "parsed": False,
            "notes": (
                "No known timing fields were detected in SABER benchmark output. "
                "Update parse_timing_output() for the official implementation."
            ),
            "raw_stdout": stdout,
            "raw_stderr": stderr,
        }

    def parsed_operation_stats(mean_ms: float | None) -> dict[str, Any]:
        """Map parsed mean-only output into the shared benchmark stat shape."""
        if mean_ms is None:
            return empty_operation_stats()

        value_ns = mean_ms * 1_000_000
        return {
            "mean_ns": value_ns,
            "median_ns": value_ns,
            "min_ns": value_ns,
            "max_ns": value_ns,
            "stdev_ns": 0.0,
            "mean_ms": mean_ms,
            "median_ms": mean_ms,
            "min_ms": mean_ms,
            "max_ms": mean_ms,
            "stdev_ms": 0.0,
            "iterations": None,
            "warmup_iterations": None,
            "peak_memory_bytes": None,
        }

    return {
        "parsed": True,
        "benchmarks": {
            "keygen": parsed_operation_stats(keygen_mean_ms),
            "encapsulation": parsed_operation_stats(encaps_mean_ms),
            "decapsulation": parsed_operation_stats(decaps_mean_ms),
        },
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


def build_algorithm_result(
    variant: str,
    parsed_output: dict[str, Any] | None = None,
    status: str = "placeholder",
    notes: str | None = None,
) -> dict[str, Any]:
    """Build a per-variant result entry shaped like the OQS output."""
    benchmarks = parsed_output.get("benchmarks") if parsed_output and parsed_output.get(
        "parsed"
    ) else {
        "keygen": empty_operation_stats(),
        "encapsulation": empty_operation_stats(),
        "decapsulation": empty_operation_stats(),
    }

    entry = build_result_entry(
        algorithm=variant,
        metadata=build_algorithm_metadata(algorithm=variant),
        benchmarks=benchmarks,
        status=status,
        notes=notes,
        raw_stdout=parsed_output.get("raw_stdout") if parsed_output else None,
        raw_stderr=parsed_output.get("raw_stderr") if parsed_output else None,
    )
    if parsed_output and parsed_output.get("notes"):
        entry["notes"] = parsed_output["notes"]
    return entry


def benchmark_variant(
    executable_path: str,
    variant: str,
) -> dict[str, Any]:
    """Run the external executable for a single SABER variant."""
    LOGGER.info("Benchmarking SABER algorithm: %s", variant)
    # TODO: Replace this command shape with the official SABER benchmarking invocation.
    command = [executable_path, variant]
    completed = run_external_command(command)

    if completed.returncode != 0:
        return build_algorithm_result(
            variant=variant,
            status="error",
            notes=(
                f"SABER benchmark command failed with exit code {completed.returncode}. "
                "Inspect raw output and update the command/parsing logic."
            ),
            parsed_output={
                "parsed": False,
                "raw_stdout": completed.stdout,
                "raw_stderr": completed.stderr,
            },
        )

    parsed_output = parse_timing_output(completed.stdout, completed.stderr)
    if parsed_output.get("parsed"):
        return build_algorithm_result(
            variant=variant,
            parsed_output=parsed_output,
            status="ok",
        )

    return build_algorithm_result(
        variant=variant,
        parsed_output=parsed_output,
        status="unparsed",
        notes="Benchmark output was captured but could not be parsed yet.",
    )


def run_saber_benchmarks(
    output_dir: Path = DEFAULT_OUTPUT_PATH.parent,
    iterations: int = 100,
    executable_path: str | None = None,
    output_path: Path | None = None,
) -> list[Path]:
    """Run the SABER scaffold and save results without crashing if unavailable."""
    configure_logging()
    _ = iterations
    resolved_output_path = output_path or (output_dir / DEFAULT_OUTPUT_PATH.name)

    resolved_executable = resolve_executable(executable_path)
    if not resolved_executable:
        message = (
            "SABER benchmark executable was not found. "
            "Set the official executable path in benchmark_saber.py or pass --executable."
        )
        LOGGER.info(message)
        document = build_results_document(
            tool="external-saber-benchmark",
            results=[
                build_algorithm_result(
                    variant=variant,
                    status="not_installed",
                    notes=message,
                )
                for variant in SABER_VARIANTS
            ],
            timed_iterations=None,
            warmup_iterations=None,
        )
        LOGGER.info("Saving SABER benchmark results to %s", resolved_output_path)
        return [write_json_document(document, resolved_output_path)]

    results = [
        benchmark_variant(executable_path=resolved_executable, variant=variant)
        for variant in SABER_VARIANTS
    ]
    document = build_results_document(
        tool="external-saber-benchmark",
        results=results,
        timed_iterations=None,
        warmup_iterations=None,
    )
    LOGGER.info("Saving SABER benchmark results to %s", resolved_output_path)
    return [write_json_document(document, resolved_output_path)]


def build_parser() -> argparse.ArgumentParser:
    """Create a command-line interface for standalone SABER benchmarking."""
    parser = argparse.ArgumentParser(
        description="Benchmark SABER variants using an external executable scaffold."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the JSON file where SABER results are saved.",
    )
    parser.add_argument(
        "--executable",
        type=str,
        default=None,
        help="Path to the official SABER benchmark executable.",
    )
    return parser


def main() -> None:
    """Run the SABER scaffold as a standalone script."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    output_path = args.output
    resolved_executable = resolve_executable(args.executable)
    if not resolved_executable:
        message = (
            "SABER benchmark executable was not found. "
            "Results will be written as placeholders to keep the pipeline usable."
        )
        LOGGER.info(message)
        document = build_results_document(
            tool="external-saber-benchmark",
            results=[
                build_algorithm_result(
                    variant=variant,
                    status="not_installed",
                    notes=message,
                )
                for variant in SABER_VARIANTS
            ],
            timed_iterations=None,
            warmup_iterations=None,
        )
        LOGGER.info("Saving SABER benchmark results to %s", output_path)
        write_json_document(document, output_path)
        return

    results = [
        benchmark_variant(executable_path=resolved_executable, variant=variant)
        for variant in SABER_VARIANTS
    ]
    document = build_results_document(
        tool="external-saber-benchmark",
        results=results,
        timed_iterations=None,
        warmup_iterations=None,
    )
    LOGGER.info("Saving SABER benchmark results to %s", output_path)
    write_json_document(document, output_path)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as exc:
        print(f"SABER benchmark command timed out: {exc}", file=sys.stderr)
        sys.exit(1)
