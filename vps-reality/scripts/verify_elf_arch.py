#!/usr/bin/env python3
"""Verify ELF machine architecture without executing the target binary."""

import argparse
import json
from pathlib import Path
import struct
import sys


ELF_MAGIC = b"\x7fELF"
ELF_DATA_LITTLE = 1
ELF_DATA_BIG = 2
MACHINES = {
    62: "x86_64",
    183: "arm64",
}


def detect_arch(path: Path) -> str:
    try:
        with path.open("rb") as binary:
            header = binary.read(20)
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if len(header) < 20 or header[:4] != ELF_MAGIC:
        raise ValueError(f"not an ELF binary: {path}")
    if header[5] == ELF_DATA_LITTLE:
        byte_order = "<"
    elif header[5] == ELF_DATA_BIG:
        byte_order = ">"
    else:
        raise ValueError(f"unsupported ELF byte order: {path}")
    machine = struct.unpack(f"{byte_order}H", header[18:20])[0]
    if machine not in MACHINES:
        raise ValueError(f"unsupported ELF machine {machine}: {path}")
    return MACHINES[machine]


def verify(path: Path, expected: str) -> dict:
    actual = detect_arch(path)
    if actual != expected:
        raise ValueError(f"architecture mismatch for {path}: expected {expected}, got {actual}")
    return {
        "path": str(path),
        "expected": expected,
        "actual": actual,
        "match": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify x86_64/ARM64 ELF architecture without executing files."
    )
    parser.add_argument("--expected", required=True, choices=("x86_64", "arm64"))
    parser.add_argument("binary", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        results = [verify(path, args.expected) for path in args.binary]
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
