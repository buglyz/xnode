#!/usr/bin/env python3
"""Lightweight regression tests for xnode helpers.

These tests intentionally avoid touching /usr/local, systemd, xray, or the
network.  They load the script as a module and monkeypatch path constants to a
temporary directory.
"""

import importlib.machinery
import importlib.util
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

        latencies = self.xnode.test_all()

        self.assertEqual(set(latencies), {1, 2, 3})
        self.assertAlmostEqual(latencies[1], 0.3)
        self.assertAlmostEqual(latencies[2], 0.1)
        self.assertAlmostEqual(latencies[3], 0.2)

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


if __name__ == "__main__":
    unittest.main()
