from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from alert_context import build_alert_context
from config import (
    K8S_MCP_URL,
    KAFKA_MCP_URL,
    LOKI_MCP_URL,
    OPENAI_MODEL,
    PROMETHEUS_MCP_URL,
)


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


async def run_investigation(alert: dict) -> str:
    agent = create_agent()
    context = build_alert_context(alert)

    prompt = f"""
Investigate this Alertmanager alert and produce an RCA using the required format.

Resolved context:
{context.to_prompt_block()}

Alert JSON:
{alert}
""".strip()

    async with agent:
        result = await agent.run(prompt)

    return result.output
