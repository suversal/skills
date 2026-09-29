#!/usr/bin/env python3
"""Prepare loopback-only 3x-ui settings and records for a subscription Tunnel.

This offline helper never contacts the panel or Cloudflare and never regenerates
client UUIDs, Sub IDs, REALITY keys, or subscription paths.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys


KINDS = ("raw", "json", "clash")
URI_FIELDS = {"raw": "subURI", "json": "subJsonURI", "clash": "subClashURI"}
PATH_FIELDS = {"raw": "subPath", "json": "subJsonPath", "clash": "subClashPath"}


def private_file(path):
    path = Path(path)
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
        raise ValueError("requires a private regular file")
    if meta.st_uid != os.geteuid():
        raise ValueError("file owner mismatch")
    return path


def hostname(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError("invalid hostname")
    labels = value.split(".")
    if len(labels) < 2 or any(
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("invalid hostname")
    return value.lower()


def subscription_path(value):
    if not isinstance(value, str) or not re.fullmatch(r"/[A-Za-z0-9_-]{8,128}/", value):
        raise ValueError("invalid private subscription path")
    return value


def prepare(settings, clients_record, public_hostname):
    public_hostname = hostname(public_hostname)
    if settings.get("webListen") != "127.0.0.1" or settings.get("subListen") != "127.0.0.1":
        raise ValueError("panel and subscription origin must remain loopback-only")
    if settings.get("subEnable") is not True:
        raise ValueError("subscription service is not enabled")
    paths = {kind: subscription_path(settings.get(field)) for kind, field in PATH_FIELDS.items()}
    base = "https://" + public_hostname
    patch = {
        "webListen": "127.0.0.1",
        "subListen": "127.0.0.1",
        "subDomain": public_hostname,
    }
    for kind, field in URI_FIELDS.items():
        patch[field] = base + paths[kind]

    if not isinstance(clients_record, dict) or not isinstance(clients_record.get("clients"), list):
        raise ValueError("invalid private client record")
    migrated = dict(clients_record)
    migrated["control_plane_mode"] = "cloudflare-subscription-only"
    migrated_clients = []
    for client in clients_record["clients"]:
        if not isinstance(client, dict):
            raise ValueError("invalid client entry")
        sub_id = client.get("sub_id")
        if not isinstance(sub_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", sub_id):
            raise ValueError("invalid client Sub ID")
        updated = dict(client)
        updated["subscription_urls"] = {
            kind: base + paths[kind] + sub_id for kind in KINDS
        }
        updated["local_subscription_urls"] = {}
        migrated_clients.append(updated)
    migrated["clients"] = migrated_clients
    return patch, migrated


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--clients", type=Path, required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--patch-output", type=Path, required=True)
    parser.add_argument("--clients-output", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(private_file(args.settings).read_text(encoding="utf-8"))
    clients = json.loads(private_file(args.clients).read_text(encoding="utf-8"))
    patch, migrated = prepare(settings, clients, args.hostname)
    write_new(args.patch_output, patch)
    try:
        write_new(args.clients_output, migrated)
    except Exception:
        args.patch_output.unlink(missing_ok=True)
        raise
    print("migration=prepared credentials=preserved secrets=not_printed panel=not_modified")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("migration=failed inspect_private_inputs_and_output_paths", file=sys.stderr)
        raise SystemExit(1)
