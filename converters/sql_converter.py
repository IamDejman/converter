"""SQL parsing logic — extract tabular data from CREATE TABLE + INSERT statements."""
import csv
import io
import re

import sqlparse


def sql_to_records(sql_text: str) -> dict:
    """Parse SQL statements and return structured table data.

    Returns ``{"tables": {"name": {"columns": [...], "rows": [[...], ...]}}}``.
    """
    tables: dict[str, dict] = {}
    statements = sqlparse.parse(sql_text)

    for stmt in statements:
        raw = stmt.value.strip()
        if not raw:
            continue
        upper = raw.upper()

        if upper.startswith("CREATE"):
            _parse_create(raw, tables)
        elif upper.startswith("INSERT"):
            _parse_insert(raw, tables)

    return {"tables": tables}


def _parse_create(sql: str, tables: dict):
    m = re.match(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\((.+)\)",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return
    name = m.group(1)
    body = m.group(2)
    cols = []
    for part in body.split(","):
        part = part.strip()
        if not part:
            continue
        token = part.split()[0].strip("`\"'")
        kw = token.upper()
        if kw in ("PRIMARY", "UNIQUE", "INDEX", "KEY", "CONSTRAINT", "CHECK", "FOREIGN"):
            continue
        cols.append(token)
    tables.setdefault(name, {"columns": cols, "rows": []})


def _parse_insert(sql: str, tables: dict):
    m = re.match(
        r"INSERT\s+INTO\s+[`\"']?(\w+)[`\"']?\s*(?:\(([^)]*)\))?\s*VALUES\s*(.+)",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return
    name = m.group(1)
    col_str = m.group(2)
    values_str = m.group(3)

    if col_str:
        cols = [c.strip().strip("`\"'") for c in col_str.split(",")]
    else:
        cols = tables.get(name, {}).get("columns", [])

    table = tables.setdefault(name, {"columns": cols, "rows": []})
    if not table["columns"] and cols:
        table["columns"] = cols

    for vm in re.finditer(r"\(([^)]+)\)", values_str):
        vals = _parse_value_tuple(vm.group(1))
        table["rows"].append(vals)


def _parse_value_tuple(s: str) -> list[str]:
    vals = []
    for v in _split_values(s):
        v = v.strip()
        if v.upper() == "NULL":
            vals.append("")
        elif (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
            vals.append(v[1:-1])
        else:
            vals.append(v)
    return vals


def _split_values(s: str) -> list[str]:
    """Split comma-separated SQL values respecting quoted strings."""
    parts = []
    current = []
    in_quote = None
    for ch in s:
        if ch in ("'", '"') and in_quote is None:
            in_quote = ch
            current.append(ch)
        elif ch == in_quote:
            in_quote = None
            current.append(ch)
        elif ch == "," and in_quote is None:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def records_to_csv(tables: dict, table_name: str | None = None) -> str:
    """Convert a table's records to a CSV string."""
    data = tables.get("tables", tables)
    if table_name is None:
        table_name = next(iter(data))
    table = data[table_name]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(table["columns"])
    for row in table["rows"]:
        writer.writerow(row)
    return buf.getvalue()
