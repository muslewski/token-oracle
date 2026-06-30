"""Reversible uninstall: remove oracle's config/cache/snapshot. The pip package
is removed separately via `pip uninstall token-oracle`."""
import os
import sys

from token_oracle.core.config import default_config_path, default_cache_path
from token_oracle.snapshot.writer import default_snapshot_path


def remove_config(path=None) -> bool:
    path = os.path.expanduser(path or default_config_path())
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def remove_cache_and_snapshot() -> None:
    for p in (default_cache_path(), default_snapshot_path()):
        try:
            os.remove(os.path.expanduser(p))
        except OSError:
            pass


def main():
    removed = remove_config()
    remove_cache_and_snapshot()
    print("removed config" if removed else "no config to remove")
    print("run `pip uninstall token-oracle` to remove the package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
