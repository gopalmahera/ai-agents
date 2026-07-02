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
import services.store.redis_client as _redis
from utils.log import get_logger

logger = get_logger(__name__)

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


def _selected_model(severity: str | None = None) -> str:
    """Raw model name after severity-based cost routing (no provider prefix)."""
    provider = getattr(_cfg, "AI_PROVIDER", "openai")
    model = getattr(_cfg, "OPENAI_MODEL", OPENAI_MODEL)
    if provider == "openai" and (severity or "").lower() == "info":
        model = getattr(_cfg, "OPENAI_MODEL_INFO", "gpt-4o-mini")
    return model


def _model_string(severity: str | None = None) -> str:
    provider = getattr(_cfg, "AI_PROVIDER", "openai")
    model = _selected_model(severity)
    if provider == "anthropic":
        return f"anthropic:{model}"
    if provider == "gemini":
        return f"google:{model}"
    if provider == "bedrock":
        return f"bedrock:{model}"
    if provider == "fake":
        return "test"
    return f"openai-chat:{model}"


def _record_usage(severity: str | None, result) -> dict | None:
    """Price the LLM run's token usage, store aggregates in Redis, and return
    a per-run usage dict (for dual-writing to the history store).

    Fully defensive: any failure here (missing usage, unknown model in the
    price DB, Redis down) must never affect the RCA that was produced.
    """
    provider = getattr(_cfg, "AI_PROVIDER", "openai")
    if provider == "fake":
        return None  # the test model has no real cost
    try:
        usage = result.usage
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        model = _selected_model(severity)
        cost_micro = 0
        try:
            from genai_prices import Usage, calc_price
            calc = calc_price(
                Usage(input_tokens=input_tokens, output_tokens=output_tokens),
                model_ref=model,
            )
            cost_micro = int(round(float(calc.total_price) * 1_000_000))
        except Exception as exc:
            logger.warning(
                "LLM cost pricing failed; recording tokens only",
                extra={"event": "llm_cost_price_error", "error": str(exc)},
            )
        _redis.record_llm_usage(model, input_tokens, output_tokens, cost_micro)
        return {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost_micro / 1_000_000, 6),
        }
    except Exception as exc:
        logger.warning(
            "Failed to record LLM usage",
            extra={"event": "llm_cost_record_error", "error": str(exc)},
        )
        return None


def create_agent(severity: str | None = None) -> Agent:
    return Agent(
        _model_string(severity),
        instructions=PROMPT_PATH.read_text(),
        output_type=str,
        toolsets=_build_toolsets(),
        retries=2,
    )


async def run_investigation(alert: dict, prefetched: dict | None = None) -> tuple[str, dict | None]:
    severity = alert.get("labels", {}).get("severity")
    agent = create_agent(severity)
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

    usage = _record_usage(severity, result)
    return result.output, usage
