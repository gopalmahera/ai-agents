import asyncio
import base64
import unittest
from unittest import mock

import yaml

import config as _cfg
import services.environments as env


_ENDPOINTS = {
    "endpoints": [
        {"name": "prod-prom", "type": "prometheus", "url": "http://prom-prod",
         "auth": {"mode": "bearer", "token": "tok123"}},
        {"name": "prod-loki", "type": "loki", "url": "http://loki-prod",
         "auth": {"mode": "basic", "username": "u", "password": "p"}},
        {"name": "prod-k8s", "type": "kubernetes", "kube_context": "prod-ctx"},
        {"name": "prod-aws", "type": "aws", "region": "ap-south-1",
         "auth": {"mode": "assume_role", "role_arn": "arn:aws:iam::1:role/x"}},
    ]
}

_ENVIRONMENTS = {
    "environments": [
        {"name": "default", "prometheus": "prod-prom", "loki": "prod-loki", "kubernetes": "prod-k8s"},
        {"name": "prod", "prometheus": "prod-prom", "loki": "prod-loki",
         "kubernetes": "prod-k8s", "aws": "prod-aws"},
        {"name": "partial", "prometheus": "prod-prom"},  # loki/k8s fall back to boot defaults
    ]
}


class TestEnvironments(unittest.TestCase):
    def setUp(self):
        env.reset_cache()
        self.addCleanup(env.reset_cache)
        for loader, data in (
            ("endpoints_yaml_load", _ENDPOINTS),
            ("environments_yaml_load", _ENVIRONMENTS),
        ):
            p = mock.patch.object(env._redis, loader, return_value=yaml.safe_dump(data))
            p.start()
            self.addCleanup(p.stop)
        for attr, val in (("PROMETHEUS_URL", "http://global-prom"), ("LOKI_URL", "http://global-loki")):
            p = mock.patch.object(_cfg, attr, val)
            p.start()
            self.addCleanup(p.stop)

    def test_resolve_named_env_with_auth(self):
        e = env.resolve("prod")
        self.assertEqual(e.prometheus.url, "http://prom-prod")
        self.assertEqual(e.prometheus.auth.header_value(), "Bearer tok123")
        self.assertEqual(e.loki.url, "http://loki-prod")
        self.assertEqual(e.loki.auth.header_value(), "Basic " + base64.b64encode(b"u:p").decode())
        self.assertEqual(e.kubernetes.kube_context, "prod-ctx")
        self.assertIsNotNone(e.aws)
        self.assertEqual(e.aws.region, "ap-south-1")
        self.assertEqual(e.aws.mode, "assume_role")

    def test_none_resolves_to_default_env(self):
        e = env.resolve(None)
        self.assertEqual(e.prometheus.url, "http://prom-prod")
        self.assertIsNone(e.aws)  # default env selects no AWS endpoint

    def test_unknown_env_falls_back_to_default_env(self):
        e = env.resolve("does-not-exist")
        self.assertEqual(e.prometheus.url, "http://prom-prod")

    def test_missing_ref_falls_back_to_boot_defaults(self):
        e = env.resolve("partial")
        self.assertEqual(e.prometheus.url, "http://prom-prod")
        self.assertEqual(e.loki.url, "http://global-loki")  # no loki ref → boot default
        self.assertEqual(e.kubernetes.kube_context, "")

    def test_no_environments_uses_boot_defaults(self):
        env.reset_cache()
        with mock.patch.object(env._redis, "environments_yaml_load",
                               return_value=yaml.safe_dump({"environments": []})):
            e = env.resolve("prod")
        self.assertEqual(e.prometheus.url, "http://global-prom")
        self.assertEqual(e.loki.url, "http://global-loki")
        self.assertEqual(e.prometheus.auth.header_value(), "")

    def test_bind_current_reset(self):
        token = env.bind("prod")
        try:
            self.assertEqual(env.current().prometheus.url, "http://prom-prod")
        finally:
            env.reset(token)
        self.assertEqual(env.current().prometheus.url, "http://global-prom")

    def test_contextvar_propagates_into_asyncio_run(self):
        token = env.bind("prod")
        try:
            async def _inner():
                return env.current().prometheus.url

            self.assertEqual(asyncio.run(_inner()), "http://prom-prod")
        finally:
            env.reset(token)

    def test_direct_query_uses_bound_url_and_auth(self):
        import services.metrics.pod_metrics as pm

        captured = {}

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"data": {}}

        def fake_get(url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            return _Resp()

        token = env.bind("prod")
        try:
            with mock.patch.object(pm.requests, "get", fake_get):
                pm._query_promql("up")
        finally:
            env.reset(token)
        self.assertTrue(captured["url"].startswith("http://prom-prod/api/v1/query"), captured["url"])
        self.assertEqual(captured["headers"], {"Authorization": "Bearer tok123"})


if __name__ == "__main__":
    unittest.main()
