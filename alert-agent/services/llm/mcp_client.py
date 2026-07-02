from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import FastMCPClient, MCPToolset, StreamableHttpTransport

from services.classification.alert_classifier import alert_for_prompt, build_alert_context
import config as _cfg
from config import (
    K8S_MCP_URL,
    KAFKA_MCP_URL,
    LOKI_MCP_URL,
    OPENAI_MODEL,
    PROMETHEUS_MCP_URL,
)
from services.metrics.prefetch import prefetched_to_prompt_block


PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "rca_prompt.txt"


def _mcp(url: str, prefix: str):
    return MCPToolset(FastMCPClient(transport=StreamableHttpTransport(url))).prefixed(prefix)


def _build_toolsets():
    return [
        _mcp(_cfg.K8S_MCP_URL, "k8s"),
        _mcp(_cfg.PROMETHEUS_MCP_URL, "prom"),
        _mcp(_cfg.LOKI_MCP_URL, "loki"),
        _mcp(_cfg.KAFKA_MCP_URL, "kafka"),
    ]


def _model_string() -> str:
    provider = getattr(_cfg, "AI_PROVIDER", "openai")
    model = getattr(_cfg, "OPENAI_MODEL", OPENAI_MODEL)
    if provider == "anthropic":
        return f"anthropic:{model}"
    if provider == "gemini":
        return f"google-gla:{model}"
    if provider == "bedrock":
        return f"bedrock:{model}"
    if provider == "fake":
        return "test:echo"
    return f"openai-chat:{model}"


def create_agent() -> Agent:
    return Agent(
        _model_string(),
        instructions=PROMPT_PATH.read_text(),
        output_type=str,
        toolsets=_build_toolsets(),
        retries=2,
    )


async def run_investigation(alert: dict, prefetched: dict | None = None) -> str:
    agent = create_agent()
    context = build_alert_context(alert)
    alert_payload = alert_for_prompt(alert, context)
    prefetched_block = prefetched_to_prompt_block(prefetched)

    prompt_parts = [
        "Investigate this Alertmanager alert and produce an RCA using the required format.",
        "",
        "Resolved context:",
        context.to_prompt_block(),
    ]
    if prefetched_block:
        prompt_parts.extend(["", prefetched_block])
    prompt_parts.extend(
        [
            "",
            "Alert JSON:",
            str(alert_payload),
        ]
    )
    prompt = "\n".join(prompt_parts)

    async with agent:
        result = await agent.run(prompt)

    return result.output
