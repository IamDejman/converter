"""YAML conversion logic."""
import json

import yaml


def yaml_to_json_str(yaml_text: str, indent: int = 2) -> str:
    """Convert YAML text to a pretty-printed JSON string."""
    data = yaml.safe_load(yaml_text)
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
