from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

from config import K8S_MCP_URL, LOKI_MCP_URL, OPENAI_MODEL, PROMETHEUS_MCP_URL


PROMPT_PATH = Path(__file__).parent / "prompts" / "rca_prompt.txt"


def _build_toolsets():
    return [
        MCPServerStreamableHTTP(K8S_MCP_URL, tool_prefix="k8s"),
        MCPServerStreamableHTTP(PROMETHEUS_MCP_URL, tool_prefix="prom"),
        MCPServerStreamableHTTP(LOKI_MCP_URL, tool_prefix="loki"),
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

    prompt = f"""
Investigate this Alertmanager alert and produce an RCA using the required format.

Alert JSON:
{alert}
""".strip()

    async with agent:
        result = await agent.run(prompt)

    return result.output
