"""Shared schema and filesystem helpers for benchmark modules."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_RESULTS_DIR = Path("results/raw")
PROCESSED_RESULTS_DIR = Path("results/processed")
PLOTS_DIR = Path("plots")

OQS_RESULTS_PATH = RAW_RESULTS_DIR / "oqs_results.json"
SABER_RESULTS_PATH = RAW_RESULTS_DIR / "saber_results.json"
COMBINED_RESULTS_JSON_PATH = PROCESSED_RESULTS_DIR / "all_results.json"
COMBINED_RESULTS_CSV_PATH = PROCESSED_RESULTS_DIR / "all_results.csv"

BENCHMARK_OPERATIONS = ("keygen", "encapsulation", "decapsulation")


def configure_logging() -> None:
    """Configure a simple INFO-level logger if the application has not done so."""
    if logging.getLogger().handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def empty_operation_stats() -> dict[str, Any]:
    """Return a benchmark stats mapping populated with null values."""
    return {
        "mean_ns": None,
        "median_ns": None,
        "min_ns": None,
        "max_ns": None,
        "stdev_ns": None,
        "mean_ms": None,
        "median_ms": None,
        "min_ms": None,
        "max_ms": None,
        "stdev_ms": None,
        "iterations": None,
        "warmup_iterations": None,
        "peak_memory_bytes": None,
    }


def build_algorithm_metadata(
    algorithm: str,
    claimed_nist_level: int | None = None,
    is_ind_cca: bool | None = None,
    length_public_key: int | None = None,
    length_secret_key: int | None = None,
    length_ciphertext: int | None = None,
    length_shared_secret: int | None = None,
) -> dict[str, Any]:
    """Build the shared metadata block for one algorithm."""
    return {
        "algorithm": algorithm,
        "claimed_nist_level": claimed_nist_level,
        "is_ind_cca": is_ind_cca,
        "length_public_key": length_public_key,
        "length_secret_key": length_secret_key,
        "length_ciphertext": length_ciphertext,
        "length_shared_secret": length_shared_secret,
    }


def build_result_entry(
    algorithm: str,
    metadata: dict[str, Any],
    benchmarks: dict[str, Any] | None = None,
    status: str = "ok",
    notes: str | None = None,
    raw_stdout: str | None = None,
    raw_stderr: str | None = None,
) -> dict[str, Any]:
    """Build a per-algorithm result entry with the shared structure."""
    entry: dict[str, Any] = {
        "algorithm": algorithm,
        "metadata": metadata,
        "benchmarks": benchmarks
        or {name: empty_operation_stats() for name in BENCHMARK_OPERATIONS},
        "status": status,
    }
    if notes is not None:
        entry["notes"] = notes
    if raw_stdout is not None:
        entry["raw_stdout"] = raw_stdout
    if raw_stderr is not None:
        entry["raw_stderr"] = raw_stderr
    return entry


def build_results_document(
    tool: str,
    results: list[dict[str, Any]],
    timed_iterations: int | None,
    warmup_iterations: int | None,
) -> dict[str, Any]:
    """Build the shared top-level JSON document structure."""
    return {
        "tool": tool,
        "generated_at_utc": utc_timestamp(),
        "benchmark_config": {
            "timed_iterations": timed_iterations,
            "warmup_iterations": warmup_iterations,
        },
        "results": results,
    }


def write_json_document(document: dict[str, Any], output_path: Path) -> Path:
    """Write a JSON document to disk with parent directory creation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return output_path
