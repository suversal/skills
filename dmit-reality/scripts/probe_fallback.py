#!/usr/bin/env python3
"""Bounded unauthenticated TLS HEAD evidence from ONE owned VPS. Preview by default.

No REALITY credentials, retries, redirects, body downloads, proxy environment,
certificate bypass, automatic mitigation, or claim that an endpoint is safe.
"""
import argparse
import ipaddress
import json
import re
import socket
import ssl
import sys
import time

from render_bundle import hostname

MAX_HEADERS = 8192


class UnsupportedTLSRuntime(ValueError):
    pass


def tls_context():
    if not ssl.HAS_TLSv1_3 or not ssl.HAS_ALPN:
        raise UnsupportedTLSRuntime("TLS 1.3 and ALPN support required")
    context = ssl.create_default_context()
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.set_alpn_protocols(["http/1.1"])
    except (ValueError, NotImplementedError):
        raise UnsupportedTLSRuntime("TLS 1.3 and ALPN support required") from None
    return context


def validate(args):
    address = ipaddress.ip_address(args.server_ip)
    # Require numeric public IP: avoids DNS rebinding, loopback and metadata endpoints.
    if not address.is_global:
        raise ValueError("a verified public server IP is required")
    if not 1 <= args.port <= 65535 or not 1 <= args.timeout <= 10:
        raise ValueError("invalid port or timeout")
    hostname(args.allowed_sni)
    if args.test_domain:
        hostname(args.test_domain)
        if args.test_domain.lower() == args.allowed_sni.lower():
            raise ValueError("alternate test domain must differ")
    # A public, side-effect-free resource only; don't accept URLs, queries or secrets.
    if not re.fullmatch(r"/[A-Za-z0-9/_\-.]{0,127}", args.path) or ".." in args.path or args.path.startswith("//"):
        raise ValueError("use a short public path without query, fragment or traversal")
    if bool(args.marker_header) != bool(args.marker_value):
        raise ValueError("marker header and value must be supplied together")
    if args.marker_header:
        if not re.fullmatch(r"X-[A-Za-z0-9-]{1,60}", args.marker_header, re.I):
            raise ValueError("use a dedicated public X- response marker")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{8,128}", args.marker_value):
            raise ValueError("marker must be a public non-secret identifier")
    if args.run:
        if not args.confirm_server or ipaddress.ip_address(args.confirm_server) != address:
            raise ValueError("run requires matching --confirm-server")
        if args.test_domain and (args.confirm_test_domain or "").lower() != args.test_domain.lower():
            raise ValueError("alternate tests require matching --confirm-test-domain")


def cases(args):
    result = [("allowed_sni_same_host", args.allowed_sni, args.allowed_sni)]
    if args.test_domain:
        result += [("alternate_sni_same_host", args.test_domain, args.test_domain),
                   ("allowed_sni_alternate_host", args.allowed_sni, args.test_domain)]
    return result


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("probe deadline")
    return value


def read_headers(tls, deadline):
    data = bytearray()
    while len(data) < MAX_HEADERS:
        tls.settimeout(remaining(deadline))
        chunk = tls.recv(min(1024, MAX_HEADERS - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b"\r\n\r\n" in data:
            return bytes(data).split(b"\r\n\r\n", 1)[0], True
    return bytes(data), False


def summarize(header_bytes, complete, marker_header=None, marker_value=None):
    summary = {"http_status": None, "headers_complete": complete,
               "cf_header_signal": False, "marker_matched": False}
    if not complete:
        return summary
    lines = header_bytes.decode("iso-8859-1").split("\r\n")
    status = re.fullmatch(r"HTTP/1\.[01] ([1-5][0-9]{2})(?: .*|)", lines[0])
    if not status:
        return summary
    summary["http_status"] = int(status.group(1))
    headers = {}
    for line in lines[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers.setdefault(key.lower().strip(), []).append(value.strip())
    summary["cf_header_signal"] = bool("cf-ray" in headers or "cf-cache-status" in headers or
                                        any("cloudflare" in x.lower() for x in headers.get("server", [])))
    # Require one exact expected header; generic status/Server/Cookie isn't a proof marker.
    if marker_header:
        summary["marker_matched"] = headers.get(marker_header.lower()) == [marker_value]
    return summary


def probe(args, case):
    name, sni, host = case
    result = {"case": name, "tls_verified": False, "http_status": None,
              "headers_complete": False, "cf_header_signal": False,
              "marker_matched": False, "outcome": "inconclusive"}
    deadline = time.monotonic() + args.timeout
    context = tls_context()
    try:
        with socket.create_connection((args.server_ip, args.port), timeout=remaining(deadline)) as raw:
            raw.settimeout(remaining(deadline))
            with context.wrap_socket(raw, server_hostname=sni) as tls:
                result["tls_verified"] = True
                request = (f"HEAD {args.path} HTTP/1.1\r\nHost: {host}\r\n"
                           "User-Agent: dmit-fallback-audit/1.0\r\nConnection: close\r\n\r\n")
                tls.settimeout(remaining(deadline))
                tls.sendall(request.encode("ascii"))
                data, complete = read_headers(tls, deadline)
                result.update(summarize(data, complete, args.marker_header, args.marker_value))
                if result["http_status"] is not None:
                    result["outcome"] = "http_response_observed"
    except ssl.SSLCertVerificationError:
        result["reason"] = "certificate_verification_failed_not_a_security_pass"
    except (OSError, ssl.SSLError, TimeoutError):
        result["reason"] = "connection_or_tls_failed_not_a_security_pass"
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server-ip", required=True)
    p.add_argument("--port", type=int, default=443)
    p.add_argument("--allowed-sni", required=True)
    p.add_argument("--test-domain")
    p.add_argument("--path", default="/")
    p.add_argument("--timeout", type=int, default=8)
    p.add_argument("--marker-header")
    p.add_argument("--marker-value")
    p.add_argument("--run", action="store_true")
    p.add_argument("--confirm-server")
    p.add_argument("--confirm-test-domain")
    args = p.parse_args()
    validate(args)
    plan = cases(args)
    if not args.run:
        print(json.dumps({"mode": "preview", "network": "not_accessed", "requests_planned": len(plan),
                          "cases": [x[0] for x in plan], "timeout_per_request_seconds": args.timeout,
                          "max_response_headers_bytes": MAX_HEADERS, "security_assessment": "not_performed"}))
        return 0
    results = [probe(args, case) for case in plan]
    print(json.dumps({"mode": "evidence_only", "requests_attempted": len(results),
                      "security_assessment": "requires_review", "results": results}))
    # Exit 0 means the bounded collection finished, never "safe".
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except UnsupportedTLSRuntime:
        print("probe=not_run reason=python_openssl_tls13_alpn_required; do_not_disable_verification", file=sys.stderr)
        sys.exit(2)
    except (OSError, ValueError, TypeError):
        print("probe=refused_or_failed verify_scope_and_parameters; no_raw_response_output", file=sys.stderr)
        sys.exit(2)
