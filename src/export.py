from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_dataframe(df: pd.DataFrame, path: str | Path) -> Path:
    """Export dataframe to CSV and return output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def export_insights(
    insights: dict[str, pd.DataFrame], output_dir: str | Path = "outputs"
) -> list[Path]:
    """Export all insight tables to output directory."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for name, table in insights.items():
        output_path = root / f"{name}.csv"
        table.to_csv(output_path, index=False)
        written.append(output_path)
    return written
