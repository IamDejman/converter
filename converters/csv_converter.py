"""CSV conversion logic."""
import io
import json

import pandas as pd


def csv_to_dataframes(csv_text: str, delimiter: str = ",") -> list[tuple[str, pd.DataFrame]]:
    """Parse CSV text into DataFrame(s) for Excel export."""
    df = pd.read_csv(io.StringIO(csv_text), delimiter=delimiter)
    return [("Sheet1", df)]


def csv_to_json_str(csv_text: str, delimiter: str = ",", orient: str = "records") -> str:
    """Convert CSV text to a JSON string."""
    df = pd.read_csv(io.StringIO(csv_text), delimiter=delimiter)
    return df.to_json(orient=orient, indent=2, force_ascii=False)
