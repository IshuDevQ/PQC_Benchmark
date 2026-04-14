"""Benchmark ML-KEM and NTRU KEMs available through the oqs Python package."""

from __future__ import annotations

import argparse
import logging
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

try:
    import oqs
except ImportError as exc:  # pragma: no cover - runtime dependency
    oqs = None
    OQS_IMPORT_ERROR = exc
else:
    OQS_IMPORT_ERROR = None

from benchmark_schema import (
    OQS_RESULTS_PATH,
    build_algorithm_metadata as build_shared_algorithm_metadata,
    build_result_entry,
    build_results_document,
    configure_logging,
    write_json_document,
)

DEFAULT_OUTPUT_PATH = OQS_RESULTS_PATH
DEFAULT_ITERATIONS = 100
DEFAULT_WARMUP_ITERATIONS = 10
TARGET_ML_KEMS = [
    "ML-KEM-512",
    "ML-KEM-768",
    "ML-KEM-1024",
]

LOGGER = logging.getLogger(__name__)
OQS_SETUP_MESSAGE = (
    "The oqs Python package could not be imported. Run this project through Docker: "
    "'docker compose run --rm pqc-bench python main.py oqs' or "
    "'./run_in_docker.sh python main.py oqs'. This avoids host liboqs setup issues."
)


def require_oqs() -> Any:
    """Return the imported oqs module or raise a clear runtime error."""
    if oqs is None:
        raise RuntimeError(OQS_SETUP_MESSAGE) from OQS_IMPORT_ERROR
    return oqs


def list_target_algorithms() -> list[str]:
    """Return the enabled ML-KEM and NTRU algorithms to benchmark."""
    oqs_module = require_oqs()
    enabled = set(oqs_module.get_enabled_kem_mechanisms())

    selected: list[str] = [name for name in TARGET_ML_KEMS if name in enabled]
    selected.extend(name for name in sorted(enabled) if name.startswith("NTRU"))
    LOGGER.info("Loaded %d enabled OQS benchmark algorithms", len(selected))
    return selected


def warm_up(operation: Callable[[], Any], iterations: int) -> None:
    """Execute an operation repeatedly before timed measurement."""
    for _ in range(iterations):
        operation()


def compute_timing_stats(samples_ns: list[int]) -> dict[str, float]:
    """Compute summary statistics for a list of nanosecond timings."""
    if not samples_ns:
        raise ValueError("At least one timing sample is required.")

    stdev_ns = statistics.stdev(samples_ns) if len(samples_ns) > 1 else 0.0
    return {
        "mean_ns": statistics.mean(samples_ns),
        "median_ns": statistics.median(samples_ns),
        "min_ns": min(samples_ns),
        "max_ns": max(samples_ns),
        "stdev_ns": stdev_ns,
        "mean_ms": statistics.mean(samples_ns) / 1_000_000,
        "median_ms": statistics.median(samples_ns) / 1_000_000,
        "min_ms": min(samples_ns) / 1_000_000,
        "max_ms": max(samples_ns) / 1_000_000,
        "stdev_ms": stdev_ns / 1_000_000,
    }


def benchmark_operation(
    operation: Callable[[], Any],
    timed_iterations: int,
    warmup_iterations: int,
) -> dict[str, float | int]:
    """Benchmark an operation with warm-up runs and peak traced memory."""
    warm_up(operation, warmup_iterations)

    timings_ns: list[int] = []
    peak_memory_bytes = 0

    tracemalloc.start()
    try:
        for _ in range(timed_iterations):
            tracemalloc.reset_peak()
            started_ns = time.perf_counter_ns()
            operation()
            elapsed_ns = time.perf_counter_ns() - started_ns
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            timings_ns.append(elapsed_ns)
            peak_memory_bytes = max(peak_memory_bytes, current_bytes, peak_bytes)
    finally:
        tracemalloc.stop()

    stats = compute_timing_stats(timings_ns)
    stats["iterations"] = timed_iterations
    stats["warmup_iterations"] = warmup_iterations
    stats["peak_memory_bytes"] = peak_memory_bytes
    return stats


def get_detail_mapping(kem: Any) -> dict[str, Any]:
    """Extract mechanism metadata from the wrapper when available."""
    detail_candidates = [
        getattr(kem, "details", None),
        getattr(kem, "mechanism_details", None),
    ]
    for candidate in detail_candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def get_metadata_value(kem: Any, key: str, default: Any = None) -> Any:
    """Return metadata from a direct attribute or a wrapper-provided details map."""
    if hasattr(kem, key):
        return getattr(kem, key)

    details = get_detail_mapping(kem)
    if key in details:
        return details[key]

    alias_keys = {
        "is_ind_cca": ["ind_cca", "is_ind_cca"],
        "claimed_nist_level": ["claimed_nist_level"],
        "length_public_key": ["length_public_key"],
        "length_secret_key": ["length_secret_key"],
        "length_ciphertext": ["length_ciphertext"],
        "length_shared_secret": ["length_shared_secret"],
    }
    for alias in alias_keys.get(key, []):
        if hasattr(kem, alias):
            return getattr(kem, alias)
        if alias in details:
            return details[alias]

    return default


def collect_algorithm_metadata(
    kem: Any,
    algorithm_name: str,
    public_key: bytes,
    secret_key: bytes,
    ciphertext: bytes,
    shared_secret: bytes,
) -> dict[str, Any]:
    """Collect algorithm metadata from oqs-python and fallback sample values."""
    return build_shared_algorithm_metadata(
        algorithm=algorithm_name,
        claimed_nist_level=get_metadata_value(kem, "claimed_nist_level"),
        is_ind_cca=bool(get_metadata_value(kem, "is_ind_cca", False)),
        length_public_key=int(
            get_metadata_value(kem, "length_public_key", len(public_key))
        ),
        length_secret_key=int(
            get_metadata_value(kem, "length_secret_key", len(secret_key))
        ),
        length_ciphertext=int(
            get_metadata_value(kem, "length_ciphertext", len(ciphertext))
        ),
        length_shared_secret=int(
            get_metadata_value(kem, "length_shared_secret", len(shared_secret))
        ),
    )


def precompute_ciphertexts(
    algorithm_name: str,
    public_key: bytes,
    count: int,
) -> list[tuple[bytes, bytes]]:
    """Generate valid ciphertext/shared-secret pairs for decapsulation timing."""
    oqs_module = require_oqs()
    ciphertexts: list[tuple[bytes, bytes]] = []

    with oqs_module.KeyEncapsulation(algorithm_name) as sender:
        for _ in range(count):
            ciphertexts.append(sender.encap_secret(public_key))
    return ciphertexts


def benchmark_algorithm(
    algorithm_name: str,
    timed_iterations: int,
    warmup_iterations: int,
) -> dict[str, Any]:
    """Run keygen, encapsulation, and decapsulation benchmarks for one KEM."""
    LOGGER.info("Benchmarking OQS algorithm: %s", algorithm_name)
    oqs_module = require_oqs()

    with oqs_module.KeyEncapsulation(algorithm_name) as recipient:
        keygen_stats = benchmark_operation(
            operation=recipient.generate_keypair,
            timed_iterations=timed_iterations,
            warmup_iterations=warmup_iterations,
        )

        public_key = recipient.generate_keypair()
        secret_key = recipient.export_secret_key()

        with oqs_module.KeyEncapsulation(algorithm_name) as sender:
            warmup_pair = sender.encap_secret(public_key)
            shared_secret_reference = warmup_pair[1]
            encapsulation_stats = benchmark_operation(
                operation=lambda: sender.encap_secret(public_key),
                timed_iterations=timed_iterations,
                warmup_iterations=warmup_iterations,
            )

        ciphertext_samples = precompute_ciphertexts(
            algorithm_name=algorithm_name,
            public_key=public_key,
            count=timed_iterations + warmup_iterations,
        )
        sample_index = 0

        def decapsulation_operation() -> bytes:
            nonlocal sample_index
            ciphertext, shared_secret_expected = ciphertext_samples[sample_index]
            sample_index += 1
            shared_secret_received = recipient.decap_secret(ciphertext)
            if shared_secret_received != shared_secret_expected:
                raise RuntimeError(
                    f"Shared secret mismatch detected for {algorithm_name}."
                )
            return shared_secret_received

        decapsulation_stats = benchmark_operation(
            operation=decapsulation_operation,
            timed_iterations=timed_iterations,
            warmup_iterations=warmup_iterations,
        )

        sample_ciphertext, sample_shared_secret = ciphertext_samples[-1]
        metadata = collect_algorithm_metadata(
            kem=recipient,
            algorithm_name=algorithm_name,
            public_key=public_key,
            secret_key=secret_key,
            ciphertext=sample_ciphertext,
            shared_secret=sample_shared_secret or shared_secret_reference,
        )

    return build_result_entry(
        algorithm=algorithm_name,
        metadata=metadata,
        benchmarks={
            "keygen": keygen_stats,
            "encapsulation": encapsulation_stats,
            "decapsulation": decapsulation_stats,
        },
        status="ok",
    )


def run_benchmarks(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    timed_iterations: int = DEFAULT_ITERATIONS,
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS,
) -> Path:
    """Benchmark all selected oqs-python KEM algorithms and save results."""
    configure_logging()
    if timed_iterations <= 0:
        raise ValueError("timed_iterations must be greater than zero.")
    if warmup_iterations < 0:
        raise ValueError("warmup_iterations cannot be negative.")

    algorithms = list_target_algorithms()
    if not algorithms:
        LOGGER.warning(
            "No target OQS algorithms are enabled. "
            "Verify that liboqs includes ML-KEM or NTRU mechanisms on this system."
        )
    results = [
        benchmark_algorithm(
            algorithm_name=algorithm_name,
            timed_iterations=timed_iterations,
            warmup_iterations=warmup_iterations,
        )
        for algorithm_name in algorithms
    ]

    document = build_results_document(
        tool="oqs-python",
        results=results,
        timed_iterations=timed_iterations,
        warmup_iterations=warmup_iterations,
    )
    LOGGER.info("Saving OQS benchmark results to %s", output_path)
    return write_json_document(document=document, output_path=output_path)


def run_oqs_benchmarks(
    output_dir: Path,
    iterations: int = DEFAULT_ITERATIONS,
) -> list[Path]:
    """Compatibility wrapper for the project entry point."""
    output_path = output_dir / DEFAULT_OUTPUT_PATH.name
    saved_path = run_benchmarks(
        output_path=output_path,
        timed_iterations=iterations,
        warmup_iterations=DEFAULT_WARMUP_ITERATIONS,
    )
    return [saved_path]


def build_parser() -> argparse.ArgumentParser:
    """Build a command-line parser for standalone execution."""
    parser = argparse.ArgumentParser(
        description="Benchmark ML-KEM and NTRU KEMs with oqs-python."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of timed iterations for each operation.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_ITERATIONS,
        help="Number of warm-up iterations before timed runs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the JSON file where benchmark results are saved.",
    )
    return parser


def main() -> None:
    """Run the benchmark suite from the command line."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    run_benchmarks(
        output_path=args.output,
        timed_iterations=args.iterations,
        warmup_iterations=args.warmup,
    )


if __name__ == "__main__":
    main()
