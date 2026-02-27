"""
Flask web UI for Ayo's Converter suite.

Supported conversions (20 total):
  Document/Text: JSON->Excel, Markdown->DOCX, Markdown->PDF, CSV->Excel, YAML->JSON, HTML->Markdown, PDF->Text
  Data: XML->JSON, SQL->CSV, CSV->JSON
  Image/Media: SVG->PNG (client), Image Resizer, Base64<->Image
  Developer Tools: JSON Formatter (client), TOML->JSON/YAML, Cron Parser
  Everyday Use: Unit Converter (client), Color Converter (client), Timestamp Tool, Time Zone Converter (client)
"""
import io
import csv as csv_mod
import json
import logging
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify, Response
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bleach

from json_converter import load_json, json_to_dataframes, to_excel
from md_converter import md_to_html, md_to_styled_html, md_to_docx_bytes, md_to_pdf_bytes

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

Compress(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"], storage_uri="memory://")

MAX_TEXT_INPUT = 5 * 1024 * 1024  # 5 MB for text inputs

# Bleach allowlist for Markdown HTML sanitization
_ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "em", "strong", "b", "i",
    "code", "pre", "blockquote", "ul", "ol", "li", "table", "thead", "tbody",
    "tr", "th", "td", "hr", "br", "img", "div", "span", "sup", "sub",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "div": ["class"],
    "span": ["class"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}


def _validate_text(text: str | None, name: str = "input") -> str:
    if not text or not text.strip():
        raise ValueError(f"{name} is empty")
    if len(text.encode("utf-8")) > MAX_TEXT_INPUT:
        raise ValueError(f"{name} too large (max 5 MB)")
    return text


# ═══════════════════════════════════════════════════════════════════════════
# HTML Template
# ═══════════════════════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Ayo's Converter - Free Online File Format Converter</title>
  <meta name="description" content="Free online converter for JSON, CSV, YAML, XML, Markdown, PDF, images, and more. Convert between 20+ file formats instantly. No signup required." />
  <meta name="keywords" content="file converter, JSON to Excel, CSV to JSON, YAML to JSON, markdown to PDF, online converter, free converter" />
  <meta property="og:title" content="Ayo's Converter - Free Online File Format Converter" />
  <meta property="og:description" content="Convert between 20+ file formats instantly. JSON, CSV, YAML, XML, Markdown, PDF, images and more." />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Ayo's Converter" />
  <meta name="twitter:description" content="Convert between 20+ file formats instantly." />
  <link rel="canonical" href="/" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Ayo's Converter",
    "applicationCategory": "UtilitiesApplication",
    "operatingSystem": "Web",
    "description": "Free online converter for 20+ file formats including JSON, CSV, YAML, XML, Markdown, PDF, images and more.",
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
  }
  </script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: "Times New Roman", Times, serif;
      background: #ffffff;
      color: #1f2328;
      min-height: 100vh;
    }

    /* ── Layout ────────────────────────────────────────────── */
    .app-header {
      text-align: center;
      padding: 24px 16px 16px;
      border-bottom: 1px solid #d1d9e0;
    }
    .app-header h1 { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
    .app-header p  { margin-top: 4px; color: #656d76; font-size: 0.85rem; }

    .app-layout {
      display: grid;
      grid-template-columns: 220px 1fr;
      min-height: calc(100vh - 80px);
    }

    /* ── Sidebar ───────────────────────────────────────────── */
    .sidebar {
      background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
      border-right: 1px solid #e2e8f0;
      padding: 20px 0;
      overflow-y: auto;
    }
    .sidebar-category { margin-bottom: 6px; }
    .sidebar-category h3 {
      font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1px; color: #94a3b8; padding: 10px 20px 6px;
    }
    .sidebar-item {
      display: block;
      padding: 9px 16px 9px 20px; cursor: pointer;
      font-size: 0.84rem; color: #475569; text-decoration: none;
      border-radius: 0 24px 24px 0; margin-right: 12px;
      transition: all 0.2s ease;
      border-left: 3px solid transparent;
    }
    .sidebar-item:hover {
      background: #e2e8f0; color: #1e293b;
    }
    .sidebar-item.active {
      background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
      color: #1d4ed8; font-weight: 600;
      border-left-color: #3b82f6;
      box-shadow: 0 1px 3px rgba(59,130,246,.15);
    }

    .mobile-select { display: none; width: 100%; padding: 10px; font-size: 1rem; font-family: inherit; margin-bottom: 12px; border: 1px solid #d1d9e0; border-radius: 8px; }

    /* ── Content ───────────────────────────────────────────── */
    .content {
      padding: 24px 32px 80px;
      max-width: 900px;
    }

    .panel { display: none; }
    .panel.active { display: block; }
    .panel h2 { font-size: 1.3rem; margin-bottom: 16px; font-weight: 600; }

    textarea, input[type="text"], input[type="number"], select {
      font-family: "Times New Roman", Times, serif;
      font-size: 0.95rem;
      border: 1px solid #d1d9e0;
      border-radius: 8px;
      padding: 10px 12px;
      width: 100%;
      background: #fff;
      color: #1f2328;
    }
    textarea { resize: vertical; min-height: 180px; }
    textarea:focus, input:focus, select:focus { outline: none; border-color: #0969da; box-shadow: 0 0 0 3px rgba(9,105,218,.15); }

    .options-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; align-items: end; }
    .options-row label { font-size: 0.8rem; color: #656d76; display: block; margin-bottom: 4px; }
    .options-row input, .options-row select { width: auto; min-width: 100px; }

    .btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 9px 20px; border: none; border-radius: 8px;
      font-family: inherit; font-size: 0.9rem; font-weight: 600;
      cursor: pointer; transition: background 0.15s;
    }
    .btn-primary { background: #0969da; color: #fff; }
    .btn-primary:hover { background: #0860ca; }
    .btn-primary:disabled { opacity: .5; cursor: not-allowed; }
    .btn-green { background: #1a7f37; color: #fff; margin-top: 8px; }
    .btn-green:hover { background: #166b2e; }
    .btn-secondary { background: #eaeef2; color: #1f2328; }
    .btn-secondary:hover { background: #d1d9e0; }
    .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }

    .status { margin: 10px 0; font-size: 0.85rem; min-height: 1.2em; }
    .status.ok { color: #1a7f37; } .status.err { color: #cf222e; } .status.info { color: #656d76; }

    .spinner { display: none; width: 18px; height: 18px; border: 3px solid #d1d9e0; border-top-color: #0969da; border-radius: 50%; animation: spin .6s linear infinite; margin-left: 8px; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .preview { margin-top: 16px; }
    .preview pre, .output-box {
      background: #f6f8fa; border: 1px solid #d1d9e0; border-radius: 8px;
      padding: 14px; font-size: 0.85rem; overflow-x: auto; white-space: pre-wrap;
      word-break: break-word; max-height: 500px; overflow-y: auto;
      font-family: "Courier New", monospace;
    }

    /* ── JSON preview table ────────────────────────────────── */
    .sheet-tabs { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
    .sheet-tab { padding: 4px 14px; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.82rem; background: #eaeef2; border: 1px solid #d1d9e0; border-bottom: none; }
    .sheet-tab.active { background: #fff; font-weight: 600; color: #0969da; }
    .preview-table-wrap { overflow-x: auto; max-height: 420px; overflow-y: auto; border: 1px solid #d1d9e0; border-radius: 0 0 8px 8px; }
    table.preview-table { border-collapse: collapse; width: 100%; font-size: 0.82rem; }
    table.preview-table th, table.preview-table td { border: 1px solid #d1d9e0; padding: 6px 10px; text-align: left; white-space: nowrap; }
    table.preview-table th { background: #0969da; color: #fff; position: sticky; top: 0; }
    table.preview-table tr:hover td { background: #f6f8fa; }

    /* ── Markdown preview ──────────────────────────────────── */
    .md-rendered { padding: 16px; border: 1px solid #d1d9e0; border-radius: 8px; background: #fff; max-height: 500px; overflow-y: auto; }
    .md-rendered h1,.md-rendered h2,.md-rendered h3,.md-rendered h4,.md-rendered h5,.md-rendered h6 { margin: 1em 0 0.5em; font-weight: 600; }
    .md-rendered h1 { font-size: 1.6em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
    .md-rendered h2 { font-size: 1.3em; border-bottom: 1px solid #d1d9e0; padding-bottom: 0.3em; }
    .md-rendered p { margin: 0 0 12px; } .md-rendered ul,.md-rendered ol { margin: 0 0 12px; padding-left: 2em; }
    .md-rendered pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; }
    .md-rendered code { background: #eff1f3; padding: 1px 5px; border-radius: 4px; font-family: "Courier New", monospace; font-size: 0.88em; }
    .md-rendered pre code { background: none; padding: 0; }
    .md-rendered table { border-collapse: collapse; margin: 0 0 12px; }
    .md-rendered th,.md-rendered td { border: 1px solid #d1d9e0; padding: 6px 12px; }
    .md-rendered th { background: #f6f8fa; font-weight: 600; }
    .md-rendered blockquote { border-left: 4px solid #d1d9e0; padding: 0 14px; color: #656d76; margin: 0 0 12px; }

    /* ── Color swatch ──────────────────────────────────────── */
    .color-swatch { width: 100%; height: 80px; border-radius: 8px; border: 1px solid #d1d9e0; margin: 12px 0; }
    .color-inputs { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    .color-inputs div label { font-size: 0.8rem; color: #656d76; display: block; margin-bottom: 4px; }

    /* ── File upload ───────────────────────────────────────── */
    .file-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .file-row input[type="file"] { display: none; }
    .file-label { padding: 7px 16px; border-radius: 8px; background: #eaeef2; cursor: pointer; font-size: 0.85rem; font-weight: 500; }
    .file-label:hover { background: #d1d9e0; }
    .file-name { font-size: 0.82rem; color: #656d76; }

    /* ── Image preview ─────────────────────────────────────── */
    .img-preview { max-width: 100%; max-height: 300px; border: 1px solid #d1d9e0; border-radius: 8px; margin: 12px 0; }

    /* ── Time Zone converter ─────────────────────────────────── */
    .tz-dropdown {
      position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
      background: #fff; border: 1px solid #d1d9e0; border-radius: 8px;
      max-height: 260px; overflow-y: auto; display: none;
      box-shadow: 0 8px 24px rgba(0,0,0,.12);
    }
    .tz-dropdown.open { display: block; }
    .tz-dropdown-group { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #94a3b8; padding: 8px 12px 4px; background: #f8fafc; }
    .tz-dropdown-item {
      padding: 8px 12px; cursor: pointer; font-size: 0.85rem; color: #1f2328;
      display: flex; justify-content: space-between; align-items: center;
    }
    .tz-dropdown-item:hover { background: #eff6ff; color: #1d4ed8; }
    .tz-dropdown-item .tz-offset { font-size: 0.75rem; color: #94a3b8; }
    .tz-card {
      background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
      border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center;
    }
    .tz-card-city { font-size: 0.85rem; font-weight: 600; color: #475569; margin-bottom: 4px; }
    .tz-card-time { font-size: 2.2rem; font-weight: 700; color: #1e293b; letter-spacing: -1px; }
    .tz-card-date { font-size: 0.85rem; color: #64748b; margin-top: 2px; }
    .tz-card-zone { font-size: 0.78rem; color: #94a3b8; margin-top: 6px; }
    .tz-invalid { border-color: #ef4444 !important; box-shadow: 0 0 0 3px rgba(239,68,68,.15) !important; }

    /* ── Footer ────────────────────────────────────────────── */
    footer { text-align: center; padding: 20px; font-size: 0.8rem; color: #8b949e; border-top: 1px solid #d1d9e0; }

    /* ── Responsive ────────────────────────────────────────── */
    @media (max-width: 768px) {
      .app-layout { grid-template-columns: 1fr; }
      .sidebar { display: none; }
      .mobile-select { display: block; }
      .content { padding: 16px; }
      .color-inputs { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

<header class="app-header">
  <h1>Ayo's Converter</h1>
  <p>20 free online converters &mdash; no signup required</p>
</header>

<!-- Mobile dropdown -->
<select class="mobile-select" onchange="switchConverter(this.value)">
  <optgroup label="Document / Text">
    <option value="json" selected>JSON &rarr; Excel</option>
    <option value="md-docx">Markdown &rarr; DOCX</option>
    <option value="md-pdf">Markdown &rarr; PDF</option>
    <option value="csv-excel">CSV &rarr; Excel</option>
    <option value="yaml-json">YAML &rarr; JSON</option>
    <option value="html-md">HTML &rarr; Markdown</option>
    <option value="pdf-text">PDF &rarr; Text</option>
  </optgroup>
  <optgroup label="Data">
    <option value="xml-json">XML &rarr; JSON</option>
    <option value="sql-csv">SQL &rarr; CSV</option>
    <option value="csv-json">CSV &rarr; JSON</option>
  </optgroup>
  <optgroup label="Image / Media">
    <option value="svg-png">SVG &rarr; PNG</option>
    <option value="image-resize">Image Resizer</option>
    <option value="base64-image">Base64 &harr; Image</option>
  </optgroup>
  <optgroup label="Developer Tools">
    <option value="json-format">JSON Formatter</option>
    <option value="toml-json">TOML &rarr; JSON/YAML</option>
    <option value="cron-human">Cron Parser</option>
  </optgroup>
  <optgroup label="Everyday Use">
    <option value="unit">Unit Converter</option>
    <option value="color">Color Converter</option>
    <option value="timestamp">Timestamp Tool</option>
    <option value="timezone">Time Zone Converter</option>
  </optgroup>
</select>

<main class="app-layout">
<nav class="sidebar">
  <div class="sidebar-category"><h3>Document / Text</h3>
    <a class="sidebar-item active" onclick="switchConverter('json')">JSON &rarr; Excel</a>
    <a class="sidebar-item" onclick="switchConverter('md-docx')">Markdown &rarr; DOCX</a>
    <a class="sidebar-item" onclick="switchConverter('md-pdf')">Markdown &rarr; PDF</a>
    <a class="sidebar-item" onclick="switchConverter('csv-excel')">CSV &rarr; Excel</a>
    <a class="sidebar-item" onclick="switchConverter('yaml-json')">YAML &rarr; JSON</a>
    <a class="sidebar-item" onclick="switchConverter('html-md')">HTML &rarr; Markdown</a>
    <a class="sidebar-item" onclick="switchConverter('pdf-text')">PDF &rarr; Text</a>
  </div>
  <div class="sidebar-category"><h3>Data</h3>
    <a class="sidebar-item" onclick="switchConverter('xml-json')">XML &rarr; JSON</a>
    <a class="sidebar-item" onclick="switchConverter('sql-csv')">SQL &rarr; CSV</a>
    <a class="sidebar-item" onclick="switchConverter('csv-json')">CSV &rarr; JSON</a>
  </div>
  <div class="sidebar-category"><h3>Image / Media</h3>
    <a class="sidebar-item" onclick="switchConverter('svg-png')">SVG &rarr; PNG</a>
    <a class="sidebar-item" onclick="switchConverter('image-resize')">Image Resizer</a>
    <a class="sidebar-item" onclick="switchConverter('base64-image')">Base64 &harr; Image</a>
  </div>
  <div class="sidebar-category"><h3>Developer Tools</h3>
    <a class="sidebar-item" onclick="switchConverter('json-format')">JSON Formatter</a>
    <a class="sidebar-item" onclick="switchConverter('toml-json')">TOML &rarr; JSON/YAML</a>
    <a class="sidebar-item" onclick="switchConverter('cron-human')">Cron Parser</a>
  </div>
  <div class="sidebar-category"><h3>Everyday Use</h3>
    <a class="sidebar-item" onclick="switchConverter('unit')">Unit Converter</a>
    <a class="sidebar-item" onclick="switchConverter('color')">Color Converter</a>
    <a class="sidebar-item" onclick="switchConverter('timestamp')">Timestamp Tool</a>
    <a class="sidebar-item" onclick="switchConverter('timezone')">Time Zone Converter</a>
  </div>
</nav>

<section class="content">

<!-- ═══════════════════ JSON → Excel ═══════════════════ -->
<div class="panel active" id="panel-json">
  <h2>JSON &rarr; Excel</h2>
  <div class="file-row">
    <input type="file" id="jsonFile" accept=".json" onchange="loadFile(this,'jsonInput')"/>
    <label for="jsonFile" class="file-label">Attach .json</label>
    <span class="file-name" id="jsonFileName"></span>
  </div>
  <textarea id="jsonInput" placeholder='Paste JSON here...'></textarea>
  <div class="options-row">
    <div><label>Flatten</label><select id="jsonFlatten"><option value="1">Yes</option><option value="0">No</option></select></div>
    <div><label>Strip prefix</label><select id="jsonStripPrefix"><option value="1">Yes</option><option value="0">No</option></select></div>
    <div><label>Separator</label><input type="text" id="jsonSep" value="." maxlength="5" style="width:60px"/></div>
    <div><label>Sheet name</label><input type="text" id="jsonSheetName" value="Sheet1" style="width:120px"/></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" id="jsonConvertBtn" onclick="jsonConvert()">Convert &amp; Preview</button>
    <span class="spinner" id="jsonSpinner"></span>
  </div>
  <div class="status" id="jsonStatus"></div>
  <div class="preview" id="jsonPreview" style="display:none">
    <button class="btn btn-green" onclick="jsonDownload()">Download .xlsx</button>
    <div class="sheet-tabs" id="sheetTabs"></div>
    <div class="preview-table-wrap"><table class="preview-table" id="previewTable"></table></div>
    <button class="btn btn-green" onclick="jsonDownload()">Download .xlsx</button>
  </div>
</div>

<!-- ═══════════════════ Markdown → DOCX ═══════════════════ -->
<div class="panel" id="panel-md-docx">
  <h2>Markdown &rarr; DOCX</h2>
  <div class="file-row">
    <input type="file" id="mdDocxFile" accept=".md,.markdown,.txt" onchange="loadFile(this,'mdDocxInput')"/>
    <label for="mdDocxFile" class="file-label">Attach .md</label>
    <span class="file-name" id="mdDocxFileName"></span>
  </div>
  <textarea id="mdDocxInput" placeholder="Paste Markdown here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" id="mdDocxConvertBtn" onclick="mdConvert('docx')">Convert &amp; Preview</button>
    <span class="spinner" id="mdDocxSpinner"></span>
  </div>
  <div class="status" id="mdDocxStatus"></div>
  <div class="preview" id="mdDocxPreview" style="display:none">
    <button class="btn btn-green" onclick="mdDownload('docx')">Download .docx</button>
    <div class="md-rendered" id="mdDocxRendered"></div>
    <button class="btn btn-green" onclick="mdDownload('docx')">Download .docx</button>
  </div>
</div>

<!-- ═══════════════════ Markdown → PDF ═══════════════════ -->
<div class="panel" id="panel-md-pdf">
  <h2>Markdown &rarr; PDF</h2>
  <div class="file-row">
    <input type="file" id="mdPdfFile" accept=".md,.markdown,.txt" onchange="loadFile(this,'mdPdfInput')"/>
    <label for="mdPdfFile" class="file-label">Attach .md</label>
    <span class="file-name" id="mdPdfFileName"></span>
  </div>
  <textarea id="mdPdfInput" placeholder="Paste Markdown here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" id="mdPdfConvertBtn" onclick="mdConvert('pdf')">Convert &amp; Preview</button>
    <span class="spinner" id="mdPdfSpinner"></span>
  </div>
  <div class="status" id="mdPdfStatus"></div>
  <div class="preview" id="mdPdfPreview" style="display:none">
    <button class="btn btn-green" onclick="mdDownload('pdf')">Download .pdf</button>
    <div class="md-rendered" id="mdPdfRendered"></div>
    <button class="btn btn-green" onclick="mdDownload('pdf')">Download .pdf</button>
  </div>
</div>

<!-- ═══════════════════ CSV → Excel ═══════════════════ -->
<div class="panel" id="panel-csv-excel">
  <h2>CSV &rarr; Excel</h2>
  <div class="file-row">
    <input type="file" id="csvExcelFile" accept=".csv,.tsv,.txt" onchange="loadFile(this,'csvExcelInput')"/>
    <label for="csvExcelFile" class="file-label">Attach .csv</label>
    <span class="file-name" id="csvExcelFileName"></span>
  </div>
  <textarea id="csvExcelInput" placeholder="Paste CSV data here..."></textarea>
  <div class="options-row">
    <div><label>Delimiter</label><select id="csvDelimiter"><option value="auto">Auto</option><option value=",">,</option><option value="&#9;">Tab</option><option value=";">;</option><option value="|">|</option></select></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="csvExcelConvert()">Convert &amp; Preview</button>
    <span class="spinner" id="csvExcelSpinner"></span>
  </div>
  <div class="status" id="csvExcelStatus"></div>
  <div class="preview" id="csvExcelPreview" style="display:none">
    <button class="btn btn-green" onclick="csvExcelDownload()">Download .xlsx</button>
    <div class="preview-table-wrap"><table class="preview-table" id="csvPreviewTable"></table></div>
    <button class="btn btn-green" onclick="csvExcelDownload()">Download .xlsx</button>
  </div>
</div>

<!-- ═══════════════════ YAML → JSON ═══════════════════ -->
<div class="panel" id="panel-yaml-json">
  <h2>YAML &rarr; JSON</h2>
  <div class="file-row">
    <input type="file" id="yamlFile" accept=".yaml,.yml,.txt" onchange="loadFile(this,'yamlInput')"/>
    <label for="yamlFile" class="file-label">Attach .yaml</label>
    <span class="file-name" id="yamlFileName"></span>
  </div>
  <textarea id="yamlInput" placeholder="Paste YAML here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="yamlConvert()">Convert</button>
    <span class="spinner" id="yamlSpinner"></span>
  </div>
  <div class="status" id="yamlStatus"></div>
  <div class="preview" id="yamlPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('yamlOutput')">Copy JSON</button>
    <pre class="output-box" id="yamlOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ HTML → Markdown ═══════════════════ -->
<div class="panel" id="panel-html-md">
  <h2>HTML &rarr; Markdown</h2>
  <div class="file-row">
    <input type="file" id="htmlMdFile" accept=".html,.htm,.txt" onchange="loadFile(this,'htmlMdInput')"/>
    <label for="htmlMdFile" class="file-label">Attach .html</label>
    <span class="file-name" id="htmlMdFileName"></span>
  </div>
  <textarea id="htmlMdInput" placeholder="Paste HTML here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="htmlMdConvert()">Convert</button>
    <span class="spinner" id="htmlMdSpinner"></span>
  </div>
  <div class="status" id="htmlMdStatus"></div>
  <div class="preview" id="htmlMdPreview" style="display:none">
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="copyText('htmlMdOutput')">Copy Markdown</button>
      <button class="btn btn-green" onclick="downloadText('htmlMdOutput','converted.md','text/markdown')">Download .md</button>
    </div>
    <pre class="output-box" id="htmlMdOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ PDF → Text ═══════════════════ -->
<div class="panel" id="panel-pdf-text">
  <h2>PDF &rarr; Text</h2>
  <div class="file-row">
    <input type="file" id="pdfFile" accept=".pdf"/>
    <label for="pdfFile" class="file-label">Choose PDF file</label>
    <span class="file-name" id="pdfFileName"></span>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="pdfExtract()">Extract Text</button>
    <span class="spinner" id="pdfSpinner"></span>
  </div>
  <div class="status" id="pdfStatus"></div>
  <div class="preview" id="pdfPreview" style="display:none">
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="copyText('pdfOutput')">Copy Text</button>
      <button class="btn btn-green" onclick="downloadText('pdfOutput','extracted.txt','text/plain')">Download .txt</button>
    </div>
    <pre class="output-box" id="pdfOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ XML → JSON ═══════════════════ -->
<div class="panel" id="panel-xml-json">
  <h2>XML &rarr; JSON</h2>
  <div class="file-row">
    <input type="file" id="xmlFile" accept=".xml,.txt" onchange="loadFile(this,'xmlInput')"/>
    <label for="xmlFile" class="file-label">Attach .xml</label>
    <span class="file-name" id="xmlFileName"></span>
  </div>
  <textarea id="xmlInput" placeholder="Paste XML here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="xmlConvert()">Convert to JSON</button>
    <button class="btn btn-green" onclick="xmlDownloadExcel()">Download as Excel</button>
    <span class="spinner" id="xmlSpinner"></span>
  </div>
  <div class="status" id="xmlStatus"></div>
  <div class="preview" id="xmlPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('xmlOutput')">Copy JSON</button>
    <pre class="output-box" id="xmlOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ SQL → CSV ═══════════════════ -->
<div class="panel" id="panel-sql-csv">
  <h2>SQL &rarr; CSV / Excel</h2>
  <div class="file-row">
    <input type="file" id="sqlFile" accept=".sql,.txt" onchange="loadFile(this,'sqlInput')"/>
    <label for="sqlFile" class="file-label">Attach .sql</label>
    <span class="file-name" id="sqlFileName"></span>
  </div>
  <textarea id="sqlInput" placeholder="Paste SQL (CREATE TABLE + INSERT INTO) here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="sqlConvert()">Parse &amp; Preview</button>
    <span class="spinner" id="sqlSpinner"></span>
  </div>
  <div class="status" id="sqlStatus"></div>
  <div class="preview" id="sqlPreview" style="display:none">
    <div class="btn-row">
      <button class="btn btn-green" onclick="sqlDownload('csv')">Download .csv</button>
      <button class="btn btn-green" onclick="sqlDownload('excel')">Download .xlsx</button>
    </div>
    <div class="preview-table-wrap"><table class="preview-table" id="sqlPreviewTable"></table></div>
  </div>
</div>

<!-- ═══════════════════ CSV → JSON ═══════════════════ -->
<div class="panel" id="panel-csv-json">
  <h2>CSV &rarr; JSON</h2>
  <div class="file-row">
    <input type="file" id="csvJsonFile" accept=".csv,.tsv,.txt" onchange="loadFile(this,'csvJsonInput')"/>
    <label for="csvJsonFile" class="file-label">Attach .csv</label>
    <span class="file-name" id="csvJsonFileName"></span>
  </div>
  <textarea id="csvJsonInput" placeholder="Paste CSV data here..."></textarea>
  <div class="options-row">
    <div><label>Delimiter</label><select id="csvJsonDelimiter"><option value="auto">Auto</option><option value=",">,</option><option value="&#9;">Tab</option><option value=";">;</option><option value="|">|</option></select></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="csvJsonConvert()">Convert</button>
    <span class="spinner" id="csvJsonSpinner"></span>
  </div>
  <div class="status" id="csvJsonStatus"></div>
  <div class="preview" id="csvJsonPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('csvJsonOutput')">Copy JSON</button>
    <pre class="output-box" id="csvJsonOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ SVG → PNG (Client-side) ═══════════════════ -->
<div class="panel" id="panel-svg-png">
  <h2>SVG &rarr; PNG</h2>
  <div class="file-row">
    <input type="file" id="svgFile" accept=".svg" onchange="loadFile(this,'svgInput')"/>
    <label for="svgFile" class="file-label">Attach .svg</label>
    <span class="file-name" id="svgFileName"></span>
  </div>
  <textarea id="svgInput" placeholder="Paste SVG markup here..."></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="svgConvert()">Convert to PNG</button>
  </div>
  <div class="status" id="svgStatus"></div>
  <div class="preview" id="svgPreview" style="display:none">
    <button class="btn btn-green" onclick="svgDownload()">Download .png</button>
    <br/><img class="img-preview" id="svgPreviewImg"/>
  </div>
</div>

<!-- ═══════════════════ Image Resizer ═══════════════════ -->
<div class="panel" id="panel-image-resize">
  <h2>Image Resizer / Compressor</h2>
  <div class="file-row">
    <input type="file" id="imageFile" accept="image/*"/>
    <label for="imageFile" class="file-label">Choose Image</label>
    <span class="file-name" id="imageFileName"></span>
  </div>
  <div class="options-row">
    <div><label>Width (px)</label><input type="number" id="imgWidth" placeholder="auto" style="width:100px"/></div>
    <div><label>Height (px)</label><input type="number" id="imgHeight" placeholder="auto" style="width:100px"/></div>
    <div><label>Quality</label><input type="number" id="imgQuality" value="85" min="1" max="100" style="width:80px"/></div>
    <div><label>Format</label><select id="imgFormat"><option value="JPEG">JPEG</option><option value="PNG">PNG</option><option value="WEBP">WebP</option></select></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="imageResize()">Resize</button>
    <span class="spinner" id="imageSpinner"></span>
  </div>
  <div class="status" id="imageStatus"></div>
  <div class="preview" id="imagePreview" style="display:none">
    <button class="btn btn-green" onclick="imageDownload()">Download</button>
    <br/><img class="img-preview" id="imagePreviewImg"/>
  </div>
</div>

<!-- ═══════════════════ Base64 ↔ Image ═══════════════════ -->
<div class="panel" id="panel-base64-image">
  <h2>Base64 &harr; Image</h2>
  <p style="font-size:0.85rem;color:#656d76;margin-bottom:12px">Encode an image to Base64, or decode Base64 to an image.</p>
  <div class="file-row">
    <input type="file" id="b64ImageFile" accept="image/*"/>
    <label for="b64ImageFile" class="file-label">Choose Image to Encode</label>
    <span class="file-name" id="b64ImageFileName"></span>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="b64Encode()">Encode to Base64</button>
    <span class="spinner" id="b64EncSpinner"></span>
  </div>
  <div class="status" id="b64EncStatus"></div>
  <div class="preview" id="b64EncPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('b64Output')">Copy Base64</button>
    <pre class="output-box" id="b64Output" style="max-height:200px"></pre>
  </div>
  <hr style="margin:24px 0;border:none;border-top:1px solid #d1d9e0"/>
  <textarea id="b64DecodeInput" placeholder="Paste Base64 / data URI here..." style="min-height:100px"></textarea>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="b64Decode()">Decode to Image</button>
    <span class="spinner" id="b64DecSpinner"></span>
  </div>
  <div class="status" id="b64DecStatus"></div>
  <div class="preview" id="b64DecPreview" style="display:none">
    <button class="btn btn-green" onclick="b64DecDownload()">Download Image</button>
    <br/><img class="img-preview" id="b64DecImg"/>
  </div>
</div>

<!-- ═══════════════════ JSON Formatter (Client-side) ═══════════════════ -->
<div class="panel" id="panel-json-format">
  <h2>JSON Formatter / Validator</h2>
  <textarea id="jsonFormatInput" placeholder="Paste JSON here..."></textarea>
  <div class="options-row">
    <div><label>Indent</label><select id="jsonIndent"><option value="2">2 spaces</option><option value="4">4 spaces</option></select></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="jsonFormat()">Format</button>
    <button class="btn btn-secondary" onclick="jsonMinify()">Minify</button>
  </div>
  <div class="status" id="jsonFormatStatus"></div>
  <div class="preview" id="jsonFormatPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('jsonFormatOutput')">Copy</button>
    <pre class="output-box" id="jsonFormatOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ TOML → JSON/YAML ═══════════════════ -->
<div class="panel" id="panel-toml-json">
  <h2>TOML &rarr; JSON / YAML</h2>
  <div class="file-row">
    <input type="file" id="tomlFile" accept=".toml,.txt" onchange="loadFile(this,'tomlInput')"/>
    <label for="tomlFile" class="file-label">Attach .toml</label>
    <span class="file-name" id="tomlFileName"></span>
  </div>
  <textarea id="tomlInput" placeholder="Paste TOML here..."></textarea>
  <div class="options-row">
    <div><label>Output</label><select id="tomlFormat"><option value="json">JSON</option><option value="yaml">YAML</option></select></div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="tomlConvert()">Convert</button>
    <span class="spinner" id="tomlSpinner"></span>
  </div>
  <div class="status" id="tomlStatus"></div>
  <div class="preview" id="tomlPreview" style="display:none">
    <button class="btn btn-secondary" onclick="copyText('tomlOutput')">Copy</button>
    <pre class="output-box" id="tomlOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ Cron Parser ═══════════════════ -->
<div class="panel" id="panel-cron-human">
  <h2>Cron Expression Parser</h2>
  <input type="text" id="cronInput" placeholder="e.g. */5 * * * *" style="max-width:400px"/>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="cronParse()">Parse</button>
    <span class="spinner" id="cronSpinner"></span>
  </div>
  <div class="status" id="cronStatus"></div>
  <div class="preview" id="cronPreview" style="display:none">
    <p><strong>Description:</strong> <span id="cronDesc"></span></p>
    <p style="margin-top:8px"><strong>Next 5 runs:</strong></p>
    <pre class="output-box" id="cronRuns"></pre>
  </div>
</div>

<!-- ═══════════════════ Unit Converter (Client-side) ═══════════════════ -->
<div class="panel" id="panel-unit">
  <h2>Unit Converter</h2>
  <div class="options-row">
    <div><label>Category</label><select id="unitCategory" onchange="unitUpdateSelects()">
      <option value="length">Length</option><option value="weight">Weight</option>
      <option value="temperature">Temperature</option><option value="volume">Volume</option>
      <option value="area">Area</option><option value="speed">Speed</option>
      <option value="data">Data</option>
    </select></div>
    <div><label>Value</label><input type="number" id="unitValue" value="1" style="width:120px" oninput="unitConvert()"/></div>
    <div><label>From</label><select id="unitFrom" onchange="unitConvert()"></select></div>
    <div><label>To</label><select id="unitTo" onchange="unitConvert()"></select></div>
  </div>
  <div style="font-size:1.4rem;margin-top:16px;font-weight:600" id="unitResult"></div>
</div>

<!-- ═══════════════════ Color Converter (Client-side) ═══════════════════ -->
<div class="panel" id="panel-color">
  <h2>Color Converter</h2>
  <div class="color-swatch" id="colorSwatch" style="background:#0969da"></div>
  <div class="color-inputs">
    <div><label>HEX</label><input type="text" id="colorHex" value="#0969da" oninput="colorFromHex()"/></div>
    <div><label>RGB</label><input type="text" id="colorRgb" value="9, 105, 218" oninput="colorFromRgb()"/></div>
    <div><label>HSL</label><input type="text" id="colorHsl" value="212, 92%, 45%" oninput="colorFromHsl()"/></div>
  </div>
</div>

<!-- ═══════════════════ Timestamp Tool ═══════════════════ -->
<div class="panel" id="panel-timestamp">
  <h2>Timestamp Converter</h2>
  <p style="font-size:0.85rem;color:#656d76;margin-bottom:12px">Current UTC: <strong id="tsNow"></strong></p>
  <input type="text" id="tsInput" placeholder="Unix timestamp, ISO date, or human-readable date..." style="max-width:500px"/>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="tsParse()">Convert</button>
    <button class="btn btn-secondary" onclick="tsNow()">Now</button>
    <span class="spinner" id="tsSpinner"></span>
  </div>
  <div class="status" id="tsStatus"></div>
  <div class="preview" id="tsPreview" style="display:none">
    <pre class="output-box" id="tsOutput"></pre>
  </div>
</div>

<!-- ═══════════════════ Time Zone Converter ═══════════════════ -->
<div class="panel" id="panel-timezone">
  <h2>Time Zone Converter</h2>
  <p style="font-size:0.85rem;color:#656d76;margin-bottom:16px">Convert time between any two cities worldwide.</p>
  <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:end;max-width:700px">
    <div>
      <label style="font-size:0.8rem;color:#656d76;display:block;margin-bottom:4px">From</label>
      <div style="position:relative">
        <input type="text" id="tzFromSearch" placeholder="Search city..." autocomplete="off" onfocus="tzOpenDropdown('from')" oninput="tzFilterCities('from')"/>
        <div class="tz-dropdown" id="tzFromDropdown"></div>
      </div>
      <input type="hidden" id="tzFromZone" value="America/New_York"/>
      <div style="font-size:0.78rem;color:#94a3b8;margin-top:2px" id="tzFromLabel">New York (UTC-5)</div>
    </div>
    <div style="text-align:center;padding-bottom:18px">
      <button class="btn btn-secondary" onclick="tzSwap()" style="padding:8px 12px;font-size:1rem" title="Swap">&harr;</button>
    </div>
    <div>
      <label style="font-size:0.8rem;color:#656d76;display:block;margin-bottom:4px">To</label>
      <div style="position:relative">
        <input type="text" id="tzToSearch" placeholder="Search city..." autocomplete="off" onfocus="tzOpenDropdown('to')" oninput="tzFilterCities('to')"/>
        <div class="tz-dropdown" id="tzToDropdown"></div>
      </div>
      <input type="hidden" id="tzToZone" value="Europe/London"/>
      <div style="font-size:0.78rem;color:#94a3b8;margin-top:2px" id="tzToLabel">London (UTC+0)</div>
    </div>
  </div>
  <div style="display:flex;gap:12px;align-items:end;margin:16px 0;flex-wrap:wrap">
    <div>
      <label style="font-size:0.8rem;color:#656d76;display:block;margin-bottom:4px">Date &amp; Time</label>
      <input type="datetime-local" id="tzDateTime" style="width:auto"/>
    </div>
    <button class="btn btn-secondary" onclick="tzSetNow()">Now</button>
    <button class="btn btn-primary" onclick="tzConvert()">Convert</button>
  </div>
  <div class="status" id="tzStatus"></div>
  <div class="preview" id="tzResult" style="display:none">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:700px">
      <div class="tz-card">
        <div class="tz-card-city" id="tzResultFromCity">New York</div>
        <div class="tz-card-time" id="tzResultFromTime">--:--</div>
        <div class="tz-card-date" id="tzResultFromDate">---</div>
        <div class="tz-card-zone" id="tzResultFromZone">EST (UTC-5)</div>
      </div>
      <div class="tz-card">
        <div class="tz-card-city" id="tzResultToCity">London</div>
        <div class="tz-card-time" id="tzResultToTime">--:--</div>
        <div class="tz-card-date" id="tzResultToDate">---</div>
        <div class="tz-card-zone" id="tzResultToZone">GMT (UTC+0)</div>
      </div>
    </div>
    <div style="margin-top:12px;font-size:0.85rem;color:#656d76" id="tzDiffText"></div>
  </div>
</div>

</section>
</main>

<footer>Ayo's Converter &mdash; 20 free converters, no signup required.</footer>

<script>
// ═══════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════
function esc(s) { const d = document.createElement("div"); d.textContent = String(s ?? ""); return d.innerHTML; }

function loadFile(input, textareaId) {
  if (!input.files[0]) return;
  const file = input.files[0];
  const nameEl = input.parentElement.querySelector(".file-name");
  if (nameEl) nameEl.textContent = file.name;
  const reader = new FileReader();
  reader.onload = () => { document.getElementById(textareaId).value = reader.result; };
  reader.readAsText(file);
}

function copyText(elId) {
  const text = document.getElementById(elId).textContent;
  navigator.clipboard.writeText(text);
}

function downloadText(elId, filename, mime) {
  const text = document.getElementById(elId).textContent;
  const blob = new Blob([text], { type: mime });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename; a.click(); URL.revokeObjectURL(a.href);
}

function downloadBlob(blob, filename) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename; a.click(); URL.revokeObjectURL(a.href);
}

function setStatus(id, msg, type) { const el = document.getElementById(id); el.textContent = msg; el.className = "status " + type; }
function showSpin(id, on) { document.getElementById(id).style.display = on ? "inline-block" : "none"; }

// ═══════════════════════════════════════════════════════════════
// Navigation
// ═══════════════════════════════════════════════════════════════
function switchConverter(id) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".sidebar-item").forEach(s => s.classList.remove("active"));
  const panel = document.getElementById("panel-" + id);
  if (panel) panel.classList.add("active");
  document.querySelectorAll(".sidebar-item").forEach(s => {
    if (s.getAttribute("onclick") && s.getAttribute("onclick").includes("'" + id + "'")) s.classList.add("active");
  });
  document.querySelector(".mobile-select").value = id;
  if (location.pathname !== "/" + id) history.pushState(null, "", "/" + id);
}

// ═══════════════════════════════════════════════════════════════
// JSON → Excel
// ═══════════════════════════════════════════════════════════════
let _sheets = [], _active = 0;

async function jsonConvert() {
  const raw = document.getElementById("jsonInput").value.trim();
  if (!raw) { setStatus("jsonStatus","Paste or attach JSON first.","err"); return; }
  setStatus("jsonStatus","Converting...","info"); showSpin("jsonSpinner",true);
  try {
    const body = { json: raw, flatten: document.getElementById("jsonFlatten").value==="1",
      sep: document.getElementById("jsonSep").value, sheet_name: document.getElementById("jsonSheetName").value,
      strip_prefix: document.getElementById("jsonStripPrefix").value==="1" };
    const res = await fetch("/json/preview", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    _sheets = data.sheets; _active = 0;
    renderSheetTabs(); renderSheetTable(0);
    document.getElementById("jsonPreview").style.display = "block";
    setStatus("jsonStatus",`${_sheets.length} sheet(s), ${_sheets.reduce((a,s)=>a+s.rows.length,0)} rows`,"ok");
  } catch(e) { setStatus("jsonStatus",e.message,"err"); }
  showSpin("jsonSpinner",false);
}

function renderSheetTabs() {
  document.getElementById("sheetTabs").innerHTML = _sheets.map((s,i) =>
    `<div class="sheet-tab${i===_active?" active":""}" onclick="switchSheetTab(${i})">${esc(s.name)}</div>`).join("");
}
function switchSheetTab(i) { _active = i; renderSheetTabs(); renderSheetTable(i); }
function renderSheetTable(i) {
  const s = _sheets[i]; if (!s) return;
  const hdr = s.columns.map(c=>`<th>${esc(c)}</th>`).join("");
  const rows = s.rows.slice(0,100).map(r=>"<tr>"+s.columns.map(c=>`<td>${esc(r[c])}</td>`).join("")+"</tr>").join("");
  document.getElementById("previewTable").innerHTML = `<thead><tr>${hdr}</tr></thead><tbody>${rows}</tbody>`;
}

async function jsonDownload() {
  const raw = document.getElementById("jsonInput").value.trim(); if (!raw) return;
  const body = { json: raw, flatten: document.getElementById("jsonFlatten").value==="1",
    sep: document.getElementById("jsonSep").value, sheet_name: document.getElementById("jsonSheetName").value,
    strip_prefix: document.getElementById("jsonStripPrefix").value==="1" };
  const res = await fetch("/json/download", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
  if (!res.ok) { setStatus("jsonStatus","Download failed","err"); return; }
  downloadBlob(await res.blob(), "converted.xlsx");
}

// ═══════════════════════════════════════════════════════════════
// Markdown → DOCX / PDF
// ═══════════════════════════════════════════════════════════════
function cap(s) { return s.charAt(0).toUpperCase()+s.slice(1); }

async function mdConvert(fmt) {
  const id = fmt==="docx"?"mdDocx":"mdPdf";
  const raw = document.getElementById(id+"Input").value.trim();
  if (!raw) { setStatus(id+"Status","Paste Markdown first.","err"); return; }
  setStatus(id+"Status","Converting...","info"); showSpin(id+"Spinner",true);
  try {
    const res = await fetch("/md/preview", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({markdown:raw}) });
    if (!res.ok) throw new Error("Server error");
    const data = await res.json();
    document.getElementById(id+"Rendered").innerHTML = data.html;
    document.getElementById(id+"Preview").style.display = "block";
    setStatus(id+"Status","Preview ready","ok");
  } catch(e) { setStatus(id+"Status",e.message,"err"); }
  showSpin(id+"Spinner",false);
}

async function mdDownload(fmt) {
  const id = fmt==="docx"?"mdDocx":"mdPdf";
  const raw = document.getElementById(id+"Input").value.trim(); if (!raw) return;
  const res = await fetch("/md/download/"+fmt, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({markdown:raw}) });
  if (!res.ok) { setStatus(id+"Status","Download failed","err"); return; }
  downloadBlob(await res.blob(), "converted."+(fmt==="docx"?"docx":"pdf"));
}

// ═══════════════════════════════════════════════════════════════
// CSV → Excel
// ═══════════════════════════════════════════════════════════════
async function csvExcelConvert() {
  const raw = document.getElementById("csvExcelInput").value.trim();
  if (!raw) { setStatus("csvExcelStatus","Paste CSV first.","err"); return; }
  setStatus("csvExcelStatus","Converting...","info"); showSpin("csvExcelSpinner",true);
  try {
    const res = await fetch("/csv/preview", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({csv: raw, delimiter: document.getElementById("csvDelimiter").value}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    const hdr = data.columns.map(c=>`<th>${esc(c)}</th>`).join("");
    const rows = data.rows.slice(0,100).map(r=>"<tr>"+data.columns.map(c=>`<td>${esc(r[c])}</td>`).join("")+"</tr>").join("");
    document.getElementById("csvPreviewTable").innerHTML = `<thead><tr>${hdr}</tr></thead><tbody>${rows}</tbody>`;
    document.getElementById("csvExcelPreview").style.display = "block";
    setStatus("csvExcelStatus",`${data.rows.length} rows`,"ok");
  } catch(e) { setStatus("csvExcelStatus",e.message,"err"); }
  showSpin("csvExcelSpinner",false);
}

async function csvExcelDownload() {
  const raw = document.getElementById("csvExcelInput").value.trim(); if (!raw) return;
  const res = await fetch("/csv/download/excel", { method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({csv: raw, delimiter: document.getElementById("csvDelimiter").value}) });
  if (!res.ok) { setStatus("csvExcelStatus","Download failed","err"); return; }
  downloadBlob(await res.blob(), "converted.xlsx");
}

// ═══════════════════════════════════════════════════════════════
// YAML → JSON
// ═══════════════════════════════════════════════════════════════
async function yamlConvert() {
  const raw = document.getElementById("yamlInput").value.trim();
  if (!raw) { setStatus("yamlStatus","Paste YAML first.","err"); return; }
  setStatus("yamlStatus","Converting...","info"); showSpin("yamlSpinner",true);
  try {
    const res = await fetch("/yaml/convert", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({yaml:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    document.getElementById("yamlOutput").textContent = data.json;
    document.getElementById("yamlPreview").style.display = "block";
    setStatus("yamlStatus","Converted","ok");
  } catch(e) { setStatus("yamlStatus",e.message,"err"); }
  showSpin("yamlSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// HTML → Markdown
// ═══════════════════════════════════════════════════════════════
async function htmlMdConvert() {
  const raw = document.getElementById("htmlMdInput").value.trim();
  if (!raw) { setStatus("htmlMdStatus","Paste HTML first.","err"); return; }
  setStatus("htmlMdStatus","Converting...","info"); showSpin("htmlMdSpinner",true);
  try {
    const res = await fetch("/html/convert", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({html:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    document.getElementById("htmlMdOutput").textContent = data.markdown;
    document.getElementById("htmlMdPreview").style.display = "block";
    setStatus("htmlMdStatus","Converted","ok");
  } catch(e) { setStatus("htmlMdStatus",e.message,"err"); }
  showSpin("htmlMdSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// PDF → Text
// ═══════════════════════════════════════════════════════════════
async function pdfExtract() {
  const fileInput = document.getElementById("pdfFile");
  if (!fileInput.files[0]) { setStatus("pdfStatus","Choose a PDF first.","err"); return; }
  document.getElementById("pdfFileName").textContent = fileInput.files[0].name;
  setStatus("pdfStatus","Extracting...","info"); showSpin("pdfSpinner",true);
  try {
    const fd = new FormData(); fd.append("file", fileInput.files[0]);
    const res = await fetch("/pdf/extract", { method:"POST", body: fd });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    document.getElementById("pdfOutput").textContent = data.text;
    document.getElementById("pdfPreview").style.display = "block";
    setStatus("pdfStatus","Extracted","ok");
  } catch(e) { setStatus("pdfStatus",e.message,"err"); }
  showSpin("pdfSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// XML → JSON
// ═══════════════════════════════════════════════════════════════
async function xmlConvert() {
  const raw = document.getElementById("xmlInput").value.trim();
  if (!raw) { setStatus("xmlStatus","Paste XML first.","err"); return; }
  setStatus("xmlStatus","Converting...","info"); showSpin("xmlSpinner",true);
  try {
    const res = await fetch("/xml/convert", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({xml:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    document.getElementById("xmlOutput").textContent = data.json;
    document.getElementById("xmlPreview").style.display = "block";
    setStatus("xmlStatus","Converted","ok");
  } catch(e) { setStatus("xmlStatus",e.message,"err"); }
  showSpin("xmlSpinner",false);
}

async function xmlDownloadExcel() {
  const raw = document.getElementById("xmlInput").value.trim();
  if (!raw) { setStatus("xmlStatus","Paste XML first.","err"); return; }
  const res = await fetch("/xml/download/excel", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({xml:raw}) });
  if (!res.ok) { setStatus("xmlStatus","Download failed","err"); return; }
  downloadBlob(await res.blob(), "converted.xlsx");
}

// ═══════════════════════════════════════════════════════════════
// SQL → CSV / Excel
// ═══════════════════════════════════════════════════════════════
let _sqlData = null;
async function sqlConvert() {
  const raw = document.getElementById("sqlInput").value.trim();
  if (!raw) { setStatus("sqlStatus","Paste SQL first.","err"); return; }
  setStatus("sqlStatus","Parsing...","info"); showSpin("sqlSpinner",true);
  try {
    const res = await fetch("/sql/preview", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({sql:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    _sqlData = await res.json();
    const tables = _sqlData.tables;
    const name = Object.keys(tables)[0];
    if (!name) throw new Error("No tables found");
    const t = tables[name];
    const hdr = t.columns.map(c=>`<th>${esc(c)}</th>`).join("");
    const rows = t.rows.slice(0,100).map(r=>"<tr>"+r.map(v=>`<td>${esc(v)}</td>`).join("")+"</tr>").join("");
    document.getElementById("sqlPreviewTable").innerHTML = `<thead><tr>${hdr}</tr></thead><tbody>${rows}</tbody>`;
    document.getElementById("sqlPreview").style.display = "block";
    setStatus("sqlStatus",`Table "${name}": ${t.rows.length} rows`,"ok");
  } catch(e) { setStatus("sqlStatus",e.message,"err"); }
  showSpin("sqlSpinner",false);
}

async function sqlDownload(fmt) {
  const raw = document.getElementById("sqlInput").value.trim(); if (!raw) return;
  const res = await fetch("/sql/download/"+ fmt, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({sql:raw}) });
  if (!res.ok) { setStatus("sqlStatus","Download failed","err"); return; }
  const ext = fmt === "csv" ? "csv" : "xlsx";
  downloadBlob(await res.blob(), "converted." + ext);
}

// ═══════════════════════════════════════════════════════════════
// CSV → JSON
// ═══════════════════════════════════════════════════════════════
async function csvJsonConvert() {
  const raw = document.getElementById("csvJsonInput").value.trim();
  if (!raw) { setStatus("csvJsonStatus","Paste CSV first.","err"); return; }
  setStatus("csvJsonStatus","Converting...","info"); showSpin("csvJsonSpinner",true);
  try {
    const res = await fetch("/csv/to-json", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({csv: raw, delimiter: document.getElementById("csvJsonDelimiter").value}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    const data = await res.json();
    document.getElementById("csvJsonOutput").textContent = data.json;
    document.getElementById("csvJsonPreview").style.display = "block";
    setStatus("csvJsonStatus","Converted","ok");
  } catch(e) { setStatus("csvJsonStatus",e.message,"err"); }
  showSpin("csvJsonSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// SVG → PNG (Client-side)
// ═══════════════════════════════════════════════════════════════
let _svgBlob = null;
function svgConvert() {
  const svg = document.getElementById("svgInput").value.trim();
  if (!svg) { setStatus("svgStatus","Paste SVG first.","err"); return; }
  setStatus("svgStatus","Converting...","info");
  const blob = new Blob([svg], {type:"image/svg+xml;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = function() {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth || 800; c.height = img.naturalHeight || 600;
    c.getContext("2d").drawImage(img, 0, 0);
    c.toBlob(function(pngBlob) {
      _svgBlob = pngBlob;
      document.getElementById("svgPreviewImg").src = URL.createObjectURL(pngBlob);
      document.getElementById("svgPreview").style.display = "block";
      setStatus("svgStatus",`Converted (${c.width}x${c.height})`,"ok");
    }, "image/png");
    URL.revokeObjectURL(url);
  };
  img.onerror = function() { setStatus("svgStatus","Invalid SVG","err"); URL.revokeObjectURL(url); };
  img.src = url;
}
function svgDownload() { if (_svgBlob) downloadBlob(_svgBlob, "converted.png"); }

// ═══════════════════════════════════════════════════════════════
// Image Resizer
// ═══════════════════════════════════════════════════════════════
let _resizedBlob = null;
async function imageResize() {
  const fileInput = document.getElementById("imageFile");
  if (!fileInput.files[0]) { setStatus("imageStatus","Choose an image.","err"); return; }
  document.getElementById("imageFileName").textContent = fileInput.files[0].name;
  setStatus("imageStatus","Resizing...","info"); showSpin("imageSpinner",true);
  try {
    const fd = new FormData(); fd.append("file", fileInput.files[0]);
    const w = document.getElementById("imgWidth").value; if (w) fd.append("width", w);
    const h = document.getElementById("imgHeight").value; if (h) fd.append("height", h);
    fd.append("quality", document.getElementById("imgQuality").value);
    fd.append("format", document.getElementById("imgFormat").value);
    const res = await fetch("/image/resize", { method:"POST", body: fd });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Server error"); }
    _resizedBlob = await res.blob();
    document.getElementById("imagePreviewImg").src = URL.createObjectURL(_resizedBlob);
    document.getElementById("imagePreview").style.display = "block";
    setStatus("imageStatus",`Done (${(_resizedBlob.size/1024).toFixed(1)} KB)`,"ok");
  } catch(e) { setStatus("imageStatus",e.message,"err"); }
  showSpin("imageSpinner",false);
}
function imageDownload() {
  if (!_resizedBlob) return;
  const fmt = document.getElementById("imgFormat").value.toLowerCase();
  downloadBlob(_resizedBlob, "resized." + (fmt==="jpeg"?"jpg":fmt));
}

// ═══════════════════════════════════════════════════════════════
// Base64 ↔ Image
// ═══════════════════════════════════════════════════════════════
async function b64Encode() {
  const fileInput = document.getElementById("b64ImageFile");
  if (!fileInput.files[0]) { setStatus("b64EncStatus","Choose an image.","err"); return; }
  document.getElementById("b64ImageFileName").textContent = fileInput.files[0].name;
  setStatus("b64EncStatus","Encoding...","info"); showSpin("b64EncSpinner",true);
  try {
    const fd = new FormData(); fd.append("file", fileInput.files[0]);
    const res = await fetch("/base64/encode", { method:"POST", body: fd });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Error"); }
    const data = await res.json();
    document.getElementById("b64Output").textContent = data.base64;
    document.getElementById("b64EncPreview").style.display = "block";
    setStatus("b64EncStatus","Encoded","ok");
  } catch(e) { setStatus("b64EncStatus",e.message,"err"); }
  showSpin("b64EncSpinner",false);
}

let _b64DecBlob = null;
async function b64Decode() {
  const raw = document.getElementById("b64DecodeInput").value.trim();
  if (!raw) { setStatus("b64DecStatus","Paste Base64 first.","err"); return; }
  setStatus("b64DecStatus","Decoding...","info"); showSpin("b64DecSpinner",true);
  try {
    const res = await fetch("/base64/decode", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({data:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Error"); }
    _b64DecBlob = await res.blob();
    document.getElementById("b64DecImg").src = URL.createObjectURL(_b64DecBlob);
    document.getElementById("b64DecPreview").style.display = "block";
    setStatus("b64DecStatus","Decoded","ok");
  } catch(e) { setStatus("b64DecStatus",e.message,"err"); }
  showSpin("b64DecSpinner",false);
}
function b64DecDownload() { if (_b64DecBlob) downloadBlob(_b64DecBlob, "decoded.png"); }

// ═══════════════════════════════════════════════════════════════
// JSON Formatter (Client-side)
// ═══════════════════════════════════════════════════════════════
function jsonFormat() {
  const raw = document.getElementById("jsonFormatInput").value.trim();
  if (!raw) { setStatus("jsonFormatStatus","Paste JSON first.","err"); return; }
  try {
    const parsed = JSON.parse(raw);
    const indent = parseInt(document.getElementById("jsonIndent").value)||2;
    document.getElementById("jsonFormatOutput").textContent = JSON.stringify(parsed, null, indent);
    document.getElementById("jsonFormatPreview").style.display = "block";
    setStatus("jsonFormatStatus","Valid JSON","ok");
  } catch(e) { setStatus("jsonFormatStatus","Invalid JSON: "+e.message,"err"); document.getElementById("jsonFormatPreview").style.display="none"; }
}
function jsonMinify() {
  const raw = document.getElementById("jsonFormatInput").value.trim();
  if (!raw) return;
  try {
    document.getElementById("jsonFormatOutput").textContent = JSON.stringify(JSON.parse(raw));
    document.getElementById("jsonFormatPreview").style.display = "block";
    setStatus("jsonFormatStatus","Minified","ok");
  } catch(e) { setStatus("jsonFormatStatus","Invalid JSON: "+e.message,"err"); }
}

// ═══════════════════════════════════════════════════════════════
// TOML → JSON/YAML
// ═══════════════════════════════════════════════════════════════
async function tomlConvert() {
  const raw = document.getElementById("tomlInput").value.trim();
  if (!raw) { setStatus("tomlStatus","Paste TOML first.","err"); return; }
  setStatus("tomlStatus","Converting...","info"); showSpin("tomlSpinner",true);
  try {
    const fmt = document.getElementById("tomlFormat").value;
    const res = await fetch("/toml/convert", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({toml:raw,format:fmt}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Error"); }
    const data = await res.json();
    document.getElementById("tomlOutput").textContent = data.result;
    document.getElementById("tomlPreview").style.display = "block";
    setStatus("tomlStatus","Converted to "+fmt.toUpperCase(),"ok");
  } catch(e) { setStatus("tomlStatus",e.message,"err"); }
  showSpin("tomlSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// Cron Parser
// ═══════════════════════════════════════════════════════════════
async function cronParse() {
  const raw = document.getElementById("cronInput").value.trim();
  if (!raw) { setStatus("cronStatus","Enter a cron expression.","err"); return; }
  setStatus("cronStatus","Parsing...","info"); showSpin("cronSpinner",true);
  try {
    const res = await fetch("/cron/parse", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({cron:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Error"); }
    const data = await res.json();
    document.getElementById("cronDesc").textContent = data.description;
    document.getElementById("cronRuns").textContent = data.next_runs.join("\n");
    document.getElementById("cronPreview").style.display = "block";
    setStatus("cronStatus","Parsed","ok");
  } catch(e) { setStatus("cronStatus",e.message,"err"); }
  showSpin("cronSpinner",false);
}

// ═══════════════════════════════════════════════════════════════
// Unit Converter (Client-side)
// ═══════════════════════════════════════════════════════════════
const UNITS = {
  length: {m:1, km:1000, cm:0.01, mm:0.001, "in":0.0254, ft:0.3048, yd:0.9144, mi:1609.344},
  weight: {kg:1, g:0.001, mg:1e-6, lb:0.453592, oz:0.0283495, t:1000},
  temperature: {C:"C", F:"F", K:"K"},
  volume: {L:1, mL:0.001, gal:3.78541, qt:0.946353, cup:0.236588, "fl oz":0.0295735},
  area: {"m2":1, "km2":1e6, "cm2":1e-4, "ft2":0.092903, "ac":4046.86, "ha":10000},
  speed: {"m/s":1, "km/h":0.277778, "mph":0.44704, "kn":0.514444},
  data: {B:1, KB:1024, MB:1048576, GB:1073741824, TB:1099511627776}
};
function unitUpdateSelects() {
  const cat = document.getElementById("unitCategory").value;
  const keys = Object.keys(UNITS[cat]);
  const opts = keys.map(k=>`<option value="${k}">${k}</option>`).join("");
  document.getElementById("unitFrom").innerHTML = opts;
  document.getElementById("unitTo").innerHTML = opts;
  if (keys.length>1) document.getElementById("unitTo").selectedIndex = 1;
  unitConvert();
}
function unitConvert() {
  const cat = document.getElementById("unitCategory").value;
  const val = parseFloat(document.getElementById("unitValue").value)||0;
  const from = document.getElementById("unitFrom").value;
  const to = document.getElementById("unitTo").value;
  let result;
  if (cat==="temperature") {
    let c;
    if (from==="C") c=val; else if (from==="F") c=(val-32)*5/9; else c=val-273.15;
    if (to==="C") result=c; else if (to==="F") result=c*9/5+32; else result=c+273.15;
  } else {
    result = val * UNITS[cat][from] / UNITS[cat][to];
  }
  document.getElementById("unitResult").textContent = `${val} ${from} = ${parseFloat(result.toPrecision(10))} ${to}`;
}

// ═══════════════════════════════════════════════════════════════
// Color Converter (Client-side)
// ═══════════════════════════════════════════════════════════════
function colorFromHex() {
  const hex = document.getElementById("colorHex").value.trim().replace("#","");
  if (hex.length!==6 && hex.length!==3) return;
  const full = hex.length===3 ? hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2] : hex;
  const r=parseInt(full.substr(0,2),16), g=parseInt(full.substr(2,2),16), b=parseInt(full.substr(4,2),16);
  if (isNaN(r)||isNaN(g)||isNaN(b)) return;
  updateColor(r,g,b,"hex");
}
function colorFromRgb() {
  const parts = document.getElementById("colorRgb").value.split(",").map(s=>parseInt(s.trim()));
  if (parts.length!==3 || parts.some(isNaN)) return;
  updateColor(parts[0],parts[1],parts[2],"rgb");
}
function colorFromHsl() {
  const raw = document.getElementById("colorHsl").value.replace(/%/g,"");
  const parts = raw.split(",").map(s=>parseFloat(s.trim()));
  if (parts.length!==3 || parts.some(isNaN)) return;
  const [r,g,b] = hslToRgb(parts[0]/360, parts[1]/100, parts[2]/100);
  updateColor(r,g,b,"hsl");
}
function updateColor(r,g,b,src) {
  const hex = "#"+[r,g,b].map(v=>v.toString(16).padStart(2,"0")).join("");
  const [h,s,l] = rgbToHsl(r,g,b);
  document.getElementById("colorSwatch").style.background = hex;
  if (src!=="hex") document.getElementById("colorHex").value = hex;
  if (src!=="rgb") document.getElementById("colorRgb").value = `${r}, ${g}, ${b}`;
  if (src!=="hsl") document.getElementById("colorHsl").value = `${Math.round(h*360)}, ${Math.round(s*100)}%, ${Math.round(l*100)}%`;
}
function rgbToHsl(r,g,b) { r/=255;g/=255;b/=255; const mx=Math.max(r,g,b),mn=Math.min(r,g,b); let h,s,l=(mx+mn)/2;
  if(mx===mn){h=s=0}else{const d=mx-mn;s=l>0.5?d/(2-mx-mn):d/(mx+mn);
  if(mx===r)h=((g-b)/d+(g<b?6:0))/6;else if(mx===g)h=((b-r)/d+2)/6;else h=((r-g)/d+4)/6;} return [h,s,l]; }
function hslToRgb(h,s,l) { if(s===0) { const v=Math.round(l*255); return [v,v,v]; }
  function hue2rgb(p,q,t){if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;}
  const q=l<0.5?l*(1+s):l+s-l*s, p=2*l-q;
  return [Math.round(hue2rgb(p,q,h+1/3)*255), Math.round(hue2rgb(p,q,h)*255), Math.round(hue2rgb(p,q,h-1/3)*255)]; }

// ═══════════════════════════════════════════════════════════════
// Timestamp Tool
// ═══════════════════════════════════════════════════════════════
async function tsParse() {
  const raw = document.getElementById("tsInput").value.trim();
  if (!raw) { setStatus("tsStatus","Enter a timestamp.","err"); return; }
  setStatus("tsStatus","Converting...","info"); showSpin("tsSpinner",true);
  try {
    const res = await fetch("/timestamp/parse", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({input:raw}) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error||"Error"); }
    const data = await res.json();
    document.getElementById("tsOutput").textContent = Object.entries(data).map(([k,v])=>`${k}: ${v}`).join("\n");
    document.getElementById("tsPreview").style.display = "block";
    setStatus("tsStatus","Converted","ok");
  } catch(e) { setStatus("tsStatus",e.message,"err"); }
  showSpin("tsSpinner",false);
}
function tsNow() { document.getElementById("tsInput").value = Math.floor(Date.now()/1000); tsParse(); }
setInterval(()=>{ const el=document.getElementById("tsNow"); if(el) el.textContent=new Date().toISOString(); }, 1000);

// ═══════════════════════════════════════════════════════════════
// Time Zone Converter (client-side)
// ═══════════════════════════════════════════════════════════════
const TZ_CITIES = [
  {region:"Africa",cities:[["Abidjan","Africa/Abidjan"],["Accra","Africa/Accra"],["Addis Ababa","Africa/Addis_Ababa"],["Algiers","Africa/Algiers"],["Cairo","Africa/Cairo"],["Cape Town","Africa/Johannesburg"],["Casablanca","Africa/Casablanca"],["Dar es Salaam","Africa/Dar_es_Salaam"],["Johannesburg","Africa/Johannesburg"],["Kampala","Africa/Kampala"],["Khartoum","Africa/Khartoum"],["Kigali","Africa/Kigali"],["Kinshasa","Africa/Kinshasa"],["Lagos","Africa/Lagos"],["Luanda","Africa/Luanda"],["Maputo","Africa/Maputo"],["Nairobi","Africa/Nairobi"],["Tunis","Africa/Tunis"],["Windhoek","Africa/Windhoek"]]},
  {region:"Americas",cities:[["Anchorage","America/Anchorage"],["Bogota","America/Bogota"],["Buenos Aires","America/Argentina/Buenos_Aires"],["Caracas","America/Caracas"],["Chicago","America/Chicago"],["Dallas","America/Chicago"],["Denver","America/Denver"],["Edmonton","America/Edmonton"],["Halifax","America/Halifax"],["Havana","America/Havana"],["Honolulu","Pacific/Honolulu"],["Lima","America/Lima"],["Los Angeles","America/Los_Angeles"],["Mexico City","America/Mexico_City"],["Montreal","America/Toronto"],["New York","America/New_York"],["Ottawa","America/Toronto"],["Panama City","America/Panama"],["Phoenix","America/Phoenix"],["San Francisco","America/Los_Angeles"],["Santiago","America/Santiago"],["Sao Paulo","America/Sao_Paulo"],["Seattle","America/Los_Angeles"],["St. John's","America/St_Johns"],["Toronto","America/Toronto"],["Vancouver","America/Vancouver"],["Winnipeg","America/Winnipeg"]]},
  {region:"Asia",cities:[["Almaty","Asia/Almaty"],["Baghdad","Asia/Baghdad"],["Bangkok","Asia/Bangkok"],["Beijing","Asia/Shanghai"],["Colombo","Asia/Colombo"],["Dhaka","Asia/Dhaka"],["Dubai","Asia/Dubai"],["Hanoi","Asia/Ho_Chi_Minh"],["Ho Chi Minh","Asia/Ho_Chi_Minh"],["Hong Kong","Asia/Hong_Kong"],["Istanbul","Europe/Istanbul"],["Jakarta","Asia/Jakarta"],["Jerusalem","Asia/Jerusalem"],["Kabul","Asia/Kabul"],["Karachi","Asia/Karachi"],["Kathmandu","Asia/Kathmandu"],["Kolkata","Asia/Kolkata"],["Kuala Lumpur","Asia/Kuala_Lumpur"],["Kuwait City","Asia/Kuwait"],["Manila","Asia/Manila"],["Mumbai","Asia/Kolkata"],["Muscat","Asia/Muscat"],["Novosibirsk","Asia/Novosibirsk"],["Riyadh","Asia/Riyadh"],["Seoul","Asia/Seoul"],["Shanghai","Asia/Shanghai"],["Singapore","Asia/Singapore"],["Taipei","Asia/Taipei"],["Tashkent","Asia/Tashkent"],["Tehran","Asia/Tehran"],["Tokyo","Asia/Tokyo"],["Vladivostok","Asia/Vladivostok"],["Yangon","Asia/Yangon"]]},
  {region:"Europe",cities:[["Amsterdam","Europe/Amsterdam"],["Athens","Europe/Athens"],["Barcelona","Europe/Madrid"],["Belgrade","Europe/Belgrade"],["Berlin","Europe/Berlin"],["Brussels","Europe/Brussels"],["Bucharest","Europe/Bucharest"],["Budapest","Europe/Budapest"],["Copenhagen","Europe/Copenhagen"],["Dublin","Europe/Dublin"],["Edinburgh","Europe/London"],["Helsinki","Europe/Helsinki"],["Kyiv","Europe/Kyiv"],["Lisbon","Europe/Lisbon"],["London","Europe/London"],["Madrid","Europe/Madrid"],["Milan","Europe/Rome"],["Minsk","Europe/Minsk"],["Moscow","Europe/Moscow"],["Munich","Europe/Berlin"],["Oslo","Europe/Oslo"],["Paris","Europe/Paris"],["Prague","Europe/Prague"],["Reykjavik","Atlantic/Reykjavik"],["Riga","Europe/Riga"],["Rome","Europe/Rome"],["Sofia","Europe/Sofia"],["Stockholm","Europe/Stockholm"],["Tallinn","Europe/Tallinn"],["Vienna","Europe/Vienna"],["Vilnius","Europe/Vilnius"],["Warsaw","Europe/Warsaw"],["Zurich","Europe/Zurich"]]},
  {region:"Oceania",cities:[["Adelaide","Australia/Adelaide"],["Auckland","Pacific/Auckland"],["Brisbane","Australia/Brisbane"],["Chatham Islands","Pacific/Chatham"],["Darwin","Australia/Darwin"],["Fiji","Pacific/Fiji"],["Guam","Pacific/Guam"],["Hobart","Australia/Hobart"],["Melbourne","Australia/Melbourne"],["Perth","Australia/Perth"],["Samoa","Pacific/Apia"],["Sydney","Australia/Sydney"],["Tonga","Pacific/Tongatapu"]]}
];

function _tzOffset(iana) {
  try {
    const now = new Date();
    const parts = new Intl.DateTimeFormat("en-US",{timeZone:iana,timeZoneName:"shortOffset"}).formatToParts(now);
    const off = parts.find(p=>p.type==="timeZoneName");
    return off ? off.value.replace("GMT","UTC") : "";
  } catch { return ""; }
}

function _tzBuildDropdown(target) {
  const el = document.getElementById(target==="from"?"tzFromDropdown":"tzToDropdown");
  let html = "";
  TZ_CITIES.forEach(g=>{
    html += `<div class="tz-dropdown-group">${esc(g.region)}</div>`;
    g.cities.forEach(([name,iana])=>{
      const off = _tzOffset(iana);
      html += `<div class="tz-dropdown-item" data-iana="${esc(iana)}" data-name="${esc(name)}" onclick="tzSelect('${target}','${iana}','${name.replace(/'/g,"\\'")}')"><span>${esc(name)}</span><span class="tz-offset">${esc(off)}</span></div>`;
    });
  });
  el.innerHTML = html;
}

function tzOpenDropdown(target) {
  document.querySelectorAll(".tz-dropdown").forEach(d=>d.classList.remove("open"));
  const dd = document.getElementById(target==="from"?"tzFromDropdown":"tzToDropdown");
  if (!dd.innerHTML) _tzBuildDropdown(target);
  dd.classList.add("open");
}

function tzFilterCities(target) {
  const dd = document.getElementById(target==="from"?"tzFromDropdown":"tzToDropdown");
  const q = document.getElementById(target==="from"?"tzFromSearch":"tzToSearch").value.toLowerCase();
  // Clear selection when user edits the text — forces re-selection from dropdown
  document.getElementById(target==="from"?"tzFromZone":"tzToZone").value = "";
  document.getElementById(target==="from"?"tzFromLabel":"tzToLabel").textContent = "";
  if (!dd.innerHTML) _tzBuildDropdown(target);
  dd.querySelectorAll(".tz-dropdown-item").forEach(item=>{
    const match = item.dataset.name.toLowerCase().includes(q) || item.dataset.iana.toLowerCase().includes(q);
    item.style.display = match ? "" : "none";
  });
  dd.querySelectorAll(".tz-dropdown-group").forEach(g=>{
    let next = g.nextElementSibling, vis = false;
    while(next && !next.classList.contains("tz-dropdown-group")) {
      if (next.style.display !== "none") vis = true;
      next = next.nextElementSibling;
    }
    g.style.display = vis ? "" : "none";
  });
  dd.classList.add("open");
}

let _tzSelectedFrom = "New York", _tzSelectedTo = "London";
function tzSelect(target, iana, name) {
  document.getElementById(target==="from"?"tzFromZone":"tzToZone").value = iana;
  const searchEl = document.getElementById(target==="from"?"tzFromSearch":"tzToSearch");
  searchEl.value = name;
  searchEl.classList.remove("tz-invalid");
  if (target==="from") _tzSelectedFrom = name; else _tzSelectedTo = name;
  const off = _tzOffset(iana);
  document.getElementById(target==="from"?"tzFromLabel":"tzToLabel").textContent = `${name} (${off})`;
  document.querySelectorAll(".tz-dropdown").forEach(d=>d.classList.remove("open"));
}

function tzSwap() {
  const fz = document.getElementById("tzFromZone").value, tz = document.getElementById("tzToZone").value;
  const fs = document.getElementById("tzFromSearch").value, ts = document.getElementById("tzToSearch").value;
  const fl = document.getElementById("tzFromLabel").textContent, tl = document.getElementById("tzToLabel").textContent;
  document.getElementById("tzFromZone").value = tz; document.getElementById("tzToZone").value = fz;
  document.getElementById("tzFromSearch").value = ts; document.getElementById("tzToSearch").value = fs;
  document.getElementById("tzFromLabel").textContent = tl; document.getElementById("tzToLabel").textContent = fl;
  const tmpName = _tzSelectedFrom; _tzSelectedFrom = _tzSelectedTo; _tzSelectedTo = tmpName;
}

function tzSetNow() {
  const now = new Date();
  const pad = n => String(n).padStart(2,"0");
  document.getElementById("tzDateTime").value = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

// Build a set of all valid city names for validation
const _tzValidCities = new Map();
TZ_CITIES.forEach(g => g.cities.forEach(([name, iana]) => _tzValidCities.set(name.toLowerCase(), iana)));

function tzConvert() {
  const fromText = document.getElementById("tzFromSearch").value.trim();
  const toText = document.getElementById("tzToSearch").value.trim();
  const dtVal = document.getElementById("tzDateTime").value;
  // Validate: typed text must exactly match a known city name (case-insensitive)
  const fromIana = _tzValidCities.get(fromText.toLowerCase());
  const toIana = _tzValidCities.get(toText.toLowerCase());
  document.getElementById("tzFromSearch").classList.toggle("tz-invalid", !fromIana);
  document.getElementById("tzToSearch").classList.toggle("tz-invalid", !toIana);
  if (!fromIana) { setStatus("tzStatus",`"${fromText || '(empty)'}" is not a recognized city. Please select one from the dropdown.`,"err"); document.getElementById("tzResult").style.display="none"; return; }
  if (!toIana) { setStatus("tzStatus",`"${toText || '(empty)'}" is not a recognized city. Please select one from the dropdown.`,"err"); document.getElementById("tzResult").style.display="none"; return; }
  if (!dtVal) { setStatus("tzStatus","Pick a date & time.","err"); return; }
  // Use the validated IANA zones (ignore the hidden inputs which can be stale)
  const fromZone = fromIana;
  const toZone = toIana;

  // Parse the datetime-local as if it were in the "from" timezone
  const [datePart, timePart] = dtVal.split("T");
  const [yr, mo, dy] = datePart.split("-").map(Number);
  const [hr, mn] = timePart.split(":").map(Number);

  // Create a Date in the "from" zone by trial: find UTC that formats to the given local time
  let guess = new Date(Date.UTC(yr, mo-1, dy, hr, mn));
  for (let i = 0; i < 3; i++) {
    const parts = new Intl.DateTimeFormat("en-US",{timeZone:fromZone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).formatToParts(guess);
    const g = {}; parts.forEach(p=>g[p.type]=parseInt(p.value)||0);
    const diffMin = (hr - g.hour)*60 + (mn - g.minute) + (dy - g.day)*1440;
    guess = new Date(guess.getTime() + diffMin*60000);
  }

  const fmt = (zone) => {
    const o = {timeZone:zone,weekday:"long",year:"numeric",month:"long",day:"numeric"};
    const date = new Intl.DateTimeFormat("en-US",o).format(guess);
    const time = new Intl.DateTimeFormat("en-US",{timeZone:zone,hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:true}).format(guess);
    const zoneParts = new Intl.DateTimeFormat("en-US",{timeZone:zone,timeZoneName:"short"}).formatToParts(guess);
    const zn = zoneParts.find(p=>p.type==="timeZoneName");
    const off = _tzOffset(zone);
    return {date, time, zoneAbbr: zn ? zn.value : "", offset: off};
  };

  const fromFmt = fmt(fromZone);
  const toFmt = fmt(toZone);
  const fromName = document.getElementById("tzFromSearch").value || fromZone.split("/").pop().replace(/_/g," ");
  const toName = document.getElementById("tzToSearch").value || toZone.split("/").pop().replace(/_/g," ");

  document.getElementById("tzResultFromCity").textContent = fromName;
  document.getElementById("tzResultFromTime").textContent = fromFmt.time;
  document.getElementById("tzResultFromDate").textContent = fromFmt.date;
  document.getElementById("tzResultFromZone").textContent = `${fromFmt.zoneAbbr} (${fromFmt.offset})`;

  document.getElementById("tzResultToCity").textContent = toName;
  document.getElementById("tzResultToTime").textContent = toFmt.time;
  document.getElementById("tzResultToDate").textContent = toFmt.date;
  document.getElementById("tzResultToZone").textContent = `${toFmt.zoneAbbr} (${toFmt.offset})`;

  // Calculate hour difference
  const fromOff = guess.getTime(); // same moment
  const fromLocal = new Intl.DateTimeFormat("en-US",{timeZone:fromZone,hour:"numeric",hour12:false,minute:"numeric"}).format(guess);
  const toLocal = new Intl.DateTimeFormat("en-US",{timeZone:toZone,hour:"numeric",hour12:false,minute:"numeric"}).format(guess);
  const [fh,fm] = fromLocal.split(":").map(Number);
  const [th,tm] = toLocal.split(":").map(Number);
  let diffH = (th - fh) + (tm - fm) / 60;
  if (diffH > 12) diffH -= 24; if (diffH < -12) diffH += 24;
  const sign = diffH >= 0 ? "+" : "";
  const diffStr = Number.isInteger(diffH) ? `${sign}${diffH}` : `${sign}${diffH.toFixed(1)}`;
  document.getElementById("tzDiffText").textContent = `${toName} is ${diffStr} hours from ${fromName}`;

  document.getElementById("tzResult").style.display = "block";
  setStatus("tzStatus","","ok");
}

// Close TZ dropdowns on outside click
document.addEventListener("click", (e) => {
  if (!e.target.closest(".tz-dropdown") && !e.target.matches("#tzFromSearch") && !e.target.matches("#tzToSearch")) {
    document.querySelectorAll(".tz-dropdown").forEach(d=>d.classList.remove("open"));
  }
});

// Init TZ with defaults
tzSelect("from","America/New_York","New York");
tzSelect("to","Europe/London","London");
tzSetNow();

// Init
unitUpdateSelects();

// Route: read initial converter from data attribute injected by server
const _initConverter = document.documentElement.dataset.converter;
if (_initConverter && document.getElementById("panel-" + _initConverter)) {
  switchConverter(_initConverter);
}
window.addEventListener("popstate", () => {
  const path = location.pathname.replace("/", "");
  if (path && document.getElementById("panel-" + path)) switchConverter(path);
  else switchConverter("json");
});
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════════════
# Security & Production Middleware
# ═══════════════════════════════════════════════════════════════════════════

@app.after_request
def set_headers(response):
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        "connect-src 'self'; frame-ancestors 'none';"
    )
    # Cache headers
    if request.path == "/":
        response.headers["Cache-Control"] = "public, max-age=3600"
    elif request.path in ("/robots.txt", "/sitemap.xml", "/llms.txt"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif request.method == "POST":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad request"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large. Maximum 10 MB."}), 413


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Too many requests. Please try again later."}), 429


@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════════
# Routes — Pages
# ═══════════════════════════════════════════════════════════════════════════

_CONVERTER_SEO = {
    "json": ("JSON to Excel Converter", "Convert JSON data to Excel spreadsheets online for free. Paste or upload JSON, preview as table, download .xlsx instantly. No signup."),
    "md-docx": ("Markdown to DOCX Converter", "Convert Markdown to Microsoft Word DOCX online for free. Preview formatted output and download .docx instantly. No signup."),
    "md-pdf": ("Markdown to PDF Converter", "Convert Markdown to PDF online for free. Preview formatted output and download PDF with proper fonts and formatting. No signup."),
    "csv-excel": ("CSV to Excel Converter", "Convert CSV to Excel spreadsheets online for free. Auto-detects delimiters (comma, tab, semicolon, pipe). Download .xlsx instantly."),
    "yaml-json": ("YAML to JSON Converter", "Convert YAML to JSON online for free. Paste YAML, get formatted JSON output instantly. No signup required."),
    "html-md": ("HTML to Markdown Converter", "Convert HTML to clean Markdown online for free. Paste HTML code and get readable Markdown output. Download .md file instantly."),
    "pdf-text": ("PDF to Text Extractor", "Extract text from PDF files online for free. Upload PDF, get plain text output. Copy or download extracted text. No signup."),
    "xml-json": ("XML to JSON Converter", "Convert XML to JSON online for free. Paste XML, get structured JSON output. Also download as Excel. No signup required."),
    "sql-csv": ("SQL to CSV/Excel Converter", "Convert SQL CREATE TABLE and INSERT statements to CSV or Excel online for free. Parse SQL into tabular data instantly."),
    "csv-json": ("CSV to JSON Converter", "Convert CSV data to JSON online for free. Auto-detects delimiters. Get formatted JSON array of records instantly. No signup."),
    "svg-png": ("SVG to PNG Converter", "Convert SVG to PNG image online for free. Client-side conversion, your files never leave your browser. Download PNG instantly."),
    "image-resize": ("Image Resizer", "Resize and compress images online for free. Support JPEG, PNG, WebP. Set custom dimensions and quality. Download resized image instantly."),
    "base64-image": ("Base64 Image Encoder/Decoder", "Encode images to Base64 or decode Base64 to images online for free. Support all common formats. No signup required."),
    "json-format": ("JSON Formatter & Validator", "Format, validate, and minify JSON online for free. Pretty-print with custom indentation. Client-side processing. No signup."),
    "toml-json": ("TOML to JSON/YAML Converter", "Convert TOML configuration files to JSON or YAML online for free. Paste TOML, get formatted output instantly. No signup."),
    "cron-human": ("Cron Expression Parser", "Parse cron expressions to human-readable descriptions online for free. See next 5 scheduled run times. Supports standard 5-field cron."),
    "unit": ("Unit Converter", "Convert between units of length, weight, temperature, volume, area, speed, and data online for free. Instant calculations. No signup."),
    "color": ("Color Converter", "Convert between HEX, RGB, and HSL color formats online for free. Live color preview swatch. No signup required."),
    "timestamp": ("Timestamp Converter", "Convert Unix timestamps, ISO dates, and human-readable dates online for free. Parse any date format to all others instantly."),
    "timezone": ("Time Zone Converter", "Convert time between 150+ cities worldwide. Search by city name, see time difference. Free online time zone converter. No signup."),
}

_DEFAULT_TITLE = "Ayo's Converter - Free Online File Format Converter"
_DEFAULT_DESC = "Free online converter for JSON, CSV, YAML, XML, Markdown, PDF, images, and more. Convert between 20+ file formats instantly. No signup required."


def _inject_seo(html, converter_id):
    """Inject per-page SEO meta tags and data-converter attribute."""
    page = html.replace("<html ", f'<html data-converter="{converter_id}" ', 1)
    if converter_id in _CONVERTER_SEO:
        title, desc = _CONVERTER_SEO[converter_id]
        full_title = f"{title} - Free Online | Ayo's Converter"
        page = page.replace(
            "<title>Ayo's Converter - Free Online File Format Converter</title>",
            f"<title>{full_title}</title>", 1)
        page = page.replace(_DEFAULT_DESC, desc, 1)
        page = page.replace(
            'content="Ayo\'s Converter - Free Online File Format Converter"',
            f'content="{full_title}"', 1)
        page = page.replace(
            'content="Convert between 20+ file formats instantly. JSON, CSV, YAML, XML, Markdown, PDF, images and more."',
            f'content="{desc}"', 1)
        page = page.replace('href="/"', f'href="/{converter_id}"', 1)
    return page


@app.route("/")
def index():
    return _inject_seo(HTML, "json")


@app.route("/<converter_id>")
def converter_page(converter_id):
    if converter_id not in _CONVERTER_SEO:
        return _inject_seo(HTML, "json"), 404
    return _inject_seo(HTML, converter_id)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "converters": 20})


@app.route("/robots.txt")
def robots():
    host = request.host_url.rstrip("/")
    return Response(f"User-agent: *\nAllow: /\nSitemap: {host}/sitemap.xml\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    host = request.host_url.rstrip("/")
    urls = [f'<url><loc>{host}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>']
    for cid in _CONVERTER_SEO:
        urls.append(f'<url><loc>{host}/{cid}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    return Response(xml, mimetype="application/xml")


@app.route("/llms.txt")
def llms_txt():
    host = request.host_url.rstrip("/")
    text = f"""# Ayo's Converter

> Free online file format converter supporting 20 converters across 5 categories.
> No signup, no ads, no file size gimmicks. All conversions run instantly.

## URL: {host}

## Converters

### Document / Text
- JSON to Excel Converter ({host}/json): Convert JSON data to formatted Excel (.xlsx) spreadsheets. Supports nested JSON with flattening. Preview as table before download.
- Markdown to DOCX ({host}/md-docx): Convert Markdown to Microsoft Word (.docx). Full support for headings, lists, tables, code blocks, and formatting.
- Markdown to PDF ({host}/md-pdf): Convert Markdown to PDF with proper Unicode font support (Liberation Serif). Handles bold, italic, headings, lists, code blocks.
- CSV to Excel ({host}/csv-excel): Convert CSV to Excel (.xlsx). Auto-detects delimiter (comma, tab, semicolon, pipe). Preview data before download.
- YAML to JSON ({host}/yaml-json): Convert YAML documents to formatted JSON. Supports nested structures, arrays, and all YAML types.
- HTML to Markdown ({host}/html-md): Convert HTML to clean, readable Markdown. Preserves links, images, tables, and formatting.
- PDF to Text Extractor ({host}/pdf-text): Extract text content from PDF files. Upload PDF, get plain text. Copy or download as .txt.

### Data
- XML to JSON ({host}/xml-json): Convert XML documents to JSON. Also supports download as Excel (.xlsx).
- SQL to CSV/Excel ({host}/sql-csv): Parse SQL CREATE TABLE + INSERT INTO statements into tabular CSV or Excel data.
- CSV to JSON ({host}/csv-json): Convert CSV data to JSON array of records. Auto-detects delimiter.

### Image / Media
- SVG to PNG ({host}/svg-png): Convert SVG vector graphics to PNG raster image. Client-side conversion, files never uploaded.
- Image Resizer ({host}/image-resize): Resize and compress JPEG, PNG, WebP images. Set custom width, height, and quality.
- Base64 Image Encoder/Decoder ({host}/base64-image): Encode images to Base64 data URIs or decode Base64 strings back to images.

### Developer Tools
- JSON Formatter ({host}/json-format): Validate, pretty-print, and minify JSON. Client-side processing with custom indentation.
- TOML to JSON/YAML ({host}/toml-json): Convert TOML configuration files to JSON or YAML format.
- Cron Expression Parser ({host}/cron-human): Parse standard 5-field cron expressions to human-readable descriptions. Shows next 5 run times.

### Everyday Use
- Unit Converter ({host}/unit): Convert between units of length, weight, temperature, volume, area, speed, and data storage.
- Color Converter ({host}/color): Convert between HEX, RGB, and HSL color formats with live preview swatch.
- Timestamp Converter ({host}/timestamp): Parse and convert between Unix timestamps, ISO 8601, UTC, and human-readable date formats.
- Time Zone Converter ({host}/timezone): Convert time between 150+ cities worldwide. Searchable city dropdown with UTC offsets.

## Technical
- Built with Python/Flask, deployed on Vercel
- OWASP security headers, rate limiting, input validation
- Client-side converters (SVG, JSON Formatter, Unit, Color) run entirely in the browser
- Maximum upload size: 10 MB
"""
    return Response(text, mimetype="text/plain; charset=utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Routes — JSON → Excel
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/json/preview", methods=["POST"])
@app.route("/preview", methods=["POST"])
def json_preview():
    body = request.get_json(force=True)
    raw = _validate_text(body.get("json", ""), "JSON input")
    try:
        data = load_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return jsonify({"error": f"Invalid JSON: {exc}"}), 400

    flatten = body.get("flatten", True)
    sep = body.get("sep", ".")
    sheet_name = body.get("sheet_name", "Sheet1")
    strip_prefix = body.get("strip_prefix", True)

    sheets = json_to_dataframes(data, flatten=flatten, sep=sep, sheet_name=sheet_name, strip_prefix=strip_prefix)
    result = []
    for name, df in sheets:
        result.append({"name": name, "columns": df.columns.tolist(), "rows": df.fillna("").to_dict(orient="records")})
    return jsonify({"sheets": result})


@app.route("/json/download", methods=["POST"])
@app.route("/download", methods=["POST"])
@limiter.limit("30 per hour")
def json_download():
    body = request.get_json(force=True)
    raw = _validate_text(body.get("json", ""), "JSON input")
    data = load_json(raw)
    sheets = json_to_dataframes(data, flatten=body.get("flatten", True), sep=body.get("sep", "."),
                                sheet_name=body.get("sheet_name", "Sheet1"), strip_prefix=body.get("strip_prefix", True))
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    to_excel(sheets, tmp.name)
    resp = send_file(tmp.name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="converted.xlsx")
    Path(tmp.name).unlink(missing_ok=True)
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# Routes — Markdown → DOCX / PDF
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/md/preview", methods=["POST"])
def md_preview():
    body = request.get_json(force=True)
    raw = _validate_text(body.get("markdown", ""), "Markdown")
    html = md_to_html(raw)
    safe = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    return jsonify({"html": safe})


@app.route("/md/download/docx", methods=["POST"])
@limiter.limit("30 per hour")
def md_download_docx():
    body = request.get_json(force=True)
    raw = _validate_text(body.get("markdown", ""), "Markdown")
    buf = io.BytesIO(md_to_docx_bytes(raw))
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     as_attachment=True, download_name="converted.docx")


@app.route("/md/download/pdf", methods=["POST"])
@limiter.limit("30 per hour")
def md_download_pdf():
    body = request.get_json(force=True)
    raw = _validate_text(body.get("markdown", ""), "Markdown")
    buf = io.BytesIO(md_to_pdf_bytes(raw))
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="converted.pdf")


# ═══════════════════════════════════════════════════════════════════════════
# Routes — CSV
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/csv/preview", methods=["POST"])
def csv_preview():
    from converters.csv_converter import csv_to_dataframes
    body = request.get_json(force=True)
    raw = _validate_text(body.get("csv", ""), "CSV")
    delimiter = body.get("delimiter", ",")
    sheets = csv_to_dataframes(raw, delimiter=delimiter)
    _, df = sheets[0]
    return jsonify({"columns": df.columns.tolist(), "rows": df.fillna("").to_dict(orient="records")})


@app.route("/csv/download/excel", methods=["POST"])
@limiter.limit("30 per hour")
def csv_download_excel():
    from converters.csv_converter import csv_to_dataframes
    body = request.get_json(force=True)
    raw = _validate_text(body.get("csv", ""), "CSV")
    sheets = csv_to_dataframes(raw, delimiter=body.get("delimiter", ","))
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    to_excel(sheets, tmp.name)
    resp = send_file(tmp.name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="converted.xlsx")
    Path(tmp.name).unlink(missing_ok=True)
    return resp


@app.route("/csv/to-json", methods=["POST"])
def csv_to_json():
    from converters.csv_converter import csv_to_json_str
    body = request.get_json(force=True)
    raw = _validate_text(body.get("csv", ""), "CSV")
    result = csv_to_json_str(raw, delimiter=body.get("delimiter", ","))
    return jsonify({"json": result})


# ═══════════════════════════════════════════════════════════════════════════
# Routes — YAML
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/yaml/convert", methods=["POST"])
def yaml_convert():
    from converters.yaml_converter import yaml_to_json_str
    body = request.get_json(force=True)
    raw = _validate_text(body.get("yaml", ""), "YAML")
    try:
        result = yaml_to_json_str(raw)
    except Exception as exc:
        return jsonify({"error": f"Invalid YAML: {exc}"}), 400
    return jsonify({"json": result})


# ═══════════════════════════════════════════════════════════════════════════
# Routes — HTML → Markdown
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/html/convert", methods=["POST"])
def html_convert():
    from converters.html_converter import html_to_markdown
    body = request.get_json(force=True)
    raw = _validate_text(body.get("html", ""), "HTML")
    result = html_to_markdown(raw)
    return jsonify({"markdown": result})


# ═══════════════════════════════════════════════════════════════════════════
# Routes — PDF → Text
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/pdf/extract", methods=["POST"])
@limiter.limit("20 per hour")
def pdf_extract():
    from converters.pdf_converter import pdf_to_text
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a PDF"}), 400
    pdf_bytes = file.read()
    try:
        text = pdf_to_text(pdf_bytes)
    except Exception as exc:
        return jsonify({"error": f"PDF extraction failed: {exc}"}), 400
    return jsonify({"text": text})


# ═══════════════════════════════════════════════════════════════════════════
# Routes — XML
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/xml/convert", methods=["POST"])
def xml_convert():
    from converters.xml_converter import xml_to_json_str
    body = request.get_json(force=True)
    raw = _validate_text(body.get("xml", ""), "XML")
    try:
        result = xml_to_json_str(raw)
    except Exception as exc:
        return jsonify({"error": f"Invalid XML: {exc}"}), 400
    return jsonify({"json": result})


@app.route("/xml/download/excel", methods=["POST"])
@limiter.limit("30 per hour")
def xml_download_excel():
    from converters.xml_converter import xml_to_dict
    body = request.get_json(force=True)
    raw = _validate_text(body.get("xml", ""), "XML")
    data = xml_to_dict(raw)
    sheets = json_to_dataframes(data, flatten=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    to_excel(sheets, tmp.name)
    resp = send_file(tmp.name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="converted.xlsx")
    Path(tmp.name).unlink(missing_ok=True)
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# Routes — SQL
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/sql/preview", methods=["POST"])
def sql_preview():
    from converters.sql_converter import sql_to_records
    body = request.get_json(force=True)
    raw = _validate_text(body.get("sql", ""), "SQL")
    try:
        result = sql_to_records(raw)
    except Exception as exc:
        return jsonify({"error": f"SQL parse error: {exc}"}), 400
    return jsonify(result)


@app.route("/sql/download/csv", methods=["POST"])
@limiter.limit("30 per hour")
def sql_download_csv():
    from converters.sql_converter import sql_to_records, records_to_csv
    body = request.get_json(force=True)
    raw = _validate_text(body.get("sql", ""), "SQL")
    result = sql_to_records(raw)
    csv_text = records_to_csv(result)
    buf = io.BytesIO(csv_text.encode("utf-8"))
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="converted.csv")


@app.route("/sql/download/excel", methods=["POST"])
@limiter.limit("30 per hour")
def sql_download_excel():
    from converters.sql_converter import sql_to_records
    import pandas as pd
    body = request.get_json(force=True)
    raw = _validate_text(body.get("sql", ""), "SQL")
    result = sql_to_records(raw)
    tables = result.get("tables", {})
    sheets = []
    for name, table in tables.items():
        df = pd.DataFrame(table["rows"], columns=table["columns"])
        sheets.append((name, df))
    if not sheets:
        return jsonify({"error": "No tables found"}), 400
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    to_excel(sheets, tmp.name)
    resp = send_file(tmp.name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="converted.xlsx")
    Path(tmp.name).unlink(missing_ok=True)
    return resp


# ═══════════════════════════════════════════════════════════════════════════
# Routes — Image
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/image/resize", methods=["POST"])
@limiter.limit("30 per hour")
def image_resize():
    from converters.image_converter import resize_image
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    image_bytes = file.read()
    width = request.form.get("width", type=int)
    height = request.form.get("height", type=int)
    quality = request.form.get("quality", 85, type=int)
    fmt = request.form.get("format", "JPEG")
    try:
        result = resize_image(image_bytes, width=width, height=height, quality=quality, fmt=fmt)
    except Exception as exc:
        return jsonify({"error": f"Resize failed: {exc}"}), 400
    mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    return send_file(io.BytesIO(result), mimetype=mime_map.get(fmt, "image/jpeg"), as_attachment=True,
                     download_name=f"resized.{fmt.lower()}")


@app.route("/base64/encode", methods=["POST"])
def base64_encode():
    from converters.image_converter import image_to_base64
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    image_bytes = file.read()
    mime = file.content_type or "image/png"
    result = image_to_base64(image_bytes, mime)
    return jsonify({"base64": result})


@app.route("/base64/decode", methods=["POST"])
def base64_decode():
    from converters.image_converter import base64_to_image
    body = request.get_json(force=True)
    data = body.get("data", "").strip()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    try:
        image_bytes, mime = base64_to_image(data)
    except Exception as exc:
        return jsonify({"error": f"Decode failed: {exc}"}), 400
    return send_file(io.BytesIO(image_bytes), mimetype=mime)


# ═══════════════════════════════════════════════════════════════════════════
# Routes — TOML
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/toml/convert", methods=["POST"])
def toml_convert():
    from converters.toml_converter import toml_to_json_str, toml_to_yaml_str
    body = request.get_json(force=True)
    raw = _validate_text(body.get("toml", ""), "TOML")
    fmt = body.get("format", "json")
    try:
        result = toml_to_json_str(raw) if fmt == "json" else toml_to_yaml_str(raw)
    except Exception as exc:
        return jsonify({"error": f"Invalid TOML: {exc}"}), 400
    return jsonify({"result": result})


# ═══════════════════════════════════════════════════════════════════════════
# Routes — Cron
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/cron/parse", methods=["POST"])
def cron_parse():
    from converters.cron_converter import cron_parse as _cron_parse
    body = request.get_json(force=True)
    raw = body.get("cron", "").strip()
    if not raw:
        return jsonify({"error": "No cron expression"}), 400
    try:
        result = _cron_parse(raw)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# Routes — Timestamp
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/timestamp/parse", methods=["POST"])
def timestamp_parse():
    from converters.timestamp_converter import parse_timestamp
    body = request.get_json(force=True)
    raw = body.get("input", "").strip()
    if not raw:
        return jsonify({"error": "No input"}), 400
    try:
        result = parse_timestamp(raw)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import threading, webbrowser
    url = "http://127.0.0.1:5123"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"  Ayo's Converter → {url}")
    app.run(port=5123, debug=False)
