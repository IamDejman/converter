"""XML conversion logic."""
import json

import xmltodict


def xml_to_json_str(xml_text: str, indent: int = 2) -> str:
    """Convert XML text to a pretty-printed JSON string."""
    data = xmltodict.parse(xml_text)
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def xml_to_dict(xml_text: str) -> dict:
    """Parse XML text into a Python dict."""
    return xmltodict.parse(xml_text)
