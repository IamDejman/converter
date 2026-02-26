"""
Core JSON to Excel/Google Sheets conversion logic.
"""
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# JSON flattening helpers
# ---------------------------------------------------------------------------

def _flatten(obj: Any, prefix: str = "", sep: str = ".") -> dict:
    """Recursively flatten a nested dict/list into a single-level dict."""
    items: dict = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{prefix}{sep}{key}" if prefix else str(key)
            items.update(_flatten(value, new_key, sep))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            new_key = f"{prefix}{sep}{idx}" if prefix else str(idx)
            items.update(_flatten(value, new_key, sep))
    else:
        items[prefix] = obj
    return items


def _sanitize_sheet_name(name: str) -> str:
    """Excel sheet names: max 31 chars, no special chars."""
    name = re.sub(r"[\\/*?\[\]:]", "_", name)
    return name[:31]


def _find_records(data: Any) -> list | None:
    """Recursively find the first list of dicts (records) inside a nested structure."""
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        return data
    if isinstance(data, dict):
        for v in data.values():
            result = _find_records(v)
            if result is not None:
                return result
    return None


def _strip_common_prefix(columns: list[str], sep: str = ".") -> list[str]:
    """Strip the longest common prefix (bounded by sep) from all column names.

    e.g. ['data.data.0.id', 'data.data.0.name'] → ['id', 'name']
    """
    if len(columns) < 2:
        return columns

    # os.path.commonprefix works character-by-character
    import os
    raw_prefix = os.path.commonprefix(columns)

    # Walk back to the last separator so we don't cut mid-word
    last_sep = raw_prefix.rfind(sep)
    if last_sep == -1:
        return columns  # nothing useful to strip

    prefix = raw_prefix[: last_sep + 1]  # include the trailing sep
    stripped = [c[len(prefix):] if c.startswith(prefix) else c for c in columns]

    # Guard: don't strip if it produces duplicate or empty names
    if len(set(stripped)) < len(set(columns)) or any(s == "" for s in stripped):
        return columns

    return stripped


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_json(source: str) -> Any:
    """Load JSON from a file path or a raw JSON string."""
    path = Path(source)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    # Try to parse as raw JSON string
    return json.loads(source)


# ---------------------------------------------------------------------------
# Conversion: JSON → list of (sheet_name, DataFrame)
# ---------------------------------------------------------------------------

def json_to_dataframes(
    data: Any,
    flatten: bool = True,
    sep: str = ".",
    sheet_name: str = "Sheet1",
    strip_prefix: bool = True,
) -> list[tuple[str, pd.DataFrame]]:
    """
    Convert parsed JSON data into one or more (sheet_name, DataFrame) pairs.

    Rules:
    - dict of lists  → one sheet per key (each list becomes a sheet)
    - list of dicts  → single sheet, columns = union of all keys
    - flat list      → single sheet with one column ("value")
    - plain dict     → single sheet (flattened to key/value pairs)
    """
    sheets: list[tuple[str, pd.DataFrame]] = []

    if isinstance(data, dict):
        # Check if all values are lists → one sheet per key (multi-sheet mode)
        list_values = {k: v for k, v in data.items() if isinstance(v, list)}
        if list_values and len(list_values) == len(data):
            for key, records in data.items():
                df = _records_to_df(records, flatten=flatten, sep=sep, strip_prefix=strip_prefix)
                sheets.append((_sanitize_sheet_name(str(key)), df))
            return sheets

        # Check if multiple direct values are lists → multi-sheet from mixed dict
        if len(list_values) > 1:
            for key, records in list_values.items():
                df = _records_to_df(records, flatten=flatten, sep=sep, strip_prefix=strip_prefix)
                sheets.append((_sanitize_sheet_name(str(key)), df))
            return sheets

        # Try to find a list of records anywhere deeper in the structure
        records = _find_records(data)
        if records is not None:
            df = _records_to_df(records, flatten=flatten, sep=sep, strip_prefix=strip_prefix)
            sheets.append((_sanitize_sheet_name(sheet_name), df))
            return sheets

        # Last resort: flatten the whole dict to two columns
        flat = _flatten(data, sep=sep) if flatten else data
        df = pd.DataFrame(list(flat.items()), columns=["key", "value"])
        if strip_prefix and flatten:
            df["key"] = _strip_common_prefix(df["key"].tolist(), sep)
        sheets.append((_sanitize_sheet_name(sheet_name), df))
        return sheets

    if isinstance(data, list):
        df = _records_to_df(data, flatten=flatten, sep=sep, strip_prefix=strip_prefix)
        sheets.append((_sanitize_sheet_name(sheet_name), df))
        return sheets

    # Scalar
    df = pd.DataFrame([{"value": data}])
    sheets.append((_sanitize_sheet_name(sheet_name), df))
    return sheets


def _records_to_df(records: list, flatten: bool, sep: str, strip_prefix: bool = True) -> pd.DataFrame:
    """Convert a list (of dicts or scalars) to a DataFrame."""
    if not records:
        return pd.DataFrame()

    if flatten and any(isinstance(r, (dict, list)) for r in records):
        flat_records = [_flatten(r, sep=sep) if isinstance(r, (dict, list)) else {"value": r} for r in records]
        df = pd.DataFrame(flat_records)
        if strip_prefix and len(df.columns) > 1:
            df.columns = _strip_common_prefix(df.columns.tolist(), sep)
        return df

    if all(isinstance(r, dict) for r in records):
        return pd.DataFrame(records)

    return pd.DataFrame(records, columns=["value"])


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def to_excel(sheets: list[tuple[str, pd.DataFrame]], output_path: str) -> str:
    """Write sheets to an .xlsx file. Returns the resolved output path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-fit column widths
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) if cell.value is not None else 0 for cell in col),
                    default=0,
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    return str(output.resolve())


# ---------------------------------------------------------------------------
# Google Sheets export
# ---------------------------------------------------------------------------

def to_google_sheets(
    sheets: list[tuple[str, pd.DataFrame]],
    spreadsheet_id: str | None,
    title: str,
    creds_file: str,
) -> str:
    """
    Write sheets to Google Sheets.

    - If spreadsheet_id is None, a new spreadsheet is created.
    - Returns the spreadsheet URL.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    import pickle

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    token_path = Path(creds_file).parent / "token.pickle"

    creds = None
    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    service = build("sheets", "v4", credentials=creds)
    ss = service.spreadsheets()

    if spreadsheet_id is None:
        # Create new spreadsheet
        body = {
            "properties": {"title": title},
            "sheets": [
                {"properties": {"title": name}} for name, _ in sheets
            ],
        }
        result = ss.create(body=body).execute()
        spreadsheet_id = result["spreadsheetId"]
        sheet_ids = {
            s["properties"]["title"]: s["properties"]["sheetId"]
            for s in result["sheets"]
        }
    else:
        # Fetch existing sheet IDs and add missing sheets
        meta = ss.get(spreadsheetId=spreadsheet_id).execute()
        sheet_ids = {
            s["properties"]["title"]: s["properties"]["sheetId"]
            for s in meta["sheets"]
        }
        existing = set(sheet_ids.keys())
        add_requests = []
        for name, _ in sheets:
            if name not in existing:
                add_requests.append({"addSheet": {"properties": {"title": name}}})
        if add_requests:
            resp = ss.batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": add_requests},
            ).execute()
            for reply in resp.get("replies", []):
                if "addSheet" in reply:
                    props = reply["addSheet"]["properties"]
                    sheet_ids[props["title"]] = props["sheetId"]

    # Write data
    value_data = []
    for sheet_name, df in sheets:
        rows = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
        value_data.append({
            "range": f"'{sheet_name}'!A1",
            "values": rows,
        })

    ss.values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": value_data},
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
