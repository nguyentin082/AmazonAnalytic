from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


def list_csv_files(data_dir: str | Path = "data") -> list[Path]:
    """Return sorted CSV-like files from the data directory."""
    root = Path(data_dir)
    patterns = ("*.csv", "*.tsv", "*.txt")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    return sorted(files)


def _detect_delimiter(sample: str) -> str:
    """Detect delimiter from sample; fallback to comma."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        if "\t" in sample:
            return "\t"
        return ","


def _find_header_row(lines: list[str]) -> int:
    """Find the real header row in Amazon settlement files."""
    for idx, line in enumerate(lines):
        normalized = line.strip().lower()
        if "date/time" in normalized and "settlement" in normalized:
            return idx
    return 0


def _read_text_with_fallbacks(path: Path, encoding: str | None = None) -> str:
    """Read a file as text using a small set of safe fallback encodings."""
    if encoding:
        return path.read_text(encoding=encoding, errors="replace")

    for candidate in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return path.read_text(encoding=candidate)
        except UnicodeDecodeError:
            continue

    return path.read_text(encoding="latin1", errors="replace")


def read_settlement_file(
    file_path: str | Path, encoding: str | None = None
) -> pd.DataFrame:
    """Read one settlement file, skipping definition preamble rows if present."""
    path = Path(file_path)
    text = _read_text_with_fallbacks(path, encoding=encoding)
    lines = text.splitlines(True)

    if not lines:
        return pd.DataFrame()

    header_row = _find_header_row(lines)
    sample = "".join(lines[header_row : header_row + 10])
    delimiter = _detect_delimiter(sample)

    buffer = StringIO("".join(lines[header_row:]))
    return pd.read_csv(
        buffer,
        sep=delimiter,
        dtype="string",
        low_memory=False,
    )


def load_all_csv(
    data_dir: str | Path = "data", encoding: str | None = None
) -> pd.DataFrame:
    """Load and concatenate all settlement files under data_dir."""
    csv_files = list_csv_files(data_dir)
    if not csv_files:
        raise FileNotFoundError(f"No data files found in {Path(data_dir).resolve()}")

    frames: list[pd.DataFrame] = []
    for file_path in csv_files:
        frame = read_settlement_file(file_path, encoding=encoding)
        frame["source_file"] = file_path.name
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


def basic_data_profile(df: pd.DataFrame) -> dict[str, Any]:
    """Generate lightweight profiling stats for quick checks."""
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_values": df.isna().sum().to_dict(),
        "dtypes": df.dtypes.astype(str).to_dict(),
    }
