"""TOML conversion logic."""
import json

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import yaml


def toml_to_json_str(toml_text: str, indent: int = 2) -> str:
    """Convert TOML text to a pretty-printed JSON string."""
    data = tomllib.loads(toml_text)
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def toml_to_yaml_str(toml_text: str) -> str:
    """Convert TOML text to YAML."""
    data = tomllib.loads(toml_text)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
