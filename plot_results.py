"""Generate bar charts from processed PQC benchmark results."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from benchmark_schema import COMBINED_RESULTS_CSV_PATH, PLOTS_DIR, configure_logging


DEFAULT_RESULTS_CSV = COMBINED_RESULTS_CSV_PATH
DEFAULT_PLOTS_DIR = PLOTS_DIR

LOGGER = logging.getLogger(__name__)


def load_results(csv_path: Path) -> pd.DataFrame | None:
    """Load processed benchmark results from CSV."""
    if not csv_path.exists():
        LOGGER.warning(
            "Processed results file not found: %s. "
            "Run 'python main.py combine' before plotting.",
            csv_path,
        )
        return None

    try:
        dataframe = pd.read_csv(csv_path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        LOGGER.warning(
            "Failed to read processed results from %s: %s. "
            "Regenerate the file with 'python main.py combine'.",
            csv_path,
            exc,
        )
        return None
    if dataframe.empty:
        LOGGER.warning(
            "Processed results file %s is empty. Run benchmarks before plotting.",
            csv_path,
        )
    return dataframe


def prepare_plot_directory(plots_dir: Path) -> None:
    """Create the plots output directory."""
    plots_dir.mkdir(parents=True, exist_ok=True)


def create_bar_chart(
    dataframe: pd.DataFrame,
    value_column: str,
    ylabel: str,
    title: str,
    output_path: Path,
    figsize: tuple[int, int] = (10, 6),
) -> Path | None:
    """Create and save a single bar chart for one metric column."""
    import matplotlib.pyplot as plt

    if value_column not in dataframe.columns:
        LOGGER.info("Skipping plot; missing column: %s", value_column)
        return None

    plot_frame = dataframe[["algorithm", value_column]].dropna()
    if plot_frame.empty:
        LOGGER.info(
            "Skipping plot; no data available for column: %s. "
            "Check whether benchmark results were generated for this metric.",
            value_column,
        )
        return None

    figure, axis = plt.subplots(figsize=figsize)
    axis.bar(plot_frame["algorithm"], plot_frame[value_column], color="#2F5D8A")
    axis.set_title(title)
    axis.set_xlabel("Algorithm")
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)
    LOGGER.info("Saved plot to %s", output_path)
    return output_path


def generate_plots(
    results_csv: Path = DEFAULT_RESULTS_CSV,
    plots_dir: Path = DEFAULT_PLOTS_DIR,
) -> list[Path]:
    """Generate all requested benchmark bar charts."""
    configure_logging()
    dataframe = load_results(results_csv)
    if dataframe is None:
        return []
    if dataframe.empty:
        return []

    prepare_plot_directory(plots_dir)
    LOGGER.info("Generating plots in %s", plots_dir)

    plot_specs = [
        (
            "length_public_key",
            "Public Key Size (bytes)",
            "Public Key Size by Algorithm",
            "public_key_size.png",
        ),
        (
            "length_secret_key",
            "Secret Key Size (bytes)",
            "Secret Key Size by Algorithm",
            "secret_key_size.png",
        ),
        (
            "length_ciphertext",
            "Ciphertext Size (bytes)",
            "Ciphertext Size by Algorithm",
            "ciphertext_size.png",
        ),
        (
            "keygen_median_ms",
            "Median Time (ms)",
            "Key Generation Median Time by Algorithm",
            "keygen_median_ms.png",
        ),
        (
            "encaps_median_ms",
            "Median Time (ms)",
            "Encapsulation Median Time by Algorithm",
            "encaps_median_ms.png",
        ),
        (
            "decaps_median_ms",
            "Median Time (ms)",
            "Decapsulation Median Time by Algorithm",
            "decaps_median_ms.png",
        ),
    ]

    saved_paths: list[Path] = []
    for column, ylabel, title, filename in plot_specs:
        saved_path = create_bar_chart(
            dataframe=dataframe,
            value_column=column,
            ylabel=ylabel,
            title=title,
            output_path=plots_dir / filename,
        )
        if saved_path is not None:
            saved_paths.append(saved_path)
    return saved_paths


def main() -> None:
    """Run the plotting step as a standalone script."""
    configure_logging()
    generate_plots()


if __name__ == "__main__":
    main()
