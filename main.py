#!/usr/bin/env python3
"""
JSON → Excel / Google Sheets converter  (CLI entry point)

Usage examples
--------------
# Convert to Excel (auto-detects output format from extension):
  python main.py data.json -o output.xlsx

# Convert raw JSON string:
  python main.py '{"users":[{"id":1,"name":"Alice"}]}' -o output.xlsx

# Push to a NEW Google Sheet:
  python main.py data.json --gsheets --credentials credentials.json --title "My Sheet"

# Push to an EXISTING Google Sheet:
  python main.py data.json --gsheets --credentials credentials.json \
      --spreadsheet-id 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

# Disable key flattening:
  python main.py nested.json -o output.xlsx --no-flatten
"""

import json
import sys
from pathlib import Path

import click

from json_converter import load_json, json_to_dataframes, to_excel, to_google_sheets


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("source")
@click.option(
    "-o", "--output",
    default=None,
    help="Output .xlsx file path (required when not using --gsheets).",
)
@click.option(
    "--sheet-name",
    default="Sheet1",
    show_default=True,
    help="Default sheet name (used when JSON is a single object/list).",
)
@click.option(
    "--flatten/--no-flatten",
    default=True,
    show_default=True,
    help="Flatten nested JSON keys using dot-notation (e.g. address.city).",
)
@click.option(
    "--sep",
    default=".",
    show_default=True,
    help="Separator used when flattening nested keys.",
)
# ── Google Sheets options ──────────────────────────────────────────────────
@click.option(
    "--gsheets",
    is_flag=True,
    default=False,
    help="Export to Google Sheets instead of Excel.",
)
@click.option(
    "--credentials",
    default=None,
    help="Path to Google OAuth2 credentials JSON file (required with --gsheets).",
)
@click.option(
    "--spreadsheet-id",
    default=None,
    help="Existing Google Spreadsheet ID to write into. Omit to create a new one.",
)
@click.option(
    "--title",
    default="Converted JSON",
    show_default=True,
    help="Title for newly created Google Spreadsheet.",
)
def main(source, output, sheet_name, flatten, sep, gsheets, credentials, spreadsheet_id, title):
    """Convert a JSON file (or JSON string) to Excel or Google Sheets.

    SOURCE can be a file path or a raw JSON string.
    """
    # ── Validate options ───────────────────────────────────────────────────
    if not gsheets and output is None:
        raise click.UsageError(
            "Specify an output file with -o / --output, "
            "or use --gsheets to export to Google Sheets."
        )

    if gsheets and credentials is None:
        raise click.UsageError(
            "--credentials is required when using --gsheets.\n"
            "Download your OAuth2 credentials from Google Cloud Console and pass "
            "the path here."
        )

    # ── Load JSON ──────────────────────────────────────────────────────────
    click.echo(f"Loading JSON from: {source if len(source) < 80 else source[:77] + '...'}")
    try:
        data = load_json(source)
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as exc:
        click.secho(f"Error loading JSON: {exc}", fg="red", err=True)
        sys.exit(1)

    # ── Convert ────────────────────────────────────────────────────────────
    click.echo("Converting…")
    sheets = json_to_dataframes(data, flatten=flatten, sep=sep, sheet_name=sheet_name)
    click.echo(f"  → {len(sheets)} sheet(s): {', '.join(n for n, _ in sheets)}")

    # ── Export ─────────────────────────────────────────────────────────────
    if gsheets:
        click.echo("Uploading to Google Sheets (browser auth may open)…")
        try:
            url = to_google_sheets(sheets, spreadsheet_id, title, credentials)
        except Exception as exc:
            click.secho(f"Google Sheets error: {exc}", fg="red", err=True)
            sys.exit(1)
        click.secho(f"\nDone! Spreadsheet URL:\n  {url}", fg="green")
    else:
        # Default output name if somehow still None
        out_path = output or "output.xlsx"
        if not out_path.endswith(".xlsx"):
            out_path += ".xlsx"
        try:
            resolved = to_excel(sheets, out_path)
        except Exception as exc:
            click.secho(f"Excel export error: {exc}", fg="red", err=True)
            sys.exit(1)
        click.secho(f"\nDone! File saved to:\n  {resolved}", fg="green")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
