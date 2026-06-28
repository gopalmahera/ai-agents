import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Stub pydantic_ai.mcp before project imports (local pydantic-ai may differ from container version).
_mcp_stub = MagicMock()
_mcp_stub.MCPServerStreamableHTTP = MagicMock
sys.modules.setdefault("pydantic_ai.mcp", _mcp_stub)

# Stub prometheus_client so agent-chain imports don't need the real package.
_prom_stub = types.ModuleType("prometheus_client")
_prom_stub.Counter = MagicMock(return_value=MagicMock())
_prom_stub.generate_latest = MagicMock(return_value=b"")
_prom_stub.CONTENT_TYPE_LATEST = "text/plain"
sys.modules.setdefault("prometheus_client", _prom_stub)

# Stub metrics module (avoids importing app.py which has its own chain).
_metrics_stub = types.ModuleType("metrics")
for _n in ("alerts_received", "alerts_deduplicated", "alerts_skipped", "alerts_accepted",
           "llm_investigations", "slack_posts"):
    setattr(_metrics_stub, _n, MagicMock())
sys.modules["metrics"] = _metrics_stub

# Force-load the real agent module now, before test_app_webhook can stub it.
sys.modules.pop("agent", None)
import importlib
import agent as _agent_module
importlib.reload(_agent_module)


FIRING_ALERT = {
    "status": "firing",
    "labels": {"alertname": "PodRestart", "namespace": "default", "pod": "my-pod-abc123"},
    "annotations": {"description": "Pod default/my-pod-abc123 restarted."},
    "fingerprint": "abc123",
}


class TestInvestigateAlert(unittest.TestCase):
    def setUp(self):
        # Ensure sys.modules["agent"] always points to the real module during tests.
        sys.modules["agent"] = _agent_module

    @patch.object(_agent_module, "send_alert_report")
    @patch.object(_agent_module, "save_rca", return_value="/tmp/rca.log")
    @patch.object(_agent_module, "build_prefetch")
    def test_skips_non_firing_alert(self, mock_prefetch, mock_save, mock_slack):
        alert = dict(FIRING_ALERT, status="resolved")
        _agent_module.investigate_alert(alert)
        mock_prefetch.assert_not_called()
        mock_slack.assert_not_called()

    @patch.object(_agent_module, "send_alert_report")
    @patch.object(_agent_module, "save_rca", return_value="/tmp/rca.log")
    @patch.object(_agent_module, "format_rca", side_effect=lambda rca, *a, **kw: rca)
    @patch.object(_agent_module, "build_prefetch", return_value=None)
    @patch.object(_agent_module, "build_deterministic_rca", return_value="Deterministic RCA body")
    @patch.object(_agent_module, "LLM_ENABLED", False)
    def test_deterministic_path_when_llm_disabled(
        self, mock_det_rca, mock_prefetch, mock_fmt, mock_save, mock_slack
    ):
        _agent_module.investigate_alert(FIRING_ALERT)
        mock_det_rca.assert_called_once()
        mock_slack.assert_called_once()

    @patch.object(_agent_module, "send_alert_report")
    @patch.object(_agent_module, "save_rca", return_value="/tmp/rca.log")
    @patch.object(_agent_module, "format_rca", side_effect=lambda rca, *a, **kw: rca)
    @patch.object(_agent_module, "build_prefetch", return_value=None)
    @patch.object(_agent_module, "asyncio")
    def test_llm_path_when_enabled(
        self, mock_asyncio, mock_prefetch, mock_fmt, mock_save, mock_slack
    ):
        mock_asyncio.run.return_value = "LLM RCA body"
        with patch.object(_agent_module, "LLM_ENABLED", True):
            _agent_module.investigate_alert(FIRING_ALERT)
        mock_asyncio.run.assert_called_once()
        mock_slack.assert_called_once()

    @patch.object(_agent_module, "send_alert_report")
    @patch.object(_agent_module, "save_rca", return_value="/tmp/rca.log")
    @patch.object(_agent_module, "format_rca", side_effect=lambda rca, *a, **kw: rca)
    @patch.object(_agent_module, "build_prefetch", return_value={"bullets": ["restart: 3"]})
    @patch.object(_agent_module, "build_deterministic_rca", return_value="Deterministic RCA body")
    @patch.object(_agent_module, "asyncio")
    def test_falls_back_to_deterministic_on_quota_error(
        self, mock_asyncio, mock_det_rca, mock_prefetch, mock_fmt, mock_save, mock_slack
    ):
        mock_asyncio.run.side_effect = Exception("429 quota")
        with patch.object(_agent_module, "LLM_ENABLED", True):
            _agent_module.investigate_alert(FIRING_ALERT)
        mock_det_rca.assert_called()
        mock_slack.assert_called_once()


if __name__ == "__main__":
    unittest.main()
