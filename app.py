"""
Flask web UI for the JSON → Excel converter.
"""
import io
import json
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify

from json_converter import load_json, json_to_dataframes, to_excel

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JSON → Excel Converter</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f1117;
      color: #e1e4e8;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 16px 80px;
    }

    header {
      text-align: center;
      margin-bottom: 36px;
    }
    header h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; }
    header p  { margin-top: 8px; color: #8b949e; font-size: 0.95rem; }

    .card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 12px;
      padding: 28px;
      width: 100%;
      max-width: 820px;
    }

    label {
      display: block;
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #8b949e;
      margin-bottom: 8px;
    }

    textarea {
      width: 100%;
      height: 320px;
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 8px;
      color: #c9d1d9;
      font-family: "SF Mono", "Fira Code", Consolas, monospace;
      font-size: 0.85rem;
      line-height: 1.6;
      padding: 14px;
      resize: vertical;
      outline: none;
      transition: border-color 0.15s;
    }
    textarea:focus { border-color: #58a6ff; }
    textarea.error  { border-color: #f85149; }

    .row {
      display: flex;
      gap: 12px;
      margin-top: 18px;
      flex-wrap: wrap;
      align-items: flex-end;
    }

    .field { display: flex; flex-direction: column; gap: 6px; }
    .field input[type="text"] {
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 6px;
      color: #c9d1d9;
      font-size: 0.88rem;
      padding: 8px 12px;
      outline: none;
      transition: border-color 0.15s;
      min-width: 160px;
    }
    .field input[type="text"]:focus { border-color: #58a6ff; }

    .toggle-group {
      display: flex;
      gap: 0;
      border: 1px solid #30363d;
      border-radius: 6px;
      overflow: hidden;
      height: 36px;
    }
    .toggle-group input[type="radio"] { display: none; }
    .toggle-group label {
      display: flex;
      align-items: center;
      padding: 0 16px;
      font-size: 0.82rem;
      font-weight: 500;
      text-transform: none;
      letter-spacing: 0;
      color: #8b949e;
      cursor: pointer;
      background: #0d1117;
      transition: background 0.12s, color 0.12s;
      margin: 0;
    }
    .toggle-group input[type="radio"]:checked + label {
      background: #1f6feb;
      color: #fff;
    }

    .spacer { flex: 1; }

    button#convertBtn {
      height: 36px;
      padding: 0 24px;
      background: #238636;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      white-space: nowrap;
    }
    button#convertBtn:hover { background: #2ea043; }
    button#convertBtn:disabled { opacity: 0.5; cursor: default; }

    /* Status / error bar */
    #status {
      margin-top: 14px;
      font-size: 0.85rem;
      min-height: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    #status.ok   { color: #3fb950; }
    #status.err  { color: #f85149; }
    #status.info { color: #8b949e; }

    /* Preview table */
    #preview {
      margin-top: 24px;
      display: none;
    }
    #preview h2 {
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #8b949e;
      margin-bottom: 10px;
    }
    .sheet-tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    .sheet-tab {
      padding: 4px 14px;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 600;
      background: #21262d;
      color: #8b949e;
      border: 1px solid #30363d;
      cursor: pointer;
      transition: background 0.12s;
    }
    .sheet-tab.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }

    .table-wrap {
      overflow-x: auto;
      border: 1px solid #30363d;
      border-radius: 8px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      font-size: 0.82rem;
    }
    th {
      background: #1c2128;
      color: #58a6ff;
      font-weight: 700;
      padding: 10px 14px;
      text-align: left;
      white-space: nowrap;
      border-bottom: 2px solid #388bfd40;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 8px 14px;
      border-bottom: 1px solid #21262d;
      color: #e6edf3;
      white-space: nowrap;
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #1c2128; }

    .row-count {
      margin-top: 6px;
      font-size: 0.78rem;
      color: #8b949e;
    }

    /* Download button */
    #downloadBtn {
      margin-top: 16px;
      height: 36px;
      padding: 0 22px;
      background: #0d1117;
      color: #58a6ff;
      border: 1px solid #58a6ff;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      display: none;
    }
    #downloadBtn:hover { background: #1c2128; }

    /* Spinner */
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid #30363d;
      border-top-color: #58a6ff;
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
      display: none;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

<header>
  <h1>JSON → Excel</h1>
  <p>Paste any JSON below, preview the result, then download as .xlsx</p>
</header>

<div class="card">
  <label for="jsonInput">JSON Input</label>
  <textarea id="jsonInput" placeholder='Paste your JSON here…&#10;&#10;Arrays, objects, nested structures — all supported.'></textarea>

  <div class="row">

    <div class="field">
      <label>Flatten nested keys</label>
      <div class="toggle-group">
        <input type="radio" name="flatten" id="flatOn"  value="true"  checked />
        <label for="flatOn">On</label>
        <input type="radio" name="flatten" id="flatOff" value="false" />
        <label for="flatOff">Off</label>
      </div>
    </div>

    <div class="field">
      <label>Strip common prefix</label>
      <div class="toggle-group">
        <input type="radio" name="strip_prefix" id="stripOn"  value="true"  checked />
        <label for="stripOn">On</label>
        <input type="radio" name="strip_prefix" id="stripOff" value="false" />
        <label for="stripOff">Off</label>
      </div>
    </div>

    <div class="field">
      <label>Separator</label>
      <input type="text" id="sepInput" value="." maxlength="5" style="width:70px;text-align:center;" />
    </div>

    <div class="field">
      <label>Sheet name (default)</label>
      <input type="text" id="sheetName" value="Sheet1" />
    </div>

    <div class="spacer"></div>

    <button id="convertBtn" onclick="convert()">Convert</button>
  </div>

  <div id="status" class="info">
    <div class="spinner" id="spinner"></div>
    <span id="statusText">Paste JSON and click Convert.</span>
  </div>

  <div id="preview">
    <h2>Preview</h2>
    <div class="sheet-tabs" id="sheetTabs"></div>
    <div class="table-wrap">
      <table id="previewTable"><thead></thead><tbody></tbody></table>
    </div>
    <div class="row-count" id="rowCount"></div>
    <button id="downloadBtn" onclick="download()">⬇ Download .xlsx</button>
  </div>
</div>

<script>
  let _sheets = [];   // [{name, columns, rows}]
  let _active = 0;

  function setStatus(msg, type = "info") {
    const el = document.getElementById("statusText");
    const bar = document.getElementById("status");
    el.textContent = msg;
    bar.className = type;
  }

  function spin(on) {
    document.getElementById("spinner").style.display = on ? "block" : "none";
    document.getElementById("convertBtn").disabled = on;
  }

  async function convert() {
    const raw = document.getElementById("jsonInput").value.trim();
    const ta  = document.getElementById("jsonInput");
    ta.classList.remove("error");

    if (!raw) { setStatus("Nothing to convert — paste some JSON first.", "err"); return; }

    // Client-side JSON validation
    let parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) {
      ta.classList.add("error");
      setStatus("Invalid JSON: " + e.message, "err");
      return;
    }

    spin(true);
    setStatus("Converting…", "info");

    const flatten      = document.querySelector('input[name="flatten"]:checked').value;
    const strip_prefix = document.querySelector('input[name="strip_prefix"]:checked').value;
    const sep          = document.getElementById("sepInput").value || ".";
    const sheetName    = document.getElementById("sheetName").value || "Sheet1";

    try {
      const res = await fetch("/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ json: raw, flatten: flatten === "true", strip_prefix: strip_prefix === "true", sep, sheet_name: sheetName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Server error");

      _sheets = data.sheets;
      _active = 0;
      renderTabs();
      renderTable(0);

      document.getElementById("preview").style.display = "block";
      document.getElementById("downloadBtn").style.display = "inline-block";
      setTimeout(() => document.getElementById("preview").scrollIntoView({ behavior: "smooth", block: "start" }), 50);

      const total = _sheets.reduce((s, sh) => s + sh.rows.length, 0);
      setStatus(
        `${_sheets.length} sheet(s) · ${total} total row(s) — ready to download.`,
        "ok"
      );
    } catch (e) {
      setStatus(e.message, "err");
    } finally {
      spin(false);
    }
  }

  function renderTabs() {
    const tabs = document.getElementById("sheetTabs");
    tabs.innerHTML = _sheets.map((s, i) =>
      `<div class="sheet-tab ${i === _active ? "active" : ""}" onclick="switchTab(${i})">${s.name}</div>`
    ).join("");
  }

  function switchTab(i) {
    _active = i;
    renderTabs();
    renderTable(i);
  }

  function renderTable(i) {
    const sheet = _sheets[i];
    const thead = document.querySelector("#previewTable thead");
    const tbody = document.querySelector("#previewTable tbody");

    thead.innerHTML = "<tr>" + sheet.columns.map(c => `<th title="${c}">${c}</th>`).join("") + "</tr>";
    tbody.innerHTML = sheet.rows.slice(0, 100).map(row =>
      "<tr>" + sheet.columns.map(c => `<td title="${row[c] ?? ""}">${row[c] ?? ""}</td>`).join("") + "</tr>"
    ).join("");

    const extra = sheet.rows.length > 100 ? ` (showing first 100 of ${sheet.rows.length})` : "";
    document.getElementById("rowCount").textContent =
      `${sheet.rows.length} row(s)${extra}`;
  }

  async function download() {
    const raw          = document.getElementById("jsonInput").value.trim();
    const flatten      = document.querySelector('input[name="flatten"]:checked').value;
    const strip_prefix = document.querySelector('input[name="strip_prefix"]:checked').value;
    const sep          = document.getElementById("sepInput").value || ".";
    const sheetName    = document.getElementById("sheetName").value || "Sheet1";

    const res = await fetch("/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ json: raw, flatten: flatten === "true", strip_prefix: strip_prefix === "true", sep, sheet_name: sheetName }),
    });

    if (!res.ok) { setStatus("Download failed.", "err"); return; }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "converted.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  // Ctrl/Cmd+Enter to convert
  document.getElementById("jsonInput").addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") convert();
  });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return HTML


@app.route("/preview", methods=["POST"])
def preview():
    body = request.get_json(force=True)
    try:
        data = json.loads(body["json"])
    except (json.JSONDecodeError, KeyError) as e:
        return jsonify({"error": f"Invalid JSON: {e}"}), 400

    try:
        sheets = json_to_dataframes(
            data,
            flatten=body.get("flatten", True),
            sep=body.get("sep", "."),
            sheet_name=body.get("sheet_name", "Sheet1"),
            strip_prefix=body.get("strip_prefix", True),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result = []
    for name, df in sheets:
        df = df.fillna("").astype(str)
        result.append({
            "name": name,
            "columns": df.columns.tolist(),
            "rows": df.to_dict(orient="records"),
        })

    return jsonify({"sheets": result})


@app.route("/download", methods=["POST"])
def download():
    body = request.get_json(force=True)
    try:
        data = json.loads(body["json"])
    except (json.JSONDecodeError, KeyError) as e:
        return jsonify({"error": f"Invalid JSON: {e}"}), 400

    sheets = json_to_dataframes(
        data,
        flatten=body.get("flatten", True),
        sep=body.get("sep", "."),
        sheet_name=body.get("sheet_name", "Sheet1"),
        strip_prefix=body.get("strip_prefix", True),
    )

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    to_excel(sheets, tmp_path)

    with open(tmp_path, "rb") as f:
        buf = io.BytesIO(f.read())
    Path(tmp_path).unlink(missing_ok=True)

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="converted.xlsx",
    )


if __name__ == "__main__":
    import webbrowser, threading
    url = "http://localhost:5123"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"  Converter UI → {url}")
    app.run(port=5123, debug=False)
