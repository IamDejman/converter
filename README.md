# JSON → Excel / Google Sheets Converter

A CLI tool that converts any JSON file (or JSON string) into a formatted `.xlsx` file or pushes it directly to Google Sheets.

## Features

- **Multi-sheet output** – a `{"users": [...], "products": [...]}` JSON becomes two sheets automatically
- **Nested key flattening** – `{"address": {"city": "NY"}}` → column `address.city`
- **Auto column widths** in Excel
- **Google Sheets upload** – create new spreadsheets or update existing ones
- Works with files or raw JSON strings

## Quick Start

### Install dependencies

```bash
pip install -r requirements.txt
```

### Convert to Excel

```bash
# From a file
python main.py sample.json -o output.xlsx

# From a raw JSON string
python main.py '[{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}]' -o output.xlsx

# Disable nested-key flattening
python main.py sample.json -o output.xlsx --no-flatten

# Custom separator (e.g. address__city instead of address.city)
python main.py sample.json -o output.xlsx --sep __
```

### Upload to Google Sheets

See `setup_gsheets.md` for one-time OAuth setup, then:

```bash
# Create a new spreadsheet
python main.py sample.json \
  --gsheets \
  --credentials credentials.json \
  --title "My Sheet"

# Write into an existing spreadsheet
python main.py sample.json \
  --gsheets \
  --credentials credentials.json \
  --spreadsheet-id YOUR_SPREADSHEET_ID
```

## Project Structure

```
converter/
├── main.py            # CLI entry point
├── json_converter.py  # Core conversion logic
├── sample.json        # Example input
├── requirements.txt   # Python dependencies
├── setup_gsheets.md   # Google Sheets OAuth setup guide
└── README.md
```

## JSON Shape → Sheet Mapping

| JSON shape | Result |
|---|---|
| `{"key1": [...], "key2": [...]}` | One sheet per key |
| `[{...}, {...}]` | Single sheet, one row per object |
| `[{...}]` with nested dicts | Flattened columns (e.g. `address.city`) |
| `{...}` (plain object) | Two-column sheet: `key` / `value` |
| Scalar / mixed | Single `value` column |

## CLI Reference

```
Usage: python main.py [OPTIONS] SOURCE

  Convert a JSON file (or JSON string) to Excel or Google Sheets.

  SOURCE can be a file path or a raw JSON string.

Options:
  -o, --output TEXT          Output .xlsx file path
  --sheet-name TEXT          Default sheet name  [default: Sheet1]
  --flatten / --no-flatten   Flatten nested JSON keys  [default: flatten]
  --sep TEXT                 Separator for flattened keys  [default: .]
  --gsheets                  Export to Google Sheets
  --credentials TEXT         Path to Google OAuth2 credentials JSON
  --spreadsheet-id TEXT      Existing spreadsheet ID to write into
  --title TEXT               Title for new spreadsheet  [default: Converted JSON]
  -h, --help                 Show this message and exit.
```
