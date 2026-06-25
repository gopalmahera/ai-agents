from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from alert_context import alert_for_prompt, build_alert_context
from config import (
    K8S_MCP_URL,
    KAFKA_MCP_URL,
    LOKI_MCP_URL,
    OPENAI_MODEL,
    PROMETHEUS_MCP_URL,
)
from prefetch import prefetched_to_prompt_block


PROMPT_PATH = Path(__file__).parent / "prompts" / "rca_prompt.txt"


def _build_toolsets():
    return [
        MCPServerStreamableHTTP(K8S_MCP_URL, tool_prefix="k8s"),
        MCPServerStreamableHTTP(PROMETHEUS_MCP_URL, tool_prefix="prom"),
        MCPServerStreamableHTTP(LOKI_MCP_URL, tool_prefix="loki"),
        MCPServerStreamableHTTP(KAFKA_MCP_URL, tool_prefix="kafka"),
    ]


def create_agent() -> Agent:
    return Agent(
        f"openai-chat:{OPENAI_MODEL}",
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
