"""Converter registry and shared utilities."""

CATEGORIES = [
    {
        "id": "doc-text",
        "name": "Document / Text",
        "converters": [
            {"id": "json", "label": "JSON \u2192 Excel"},
            {"id": "md-docx", "label": "Markdown \u2192 DOCX"},
            {"id": "md-pdf", "label": "Markdown \u2192 PDF"},
            {"id": "csv-excel", "label": "CSV \u2192 Excel"},
            {"id": "yaml-json", "label": "YAML \u2192 JSON"},
            {"id": "html-md", "label": "HTML \u2192 Markdown"},
            {"id": "pdf-text", "label": "PDF \u2192 Text"},
        ],
    },
    {
        "id": "data",
        "name": "Data",
        "converters": [
            {"id": "xml-json", "label": "XML \u2192 JSON"},
            {"id": "sql-csv", "label": "SQL \u2192 CSV"},
            {"id": "csv-json", "label": "CSV \u2192 JSON"},
        ],
    },
    {
        "id": "image",
        "name": "Image / Media",
        "converters": [
            {"id": "svg-png", "label": "SVG \u2192 PNG"},
            {"id": "image-resize", "label": "Image Resizer"},
            {"id": "base64-image", "label": "Base64 \u2194 Image"},
        ],
    },
    {
        "id": "dev-tools",
        "name": "Developer Tools",
        "converters": [
            {"id": "json-format", "label": "JSON Formatter"},
            {"id": "toml-json", "label": "TOML \u2192 JSON/YAML"},
            {"id": "cron-human", "label": "Cron Parser"},
        ],
    },
    {
        "id": "everyday",
        "name": "Everyday Use",
        "converters": [
            {"id": "unit", "label": "Unit Converter"},
            {"id": "color", "label": "Color Converter"},
            {"id": "timestamp", "label": "Timestamp Tool"},
        ],
    },
]
