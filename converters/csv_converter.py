"""CSV conversion logic."""
import csv
import io
import json

import pandas as pd


def _detect_delimiter(csv_text: str) -> str:
    """Auto-detect the CSV delimiter using csv.Sniffer."""
    try:
        sample = csv_text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def csv_to_dataframes(csv_text: str, delimiter: str = "auto") -> list[tuple[str, pd.DataFrame]]:
    """Parse CSV text into DataFrame(s) for Excel export."""
    if delimiter == "auto":
        delimiter = _detect_delimiter(csv_text)
    df = pd.read_csv(io.StringIO(csv_text), delimiter=delimiter)
    return [("Sheet1", df)]


def csv_to_json_str(csv_text: str, delimiter: str = "auto", orient: str = "records") -> str:
    """Convert CSV text to a JSON string."""
    if delimiter == "auto":
        delimiter = _detect_delimiter(csv_text)
    df = pd.read_csv(io.StringIO(csv_text), delimiter=delimiter)
    return df.to_json(orient=orient, indent=2, force_ascii=False)
