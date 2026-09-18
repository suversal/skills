#!/usr/bin/env python3
"""Classify a Linux host for this skill without changing the system."""
import argparse
import json
import platform
import shlex
from pathlib import Path


APT_IDS = {"debian", "ubuntu"}
DNF_IDS = {"rhel", "rocky", "almalinux", "ol", "centos"}
ARCHES = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}


def read_os_release(path):
    data = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parsed = shlex.split(value, posix=True)
            data[key] = " ".join(parsed) if parsed else ""
        except ValueError:
            data[key] = value.strip('"')
    return data


def classify(data, architecture, init_name):
    distro = data.get("ID", "").lower()
    like = set(data.get("ID_LIKE", "").lower().split())
    ids = {distro} | like
    if ids & APT_IDS:
        family = "apt"
    elif ids & DNF_IDS:
        family = "dnf"
    else:
        family = "unsupported"
    arch = ARCHES.get(architecture.lower(), "unsupported")
    init = "systemd" if init_name.strip() == "systemd" else "unsupported"
    supported = family in {"apt", "dnf"} and arch != "unsupported" and init == "systemd"
    return {
        "distribution_id": distro or "unknown",
        "distribution_version": data.get("VERSION_ID", "unknown"),
        "os_family": family,
        "architecture": arch,
        "init": init,
        "release_support": "verify_current_vendor_status",
        "profile_status": "supported_baseline" if supported else "manual_adaptation_required",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--os-release", type=Path, default=Path("/etc/os-release"))
    parser.add_argument("--architecture", default=platform.machine())
    parser.add_argument("--init", dest="init_name", default="")
    parser.add_argument("--require-supported", action="store_true")
    args = parser.parse_args()
    init_name = args.init_name
    if not init_name:
        try:
            init_name = Path("/proc/1/comm").read_text(encoding="utf-8").strip()
        except OSError:
            init_name = "unknown"
    result = classify(read_os_release(args.os_release), args.architecture, init_name)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.require_supported and result["profile_status"] != "supported_baseline":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
