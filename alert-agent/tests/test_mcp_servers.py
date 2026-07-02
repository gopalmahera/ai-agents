import importlib.util
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMcpServerHeaderRouting(unittest.TestCase):
    """The MCP servers pick the upstream URL from the per-request header the
    agent injects, falling back to the boot-time default when absent."""

    def test_prometheus_base_url(self):
        m = _load("mcp-servers/prometheus-mcp/server.py", "prom_srv")
        self.assertEqual(m._base_url(), m.PROMETHEUS_URL)  # no header → default
        tok = m._req_headers.set({"x-prometheus-url": "http://prom-prod"})
        try:
            self.assertEqual(m._base_url(), "http://prom-prod")
        finally:
            m._req_headers.reset(tok)

    def test_kafka_base_url(self):
        m = _load("mcp-servers/kafka-mcp/server.py", "kafka_srv")
        tok = m._req_headers.set({"x-prometheus-url": "http://prom-sit"})
        try:
            self.assertEqual(m._base_url(), "http://prom-sit")
        finally:
            m._req_headers.reset(tok)
        self.assertEqual(m._base_url(), m.PROMETHEUS_URL)

    def test_loki_base_url(self):
        m = _load("mcp-servers/loki-mcp/server.py", "loki_srv")
        self.assertEqual(m._base_url(), m.LOKI_URL)
        tok = m._req_headers.set({"x-loki-url": "http://loki-prod"})
        try:
            self.assertEqual(m._base_url(), "http://loki-prod")
        finally:
            m._req_headers.reset(tok)


class TestMcpServerAuth(unittest.TestCase):
    """The agent injects a ready-to-use Authorization value; servers pass it through."""

    def test_prometheus_auth_header(self):
        m = _load("mcp-servers/prometheus-mcp/server.py", "prom_auth")
        self.assertEqual(m._auth_header(), {})
        tok = m._req_headers.set({"x-prometheus-authorization": "Bearer abc"})
        try:
            self.assertEqual(m._auth_header(), {"Authorization": "Bearer abc"})
        finally:
            m._req_headers.reset(tok)

    def test_prometheus_get_injects_auth(self):
        m = _load("mcp-servers/prometheus-mcp/server.py", "prom_auth2")
        captured = {}

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {}

        def fake_get(url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            return _Resp()

        m.requests.get = fake_get
        tok = m._req_headers.set({"x-prometheus-url": "http://p", "x-prometheus-authorization": "Bearer z"})
        try:
            m._query("up")
        finally:
            m._req_headers.reset(tok)
        self.assertTrue(captured["url"].startswith("http://p/api/v1/query"))
        self.assertEqual(captured["headers"], {"Authorization": "Bearer z"})

    def test_loki_auth_header(self):
        m = _load("mcp-servers/loki-mcp/server.py", "loki_auth")
        self.assertEqual(m._auth_header(), {})
        tok = m._req_headers.set({"x-loki-authorization": "Basic zzz"})
        try:
            self.assertEqual(m._auth_header(), {"Authorization": "Basic zzz"})
        finally:
            m._req_headers.reset(tok)


class TestCloudwatchSession(unittest.TestCase):
    """CloudWatch builds a boto3 Session per request from the X-Aws-* headers."""

    def _fake_boto3(self, calls):
        import types

        class _Sts:
            def assume_role(self, **kw):
                calls["assume"] = kw
                return {"Credentials": {"AccessKeyId": "AK", "SecretAccessKey": "SK", "SessionToken": "TK"}}

        class _Session:
            def __init__(self, **kw):
                calls["session"] = kw

            def client(self, name):
                calls.setdefault("clients", []).append(name)
                return object()

        fake = types.SimpleNamespace()
        fake.Session = _Session
        fake.client = lambda name, **kw: _Sts()
        return fake

    def test_session_modes(self):
        import sys
        m = _load("mcp-servers/cloudwatch-mcp/server.py", "cw_srv")
        calls: dict = {}
        sys.modules["boto3"] = self._fake_boto3(calls)
        try:
            # default (no headers) — ambient credential chain
            m._session()
            self.assertIn("region_name", calls["session"])

            # keys mode
            tok = m._req_headers.set({
                "x-aws-auth-mode": "keys", "x-aws-region": "ap-south-1",
                "x-aws-access-key-id": "AK", "x-aws-secret-access-key": "SK",
            })
            try:
                m._session()
            finally:
                m._req_headers.reset(tok)
            self.assertEqual(calls["session"]["aws_access_key_id"], "AK")
            self.assertEqual(calls["session"]["region_name"], "ap-south-1")

            # assume_role mode
            tok = m._req_headers.set({"x-aws-auth-mode": "assume_role", "x-aws-role-arn": "arn:x"})
            try:
                m._session()
            finally:
                m._req_headers.reset(tok)
            self.assertEqual(calls["assume"]["RoleArn"], "arn:x")
            self.assertEqual(calls["session"]["aws_session_token"], "TK")
        finally:
            sys.modules.pop("boto3", None)


if __name__ == "__main__":
    unittest.main()
