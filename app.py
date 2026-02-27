"""
Flask web UI for the converter suite.

Supported conversions:
  - JSON → Excel (.xlsx)
  - Markdown → Word (.docx)
  - Markdown → PDF (.pdf)
"""
import io
import json
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify

from json_converter import load_json, json_to_dataframes, to_excel
from md_converter import md_to_html, md_to_styled_html, md_to_docx_bytes, md_to_pdf_bytes

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Ayo's Converter</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: "Times New Roman", Times, serif;
      background: #ffffff;
      color: #1f2328;
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
    header h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; color: #1f2328; }
    header p  { margin-top: 8px; color: #656d76; font-size: 0.95rem; }

    /* ── Converter tabs ─────────────────────────────────────── */
    .converter-tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 24px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .converter-tab {
      padding: 8px 20px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 600;
      background: #f6f8fa;
      color: #656d76;
      border: 1px solid #d1d9e0;
      cursor: pointer;
      transition: background 0.15s, color 0.15s, border-color 0.15s;
    }
    .converter-tab:hover { background: #eaeef2; color: #1f2328; }
    .converter-tab.active {
      background: #0969da;
      color: #fff;
      border-color: #0969da;
    }

    .card {
      background: #f6f8fa;
      border: 1px solid #d1d9e0;
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
      color: #656d76;
      margin-bottom: 8px;
    }

    textarea {
      width: 100%;
      height: 320px;
      background: #ffffff;
      border: 1px solid #d1d9e0;
      border-radius: 8px;
      color: #1f2328;
      font-family: "Times New Roman", Times, serif;
      font-size: 0.85rem;
      line-height: 1.6;
      padding: 14px;
      resize: vertical;
      outline: none;
      transition: border-color 0.15s;
    }
    textarea:focus { border-color: #0969da; }
    textarea.error  { border-color: #cf222e; }

    .row {
      display: flex;
      gap: 12px;
      margin-top: 18px;
      flex-wrap: wrap;
      align-items: flex-end;
    }

    .field { display: flex; flex-direction: column; gap: 6px; }
    .field input[type="text"] {
      background: #ffffff;
      border: 1px solid #d1d9e0;
      border-radius: 6px;
      color: #1f2328;
      font-size: 0.88rem;
      padding: 8px 12px;
      outline: none;
      transition: border-color 0.15s;
      min-width: 160px;
    }
    .field input[type="text"]:focus { border-color: #0969da; }

    .toggle-group {
      display: flex;
      gap: 0;
      border: 1px solid #d1d9e0;
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
      color: #656d76;
      cursor: pointer;
      background: #ffffff;
      transition: background 0.12s, color 0.12s;
      margin: 0;
    }
    .toggle-group input[type="radio"]:checked + label {
      background: #0969da;
      color: #fff;
    }

    .spacer { flex: 1; }

    button.primary-btn {
      height: 36px;
      padding: 0 24px;
      background: #1f883d;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      white-space: nowrap;
    }
    button.primary-btn:hover { background: #1a7f37; }
    button.primary-btn:disabled { opacity: 0.5; cursor: default; }

    /* Status / error bar */
    .status-bar {
      margin-top: 14px;
      font-size: 0.85rem;
      min-height: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-bar.ok   { color: #1a7f37; }
    .status-bar.err  { color: #cf222e; }
    .status-bar.info { color: #656d76; }

    /* Preview table (JSON) */
    #jsonPreview {
      margin-top: 24px;
      display: none;
    }
    #jsonPreview h2, #mdPreview h2 {
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #656d76;
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
      background: #eaeef2;
      color: #656d76;
      border: 1px solid #d1d9e0;
      cursor: pointer;
      transition: background 0.12s;
    }
    .sheet-tab.active { background: #0969da; color: #fff; border-color: #0969da; }

    .table-wrap {
      overflow-x: auto;
      border: 1px solid #d1d9e0;
      border-radius: 8px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      font-size: 0.82rem;
    }
    th {
      background: #f6f8fa;
      color: #0969da;
      font-weight: 700;
      padding: 10px 14px;
      text-align: left;
      white-space: nowrap;
      border-bottom: 2px solid #0969da30;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 8px 14px;
      border-bottom: 1px solid #eaeef2;
      color: #1f2328;
      white-space: nowrap;
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f6f8fa; }

    .row-count {
      margin-top: 6px;
      font-size: 0.78rem;
      color: #656d76;
    }

    /* Download buttons */
    .download-btn {
      height: 36px;
      padding: 0 22px;
      background: #ffffff;
      color: #0969da;
      border: 1px solid #0969da;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      display: none;
    }
    .download-btn:hover { background: #f6f8fa; }

    .download-row {
      display: flex;
      gap: 10px;
      margin-top: 16px;
      flex-wrap: wrap;
    }

    /* Markdown preview */
    #mdPreview {
      margin-top: 24px;
      display: none;
    }
    .md-rendered {
      background: #fff;
      border: 1px solid #d1d9e0;
      border-radius: 8px;
      padding: 24px 28px;
      color: #1f2328;
      font-family: "Times New Roman", Times, serif;
      font-size: 14px;
      line-height: 1.7;
      overflow-x: auto;
    }
    .md-rendered h1, .md-rendered h2, .md-rendered h3,
    .md-rendered h4, .md-rendered h5, .md-rendered h6 {
      margin-top: 1.2em; margin-bottom: 0.5em; font-weight: 600; color: #1f2328;
    }
    .md-rendered h1 { font-size: 1.8em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
    .md-rendered h2 { font-size: 1.4em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
    .md-rendered h3 { font-size: 1.15em; }
    .md-rendered p { margin: 0 0 14px; }
    .md-rendered a { color: #0969da; }
    .md-rendered code {
      background: #eff1f3; padding: 2px 5px; border-radius: 4px;
      font-family: "Times New Roman", Times, serif; font-size: 0.88em;
    }
    .md-rendered pre {
      background: #f6f8fa; border: 1px solid #d1d9e0; border-radius: 6px;
      padding: 14px; overflow-x: auto; margin: 0 0 14px;
    }
    .md-rendered pre code { background: none; padding: 0; }
    .md-rendered blockquote {
      border-left: 4px solid #d1d9e0; padding: 0 14px; color: #656d76; margin: 0 0 14px;
    }
    .md-rendered table { border-collapse: collapse; width: 100%; margin: 0 0 14px; }
    .md-rendered th, .md-rendered td {
      border: 1px solid #d1d9e0; padding: 8px 12px; text-align: left;
      color: #1f2328; background: transparent; text-transform: none;
      font-size: 14px; letter-spacing: normal; font-weight: normal;
      white-space: normal; max-width: none; overflow: visible;
    }
    .md-rendered th { background: #f6f8fa; font-weight: 600; }
    .md-rendered ul, .md-rendered ol { margin: 0 0 14px; padding-left: 2em; }
    .md-rendered li { margin-bottom: 3px; color: #1f2328; }
    .md-rendered hr { border: none; border-top: 2px solid #d1d9e0; margin: 20px 0; }

    /* Spinner */
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid #d1d9e0;
      border-top-color: #0969da;
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
      display: none;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* File upload */
    .file-upload-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .file-upload-row label.upload-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      background: #eaeef2;
      border: 1px solid #d1d9e0;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 600;
      color: #1f2328;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
      text-transform: none;
      letter-spacing: 0;
      margin: 0;
    }
    .file-upload-row label.upload-label:hover {
      background: #d1d9e0;
      border-color: #0969da;
    }
    .file-upload-row input[type="file"] { display: none; }
    .file-upload-row .file-name {
      font-size: 0.82rem;
      color: #656d76;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 300px;
    }

    /* Panel visibility */
    .panel { display: none; }
    .panel.active { display: block; }
  </style>
</head>
<body>

<header>
  <h1>Ayo's Converter</h1>
  <p>Convert between formats — paste, preview, download</p>
</header>

<div class="converter-tabs">
  <div class="converter-tab active" onclick="switchConverter('json')">JSON → Excel</div>
  <div class="converter-tab" onclick="switchConverter('md-docx')">Markdown → DOCX</div>
  <div class="converter-tab" onclick="switchConverter('md-pdf')">Markdown → PDF</div>
</div>

<!-- ═══════════════════ JSON → Excel ═══════════════════ -->
<div class="card panel active" id="panel-json">
  <div class="file-upload-row">
    <label for="jsonInput">JSON Input</label>
    <label class="upload-label" for="jsonFileInput">&#128206; Attach .json</label>
    <input type="file" id="jsonFileInput" accept=".json,application/json" onchange="loadFile(this, 'jsonInput')" />
    <span class="file-name" id="jsonFileName"></span>
  </div>
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
    <button class="primary-btn" id="jsonConvertBtn" onclick="jsonConvert()">Convert</button>
  </div>

  <div id="jsonStatus" class="status-bar info">
    <div class="spinner" id="jsonSpinner"></div>
    <span id="jsonStatusText">Paste JSON and click Convert.</span>
  </div>

  <div id="jsonPreview">
    <div class="download-row">
      <button class="download-btn" id="jsonDownloadBtnTop" onclick="jsonDownload()">⬇ Download .xlsx</button>
    </div>
    <h2>Preview</h2>
    <div class="sheet-tabs" id="sheetTabs"></div>
    <div class="table-wrap">
      <table id="previewTable"><thead></thead><tbody></tbody></table>
    </div>
    <div class="row-count" id="rowCount"></div>
    <div class="download-row">
      <button class="download-btn" id="jsonDownloadBtn" onclick="jsonDownload()">⬇ Download .xlsx</button>
    </div>
  </div>
</div>

<!-- ═══════════════════ Markdown → DOCX ═══════════════════ -->
<div class="card panel" id="panel-md-docx">
  <div class="file-upload-row">
    <label for="mdDocxInput">Markdown Input</label>
    <label class="upload-label" for="mdDocxFileInput">&#128206; Attach .md</label>
    <input type="file" id="mdDocxFileInput" accept=".md,.markdown,text/markdown,text/plain" onchange="loadFile(this, 'mdDocxInput')" />
    <span class="file-name" id="mdDocxFileName"></span>
  </div>
  <textarea id="mdDocxInput" placeholder='# Hello World&#10;&#10;Write or paste your **Markdown** here…&#10;&#10;- Lists&#10;- Tables&#10;- Code blocks&#10;&#10;All supported.'></textarea>

  <div class="row">
    <div class="spacer"></div>
    <button class="primary-btn" id="mdDocxConvertBtn" onclick="mdConvert('docx')">Convert</button>
  </div>

  <div id="mdDocxStatus" class="status-bar info">
    <div class="spinner" id="mdDocxSpinner"></div>
    <span id="mdDocxStatusText">Write Markdown and click Convert.</span>
  </div>

  <div id="mdDocxPreview">
    <div class="download-row">
      <button class="download-btn" id="mdDocxDownloadBtnTop" onclick="mdDownload('docx')">⬇ Download .docx</button>
    </div>
    <h2>Preview</h2>
    <div class="md-rendered" id="mdDocxRendered"></div>
    <div class="download-row">
      <button class="download-btn" id="mdDocxDownloadBtn" onclick="mdDownload('docx')">⬇ Download .docx</button>
    </div>
  </div>
</div>

<!-- ═══════════════════ Markdown → PDF ═══════════════════ -->
<div class="card panel" id="panel-md-pdf">
  <div class="file-upload-row">
    <label for="mdPdfInput">Markdown Input</label>
    <label class="upload-label" for="mdPdfFileInput">&#128206; Attach .md</label>
    <input type="file" id="mdPdfFileInput" accept=".md,.markdown,text/markdown,text/plain" onchange="loadFile(this, 'mdPdfInput')" />
    <span class="file-name" id="mdPdfFileName"></span>
  </div>
  <textarea id="mdPdfInput" placeholder='# Hello World&#10;&#10;Write or paste your **Markdown** here…&#10;&#10;- Lists&#10;- Tables&#10;- Code blocks&#10;&#10;All supported.'></textarea>

  <div class="row">
    <div class="spacer"></div>
    <button class="primary-btn" id="mdPdfConvertBtn" onclick="mdConvert('pdf')">Convert</button>
  </div>

  <div id="mdPdfStatus" class="status-bar info">
    <div class="spinner" id="mdPdfSpinner"></div>
    <span id="mdPdfStatusText">Write Markdown and click Convert.</span>
  </div>

  <div id="mdPdfPreview">
    <div class="download-row">
      <button class="download-btn" id="mdPdfDownloadBtnTop" onclick="mdDownload('pdf')">⬇ Download .pdf</button>
    </div>
    <h2>Preview</h2>
    <div class="md-rendered" id="mdPdfRendered"></div>
    <div class="download-row">
      <button class="download-btn" id="mdPdfDownloadBtn" onclick="mdDownload('pdf')">⬇ Download .pdf</button>
    </div>
  </div>
</div>

<script>
  /* ── File upload ─────────────────────────────────────────── */
  function loadFile(input, textareaId) {
    const file = input.files[0];
    if (!file) return;

    // Show file name
    const nameSpan = input.parentElement.querySelector(".file-name");
    nameSpan.textContent = file.name;

    const reader = new FileReader();
    reader.onload = function(e) {
      document.getElementById(textareaId).value = e.target.result;
    };
    reader.onerror = function() {
      nameSpan.textContent = "Failed to read file.";
    };
    reader.readAsText(file);
  }

  /* ── Converter switching ────────────────────────────────── */
  let _currentConverter = "json";

  function switchConverter(id) {
    _currentConverter = id;
    document.querySelectorAll(".converter-tab").forEach((t, i) => {
      const ids = ["json", "md-docx", "md-pdf"];
      t.classList.toggle("active", ids[i] === id);
    });
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + id).classList.add("active");
  }

  /* ── JSON helpers ───────────────────────────────────────── */
  let _sheets = [];
  let _active = 0;

  function jsonSetStatus(msg, type = "info") {
    document.getElementById("jsonStatusText").textContent = msg;
    document.getElementById("jsonStatus").className = "status-bar " + type;
  }
  function jsonSpin(on) {
    document.getElementById("jsonSpinner").style.display = on ? "block" : "none";
    document.getElementById("jsonConvertBtn").disabled = on;
  }

  async function jsonConvert() {
    const raw = document.getElementById("jsonInput").value.trim();
    const ta  = document.getElementById("jsonInput");
    ta.classList.remove("error");

    if (!raw) { jsonSetStatus("Nothing to convert — paste some JSON first.", "err"); return; }

    let parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) {
      ta.classList.add("error");
      jsonSetStatus("Invalid JSON: " + e.message, "err");
      return;
    }

    jsonSpin(true);
    jsonSetStatus("Converting…", "info");

    const flatten      = document.querySelector('input[name="flatten"]:checked').value;
    const strip_prefix = document.querySelector('input[name="strip_prefix"]:checked').value;
    const sep          = document.getElementById("sepInput").value || ".";
    const sheetName    = document.getElementById("sheetName").value || "Sheet1";

    try {
      const res = await fetch("/json/preview", {
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

      document.getElementById("jsonPreview").style.display = "block";
      document.getElementById("jsonDownloadBtn").style.display = "inline-block";
      document.getElementById("jsonDownloadBtnTop").style.display = "inline-block";
      setTimeout(() => document.getElementById("jsonPreview").scrollIntoView({ behavior: "smooth", block: "start" }), 50);

      const total = _sheets.reduce((s, sh) => s + sh.rows.length, 0);
      jsonSetStatus(`${_sheets.length} sheet(s) · ${total} total row(s) — ready to download.`, "ok");
    } catch (e) {
      jsonSetStatus(e.message, "err");
    } finally {
      jsonSpin(false);
    }
  }

  function renderTabs() {
    document.getElementById("sheetTabs").innerHTML = _sheets.map((s, i) =>
      `<div class="sheet-tab ${i === _active ? "active" : ""}" onclick="switchTab(${i})">${s.name}</div>`
    ).join("");
  }
  function switchTab(i) { _active = i; renderTabs(); renderTable(i); }

  function renderTable(i) {
    const sheet = _sheets[i];
    const thead = document.querySelector("#previewTable thead");
    const tbody = document.querySelector("#previewTable tbody");
    thead.innerHTML = "<tr>" + sheet.columns.map(c => `<th title="${c}">${c}</th>`).join("") + "</tr>";
    tbody.innerHTML = sheet.rows.slice(0, 100).map(row =>
      "<tr>" + sheet.columns.map(c => `<td title="${row[c] ?? ""}">${row[c] ?? ""}</td>`).join("") + "</tr>"
    ).join("");
    const extra = sheet.rows.length > 100 ? ` (showing first 100 of ${sheet.rows.length})` : "";
    document.getElementById("rowCount").textContent = `${sheet.rows.length} row(s)${extra}`;
  }

  async function jsonDownload() {
    const raw          = document.getElementById("jsonInput").value.trim();
    const flatten      = document.querySelector('input[name="flatten"]:checked').value;
    const strip_prefix = document.querySelector('input[name="strip_prefix"]:checked').value;
    const sep          = document.getElementById("sepInput").value || ".";
    const sheetName    = document.getElementById("sheetName").value || "Sheet1";

    const res = await fetch("/json/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ json: raw, flatten: flatten === "true", strip_prefix: strip_prefix === "true", sep, sheet_name: sheetName }),
    });
    if (!res.ok) { jsonSetStatus("Download failed.", "err"); return; }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "converted.xlsx"; a.click();
    URL.revokeObjectURL(url);
  }

  document.getElementById("jsonInput").addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") jsonConvert();
  });

  /* ── Markdown helpers ───────────────────────────────────── */

  function mdSetStatus(fmt, msg, type = "info") {
    document.getElementById("md" + cap(fmt) + "StatusText").textContent = msg;
    document.getElementById("md" + cap(fmt) + "Status").className = "status-bar " + type;
  }
  function mdSpin(fmt, on) {
    document.getElementById("md" + cap(fmt) + "Spinner").style.display = on ? "block" : "none";
    document.getElementById("md" + cap(fmt) + "ConvertBtn").disabled = on;
  }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  async function mdConvert(fmt) {
    const ta  = document.getElementById("md" + cap(fmt) + "Input");
    const raw = ta.value.trim();
    ta.classList.remove("error");

    if (!raw) { mdSetStatus(fmt, "Nothing to convert — write some Markdown first.", "err"); return; }

    mdSpin(fmt, true);
    mdSetStatus(fmt, "Converting…", "info");

    try {
      const res = await fetch("/md/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: raw }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Server error");

      document.getElementById("md" + cap(fmt) + "Rendered").innerHTML = data.html;
      document.getElementById("md" + cap(fmt) + "Preview").style.display = "block";
      document.getElementById("md" + cap(fmt) + "DownloadBtn").style.display = "inline-block";
      document.getElementById("md" + cap(fmt) + "DownloadBtnTop").style.display = "inline-block";
      setTimeout(() => document.getElementById("md" + cap(fmt) + "Preview").scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      mdSetStatus(fmt, "Preview ready — click download to save.", "ok");
    } catch (e) {
      mdSetStatus(fmt, e.message, "err");
    } finally {
      mdSpin(fmt, false);
    }
  }

  async function mdDownload(fmt) {
    const raw = document.getElementById("md" + cap(fmt) + "Input").value.trim();
    if (!raw) return;

    mdSetStatus(fmt, "Generating file…", "info");
    mdSpin(fmt, true);

    try {
      const res = await fetch("/md/download/" + fmt, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: raw }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Download failed.");
      }

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url;
      a.download = "converted." + fmt;
      a.click();
      URL.revokeObjectURL(url);
      mdSetStatus(fmt, "Downloaded!", "ok");
    } catch (e) {
      mdSetStatus(fmt, e.message, "err");
    } finally {
      mdSpin(fmt, false);
    }
  }

  // Ctrl/Cmd+Enter in markdown textareas
  ["mdDocxInput", "mdPdfInput"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        const fmt = id.includes("Docx") ? "docx" : "pdf";
        mdConvert(fmt);
      }
    });
  });
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return HTML


# ── JSON → Excel ────────────────────────────────────────────

@app.route("/preview", methods=["POST"])
@app.route("/json/preview", methods=["POST"])
def json_preview():
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
@app.route("/json/download", methods=["POST"])
def json_download():
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


# ── Markdown preview / download ─────────────────────────────

@app.route("/md/preview", methods=["POST"])
def md_preview():
    body = request.get_json(force=True)
    raw = body.get("markdown", "")
    if not raw.strip():
        return jsonify({"error": "Empty markdown."}), 400

    try:
        html = md_to_html(raw)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"html": html})


@app.route("/md/download/docx", methods=["POST"])
def md_download_docx():
    body = request.get_json(force=True)
    raw = body.get("markdown", "")
    if not raw.strip():
        return jsonify({"error": "Empty markdown."}), 400

    try:
        data = md_to_docx_bytes(raw)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    buf = io.BytesIO(data)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name="converted.docx",
    )


@app.route("/md/download/pdf", methods=["POST"])
def md_download_pdf():
    body = request.get_json(force=True)
    raw = body.get("markdown", "")
    if not raw.strip():
        return jsonify({"error": "Empty markdown."}), 400

    try:
        data = md_to_pdf_bytes(raw)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    buf = io.BytesIO(data)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="converted.pdf",
    )


if __name__ == "__main__":
    import webbrowser, threading
    url = "http://localhost:5123"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"  Converter UI → {url}")
    app.run(port=5123, debug=False)
