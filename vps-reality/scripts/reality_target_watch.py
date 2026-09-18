#!/usr/bin/env python3
"""Monitor a REALITY disguise target and send stateful Telegram alerts."""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import stat
import shlex
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


CONFIG_PATH = Path("/etc/x-ui/reality-watch.env")
STATE_PATH = Path("/var/lib/reality-target-watch/state.json")
ACTIVE_PROFILE_PATH = Path("/etc/x-ui/reality-active-target.env")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        parts = shlex.split(raw_value, posix=True)
        values[key] = parts[0] if parts else ""
    return values


def require_config() -> dict[str, str]:
    meta = CONFIG_PATH.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077 or meta.st_uid != os.geteuid():
        raise SystemExit("monitor_config=requires_private_owned_regular_file")
    cfg = read_env(CONFIG_PATH)
    required = ("WATCH_DOMAIN", "WATCH_IP", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise SystemExit("monitor_config=missing keys=" + ",".join(missing))
    try:
        ipaddress.ip_address(cfg["WATCH_IP"])
    except ValueError as exc:
        raise SystemExit("monitor_config=invalid WATCH_IP") from exc
    cfg.setdefault("FAILURE_THRESHOLD", "3")
    cfg.setdefault("RECOVERY_THRESHOLD", "2")
    cfg.setdefault("CERT_WARN_DAYS", "14")
    cfg.setdefault("CONNECT_TIMEOUT_SECONDS", "8")
    cfg.setdefault("TARGET_PORT", "443")
    cfg.setdefault("LISTEN_PORT", "443")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", cfg["WATCH_DOMAIN"]):
        raise SystemExit("monitor_config=invalid_domain")
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{30,}", cfg["TELEGRAM_BOT_TOKEN"]):
        raise SystemExit("monitor_config=invalid_token_format")
    if not re.fullmatch(r"-?[0-9]+", cfg["TELEGRAM_CHAT_ID"]):
        raise SystemExit("monitor_config=invalid_chat_id")
    for key in ("FAILURE_THRESHOLD", "RECOVERY_THRESHOLD", "CERT_WARN_DAYS", "CONNECT_TIMEOUT_SECONDS"):
        if not cfg[key].isdigit() or not 1 <= int(cfg[key]) <= 120:
            raise SystemExit("monitor_config=invalid_threshold_or_timeout")
    for key in ("TARGET_PORT", "LISTEN_PORT"):
        if not cfg[key].isdigit() or not 1 <= int(cfg[key]) <= 65535:
            raise SystemExit("monitor_config=invalid_port")
    return cfg


def active_profile() -> str:
    return read_env(ACTIVE_PROFILE_PATH).get("ACTIVE_TARGET_PROFILE", "unknown")


def run_quiet(command: list[str]) -> bool:
    return subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def run_has_output(command: list[str]) -> bool:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


def check_target(cfg: dict[str, str]) -> dict[str, object]:
    domain = cfg["WATCH_DOMAIN"]
    target_ip = cfg["WATCH_IP"]
    target_port = int(cfg["TARGET_PORT"])
    listen_port = int(cfg["LISTEN_PORT"])
    timeout = float(cfg["CONNECT_TIMEOUT_SECONDS"])
    result: dict[str, object] = {
        "domain": domain,
        "ip": target_ip,
        "tcp": False,
        "tls13": False,
        "san": False,
        "cert_days": -1,
        "http_status": 0,
        "dns": False,
        "x_ui": False,
        "listener": False,
        "listen_port": listen_port,
        "errors": [],
    }

    result["x_ui"] = run_quiet(["systemctl", "is-active", "--quiet", "x-ui"])
    result["listener"] = run_has_output(
        ["ss", "-H", "-lnt", "sport", "=", ":" + str(listen_port)]
    )

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(domain, target_port, type=socket.SOCK_STREAM)
        }
        result["dns"] = target_ip in addresses
        if not result["dns"]:
            result["errors"].append("dns_ip_changed")
    except OSError:
        result["errors"].append("dns_failed")

    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    try:
        with socket.create_connection((target_ip, target_port), timeout=timeout) as raw_sock:
            result["tcp"] = True
            with context.wrap_socket(raw_sock, server_hostname=domain) as tls_sock:
                result["tls13"] = tls_sock.version() == "TLSv1.3"
                cert = tls_sock.getpeercert()
                # create_default_context() verifies hostname/SAN during wrap_socket().
                result["san"] = True
                expires = dt.datetime.fromtimestamp(
                    ssl.cert_time_to_seconds(cert["notAfter"]), tz=dt.timezone.utc
                )
                remaining = expires - dt.datetime.now(dt.timezone.utc)
                result["cert_days"] = max(-1, remaining.days)
    except (OSError, ssl.SSLError, ssl.CertificateError, KeyError, ValueError) as exc:
        result["errors"].append("tls_or_certificate_failed")

    try:
        with socket.create_connection((target_ip, target_port), timeout=timeout) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=domain) as tls_sock:
                request = (
                    f"GET / HTTP/1.1\r\nHost: {domain}\r\n"
                    "User-Agent: reality-target-watch/1.0\r\n"
                    "Accept: text/html,*/*;q=0.1\r\nConnection: close\r\n\r\n"
                )
                tls_sock.sendall(request.encode("ascii"))
                response = tls_sock.recv(4096).split(b"\r\n", 1)[0]
                parts = response.decode("ascii", errors="replace").split()
                if len(parts) >= 2 and parts[1].isdigit():
                    result["http_status"] = int(parts[1])
    except (OSError, ssl.SSLError):
        result["errors"].append("https_failed")

    status = int(result["http_status"])
    result["healthy"] = all(
        (
            result["tcp"],
            result["tls13"],
            result["san"],
            int(result["cert_days"]) >= 0,
            200 <= status < 400,
            result["dns"],
            result["x_ui"],
            result["listener"],
        )
    )
    return result


def telegram_send(cfg: dict[str, str], message: str) -> None:
    # urllib keeps the bot token out of process arguments and shell history.
    url = "https://api.telegram.org/bot" + cfg["TELEGRAM_BOT_TOKEN"] + "/sendMessage"
    body = urllib.parse.urlencode(
        {
            "chat_id": cfg["TELEGRAM_CHAT_ID"],
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("ok"):
            raise RuntimeError("Telegram returned ok=false")
    except urllib.error.HTTPError as exc:
        description = ""
        try:
            error_payload = json.loads(exc.read(4096).decode("utf-8"))
            description = str(error_payload.get("description") or "").casefold()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        if exc.code in (401, 404):
            reason = "invalid_bot_token"
        elif "chat not found" in description:
            reason = "chat_not_found_start_the_bot_or_check_chat_id"
        elif "bot was blocked" in description:
            reason = "bot_blocked_by_recipient"
        elif exc.code == 403:
            reason = "telegram_chat_permission_denied"
        else:
            reason = f"telegram_http_{exc.code}"
        raise RuntimeError(f"telegram_delivery_failed reason={reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("telegram_delivery_failed reason=network_error") from exc
    except Exception as exc:
        raise RuntimeError("telegram_delivery_failed") from exc


def load_state() -> dict[str, object]:
    if not STATE_PATH.exists():
        return {
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "alert_open": False,
            "cert_warning_for": "",
        }
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "alert_open": False,
            "cert_warning_for": "",
        }


def save_state(state: dict[str, object]) -> None:
    STATE_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="state.", dir=STATE_PATH.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(state, target, ensure_ascii=False, separators=(",", ":"))
            target.write("\n")
        os.replace(temp_path, STATE_PATH)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def failure_summary(result: dict[str, object]) -> str:
    failed = []
    for key in ("tcp", "tls13", "san", "dns", "x_ui", "listener"):
        if not result[key]:
            failed.append(key)
    if not 200 <= int(result["http_status"]) < 400:
        failed.append("https")
    if int(result["cert_days"]) < 0:
        failed.append("certificate")
    return ", ".join(failed) or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-alert", action="store_true")
    parser.add_argument("--no-alert", action="store_true")
    args = parser.parse_args()

    cfg = require_config()
    profile = active_profile()
    if args.test_alert:
        telegram_send(
            cfg,
            "[TEST] VPS REALITY 监控已连接\n"
            f"监控目标: {cfg['WATCH_DOMAIN']} ({cfg['WATCH_IP']}:{cfg['TARGET_PORT']})\n"
            f"本机监听: {cfg['LISTEN_PORT']}/TCP\n"
            f"当前档位: {profile}\n"
            "此监控只发送告警；Token 是否另有面板管理权限取决于其他集成。",
        )
        print("telegram_test=delivered")
        return 0

    result = check_target(cfg)
    if args.no_alert:
        print("status=" + ("healthy" if result["healthy"] else "failed") + " alerts=disabled state=unchanged")
        return 0 if result["healthy"] else 1
    state = load_state()
    healthy = bool(result["healthy"])
    if healthy:
        state["consecutive_successes"] = int(state.get("consecutive_successes", 0)) + 1
        state["consecutive_failures"] = 0
        if state.get("alert_open") and int(state["consecutive_successes"]) >= int(
            cfg["RECOVERY_THRESHOLD"]
        ):
            if not args.no_alert:
                telegram_send(
                    cfg,
                    "[RECOVERED] VPS REALITY 目标已恢复\n"
                    f"目标: {result['domain']} ({result['ip']})\n"
                    f"当前档位: {profile}\n"
                    f"HTTPS: {result['http_status']}，证书剩余约 {result['cert_days']} 天。",
                )
            state["alert_open"] = False
    else:
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        state["consecutive_successes"] = 0
        if (
            not state.get("alert_open")
            and int(state["consecutive_failures"]) >= int(cfg["FAILURE_THRESHOLD"])
        ):
            impact = "请核对当前入站是否使用该目标，按已授权回滚预案处理；监控不会自动切换。"
            if not args.no_alert:
                telegram_send(
                    cfg,
                    "[ALERT] VPS REALITY 目标连续检查失败\n"
                    f"目标: {result['domain']} ({result['ip']})\n"
                    f"失败项: {failure_summary(result)}\n"
                    f"当前档位: {profile}\n{impact}",
                )
            state["alert_open"] = True

    cert_days = int(result["cert_days"])
    warning_key = str(result["domain"]) if 0 <= cert_days <= int(
        cfg["CERT_WARN_DAYS"]
    ) else ""
    if warning_key and state.get("cert_warning_for") != warning_key:
        if not args.no_alert:
            telegram_send(
                cfg,
                "[WARNING] REALITY 目标证书即将到期\n"
                f"目标: {result['domain']} ({result['ip']})\n"
                f"证书剩余约 {cert_days} 天，请确认站点已续证。",
            )
        state["cert_warning_for"] = warning_key
    elif not warning_key and cert_days > int(cfg["CERT_WARN_DAYS"]):
        state["cert_warning_for"] = ""

    state["last_healthy"] = healthy
    state["last_checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    state["last_http_status"] = result["http_status"]
    state["last_cert_days"] = result["cert_days"]
    save_state(state)
    print(
        "status={status} domain={domain} ip={ip} tls13={tls} cert_days={days} "
        "http={http} dns={dns} x_ui={xui} listen_port={listen_port} listener={listener} failures={failures}".format(
            status="healthy" if healthy else "failed",
            domain=result["domain"],
            ip=result["ip"],
            tls=str(result["tls13"]).lower(),
            days=result["cert_days"],
            http=result["http_status"],
            dns=str(result["dns"]).lower(),
            xui=str(result["x_ui"]).lower(),
            listen_port=result["listen_port"],
            listener=str(result["listener"]).lower(),
            failures=state["consecutive_failures"],
        )
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError):
        print("monitor=failed inspect_config_network_and_delivery_privately", file=sys.stderr)
        raise SystemExit(1) from None
