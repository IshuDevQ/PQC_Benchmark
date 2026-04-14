"""Combine raw OQS and SABER benchmark results into processed outputs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from benchmark_schema import (
    COMBINED_RESULTS_CSV_PATH,
    COMBINED_RESULTS_JSON_PATH,
    OQS_RESULTS_PATH,
    PROCESSED_RESULTS_DIR,
    RAW_RESULTS_DIR,
    SABER_RESULTS_PATH,
    configure_logging,
)


DEFAULT_RAW_DIR = RAW_RESULTS_DIR
DEFAULT_PROCESSED_DIR = PROCESSED_RESULTS_DIR
FLATTENED_COLUMNS = [
    "algorithm",
    "claimed_nist_level",
    "length_public_key",
    "length_secret_key",
    "length_ciphertext",
    "length_shared_secret",
    "keygen_median_ms",
    "encaps_median_ms",
    "decaps_median_ms",
    "peak_mem_keygen",
    "peak_mem_encaps",
    "peak_mem_decaps",
]

LOGGER = logging.getLogger(__name__)


def load_json_file(path: Path) -> dict[str, Any] | None:
    """Load one JSON file and return None if it is missing or invalid."""
    if not path.exists():
        LOGGER.info("Raw results file not found: %s", path)
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        LOGGER.warning("Failed to read %s: %s", path, exc)
        return None
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "Invalid JSON in %s: %s. Re-run the benchmark that produced this file.",
            path,
            exc,
        )
        return None


def load_raw_documents(paths: list[Path]) -> list[dict[str, Any]]:
    """Load all available raw benchmark documents."""
    documents: list[dict[str, Any]] = []
    for path in paths:
        document = load_json_file(path)
        if document is not None:
            documents.append(document)
    return documents


def extract_metric(
    result: dict[str, Any],
    operation_name: str,
    field_name: str,
) -> Any:
    """Extract a benchmark metric from a per-algorithm result entry."""
    benchmarks = result.get("benchmarks") or {}
    operation = benchmarks.get(operation_name) or {}
    return operation.get(field_name)


def flatten_result_entry(
    result: dict[str, Any],
    source_tool: str | None = None,
) -> dict[str, Any]:
    """Flatten a single benchmark result entry into one table row."""
    metadata = result.get("metadata") or {}
    return {
        "source_tool": source_tool,
        "algorithm": result.get("algorithm") or metadata.get("algorithm"),
        "claimed_nist_level": metadata.get("claimed_nist_level"),
        "length_public_key": metadata.get("length_public_key"),
        "length_secret_key": metadata.get("length_secret_key"),
        "length_ciphertext": metadata.get("length_ciphertext"),
        "length_shared_secret": metadata.get("length_shared_secret"),
        "keygen_median_ms": extract_metric(result, "keygen", "median_ms"),
        "encaps_median_ms": extract_metric(result, "encapsulation", "median_ms"),
        "decaps_median_ms": extract_metric(result, "decapsulation", "median_ms"),
        "peak_mem_keygen": extract_metric(result, "keygen", "peak_memory_bytes"),
        "peak_mem_encaps": extract_metric(
            result,
            "encapsulation",
            "peak_memory_bytes",
        ),
        "peak_mem_decaps": extract_metric(
            result,
            "decapsulation",
            "peak_memory_bytes",
        ),
    }


def flatten_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a benchmark document into a list of rows."""
    results = document.get("results") or []
    source_tool = document.get("tool")
    if not isinstance(results, list):
        LOGGER.warning(
            "Skipping malformed benchmark document from %s because 'results' is not a list.",
            source_tool or "unknown source",
        )
        return []
    return [
        flatten_result_entry(result=result, source_tool=source_tool)
        for result in results
        if isinstance(result, dict)
    ]


def build_results_dataframe(documents: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a combined pandas DataFrame from raw benchmark documents."""
    rows: list[dict[str, Any]] = []
    for document in documents:
        rows.extend(flatten_document(document))

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        LOGGER.warning(
            "No benchmark rows were available to combine. "
            "Run 'python main.py oqs' or 'python main.py saber' first."
        )
        return pd.DataFrame(columns=FLATTENED_COLUMNS)
    return dataframe.loc[:, FLATTENED_COLUMNS]


def save_dataframe_json(dataframe: pd.DataFrame, output_path: Path) -> Path:
    """Save a DataFrame as JSON records."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        dataframe.to_json(orient="records", indent=2),
        encoding="utf-8",
    )
    return output_path


def save_dataframe_csv(dataframe: pd.DataFrame, output_path: Path) -> Path:
    """Save a DataFrame as CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)
    return output_path


def combine_raw_results(
    raw_dir: Path = DEFAULT_RAW_DIR,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
) -> tuple[Path, Path]:
    """Combine OQS and SABER benchmark documents into JSON and CSV outputs."""
    configure_logging()
    raw_paths = [
        raw_dir / OQS_RESULTS_PATH.name,
        raw_dir / SABER_RESULTS_PATH.name,
    ]
    LOGGER.info("Loading raw benchmark results")
    documents = load_raw_documents(raw_paths)
    dataframe = build_results_dataframe(documents)

    LOGGER.info("Saving combined JSON results to %s", processed_dir / COMBINED_RESULTS_JSON_PATH.name)
    json_path = save_dataframe_json(
        dataframe,
        processed_dir / COMBINED_RESULTS_JSON_PATH.name,
    )
    LOGGER.info("Saving combined CSV results to %s", processed_dir / COMBINED_RESULTS_CSV_PATH.name)
    csv_path = save_dataframe_csv(
        dataframe,
        processed_dir / COMBINED_RESULTS_CSV_PATH.name,
    )
    return json_path, csv_path


def main() -> None:
    """Run the combine step as a standalone script."""
    configure_logging()
    combine_raw_results()


if __name__ == "__main__":
    main()
