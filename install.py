"""Reversible installer: write a starter config from a preset (non-clobbering)."""
import json
import os
import sys

from token_oracle.core.config import default_config_path, PRESETS


def write_default_config(path=None, preset="max20", force=False) -> str:
    path = os.path.expanduser(path or default_config_path())
    if os.path.exists(path) and not force:
        return path
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(PRESETS[preset], fh, indent=2)
    return path


def main():
    path = write_default_config()
    print(f"config: {path}")
    print("next: `oracle doctor` then `oracle forecast`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
