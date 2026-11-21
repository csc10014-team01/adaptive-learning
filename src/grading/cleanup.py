"""Delete only old optional trace files; never submissions or compact results.

Usage: python -m src.grading.cleanup --older-than-days 7
"""

import argparse
import re
import time

from src.grading.config import GradingConfig


def cleanup_debug(config, older_than_days):
    root = config.debug_dir.resolve()
    cutoff = time.time() - older_than_days * 86400
    removed = 0
    if not root.is_dir():
        return removed
    for folder in root.iterdir():
        if (
            folder.is_symlink()
            or not folder.is_dir()
            or not re.fullmatch(r"G_[a-f0-9]{32}", folder.name)
        ):
            continue
        for trace in folder.iterdir():
            if (
                trace.is_symlink()
                or not trace.is_file()
                or not re.fullmatch(r"\d{2}\.json", trace.name)
                or trace.resolve().parent != folder.resolve()
                or root not in trace.resolve().parents
            ):
                continue
            if trace.resolve() == config.db_path.resolve():
                continue
            if trace.stat().st_mtime < cutoff:
                trace.unlink()
                removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-days", type=int, default=7)
    args = parser.parse_args()
    if args.older_than_days < 1:
        parser.error("Retention must be at least one day")
    print(
        f"Removed {cleanup_debug(GradingConfig.from_env(), args.older_than_days)} optional debug files."
    )


if __name__ == "__main__":
    main()
