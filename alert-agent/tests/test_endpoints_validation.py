import unittest

from services.endpoints_validation import validate_endpoints_body
from services.environments_validation import validate_environments_body


class TestEndpointsValidation(unittest.TestCase):
    def test_valid_registry(self):
        body = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p", "auth": {"mode": "bearer", "token": "t"}},
            {"name": "l", "type": "loki", "url": "http://l", "auth": {"mode": "basic", "username": "u", "password": "x"}},
            {"name": "k", "type": "kubernetes", "kube_context": "ctx"},
            {"name": "a", "type": "aws", "region": "ap-south-1", "auth": {"mode": "assume_role", "role_arn": "arn:x"}},
        ]}
        self.assertEqual(validate_endpoints_body(body), [])

    def test_bad_url_and_type(self):
        body = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "not-a-url"},
            {"name": "z", "type": "unknown"},
        ]}
        errors = validate_endpoints_body(body)
        self.assertTrue(any("url" in e for e in errors))
        self.assertTrue(any("type" in e for e in errors))

    def test_duplicate_name(self):
        body = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p"},
            {"name": "p", "type": "loki", "url": "http://l"},
        ]}
        self.assertTrue(any("duplicate" in e for e in validate_endpoints_body(body)))

    def test_basic_requires_username(self):
        body = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p", "auth": {"mode": "basic", "password": "x"}}]}
        self.assertTrue(any("username" in e for e in validate_endpoints_body(body)))

    def test_kubernetes_apiserver_requires_token(self):
        body = {"endpoints": [
            {"name": "k", "type": "kubernetes", "api_server": "https://k"}]}
        self.assertTrue(any("token" in e for e in validate_endpoints_body(body)))

    def test_aws_keys_require_both(self):
        body = {"endpoints": [
            {"name": "a", "type": "aws", "auth": {"mode": "keys", "access_key_id": "AK"}}]}
        self.assertTrue(any("secret_access_key" in e for e in validate_endpoints_body(body)))


class TestEnvironmentsValidation(unittest.TestCase):
    _REGISTRY = {"prod-prom": "prometheus", "prod-loki": "loki"}

    def test_valid_refs(self):
        body = {"environments": [{"name": "prod", "prometheus": "prod-prom", "loki": "prod-loki"}]}
        self.assertEqual(validate_environments_body(body, endpoints_by_type=self._REGISTRY), [])

    def test_unknown_ref(self):
        body = {"environments": [{"name": "prod", "prometheus": "missing"}]}
        errors = validate_environments_body(body, endpoints_by_type=self._REGISTRY)
        self.assertTrue(any("does not exist" in e for e in errors))

    def test_type_mismatch(self):
        body = {"environments": [{"name": "prod", "prometheus": "prod-loki"}]}
        errors = validate_environments_body(body, endpoints_by_type=self._REGISTRY)
        self.assertTrue(any("expected prometheus" in e for e in errors))

    def test_reserved_and_bad_name(self):
        self.assertTrue(any("reserved" in e for e in
                            validate_environments_body({"environments": [{"name": "test"}]})))
        self.assertTrue(any("letters" in e for e in
                            validate_environments_body({"environments": [{"name": "has space"}]})))

    def test_duplicate_name(self):
        body = {"environments": [{"name": "prod"}, {"name": "prod"}]}
        self.assertTrue(any("duplicate" in e for e in validate_environments_body(body)))


if __name__ == "__main__":
    unittest.main()
