#!/usr/bin/env python3
"""Lightweight regression tests for xnode helpers.

These tests intentionally avoid touching /usr/local, systemd, xray, or the
network.  They load the script as a module and monkeypatch path constants to a
temporary directory.
"""

import importlib.machinery
import importlib.util
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
XNODE_PATH = ROOT / "xnode"


def load_xnode_module():
    loader = importlib.machinery.SourceFileLoader("xnode_module", str(XNODE_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class XnodeHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.xnode = load_xnode_module()
        setattr(self.xnode, "XRAY_DIR", str(self.tmp / "xray"))
        setattr(self.xnode, "CONFIG", str(self.tmp / "xray" / "config.json"))
        setattr(self.xnode, "NODES_STATE", str(self.tmp / "xray" / "nodes.json"))
        setattr(self.xnode, "SUB_ENV", str(self.tmp / "xray-sub-sync.env"))

    def tearDown(self):
        self.tmpdir.cleanup()

    @staticmethod
    def outbound(tag):
        return {
            "tag": tag,
            "protocol": "vless",
            "settings": {"vnext": [{"address": f"{tag}.example.com", "port": 443}]},
        }

    def write_config(self, tags):
        cfg = {
            "outbounds": [self.outbound(tag) for tag in tags]
            + [
                {"tag": "direct", "protocol": "freedom", "settings": {}},
                {"tag": "block", "protocol": "blackhole", "settings": {}},
            ]
        }
        self.xnode.save_cfg(cfg)
        return cfg

    def test_get_nodes_initializes_stable_sorted_order(self):
        self.write_config(["beta", "alpha"])

        nodes = self.xnode.get_nodes()

        self.assertEqual([node["tag"] for node in nodes], ["alpha", "beta"])
        self.assertEqual(
            json.loads(Path(self.xnode.NODES_STATE).read_text())["order"],
            ["alpha", "beta"],
        )

    def test_get_nodes_preserves_existing_order_and_appends_new_tags(self):
        self.write_config(["alpha", "beta"])
        self.xnode.save_node_order(["beta", "alpha"])
        self.write_config(["alpha", "gamma", "beta"])

        nodes = self.xnode.get_nodes()

        self.assertEqual([node["tag"] for node in nodes], ["beta", "alpha", "gamma"])

    def test_refresh_node_order_removes_missing_and_appends_new_tags(self):
        self.xnode.save_node_order(["b", "a", "removed"])

        self.xnode.refresh_node_order_after_sub(["a", "c", "b"])

        self.assertEqual(
            json.loads(Path(self.xnode.NODES_STATE).read_text())["order"],
            ["b", "a", "c"],
        )

    def test_set_sub_url_replaces_existing_url_without_duplicate_defaults(self):
        Path(self.xnode.SUB_ENV).write_text(
            'XRAY_SUB_URL="old"\nXRAY_SOCKS_PORT="123"\n',
            encoding="utf-8",
        )

        self.xnode.set_sub_url("https://example.com/sub?token=abc")

        env = Path(self.xnode.SUB_ENV).read_text(encoding="utf-8").splitlines()
        self.assertEqual(env.count('XRAY_SUB_URL="https://example.com/sub?token=abc"'), 1)
        self.assertEqual(env.count('XRAY_SOCKS_PORT="123"'), 1)
        self.assertEqual(env.count(f'XRAY_HTTP_PORT="{self.xnode.HTTP_PORT}"'), 1)
        self.assertEqual(env.count(f'XRAY_CONFIG="{self.xnode.CONFIG}"'), 1)

    def test_parse_vless_supports_reality_settings(self):
        outbound = self.xnode.parse_vless(
            "vless://uuid@example.com:443?security=reality&type=tcp&sni=example.com"
            "&fp=chrome&pbk=public-key&sid=abcd&flow=xtls-rprx-vision#node-name"
        )

        self.assertEqual(outbound["tag"], "node-name")
        self.assertEqual(outbound["settings"]["vnext"][0]["address"], "example.com")
        self.assertEqual(outbound["streamSettings"]["realitySettings"]["publicKey"], "public-key")

    def test_tcping_average_ignores_failed_attempts(self):
        node = self.outbound("alpha")
        samples = iter([None, 0.2, 0.4])
        setattr(self.xnode, "tcping", lambda host, port: next(samples))

        self.assertAlmostEqual(self.xnode.tcping_average(node), 0.3)

    def test_test_all_preserves_display_order_with_parallel_results(self):
        self.write_config(["alpha", "beta", "gamma"])
        latencies_by_host = {
            "alpha.example.com": 0.3,
            "beta.example.com": 0.1,
            "gamma.example.com": 0.2,
        }
        setattr(self.xnode, "tcping", lambda host, port: latencies_by_host[host])

        with contextlib.redirect_stdout(io.StringIO()):
            latencies = self.xnode.test_all()

        self.assertEqual(set(latencies), {1, 2, 3})
        self.assertAlmostEqual(latencies[1], 0.3)
        self.assertAlmostEqual(latencies[2], 0.1)
        self.assertAlmostEqual(latencies[3], 0.2)

    def test_main_prints_help_and_exits_successfully_for_help_flags(self):
        original_argv = self.xnode.sys.argv
        try:
            for flag in ("-h", "--help"):
                with self.subTest(flag=flag):
                    stdout = io.StringIO()
                    setattr(self.xnode.sys, "argv", ["xnode", flag])
                    with contextlib.redirect_stdout(stdout):
                        self.xnode.main()
                    output = stdout.getvalue()
                    self.assertIn("用法:", output)
                    self.assertIn("xnode -T", output)
                    self.assertNotIn("❌", output)
        finally:
            setattr(self.xnode.sys, "argv", original_argv)

    def test_restart_xray_returns_false_when_readiness_never_succeeds(self):
        calls = []

        class Result:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stderr = ""
                self.stdout = ""

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[:2] == ["systemctl", "restart"]:
                return Result(0)
            if cmd and cmd[0] == "curl":
                return Result(28)
            return Result(0)

        setattr(self.xnode, "run", fake_run)
        setattr(self.xnode.time, "sleep", lambda seconds: None)

        self.assertFalse(self.xnode.restart_xray())
        self.assertEqual(sum(1 for cmd in calls if cmd and cmd[0] == "curl"), 10)

    def test_restart_xray_treats_readiness_exceptions_as_failed_attempts(self):
        class Result:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stderr = ""
                self.stdout = ""

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["systemctl", "restart"]:
                return Result(0)
            if cmd and cmd[0] == "curl":
                raise TimeoutError("readiness timed out")
            return Result(0)

        setattr(self.xnode, "run", fake_run)
        setattr(self.xnode.time, "sleep", lambda seconds: None)

        self.assertFalse(self.xnode.restart_xray())

    def test_restart_xray_returns_true_after_readiness_succeeds(self):
        curl_attempts = 0

        class Result:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stderr = ""
                self.stdout = ""

        def fake_run(cmd, **kwargs):
            nonlocal curl_attempts
            if cmd[:2] == ["systemctl", "restart"]:
                return Result(0)
            if cmd and cmd[0] == "curl":
                curl_attempts += 1
                return Result(0 if curl_attempts == 3 else 28)
            return Result(0)

        setattr(self.xnode, "run", fake_run)
        setattr(self.xnode.time, "sleep", lambda seconds: None)

        self.assertTrue(self.xnode.restart_xray())
        self.assertEqual(curl_attempts, 3)

    def test_reorder_outbounds_preserves_old_default_and_stable_order(self):
        outbounds = [self.outbound(tag) for tag in ["c", "a", "b"]]
        config = self.xnode.generate_config(outbounds)

        reordered = self.xnode.reorder_outbounds(config, ["b", "a", "c"], "a")

        tags = [outbound["tag"] for outbound in reordered["outbounds"]]
        self.assertEqual(tags, ["a", "b", "c", "direct", "block"])

    def test_reorder_outbounds_uses_saved_order_when_old_default_missing(self):
        outbounds = [self.outbound(tag) for tag in ["c", "a", "b"]]
        config = self.xnode.generate_config(outbounds)

        reordered = self.xnode.reorder_outbounds(config, ["b", "a", "c"], "missing")

        tags = [outbound["tag"] for outbound in reordered["outbounds"]]
        self.assertEqual(tags, ["b", "a", "c", "direct", "block"])


    def test_get_nodes_skips_malformed_outbounds(self):
        cfg = {"outbounds": [{"protocol": "vless"}, self.outbound("alpha"), {"tag": "direct"}]}
        self.xnode.save_cfg(cfg)

        nodes = self.xnode.get_nodes()

        self.assertEqual([node["tag"] for node in nodes], ["alpha"])

    def test_current_tag_skips_malformed_outbounds(self):
        cfg = {"outbounds": [{"protocol": "vless"}, {"tag": "direct"}, self.outbound("alpha")]}

        self.assertEqual(self.xnode.current_tag(cfg), "alpha")

    def test_node_info_handles_malformed_nodes(self):
        self.assertEqual(self.xnode.node_info({"protocol": "vless"}), ("VLESS", ""))
        self.assertEqual(self.xnode.node_info({"protocol": "vless", "settings": {"vnext": []}}), ("VLESS", ""))
        self.assertEqual(self.xnode.node_info({"settings": {}}), ("?", ""))

    def test_node_addr_handles_malformed_nodes(self):
        self.assertEqual(self.xnode.node_addr({"protocol": "vless"}), (None, None))
        self.assertEqual(self.xnode.node_addr({"settings": {"vnext": []}}), (None, None))
        self.assertEqual(self.xnode.node_addr({"settings": {"servers": [{"address": "host"}]}}), (None, None))

    def test_get_sub_url_accepts_whitespace_and_comments(self):
        Path(self.xnode.SUB_ENV).write_text(
            "# comment\n\n  XRAY_SUB_URL=\"https://example.com/sub\"\n",
            encoding="utf-8",
        )

        self.assertEqual(self.xnode.get_sub_url(), "https://example.com/sub")

    def test_set_sub_url_creates_parent_directory(self):
        nested_env = self.tmp / "nested" / "env" / "xray-sub-sync.env"
        setattr(self.xnode, "SUB_ENV", str(nested_env))

        self.xnode.set_sub_url("https://example.com/sub")

        self.assertTrue(nested_env.is_file())

    def test_sub_url_env_quoting_rejects_newlines_and_round_trips_specials(self):
        with self.assertRaises(ValueError):
            self.xnode.set_sub_url("https://example.com/sub\nINJECT=1")

        url = 'https://example.com/sub?x="quoted"&y=$dollar&z=`tick`&b=\\slash'
        self.xnode.set_sub_url(url)

        env = Path(self.xnode.SUB_ENV).read_text(encoding="utf-8")
        self.assertNotIn("INJECT=1", env)
        self.assertIn('\\"quoted\\"', env)
        self.assertIn('\\$dollar', env)
        self.assertEqual(self.xnode.get_sub_url(), url)

    def test_b64decode_text_supports_unpadded_urlsafe_values(self):
        import base64
        encoded = base64.urlsafe_b64encode("hello?+".encode()).decode().rstrip("=")

        self.assertEqual(self.xnode.b64decode_text(encoded), "hello?+")

    def test_parse_vmess_supports_unpadded_urlsafe_base64(self):
        import base64
        payload = json.dumps(
            {"add": "vm.example", "port": "443", "id": "uuid", "ps": "vm-node"},
            separators=(",", ":"),
        ).encode()
        b64url = base64.urlsafe_b64encode(payload).decode().rstrip("=")

        outbound = self.xnode.parse_vmess("vmess://" + b64url)

        self.assertEqual(outbound["tag"], "vm-node")
        self.assertEqual(outbound["settings"]["vnext"][0]["address"], "vm.example")

    def test_parse_ss_url_decodes_inline_userinfo(self):
        outbound = self.xnode.parse_ss(
            "ss://aes-128-gcm:p%40ss%2Fword@ss.example:8388#ss-node"
        )

        server = outbound["settings"]["servers"][0]
        self.assertEqual(server["method"], "aes-128-gcm")
        self.assertEqual(server["password"], "p@ss/word")

    def test_parse_ss_supports_bracketed_ipv6_hosts(self):
        outbound = self.xnode.parse_ss(
            "ss://aes-128-gcm:password@[2001:db8::1]:8388#ipv6-node"
        )

        server = outbound["settings"]["servers"][0]
        self.assertEqual(server["address"], "2001:db8::1")
        self.assertEqual(server["port"], 8388)

    def test_parse_vless_returns_none_for_invalid_or_incomplete_links(self):
        self.assertIsNone(self.xnode.parse_vless("vless://uuid@example.com:bad#node"))
        self.assertIsNone(self.xnode.parse_vless("vless://example.com:443#missing-user"))

    def test_parse_vless_supports_websocket_settings(self):
        outbound = self.xnode.parse_vless(
            "vless://uuid@host.example:443"
            "?security=tls&type=ws&path=%2Fws&host=cdn.example&sni=sni.example"
            "#vless-ws"
        )

        stream = outbound["streamSettings"]
        self.assertEqual(stream["network"], "ws")
        self.assertEqual(stream["wsSettings"]["path"], "/ws")
        self.assertEqual(stream["wsSettings"]["headers"]["Host"], "cdn.example")

    def test_curl_once_uses_configured_socks_port(self):
        calls = []

        class Result:
            returncode = 0
            stdout = "0.123"
            stderr = ""

        setattr(self.xnode, "SOCKS_PORT", 29999)
        setattr(self.xnode, "run", lambda cmd, **kwargs: calls.append(cmd) or Result())

        self.assertEqual(self.xnode.curl_once(), 0.123)
        self.assertIn("127.0.0.1:29999", calls[0])

    def test_direct_switch_reports_no_config_before_range_error(self):
        stdout = io.StringIO()

        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(stdout):
            self.xnode.direct_switch(1)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("无配置", stdout.getvalue())
        self.assertNotIn("范围 1-0", stdout.getvalue())

    def test_main_rejects_extra_arguments(self):
        original_argv = self.xnode.sys.argv
        stdout = io.StringIO()
        try:
            setattr(self.xnode.sys, "argv", ["xnode", "-T", "extra"])
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(stdout):
                self.xnode.main()
        finally:
            setattr(self.xnode.sys, "argv", original_argv)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("参数过多", stdout.getvalue())

    def test_prompt_scope_prints_message_for_invalid_input(self):
        stdout = io.StringIO()
        setattr(self.xnode, "input", lambda prompt="": "x")

        with contextlib.redirect_stdout(stdout):
            self.assertIsNone(self.xnode.prompt_scope())

        self.assertIn("请输入 1 或 2", stdout.getvalue())

    def test_sync_sub_warns_when_restart_readiness_fails(self):
        self.xnode.set_sub_url("https://example.com/sub")
        old_cfg = self.write_config(["old"])
        old_cfg["outbounds"].insert(0, {"protocol": "vless", "settings": {}})
        self.xnode.save_cfg(old_cfg)
        link = "vless://uuid@example.com:443?security=none&type=tcp#new-node"

        class Result:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(cmd, **kwargs):
            if cmd and cmd[0] == "curl":
                return Result(stdout=link)
            if cmd[:2] == [self.xnode.XRAY_BIN, "run"]:
                return Result()
            return Result()

        setattr(self.xnode, "run", fake_run)
        setattr(self.xnode, "service_active", lambda: False)
        setattr(self.xnode, "restart_xray", lambda: False)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            self.assertTrue(self.xnode.sync_sub())

        self.assertIn("端口未验证", stdout.getvalue())

    def test_test_all_omits_fastest_line_when_every_node_times_out(self):
        self.write_config(["alpha", "beta"])
        setattr(self.xnode, "tcping", lambda host, port: None)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            latencies = self.xnode.test_all()

        self.assertEqual(latencies, {1: None, 2: None})
        self.assertNotIn("最快", stdout.getvalue())

    def test_do_switch_returns_restart_result_and_direct_switch_skips_curl_on_failure(self):
        self.write_config(["alpha", "beta"])
        setattr(self.xnode, "restart_xray", lambda: False)
        curl_calls = []
        setattr(self.xnode, "curl_once", lambda: curl_calls.append(True) or 0.1)
        setattr(self.xnode.time, "sleep", lambda seconds: None)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.xnode.direct_switch(2)

        self.assertEqual(curl_calls, [])
        self.assertIn("端口未验证", stdout.getvalue())

    def test_do_switch_preserves_malformed_outbounds_without_crashing(self):
        cfg = self.write_config(["alpha", "beta"])
        cfg["outbounds"].insert(1, {"protocol": "vless", "settings": {}})
        self.xnode.save_cfg(cfg)
        setattr(self.xnode, "restart_xray", lambda: True)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertTrue(self.xnode.do_switch(2, self.xnode.get_nodes()))

        outbounds = self.xnode.load_cfg()["outbounds"]
        self.assertEqual(outbounds[0]["tag"], "beta")
        self.assertIn({"protocol": "vless", "settings": {}}, outbounds)


    def test_test_all_curl_handles_malformed_outbounds_and_restart_failures(self):
        cfg = self.write_config(["alpha", "beta"])
        cfg["outbounds"].insert(1, {"protocol": "vless", "settings": {}})
        self.xnode.save_cfg(cfg)
        setattr(self.xnode, "service_active", lambda: True)
        restart_calls = []
        setattr(self.xnode, "restart_xray", lambda: restart_calls.append(True) and False)
        curl_calls = []
        setattr(self.xnode, "curl_once", lambda: curl_calls.append(True) or 0.1)
        setattr(self.xnode.time, "sleep", lambda seconds: None)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            latencies = self.xnode.test_all_curl()

        self.assertAlmostEqual(latencies[1], 0.1)
        self.assertIsNone(latencies[2])
        self.assertEqual(len(curl_calls), 3)
        self.assertIn("重启失败", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
