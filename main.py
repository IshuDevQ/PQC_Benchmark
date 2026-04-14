"""CLI entry point for the PQC KEM benchmarking project."""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path
from typing import Callable

from benchmark_schema import (
    COMBINED_RESULTS_CSV_PATH,
    OQS_RESULTS_PATH,
    PLOTS_DIR,
    PROCESSED_RESULTS_DIR,
    RAW_RESULTS_DIR,
    SABER_RESULTS_PATH,
    configure_logging,
)


DEFAULT_ITERATIONS = 100
DEFAULT_WARMUP_ITERATIONS = 10
LOGGER = logging.getLogger(__name__)


def load_module(module_name: str) -> object:
    """Import a project module lazily."""
    return importlib.import_module(module_name)


def build_parser() -> argparse.ArgumentParser:
    """Create the project command-line interface."""
    parser = argparse.ArgumentParser(
        description="Run PQC KEM benchmarks and process results."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    oqs_parser = subparsers.add_parser("oqs", help="Run oqs-python benchmarks.")
    oqs_parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of timed iterations for each OQS operation.",
    )
    oqs_parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_ITERATIONS,
        help="Number of warm-up iterations before timed OQS runs.",
    )
    oqs_parser.add_argument(
        "--output",
        type=Path,
        default=OQS_RESULTS_PATH,
        help="Output path for OQS benchmark JSON.",
    )

    saber_parser = subparsers.add_parser("saber", help="Run SABER benchmarks.")
    saber_parser.add_argument(
        "--output",
        type=Path,
        default=SABER_RESULTS_PATH,
        help="Output path for SABER benchmark JSON.",
    )
    saber_parser.add_argument(
        "--executable",
        type=str,
        default=None,
        help="Path to the SABER benchmark executable.",
    )

    combine_parser = subparsers.add_parser(
        "combine",
        help="Combine raw benchmark JSON into processed outputs.",
    )
    combine_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_RESULTS_DIR,
        help="Directory containing raw benchmark JSON files.",
    )
    combine_parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROCESSED_RESULTS_DIR,
        help="Directory for combined JSON and CSV output.",
    )

    plot_parser = subparsers.add_parser(
        "plot",
        help="Generate plots from combined CSV results.",
    )
    plot_parser.add_argument(
        "--input",
        type=Path,
        default=COMBINED_RESULTS_CSV_PATH,
        help="Input CSV for plot generation.",
    )
    plot_parser.add_argument(
        "--plots-dir",
        type=Path,
        default=PLOTS_DIR,
        help="Directory where plot images are written.",
    )

    all_parser = subparsers.add_parser(
        "all",
        help="Run OQS, SABER, combine, and plot in sequence.",
    )
    all_parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of timed iterations for each OQS operation.",
    )
    all_parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_ITERATIONS,
        help="Number of warm-up iterations before timed OQS runs.",
    )
    all_parser.add_argument(
        "--saber-executable",
        type=str,
        default=None,
        help="Path to the SABER benchmark executable.",
    )
    all_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_RESULTS_DIR,
        help="Directory containing raw benchmark JSON files.",
    )
    all_parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROCESSED_RESULTS_DIR,
        help="Directory for combined JSON and CSV output.",
    )
    all_parser.add_argument(
        "--plots-dir",
        type=Path,
        default=PLOTS_DIR,
        help="Directory where plot images are written.",
    )
    return parser


def run_with_progress(label: str, action: Callable[[], object]) -> object:
    """Print a progress message and execute a pipeline step."""
    LOGGER.info("Starting %s", label)
    result = action()
    LOGGER.info("Finished %s", label)
    return result


def run_all_pipeline(args: argparse.Namespace) -> None:
    """Run the full benchmark and reporting pipeline."""
    oqs_module = load_module("benchmark_oqs")
    saber_module = load_module("benchmark_saber")
    combine_module = load_module("combine_results")
    plot_module = load_module("plot_results")

    raw_dir = args.raw_dir
    processed_dir = args.processed_dir

    run_with_progress(
        "OQS benchmarks",
        lambda: oqs_module.run_benchmarks(
            output_path=raw_dir / "oqs_results.json",
            timed_iterations=args.iterations,
            warmup_iterations=args.warmup,
        ),
    )
    run_with_progress(
        "SABER benchmarks",
        lambda: saber_module.run_saber_benchmarks(
            output_dir=raw_dir,
            executable_path=args.saber_executable,
        ),
    )
    run_with_progress(
        "Combine results",
        lambda: combine_module.combine_raw_results(
            raw_dir=raw_dir,
            processed_dir=processed_dir,
        ),
    )
    run_with_progress(
        "Generate plots",
        lambda: plot_module.generate_plots(
            results_csv=processed_dir / "all_results.csv",
            plots_dir=args.plots_dir,
        ),
    )


def dispatch_command(args: argparse.Namespace) -> None:
    """Dispatch the selected CLI command."""
    handlers: dict[str, Callable[[], object]] = {
        "oqs": lambda: run_with_progress(
            "OQS benchmarks",
            lambda: load_module("benchmark_oqs").run_benchmarks(
                output_path=args.output,
                timed_iterations=args.iterations,
                warmup_iterations=args.warmup,
            ),
        ),
        "saber": lambda: run_with_progress(
            "SABER benchmarks",
            lambda: load_module("benchmark_saber").run_saber_benchmarks(
                output_dir=args.output.parent,
                executable_path=args.executable,
                output_path=args.output,
            ),
        ),
        "combine": lambda: run_with_progress(
            "Combine results",
            lambda: load_module("combine_results").combine_raw_results(
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
            ),
        ),
        "plot": lambda: run_with_progress(
            "Generate plots",
            lambda: load_module("plot_results").generate_plots(
                results_csv=args.input,
                plots_dir=args.plots_dir,
            ),
        ),
        "all": lambda: run_all_pipeline(args),
    }
    handlers[args.command]()


def main() -> int:
    """Run the CLI and return an exit code."""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    try:
        dispatch_command(args)
    except Exception as exc:  # pragma: no cover - CLI error path
        LOGGER.error(
            "Command '%s' failed with %s: %s",
            args.command,
            type(exc).__name__,
            exc,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
