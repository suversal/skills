#!/usr/bin/env python3
"""Temporary REALITY client smoke test; no system proxy changes. Python >=3.9."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from panel_api import private_file


def client_config(record, name, port, key_field):
    clients = [c for c in record["clients"] if c["name"] == name]
    if len(clients) != 1:
        raise ValueError("unknown or duplicate client label")
    return {"log": {"loglevel": "warning"},
            "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "socks", "settings": {"udp": False}}],
            "outbounds": [{"tag": "proxy", "protocol": "vless",
                           "settings": {"vnext": [{"address": record["server_address"], "port": record["server_port"],
                                                   "users": [{"id": clients[0]["uuid"], "encryption": "none", "flow": "xtls-rprx-vision"}]}]},
                           "streamSettings": {"network": "tcp", "security": "reality",
                                              "realitySettings": {"serverName": record["sni"], "fingerprint": "chrome",
                                                                   key_field: record["public_key"], "shortId": record["short_id"], "spiderX": "/"}}}]}


def smoke(record, name, binary, key_field):
    # Caller must provide a trusted local binary; never download an unverified core here.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="vps-reality-smoke-") as tmp:
        root = Path(tmp)
        config = root / "client.json"
        config.write_text(json.dumps(client_config(record, name, port, key_field)), encoding="utf-8")
        config.chmod(0o600)
        subprocess.run([str(binary), "run", "-test", "-config", str(config)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=True)
        with (root / "client.log").open("wb") as log:
            proc = subprocess.Popen([str(binary), "run", "-config", str(config)], stdout=log, stderr=log)
            try:
                for _ in range(40):
                    if proc.poll() is not None:
                        raise ValueError("temporary client exited")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.25)
                else:
                    raise ValueError("temporary client did not listen")
                # Explicit proxy plus empty noproxy prevents inherited env from bypassing it.
                result = subprocess.run(["curl", "-4", "--fail", "--silent", "--show-error", "--noproxy", "",
                                         "--max-time", "25", "--socks5-hostname", "127.0.0.1:" + str(port),
                                         "https://api.ipify.org"], capture_output=True, text=True, timeout=30, check=True)
                actual = ipaddress.IPv4Address(result.stdout.strip())
                if actual != ipaddress.IPv4Address(record["expected_exit_ipv4"]):
                    raise ValueError("proxy exit differs from expected IPv4")
                if proc.poll() is not None:
                    raise ValueError("temporary client exited during test")
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
    return actual


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record", type=Path, required=True)
    p.add_argument("--client", required=True)
    p.add_argument("--xray", type=Path, required=True)
    p.add_argument("--key-field", choices=("password", "publicKey"), default="password")
    args = p.parse_args()
    os.umask(0o077)
    record = json.loads(private_file(args.record).read_text(encoding="utf-8"))
    smoke(record, args.client, args.xray, args.key_field)
    print("xray_client_config=valid reality_handshake=passed expected_exit_ipv4=matched")
    print("scope=current_host_only external_user_network_requires_separate_test")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("smoke=failed inspect_parameters_core_version_network; secrets_and_logs_not_printed", file=sys.stderr)
        sys.exit(1)
