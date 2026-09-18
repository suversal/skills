#!/usr/bin/env python3
"""Render a NEW private bundle; no panel/network/OS mutations. Python >=3.9."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import quote, urlencode
import uuid


def hostname(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError("invalid hostname")
    labels = value.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", x) for x in labels):
        raise ValueError("invalid hostname")
    return value


def integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid " + field)
    return value


def validate(c):
    expected = {"provider", "network_mode", "control_plane_mode", "server_address",
                "expected_exit_ipv4", "ssh_port", "reality_listen_port", "reality_public_port",
                "panel_domain", "subscription_domain", "subscription_port", "reality_target",
                "reality_sni", "min_client_ver", "inbound_remark", "inbound_quota_gib",
                "traffic_reset_day", "clients"}
    if not isinstance(c, dict) or set(c) != expected:
        raise ValueError("configuration keys missing or unknown")
    if not isinstance(c["provider"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,31}", c["provider"]):
        raise ValueError("provider requires a simple public label")
    if c["network_mode"] not in {"direct", "nat"}:
        raise ValueError("network_mode must be direct or nat")
    if c["control_plane_mode"] not in {"cloudflare-tunnel", "ssh-only"}:
        raise ValueError("control_plane_mode must be cloudflare-tunnel or ssh-only")
    ipaddress.IPv4Address(c["server_address"])
    ipaddress.IPv4Address(c["expected_exit_ipv4"])
    if c["control_plane_mode"] == "cloudflare-tunnel":
        hostname(c["panel_domain"])
        hostname(c["subscription_domain"])
        if c["panel_domain"] == c["subscription_domain"]:
            raise ValueError("panel and subscription domains must differ")
    elif c["panel_domain"] or c["subscription_domain"]:
        raise ValueError("ssh-only requires empty panel and subscription domains")
    hostname(c["reality_sni"])
    target_host, target_port = c["reality_target"].rsplit(":", 1)
    try:
        ipaddress.IPv4Address(target_host)
    except ValueError:
        hostname(target_host)
    integer(int(target_port), 1, 65535, "target port")
    ssh_port = integer(c["ssh_port"], 1, 65535, "ssh_port")
    listen_port = integer(c["reality_listen_port"], 1, 65535, "reality_listen_port")
    public_port = integer(c["reality_public_port"], 1, 65535, "reality_public_port")
    sub_port = integer(c["subscription_port"], 1024, 65535, "subscription_port")
    if c["network_mode"] == "direct" and listen_port != public_port:
        raise ValueError("direct mode requires matching listen and public ports")
    if ssh_port == public_port:
        raise ValueError("public SSH and REALITY ports must differ")
    if sub_port == listen_port:
        raise ValueError("local subscription and REALITY listen ports must differ")
    integer(c["traffic_reset_day"], 1, 31, "traffic_reset_day (1..31)")
    integer(c["inbound_quota_gib"], 1, 1000000, "inbound_quota_gib")
    if not isinstance(c["min_client_ver"], str) or (c["min_client_ver"] and not re.fullmatch(r"\d+\.\d+\.\d+", c["min_client_ver"])):
        raise ValueError("min_client_ver must be empty or an explicitly reviewed x.y.z")
    if not isinstance(c["inbound_remark"], str) or not 1 <= len(c["inbound_remark"]) <= 100:
        raise ValueError("invalid inbound_remark")
    if any(ord(ch) < 32 for ch in c["inbound_remark"]):
        raise ValueError("invalid inbound_remark control character")
    if not isinstance(c["clients"], list) or not 1 <= len(c["clients"]) <= 20:
        raise ValueError("expected 1..20 personal clients")
    names = set()
    for client in c["clients"]:
        if not isinstance(client, dict) or set(client) != {"name", "quota_gib", "expiry_ms", "limit_ip"}:
            raise ValueError("invalid client keys")
        name = client["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", name):
            raise ValueError("client name requires a simple non-secret label")
        if name.casefold() in names:
            raise ValueError("duplicate client name")
        names.add(name.casefold())
        integer(client["quota_gib"], 1, c["inbound_quota_gib"], "client quota_gib")
        integer(client["expiry_ms"], 0, 4102444800000, "expiry_ms")
        if 0 < client["expiry_ms"] < 1000000000000:
            raise ValueError("expiry_ms looks like seconds rather than milliseconds")
        integer(client["limit_ip"], 0, 100, "limit_ip")
    return c


def keypair(binary):
    result = subprocess.run([str(binary), "x25519"], text=True, capture_output=True, timeout=20, check=True)
    fields = dict(line.split(":", 1) for line in result.stdout.splitlines() if ":" in line)
    private = fields.get("PrivateKey", "").strip()
    public = next((fields[k].strip() for k in ("Password (PublicKey)", "PublicKey", "Password") if k in fields), "")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{43}", x) for x in (private, public)):
        raise ValueError("unrecognized xray x25519 output; inspect installed version privately")
    return private, public


def build(c, private, public, routing):
    short_id = secrets.token_hex(8)
    paths = {kind: "/" + prefix + "-" + secrets.token_hex(10) + "/"
             for kind, prefix in (("raw", "r"), ("json", "j"), ("clash", "m"))}
    clients = []
    records = []
    for person in c["clients"]:
        identity = str(uuid.uuid4())
        sub_id = secrets.token_hex(12)
        clients.append({"id": identity, "email": person["name"], "flow": "xtls-rprx-vision",
                        "limitIp": person["limit_ip"], "totalGB": person["quota_gib"] * 1024**3,
                        "expiryTime": person["expiry_ms"], "enable": True, "tgId": 0,
                        "subId": sub_id, "comment": "Independent personal credential", "reset": 0})
        query = urlencode({"encryption": "none", "flow": "xtls-rprx-vision", "security": "reality",
                           "sni": c["reality_sni"], "fp": "chrome", "pbk": public,
                           "sid": short_id, "spx": "/", "type": "tcp", "headerType": "none"})
        vless_uri = ("vless://" + identity + "@" + c["server_address"] + ":" +
                     str(c["reality_public_port"]) + "?" + query + "#" + quote(person["name"], safe=""))
        if c["control_plane_mode"] == "cloudflare-tunnel":
            urls = {k: "https://" + c["subscription_domain"] + p + sub_id for k, p in paths.items()}
            local_urls = {}
        else:
            urls = {}
            local_urls = {k: "http://127.0.0.1:" + str(c["subscription_port"]) + p + sub_id
                          for k, p in paths.items()}
        records.append({"name": person["name"], "uuid": identity, "sub_id": sub_id,
                        "subscription_urls": urls, "local_subscription_urls": local_urls,
                        "vless_uri": vless_uri})
    reality = {"show": False, "xver": 0, "target": c["reality_target"],
               "serverNames": [c["reality_sni"]], "privateKey": private,
               "minClientVer": c["min_client_ver"], "maxClientVer": "", "maxTimediff": 0,
               "shortIds": [short_id], "mldsa65Seed": "",
               "settings": {"publicKey": public, "fingerprint": "chrome", "serverName": "",
                            "spiderX": "/", "mldsa65Verify": ""}}
    stream = {"network": "tcp", "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
              "security": "reality", "realitySettings": reality}
    inbound = {"up": 0, "down": 0, "total": c["inbound_quota_gib"] * 1024**3,
               "remark": c["inbound_remark"], "enable": True, "expiryTime": 0,
               "trafficReset": "monthly", "trafficResetDay": c["traffic_reset_day"],
               "lastTrafficResetTime": 0, "listen": "", "port": c["reality_listen_port"], "protocol": "vless",
               "settings": json.dumps({"clients": clients, "decryption": "none", "encryption": "none"}),
               "streamSettings": json.dumps(stream),
               "sniffing": json.dumps({"enabled": True, "destOverride": ["http", "tls", "quic"], "metadataOnly": False, "routeOnly": False}),
               "tag": "inbound-vless-reality-" + str(c["reality_listen_port"]), "shareAddrStrategy": "custom",
               "shareAddr": c["server_address"], "subSortIndex": 1, "disableFlow": False}
    patch = {"webListen": "127.0.0.1", "subListen": "127.0.0.1", "subEnable": True,
             "subPort": c["subscription_port"], "subDomain": c["subscription_domain"],
             "subPath": paths["raw"], "subJsonEnable": True, "subJsonPath": paths["json"],
             "subClashEnable": True, "subClashPath": paths["clash"], "subEncrypt": True,
             "subUpdates": 12, "subTitle": "Private REALITY", "subClashEnableRouting": True,
             "subClashRules": routing}
    if c["control_plane_mode"] == "cloudflare-tunnel":
        base = "https://" + c["subscription_domain"]
    else:
        base = "http://127.0.0.1:" + str(c["subscription_port"])
    for field, kind in (("subURI", "raw"), ("subJsonURI", "json"), ("subClashURI", "clash")):
        patch[field] = base + paths[kind]
    record = {"provider": c["provider"], "network_mode": c["network_mode"],
              "control_plane_mode": c["control_plane_mode"], "server_address": c["server_address"],
              "server_port": c["reality_public_port"], "listen_port": c["reality_listen_port"],
              "expected_exit_ipv4": c["expected_exit_ipv4"], "sni": c["reality_sni"],
              "public_key": public, "short_id": short_id, "clients": records}
    artifacts = {"inbound.json": inbound, "settings.patch.json": patch, "clients.private.json": record}
    if c["network_mode"] == "nat":
        # Current 3x-ui Hosts API supersedes legacy streamSettings.externalProxy.
        # inboundIds stays empty until the freshly-created inbound is read back.
        artifacts["hosts.pending.json"] = {
            "inboundIds": [],
            "remark": "NAT public endpoint",
            "hosts": [c["server_address"]],
            "port": c["reality_public_port"],
            "security": "same",
            "tags": ["NAT"],
        }
    return artifacts


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--check", action="store_true")
    p.add_argument("--xray", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    c = validate(json.loads(args.config.read_text(encoding="utf-8")))
    if args.check:
        print("parameters=valid network=not_checked secrets=not_generated")
        return
    if not args.xray or not args.output:
        p.error("render requires --xray and --output")
    if args.output.exists():
        raise ValueError("output already exists; refusing credential regeneration/overwrite")
    if not ipaddress.IPv4Address(c["server_address"]).is_global:
        raise ValueError("server_address must be a verified public address, not the example")
    domains = [c["reality_sni"]]
    if c["control_plane_mode"] == "cloudflare-tunnel":
        domains.extend([c["panel_domain"], c["subscription_domain"]])
    if any(value.endswith(".example.com") or value == "example.com" for value in domains):
        raise ValueError("replace example domains before rendering")
    private, public = keypair(args.xray)
    routing = (Path(__file__).resolve().parent.parent / "assets/mihomo-routing.yaml").read_text(encoding="utf-8")
    artifacts = build(c, private, public, routing)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, value in artifacts.items():
        write_new(args.output / name, value)
    print("bundle=generated mode=private_700_600 panel=not_modified")
    print("target_safety=not_checked follow_sni_fallback_review_before_handoff")
    print("bundle_directory=" + str(args.output.resolve()))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("bundle=failed check_parameters_paths_and_xray_version; no_secret_output", file=sys.stderr)
        sys.exit(1)
