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

        output, _usage = await run_investigation(FIRING_ALERT)
        self.assertEqual(output, "LLM RCA text")
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


_EXPECTED_PREFIX = {
    "openai": "openai-chat:m",
    "anthropic": "anthropic:m",
    "gemini": "google:m",
    "bedrock": "bedrock:m",
    "fake": "test",
}


class TestUsageRecording(unittest.IsolatedAsyncioTestCase):
    @patch("services.llm.mcp_client._redis")
    @patch("services.llm.mcp_client.Agent")
    async def test_records_token_usage_after_run(self, MockAgent, mock_redis):
        usage = MagicMock(input_tokens=4000, output_tokens=800)
        mock_result = MagicMock(output="RCA", usage=usage)
        agent = AsyncMock()
        agent.run = AsyncMock(return_value=mock_result)
        agent.__aenter__ = AsyncMock(return_value=agent)
        agent.__aexit__ = AsyncMock(return_value=False)
        MockAgent.return_value = agent

        from services.llm.mcp_client import run_investigation

        with patch("services.llm.mcp_client._cfg") as cfg:
            cfg.AI_PROVIDER = "openai"
            cfg.OPENAI_MODEL = "gpt-4o"
            await run_investigation(FIRING_ALERT)

        mock_redis.record_llm_usage.assert_called_once()
        args = mock_redis.record_llm_usage.call_args.args
        self.assertEqual(args[0], "gpt-4o")   # model
        self.assertEqual(args[1], 4000)       # input tokens
        self.assertEqual(args[2], 800)        # output tokens
        self.assertGreater(args[3], 0)        # priced cost in micro-USD

    @patch("services.llm.mcp_client._redis")
    @patch("services.llm.mcp_client.Agent")
    async def test_fake_provider_records_nothing(self, MockAgent, mock_redis):
        mock_result = MagicMock(output="RCA", usage=MagicMock(input_tokens=1, output_tokens=1))
        agent = AsyncMock()
        agent.run = AsyncMock(return_value=mock_result)
        agent.__aenter__ = AsyncMock(return_value=agent)
        agent.__aexit__ = AsyncMock(return_value=False)
        MockAgent.return_value = agent

        from services.llm.mcp_client import run_investigation

        with patch("services.llm.mcp_client._cfg") as cfg:
            cfg.AI_PROVIDER = "fake"
            cfg.OPENAI_MODEL = "gpt-4o"
            await run_investigation(FIRING_ALERT)

        mock_redis.record_llm_usage.assert_not_called()


class TestModelSelection(unittest.TestCase):
    @patch("services.llm.mcp_client._cfg")
    def test_info_severity_uses_mini_model(self, mock_cfg):
        from services.llm.mcp_client import _model_string

        mock_cfg.AI_PROVIDER = "openai"
        mock_cfg.OPENAI_MODEL = "gpt-4o"
        mock_cfg.OPENAI_MODEL_INFO = "gpt-4o-mini"
        self.assertEqual(_model_string("info"), "openai-chat:gpt-4o-mini")
        self.assertEqual(_model_string("critical"), "openai-chat:gpt-4o")

    @patch("services.llm.mcp_client._cfg")
    def test_each_provider_maps_to_expected_prefix(self, mock_cfg):
        from services.llm.mcp_client import _model_string

        mock_cfg.OPENAI_MODEL = "m"
        for provider, expected in _EXPECTED_PREFIX.items():
            mock_cfg.AI_PROVIDER = provider
            self.assertEqual(_model_string(), expected, f"provider={provider}")

    @patch("services.llm.mcp_client._mcp")
    def test_build_toolsets_injects_env_headers(self, mock_mcp):
        from services.llm import mcp_client
        from services.environments import Endpoints, HttpEndpoint, HttpAuth, KubeEndpoint, AwsEndpoint
        endpoints = Endpoints(
            prometheus=HttpEndpoint("http://p", HttpAuth(mode="bearer", token="tok")),
            loki=HttpEndpoint("http://l", HttpAuth(mode="none")),
            kubernetes=KubeEndpoint(kube_context="ctx1"),
            aws=AwsEndpoint(region="ap-south-1", mode="assume_role", role_arn="arn:x"),
        )
        with patch.object(mcp_client._environments, "current", return_value=endpoints), \
             patch.object(mcp_client._cfg, "CLOUDWATCH_MCP_URL", "http://127.0.0.1:8005/mcp"):
            mcp_client._build_toolsets()
        # _mcp(url, prefix, headers) — map prefix -> headers
        by_prefix = {c.args[1]: c.args[2] for c in mock_mcp.call_args_list}
        self.assertEqual(by_prefix["prom"], {"X-Prometheus-Url": "http://p", "X-Prometheus-Authorization": "Bearer tok"})
        self.assertEqual(by_prefix["loki"], {"X-Loki-Url": "http://l"})
        self.assertEqual(by_prefix["kafka"], {"X-Prometheus-Url": "http://p", "X-Prometheus-Authorization": "Bearer tok"})
        self.assertEqual(by_prefix["k8s"], {"X-Kube-Context": "ctx1"})
        # AWS endpoint present + CW configured → CloudWatch toolset added.
        self.assertIn("cw", by_prefix)
        self.assertEqual(by_prefix["cw"]["X-Aws-Region"], "ap-south-1")
        self.assertEqual(by_prefix["cw"]["X-Aws-Role-Arn"], "arn:x")

    @patch("services.llm.mcp_client._mcp")
    def test_build_toolsets_no_headers_when_default(self, mock_mcp):
        from services.llm import mcp_client
        from services.environments import Endpoints
        with patch.object(mcp_client._environments, "current", return_value=Endpoints()), \
             patch.object(mcp_client._cfg, "CLOUDWATCH_MCP_URL", "http://127.0.0.1:8005/mcp"):
            mcp_client._build_toolsets()
        by_prefix = {c.args[1]: c.args[2] for c in mock_mcp.call_args_list}
        self.assertIsNone(by_prefix["prom"])
        self.assertIsNone(by_prefix["k8s"])
        self.assertNotIn("cw", by_prefix)  # no AWS endpoint → no CloudWatch toolset

    @patch("services.llm.mcp_client._cfg")
    def test_bedrock_without_role_uses_plain_string(self, mock_cfg):
        from services.llm.mcp_client import _resolve_model
        mock_cfg.AI_PROVIDER = "bedrock"
        mock_cfg.OPENAI_MODEL = "us.anthropic.claude-sonnet-4-5"
        mock_cfg.AWS_ROLE_ARN = ""
        self.assertEqual(_resolve_model(), "bedrock:us.anthropic.claude-sonnet-4-5")

    @patch("services.llm.mcp_client._bedrock_assumed_role_model")
    @patch("services.llm.mcp_client._cfg")
    def test_bedrock_with_role_uses_assumed_model(self, mock_cfg, mock_assumed):
        from services.llm.mcp_client import _resolve_model
        mock_cfg.AI_PROVIDER = "bedrock"
        mock_cfg.OPENAI_MODEL = "m"
        mock_cfg.AWS_ROLE_ARN = "arn:aws:iam::1:role/x"
        sentinel = object()
        mock_assumed.return_value = sentinel
        self.assertIs(_resolve_model(), sentinel)
        mock_assumed.assert_called_once()

    @patch("services.llm.mcp_client._bedrock_assumed_role_model", return_value=None)
    @patch("services.llm.mcp_client._cfg")
    def test_bedrock_role_failure_falls_back_to_string(self, mock_cfg, _mock_assumed):
        from services.llm.mcp_client import _resolve_model
        mock_cfg.AI_PROVIDER = "bedrock"
        mock_cfg.OPENAI_MODEL = "m"
        mock_cfg.AWS_ROLE_ARN = "arn:aws:iam::1:role/x"
        self.assertEqual(_resolve_model(), "bedrock:m")

    @patch("services.llm.mcp_client._cfg")
    def test_all_provider_strings_are_recognized_by_pydantic_ai(self, mock_cfg):
        # Regression guard: pydantic-ai must RECOGNISE every emitted prefix.
        # A missing provider lib (ImportError) or missing API key is fine —
        # those mean the prefix resolved; only "Unknown provider" is a bug
        # (previously hit by google-gla: and test:echo).
        from pydantic_ai.models import infer_model
        from services.llm.mcp_client import _model_string

        mock_cfg.OPENAI_MODEL = "gpt-4o"
        for provider in _EXPECTED_PREFIX:
            mock_cfg.AI_PROVIDER = provider
            s = _model_string()
            try:
                infer_model(s)
            except ValueError as e:
                self.assertNotIn("Unknown provider", str(e), f"{provider}: {s!r} not recognized")
            except Exception:
                pass  # missing lib / missing credentials → prefix recognized


if __name__ == "__main__":
    unittest.main()
