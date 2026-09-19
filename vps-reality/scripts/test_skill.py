#!/usr/bin/env python3
"""Offline behavioral tests: no SSH, external HTTP, service changes or real secrets."""
import copy
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from argparse import Namespace
import ssl

import panel_api as panel
import reality_target_watch as watch
import render_bundle as render
import smoke_xray as smoke
import sqlite_snapshot as backup
import probe_fallback as fallback
import platform_profile as profile

ROOT = Path(__file__).resolve().parent.parent


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads((ROOT / "assets/deployment.example.json").read_text())

    def bundle(self):
        return render.build(self.c, "A" * 43, "B" * 43, (ROOT / "assets/mihomo-routing.yaml").read_text())

    def test_complete_config_and_safety_defaults(self):
        render.validate(self.c)
        bundle = self.bundle()
        inbound = bundle["inbound.json"]
        settings = json.loads(inbound["settings"])
        stream = json.loads(inbound["streamSettings"])
        self.assertEqual(inbound["total"], 900 * 1024**3)
        self.assertEqual(stream["security"], "reality")
        self.assertEqual(inbound["trafficResetDay"], self.c["traffic_reset_day"])
        self.assertEqual(inbound["port"], self.c["reality_listen_port"])
        self.assertEqual(bundle["clients.private.json"]["server_port"], self.c["reality_public_port"])
        self.assertEqual(bundle["settings.patch.json"]["webListen"], "127.0.0.1")
        self.assertEqual(bundle["settings.patch.json"]["subListen"], "127.0.0.1")
        clients = settings["clients"]
        self.assertEqual(len(set(x["id"] for x in clients)), len(clients))
        self.assertEqual(len(set(x["subId"] for x in clients)), len(clients))
        self.assertTrue(all(x["flow"] == "xtls-rprx-vision" for x in clients))
        record_text = json.dumps(bundle["clients.private.json"])
        self.assertNotIn("A" * 43, record_text)  # private server key never in client record
        self.assertTrue(all(x["vless_uri"].startswith("vless://") for x in bundle["clients.private.json"]["clients"]))
        self.assertEqual(self.c["control_plane_mode"], "ssh-only")
        self.assertTrue(all(not x["subscription_urls"] for x in bundle["clients.private.json"]["clients"]))
        self.assertTrue(all(x["local_subscription_urls"] for x in bundle["clients.private.json"]["clients"]))
        self.assertNotEqual(bundle["clients.private.json"], self.bundle()["clients.private.json"])

    def test_reject_invalid_or_ambiguous_input(self):
        for field, value in (("traffic_reset_day", 32), ("ssh_port", 443),
                             ("subscription_port", 22), ("inbound_quota_gib", True),
                             ("panel_domain", "x.example.com/path"), ("reality_sni", "example.com\r\nHost:x")):
            c = copy.deepcopy(self.c)
            c[field] = value
            with self.assertRaises(ValueError):
                render.validate(c)
        self.c["clients"][1]["name"] = "OWNER"
        with self.assertRaises(ValueError):
            render.validate(self.c)

    def test_direct_nat_and_control_plane_modes(self):
        direct = copy.deepcopy(self.c)
        render.validate(direct)
        with self.assertRaises(ValueError):
            direct["reality_public_port"] = 2443
            render.validate(direct)

        nat = copy.deepcopy(self.c)
        nat.update(network_mode="nat", reality_listen_port=2081, reality_public_port=34438)
        render.validate(nat)
        bundle = render.build(nat, "A" * 43, "B" * 43, "")
        inbound = bundle["inbound.json"]
        stream = json.loads(inbound["streamSettings"])
        panel.fresh_inbound(inbound, [])
        self.assertEqual(inbound["port"], 2081)
        self.assertNotIn("externalProxy", stream)
        self.assertEqual(bundle["hosts.pending.json"]["port"], 34438)
        self.assertEqual(bundle["hosts.pending.json"]["inboundIds"], [])
        self.assertEqual(bundle["clients.private.json"]["server_port"], 34438)
        self.assertIn(":34438?", bundle["clients.private.json"]["clients"][0]["vless_uri"])

        local = copy.deepcopy(self.c)
        render.validate(local)
        client = render.build(local, "A" * 43, "B" * 43, "")["clients.private.json"]["clients"][0]
        self.assertEqual(client["subscription_urls"], {})
        self.assertTrue(client["local_subscription_urls"]["raw"].startswith("http://127.0.0.1:"))

        local["panel_domain"] = "panel.unit.invalid"
        with self.assertRaises(ValueError):
            render.validate(local)

        cloudflare = json.loads((ROOT / "assets/deployment.cloudflare.example.json").read_text())
        render.validate(cloudflare)
        client = render.build(cloudflare, "A" * 43, "B" * 43, "")["clients.private.json"]["clients"][0]
        self.assertTrue(client["subscription_urls"]["raw"].startswith("https://sub.example.com/"))
        self.assertEqual(client["local_subscription_urls"], {})

    def test_platform_profiles_cover_supported_families_and_safe_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            os_release = Path(tmp) / "os-release"
            os_release.write_text('ID=ubuntu\nVERSION_ID="24.04"\nID_LIKE=debian\n')
            result = profile.classify(profile.read_os_release(os_release), "x86_64", "systemd")
            self.assertEqual(result["os_family"], "apt")
            self.assertEqual(result["profile_status"], "supported_baseline")

            os_release.write_text('ID="ol"\nVERSION_ID="9.5"\nID_LIKE="fedora"\n')
            result = profile.classify(profile.read_os_release(os_release), "aarch64", "systemd")
            self.assertEqual(result["os_family"], "dnf")
            self.assertEqual(result["architecture"], "arm64")
            self.assertEqual(result["profile_status"], "supported_baseline")

            os_release.write_text('ID=alpine\nVERSION_ID=3.20\n')
            result = profile.classify(profile.read_os_release(os_release), "x86_64", "openrc")
            self.assertEqual(result["profile_status"], "manual_adaptation_required")

    def test_x25519_version_aliases_and_reject_unknown(self):
        for name in ("Password (PublicKey)", "PublicKey", "Password"):
            result = subprocess.CompletedProcess([], 0, stdout="PrivateKey: " + "A" * 43 + "\n" + name + ": " + "B" * 43)
            with patch.object(render.subprocess, "run", return_value=result):
                self.assertEqual(render.keypair(Path("/unused")), ("A" * 43, "B" * 43))
        with patch.object(render.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="unknown")):
            with self.assertRaises(ValueError):
                render.keypair(Path("/unused"))

    def test_no_overwrite_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "private.json"
            render.write_new(out, {"test": "synthetic"})
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                render.write_new(out, {})
            self.assertEqual(json.loads(out.read_text()), {"test": "synthetic"})

    def test_online_sqlite_snapshot_includes_committed_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source.db", Path(tmp) / "backup.db"
            con = sqlite3.connect(source)
            try:
                con.execute("PRAGMA journal_mode=WAL")
                con.execute("CREATE TABLE inbounds (id INTEGER)")
                con.execute("CREATE TABLE settings (key TEXT, value TEXT)")
                con.execute("INSERT INTO inbounds VALUES (73)")
                con.commit()
                self.assertTrue(Path(str(source) + "-wal").exists())
                backup.snapshot(source, target)
                panel.check_backup(target)
                check = sqlite3.connect(target)
                try:
                    self.assertEqual(check.execute("SELECT id FROM inbounds").fetchall(), [(73,)])
                finally:
                    check.close()
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                with self.assertRaises(FileExistsError):
                    backup.snapshot(source, target)
            finally:
                con.close()

    def test_env_no_execution_and_loopback_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "input.env"
            file.write_text("XUI_PANEL_PORT=29081\nXUI_WEB_BASE_PATH=/synthetic-path/\nXUI_API_TOKEN='synthetic-token'\nXUI_USERNAME='$(not-a-command)'\n")
            file.chmod(0o600)
            values = panel.read_env(file)
            self.assertEqual(values["XUI_USERNAME"], "$(not-a-command)")
            base, token = panel.connection(values)
            self.assertTrue(base.startswith("http://127.0.0.1:29081/"))
            self.assertNotIn(token, base)
            file.chmod(0o644)
            with self.assertRaises(ValueError):
                panel.read_env(file)

    def test_no_write_without_apply_or_backup(self):
        with patch.object(sys, "argv", ["panel_api.py", "add-inbound"]), patch.object(panel, "API") as api, patch("sys.stdout", new_callable=io.StringIO):
            panel.main()
            api.assert_not_called()
        with patch.object(sys, "argv", ["panel_api.py", "add-inbound", "--apply"]), patch.object(panel, "API") as api, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                panel.main()
            api.assert_not_called()

    def test_no_existing_inbound_overwrite(self):
        inbound = self.bundle()["inbound.json"]
        panel.fresh_inbound(inbound, [])
        with self.assertRaises(ValueError):
            panel.fresh_inbound(inbound, [dict(inbound, id=73)])

    def test_add_client_duplicate_guard(self):
        inbound = dict(self.bundle()["inbound.json"], id=73)
        old = json.loads(inbound["settings"])["clients"][0]
        with self.assertRaises(ValueError):
            panel.new_client({"client": old, "inboundIds": [73]}, [inbound])
        new = dict(old, id="00000000-0000-4000-8000-000000000001", subId="synthetic-new-sub-id", email="new-test-client")
        panel.new_client({"client": new, "inboundIds": [73]}, [inbound])

    def test_nat_hosts_requires_created_reality_inbound_and_no_existing_hosts(self):
        nat = copy.deepcopy(self.c)
        nat.update(network_mode="nat", reality_listen_port=2081, reality_public_port=34438)
        bundle = render.build(nat, "A" * 43, "B" * 43, "")
        inbound = dict(bundle["inbound.json"], id=73)
        host = bundle["hosts.pending.json"]
        with self.assertRaises(ValueError):
            panel.fresh_host(host, [inbound], [])
        host["inboundIds"] = [73]
        panel.fresh_host(host, [inbound], [])
        with self.assertRaises(ValueError):
            panel.fresh_host(host, [inbound], [{"groupId": "already-present"}])

    def test_settings_merge_preserves_unrelated_values_and_rejects_schema_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "patch.json"
            render.write_new(source, {"webListen": "127.0.0.1", "subListen": "127.0.0.1"})
            for drift in (False, True):
                current = {"webListen": "127.0.0.1", "subListen": "127.0.0.1", "unrelated": "preserve-me"}
                if drift:
                    del current["subListen"]
                with patch.object(sys, "argv", ["panel", "merge-settings", "--input", str(source), "--backup", "unused", "--apply"]), patch.object(panel, "check_backup"), patch.object(panel, "read_env", return_value={}), patch.object(panel, "API") as api, patch("sys.stdout", new_callable=io.StringIO) as output:
                    api.return_value.call.side_effect = [current, None]
                    if drift:
                        with self.assertRaises(ValueError):
                            panel.main()
                        self.assertEqual(api.return_value.call.call_count, 1)
                    else:
                        panel.main()
                        sent = api.return_value.call.call_args.args[2]
                        self.assertEqual(sent["unrelated"], "preserve-me")
                        self.assertNotIn("preserve-me", output.getvalue())

    def test_full_render_and_repeat_refusal_without_real_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            c = copy.deepcopy(self.c)
            c.update(server_address="8.8.8.8", control_plane_mode="cloudflare-tunnel",
                     panel_domain="panel.unit.invalid", subscription_domain="sub.unit.invalid",
                     reality_sni="target.unit.invalid")
            config.write_text(json.dumps(c))
            args = ["render", "--config", str(config), "--xray", "/unused", "--output", str(root / "bundle")]
            with patch.object(sys, "argv", args), patch.object(render, "keypair", return_value=("A" * 43, "B" * 43)) as keys, patch("sys.stdout", new_callable=io.StringIO) as output:
                render.main()
                self.assertEqual(len(list((root / "bundle").iterdir())), 3)
                self.assertEqual(stat.S_IMODE((root / "bundle").stat().st_mode), 0o700)
                self.assertNotIn("A" * 43, output.getvalue())
                with self.assertRaises(ValueError):
                    render.main()
                self.assertEqual(keys.call_count, 1)

    def test_api_never_follows_redirects_with_token(self):
        with self.assertRaises(ValueError):
            panel.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.com")

    def test_smoke_uses_explicit_node_and_current_sni(self):
        record = self.bundle()["clients.private.json"]
        for field in ("password", "publicKey"):
            config = smoke.client_config(record, "owner", 19443, field)
            self.assertEqual(config["inbounds"][0]["listen"], "127.0.0.1")
            outbound = config["outbounds"][0]
            self.assertEqual(outbound["settings"]["vnext"][0]["address"], record["server_address"])
            rs = outbound["streamSettings"]["realitySettings"]
            self.assertEqual(rs["serverName"], record["sni"])
            self.assertEqual(rs[field], record["public_key"])

    def test_monitor_readonly_probe_does_not_consume_notification_state(self):
        with patch.object(sys, "argv", ["watch", "--no-alert"]), patch.object(watch, "require_config", return_value={}), patch.object(watch, "active_profile", return_value="test"), patch.object(watch, "check_target", return_value={"healthy": True}), patch.object(watch, "load_state") as load, patch.object(watch, "save_state") as save, patch.object(watch, "telegram_send") as send, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(watch.main(), 0)
            load.assert_not_called()
            save.assert_not_called()
            send.assert_not_called()

    def test_monitor_failed_delivery_never_marks_delivered(self):
        cfg = {"FAILURE_THRESHOLD": "3", "RECOVERY_THRESHOLD": "2", "CERT_WARN_DAYS": "14"}
        result = {"healthy": False, "tcp": False, "tls13": False, "san": False, "dns": False,
                  "x_ui": True, "listener": True, "listen_port": 443, "http_status": 0,
                  "cert_days": -1, "domain": "target.example.com", "ip": "203.0.113.9"}
        state = {"consecutive_failures": 2, "consecutive_successes": 0, "alert_open": False}
        with patch.object(sys, "argv", ["watch"]), patch.object(watch, "require_config", return_value=cfg), patch.object(watch, "active_profile", return_value="test"), patch.object(watch, "check_target", return_value=result), patch.object(watch, "load_state", return_value=state), patch.object(watch, "save_state") as save, patch.object(watch, "telegram_send", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                watch.main()
            save.assert_not_called()
            self.assertFalse(state["alert_open"])

    def test_local_document_links_and_python_syntax(self):
        for source in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", source.read_text()):
                if not target.startswith(("https://", "http://", "#")):
                    self.assertTrue((source.parent / target.split("#")[0]).exists(), (source, target))
        for source in (ROOT / "scripts").glob("*.py"):
            compile(source.read_text(), str(source), "exec")

    def test_routing_order_and_providers(self):
        import yaml
        config = yaml.safe_load((ROOT / "assets/mihomo-routing.yaml").read_text())
        rules = config["rules"]
        github = next(i for i, r in enumerate(rules) if r.startswith("RULE-SET,github,"))
        microsoft = next(i for i, r in enumerate(rules) if r.startswith("RULE-SET,microsoft,"))
        self.assertLess(github, microsoft)
        providers = set(config["rule-providers"])
        for rule in rules:
            if rule.startswith("RULE-SET,"):
                self.assertIn(rule.split(",")[1], providers)
        self.assertEqual(rules[-1], "MATCH,🚀 节点选择")


class FallbackTests(unittest.TestCase):
    def args(self, **changes):
        # Synthetic local fixture. No test sends traffic to this or any remote IP.
        values = dict(server_ip="8.8.8.8", port=443, allowed_sni="target.unit.invalid",
                      test_domain=None, path="/", timeout=8, marker_header=None,
                      marker_value=None, run=False, confirm_server=None, confirm_test_domain=None)
        values.update(changes)
        return Namespace(**values)

    def test_preview_does_not_network(self):
        argv = ["probe", "--server-ip", "8.8.8.8", "--allowed-sni", "target.unit.invalid"]
        with patch.object(sys, "argv", argv), patch.object(fallback.socket, "create_connection") as connect, patch.object(fallback, "probe") as probe, patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(fallback.main(), 0)
            self.assertEqual(json.loads(out.getvalue())["network"], "not_accessed")
            connect.assert_not_called()
            probe.assert_not_called()

    def test_scope_confirmation_before_any_request(self):
        for args in (self.args(run=True), self.args(run=True, confirm_server="1.1.1.1"),
                     self.args(run=True, confirm_server="8.8.8.8", test_domain="other.unit.invalid")):
            with self.assertRaises(ValueError):
                fallback.validate(args)
        fallback.validate(self.args(run=True, confirm_server="8.8.8.8", test_domain="other.unit.invalid", confirm_test_domain="other.unit.invalid"))

    def test_reject_private_ip_header_injection_and_unbounded_inputs(self):
        bad = [{"server_ip": "127.0.0.1"}, {"server_ip": "169.254.169.254"},
               {"server_ip": "::1"}, {"server_ip": "host.unit.invalid"},
               {"path": "/?token=secret"}, {"path": "/x\r\nHost: other"},
               {"path": "//other/path"}, {"path": "/../secret"},
               {"allowed_sni": "x.unit.invalid\r\nHost:other"}, {"timeout": 999},
               {"marker_header": "Set-Cookie", "marker_value": "public-marker"}]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                fallback.validate(self.args(**changes))

    def test_exact_three_cases_no_domain_enumeration(self):
        args = self.args(test_domain="other.unit.invalid")
        cases = fallback.cases(args)
        self.assertEqual(len(cases), 3)
        self.assertEqual(cases[2][1:], ("target.unit.invalid", "other.unit.invalid"))
        self.assertEqual(len(fallback.cases(self.args())), 1)

    def test_cf_403_is_signal_not_safe_or_proven_abuse(self):
        evidence = fallback.summarize(b"HTTP/1.1 403 Forbidden\r\nServer: cloudflare\r\nCF-Ray: synthetic", True)
        self.assertEqual(evidence["http_status"], 403)
        self.assertTrue(evidence["cf_header_signal"])
        self.assertFalse(evidence["marker_matched"])
        self.assertNotIn("safe", evidence)
        self.assertNotIn("abuse_confirmed", evidence)

    def test_missing_cf_headers_404_not_exoneration(self):
        evidence = fallback.summarize(b"HTTP/1.1 404 Not Found\r\nServer: nginx", True)
        self.assertFalse(evidence["cf_header_signal"])
        self.assertEqual(evidence["http_status"], 404)
        self.assertNotIn("safe", evidence)

    def test_marker_requires_complete_exact_unique_header(self):
        raw = b"HTTP/1.1 200 OK\r\nX-Reality-Probe: public-marker"
        self.assertTrue(fallback.summarize(raw, True, "X-Reality-Probe", "public-marker")["marker_matched"])
        self.assertFalse(fallback.summarize(raw, False, "X-Reality-Probe", "public-marker")["marker_matched"])
        self.assertFalse(fallback.summarize(raw + b"\r\nX-Reality-Probe: public-marker", True, "X-Reality-Probe", "public-marker")["marker_matched"])

    def test_header_read_cap_and_deadline(self):
        tls = MagicMock()
        tls.recv.side_effect = lambda n: b"x" * n
        with patch.object(fallback.time, "monotonic", return_value=0):
            body, complete = fallback.read_headers(tls, 1)
        self.assertEqual(len(body), fallback.MAX_HEADERS)
        self.assertFalse(complete)
        with patch.object(fallback.time, "monotonic", return_value=2):
            with self.assertRaises(TimeoutError):
                fallback.read_headers(tls, 1)

    @unittest.skipUnless(ssl.HAS_TLSv1_3 and ssl.HAS_ALPN, "requires supported TLS runtime; run full suite on OpenSSL Python")
    def test_probe_connects_to_numeric_vps_and_keeps_tls_verification(self):
        args = self.args(test_domain="other.unit.invalid")
        raw, tls = MagicMock(), MagicMock()
        raw.__enter__.return_value = raw
        tls.__enter__.return_value = tls
        tls.recv.return_value = b"HTTP/1.1 302 Found\r\nLocation: https://not-followed.invalid/\r\n\r\n"
        context = ssl.create_default_context()
        with patch.object(fallback.ssl, "create_default_context", return_value=context), patch.object(context, "wrap_socket", return_value=tls) as wrap, patch.object(fallback.socket, "create_connection", return_value=raw) as connect:
            result = fallback.probe(args, fallback.cases(args)[2])
        self.assertEqual(connect.call_args.args[0], (args.server_ip, 443))
        self.assertEqual(wrap.call_args.kwargs["server_hostname"], args.allowed_sni)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_3)
        request = tls.sendall.call_args.args[0]
        self.assertTrue(request.startswith(b"HEAD / HTTP/1.1\r\n"))
        self.assertIn(b"Host: other.unit.invalid\r\n", request)
        self.assertEqual(connect.call_count, 1)  # does not follow Location
        self.assertEqual(result["http_status"], 302)
        self.assertNotIn("not-followed", json.dumps(result))

    @unittest.skipUnless(ssl.HAS_TLSv1_3 and ssl.HAS_ALPN, "requires supported TLS runtime; run full suite on OpenSSL Python")
    def test_certificate_failure_is_inconclusive_no_retry(self):
        raw = MagicMock()
        raw.__enter__.return_value = raw
        context = ssl.create_default_context()
        with patch.object(fallback.ssl, "create_default_context", return_value=context), patch.object(context, "wrap_socket", side_effect=ssl.SSLCertVerificationError("synthetic")), patch.object(fallback.socket, "create_connection", return_value=raw) as connect:
            result = fallback.probe(self.args(), fallback.cases(self.args())[0])
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertFalse(result["tls_verified"])
        self.assertEqual(connect.call_count, 1)

    def test_unsupported_tls_runtime_refuses_before_network(self):
        with patch.object(fallback.ssl, "HAS_TLSv1_3", False), patch.object(fallback.socket, "create_connection") as connect:
            with self.assertRaises(fallback.UnsupportedTLSRuntime):
                fallback.probe(self.args(), fallback.cases(self.args())[0])
            connect.assert_not_called()

    def test_collection_result_always_requires_review(self):
        argv = ["probe", "--server-ip", "8.8.8.8", "--allowed-sni", "target.unit.invalid",
                "--test-domain", "other.unit.invalid", "--run", "--confirm-server", "8.8.8.8",
                "--confirm-test-domain", "other.unit.invalid"]
        with patch.object(sys, "argv", argv), patch.object(fallback, "probe", return_value={"outcome": "inconclusive"}) as probe, patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(fallback.main(), 0)
            summary = json.loads(out.getvalue())
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(summary["security_assessment"], "requires_review")
        self.assertEqual(summary["requests_attempted"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
