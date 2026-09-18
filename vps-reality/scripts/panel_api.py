#!/usr/bin/env python3
"""Limited loopback-only 3x-ui API helper. No automatic retries or rollback."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import stat
import sys
import uuid
from urllib.parse import quote
import urllib.request


def private_file(path):
    path = Path(path)
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
        raise ValueError("requires a private regular file")
    if meta.st_uid != os.geteuid():
        raise ValueError("file owner mismatch")
    return path


def read_env(path):
    values = {}
    for line in private_file(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("invalid environment record")
        # Official installer values are single quoted/plain shell scalars. Never eval.
        parts = shlex.split(value, comments=True)
        if len(parts) != 1 or value.startswith("$'"):
            raise ValueError("unsupported environment quoting")
        values[key] = parts[0]
    return values


def connection(values):
    port = int(values["XUI_PANEL_PORT"])
    base_path = values["XUI_WEB_BASE_PATH"].strip("/")
    token = values["XUI_API_TOKEN"]
    if not 1024 <= port <= 65535 or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", base_path):
        raise ValueError("invalid panel port/path")
    if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("invalid API token")
    return "http://127.0.0.1:" + str(port) + "/" + base_path + "/panel/api", token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unexpected redirect; verify API base privately")


class API:
    def __init__(self, values):
        self.base, self.token = connection(values)
        # Ignore host proxy variables, keeping credentials on loopback.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, endpoint, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
        req = urllib.request.Request(self.base + endpoint, data=data, method=method,
                                     headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        with self.opener.open(req, timeout=20) as reply:
            payload = json.loads(reply.read(8 * 1024 * 1024))
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise ValueError("API rejected operation")
        return payload.get("obj")


def check_backup(path):
    path = private_file(path).resolve()
    if path == Path("/etc/x-ui/x-ui.db"):
        raise ValueError("live database is not a backup")
    con = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True)
    try:
        if con.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("invalid snapshot")
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"inbounds", "settings"}.issubset(tables):
            raise ValueError("not a 3x-ui snapshot")
    finally:
        con.close()


def decode(value):
    return json.loads(value) if isinstance(value, str) else value


def fresh_inbound(payload, existing):
    if existing:
        raise ValueError("fresh-deploy command refuses existing inbounds")
    if type(payload.get("port")) is not int or not 1 <= payload["port"] <= 65535 or payload.get("protocol") != "vless":
        raise ValueError("unexpected inbound protocol/port")
    stream = decode(payload["streamSettings"])
    if stream.get("security") != "reality" or stream.get("network") != "tcp":
        raise ValueError("REALITY required")


def new_client(payload, existing):
    client = payload["client"]
    ids = payload["inboundIds"]
    if not isinstance(ids, list) or len(ids) != 1 or type(ids[0]) is not int:
        raise ValueError("one inbound ID required")
    selected = [x for x in existing if x.get("id") == ids[0]]
    if len(selected) != 1 or selected[0].get("protocol") != "vless":
        raise ValueError("unknown VLESS inbound")
    if decode(selected[0]["streamSettings"]).get("security") != "reality":
        raise ValueError("target inbound is not REALITY")
    for required in ("id", "subId", "email"):
        if not isinstance(client.get(required), str) or not client[required]:
            raise ValueError("missing client identity")
    if client.get("flow") != "xtls-rprx-vision":
        raise ValueError("Vision flow required")
    uuid.UUID(client["id"])
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", client["subId"]):
        raise ValueError("client subId must be a strong random identifier")
    if type(client.get("totalGB")) is not int or client["totalGB"] <= 0:
        raise ValueError("explicit positive quota bytes required")
    if type(client.get("expiryTime")) is not int or client["expiryTime"] < 0:
        raise ValueError("explicit expiry milliseconds required")
    for inbound in existing:
        for old in decode(inbound["settings"]).get("clients", []):
            if any(str(old.get(key, "")).casefold() == client[key].casefold() for key in ("id", "subId", "email")):
                raise ValueError("duplicate credential or client name")


def fresh_host(payload, inbounds, existing_hosts):
    if set(payload) != {"inboundIds", "remark", "hosts", "port", "security", "tags"}:
        raise ValueError("unexpected Hosts payload fields")
    ids = payload["inboundIds"]
    if not isinstance(ids, list) or len(ids) != 1 or type(ids[0]) is not int:
        raise ValueError("replace pending inboundIds with one created inbound ID")
    selected = [x for x in inbounds if x.get("id") == ids[0]]
    if len(selected) != 1 or selected[0].get("protocol") != "vless":
        raise ValueError("unknown VLESS inbound")
    stream = decode(selected[0]["streamSettings"])
    if stream.get("security") != "reality" or stream.get("network") != "tcp":
        raise ValueError("Hosts target must be a TCP REALITY inbound")
    hosts = payload["hosts"]
    if not isinstance(hosts, list) or len(hosts) != 1 or not isinstance(hosts[0], str) or not hosts[0]:
        raise ValueError("one public host or address required")
    port = payload["port"]
    if type(port) is not int or not 1 <= port <= 65535 or payload["security"] != "same":
        raise ValueError("invalid public port/security")
    if not isinstance(payload["remark"], str) or not payload["remark"]:
        raise ValueError("host remark required")
    if not isinstance(payload["tags"], list) or any(not isinstance(x, str) or not x for x in payload["tags"]):
        raise ValueError("invalid host tags")
    if existing_hosts:
        raise ValueError("refusing to replace or duplicate existing Hosts entries")


def save_output(path, value):
    # Refuse preexisting paths; umask plus O_EXCL prevents casual leakage/overwrite.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=("list", "settings", "list-hosts", "merge-settings", "add-inbound", "add-client", "add-host"))
    p.add_argument("--env", type=Path, default=Path("/etc/x-ui/install-result.env"))
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--backup", type=Path)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    read_only = args.operation in ("list", "settings", "list-hosts")
    if not read_only and not args.apply:
        print("panel=not_modified use_apply_only_after_authorization_schema_review_and_backup")
        return
    if not read_only:
        if not args.input or not args.backup:
            p.error("write requires --input and --backup")
        check_backup(args.backup)
        payload = json.loads(private_file(args.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    # Reserve read outputs before any request; don't lose a response to overwrite refusal.
    if args.output and args.output.exists():
        raise ValueError("output exists")
    api = API(read_env(args.env))
    if args.operation == "list":
        result = api.call("/inbounds/list")
    elif args.operation == "settings":
        result = api.call("/setting/all", "POST")
    elif args.operation == "list-hosts":
        result = api.call("/hosts/list")
    elif args.operation == "merge-settings":
        current = api.call("/setting/all", "POST")
        if not isinstance(current, dict) or not set(payload).issubset(current):
            raise ValueError("unknown settings fields; review installed schema")
        forbidden = {"webPort", "webBasePath", "webDomain", "webCertFile", "webKeyFile"}
        if forbidden.intersection(payload):
            raise ValueError("this helper does not change panel identity or TLS paths")
        if payload.get("webListen", current.get("webListen")) != "127.0.0.1" or payload.get("subListen", current.get("subListen")) != "127.0.0.1":
            raise ValueError("only loopback listeners permitted")
        current.update(payload)
        result = api.call("/setting/update", "POST", current)
    else:
        existing = api.call("/inbounds/list")
        if not isinstance(existing, list):
            raise ValueError("unexpected inbound schema")
        if args.operation == "add-inbound":
            fresh_inbound(payload, existing)
            result = api.call("/inbounds/add", "POST", payload)
        elif args.operation == "add-client":
            new_client(payload, existing)
            result = api.call("/clients/add", "POST", payload)
        else:
            ids = payload.get("inboundIds")
            inbound_id = ids[0] if isinstance(ids, list) and len(ids) == 1 and type(ids[0]) is int else 0
            existing_hosts = api.call("/hosts/byInbound/" + str(inbound_id)) if inbound_id else None
            if not isinstance(existing_hosts, list):
                raise ValueError("unexpected Hosts API schema")
            fresh_host(payload, existing, existing_hosts)
            result = api.call("/hosts/add", "POST", payload)
    if args.output:
        save_output(args.output, result)
    print("api=success operation=" + args.operation + " secrets=not_printed")
    if not read_only:
        print("next=read_back_and_verify_services_subscriptions_and_real_handshake")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # HTTP errors can contain private API paths or server credential-bearing messages.
        print("api=failed_or_unknown inspect_privately_read_back_before_retry; no_automatic_rollback", file=sys.stderr)
        sys.exit(1)
