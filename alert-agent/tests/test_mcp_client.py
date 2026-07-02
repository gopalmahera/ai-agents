import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Stub out pydantic_ai.mcp before any project imports so tests run
# regardless of which pydantic-ai version is installed locally.
_mcp_stub = MagicMock()
_mcp_stub.MCPServerStreamableHTTP = MagicMock
sys.modules.setdefault("pydantic_ai.mcp", _mcp_stub)


FIRING_ALERT = {
    "status": "firing",
    "labels": {"alertname": "PodRestart", "namespace": "default", "pod": "my-pod-abc123"},
    "annotations": {},
    "fingerprint": "abc123",
}


class TestRunInvestigation(unittest.IsolatedAsyncioTestCase):
    @patch("services.llm.mcp_client.Agent")
    async def test_returns_agent_output(self, MockAgent):
        mock_result = MagicMock()
        mock_result.output = "LLM RCA text"

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_instance.__aexit__ = AsyncMock(return_value=False)
        MockAgent.return_value = mock_agent_instance

        from services.llm.mcp_client import run_investigation

        result = await run_investigation(FIRING_ALERT)
        self.assertEqual(result, "LLM RCA text")
        mock_agent_instance.run.assert_called_once()

    @patch("services.llm.mcp_client.Agent")
    async def test_prompt_contains_alert_context(self, MockAgent):
        mock_result = MagicMock()
        mock_result.output = "RCA"

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_instance.__aexit__ = AsyncMock(return_value=False)
        MockAgent.return_value = mock_agent_instance

        from services.llm.mcp_client import run_investigation

        await run_investigation(FIRING_ALERT)
        prompt_arg = mock_agent_instance.run.call_args[0][0]
        self.assertIn("PodRestart", prompt_arg)
        self.assertIn("kubernetes", prompt_arg)

    @patch("services.llm.mcp_client.Agent")
    async def test_prefetched_block_included_in_prompt(self, MockAgent):
        mock_result = MagicMock()
        mock_result.output = "RCA"

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
        mock_agent_instance.__aexit__ = AsyncMock(return_value=False)
        MockAgent.return_value = mock_agent_instance

        from services.llm.mcp_client import run_investigation

        prefetched = {"bullets": ["restart_count: 3"], "snapshot": {}, "findings": []}
        await run_investigation(FIRING_ALERT, prefetched=prefetched)
        prompt_arg = mock_agent_instance.run.call_args[0][0]
        self.assertIn("restart_count", prompt_arg)


class TestModelSelection(unittest.TestCase):
    @patch("services.llm.mcp_client._cfg")
    def test_info_severity_uses_mini_model(self, mock_cfg):
        from services.llm.mcp_client import _model_string

        mock_cfg.AI_PROVIDER = "openai"
        mock_cfg.OPENAI_MODEL = "gpt-4o"
        mock_cfg.OPENAI_MODEL_INFO = "gpt-4o-mini"
        self.assertEqual(_model_string("info"), "openai-chat:gpt-4o-mini")
        self.assertEqual(_model_string("critical"), "openai-chat:gpt-4o")


if __name__ == "__main__":
    unittest.main()
