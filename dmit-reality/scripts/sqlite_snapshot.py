#!/usr/bin/env python3
"""Create an exclusive, consistent, private SQLite snapshot. Never restores."""
import argparse
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib.parse import quote


def snapshot(database, output):
    database = Path(database).resolve(strict=True)
    output = Path(output)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        source = sqlite3.connect("file:" + quote(str(database), safe="/") + "?mode=ro", uri=True, timeout=15)
        dest = sqlite3.connect(str(output), timeout=15)
        try:
            deadline = time.monotonic() + 30
            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError("snapshot exceeded 30 seconds")
            source.backup(dest, pages=256, progress=progress, sleep=0.1)
            if dest.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("snapshot integrity failure")
        finally:
            dest.close()
            source.close()
    except Exception:
        # Keep the failed artifact for explicit inspection; never silently reuse it.
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    snapshot(args.database, args.output)
    print("snapshot=created integrity=ok mode=600")
    print("snapshot_file=" + str(args.output.resolve()))


if __name__ == "__main__":
    try:
        main()
    except (OSError, sqlite3.Error, ValueError):
        print("snapshot=failed inspect_paths_permissions_and_database; do_not_use_failed_artifact", file=sys.stderr)
        sys.exit(1)
