"""Reversible installer: write a starter config from a preset (non-clobbering)."""

import sys

from token_oracle.core.config import write_default_config  # noqa: F401  (re-export for scripts)


def main():
    path = write_default_config()
    print(f"config: {path}")
    print("next: `token-oracle doctor` then `token-oracle forecast`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
