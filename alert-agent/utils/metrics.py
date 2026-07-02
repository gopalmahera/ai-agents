"""Shared Prometheus counters for the alert agent."""
from prometheus_client import Counter

alerts_received = Counter(
    "alert_agent_alerts_received_total",
    "Total alerts received from Alertmanager",
    ["alertname"],
)
alerts_deduplicated = Counter(
    "alert_agent_alerts_deduplicated_total",
    "Duplicate alerts dropped by dedup cache",
)
alerts_skipped = Counter(
    "alert_agent_alerts_skipped_total",
    "Alerts skipped (non-firing status or filtered by allowlist)",
)
alerts_accepted = Counter(
    "alert_agent_alerts_accepted_total",
    "Alerts accepted and queued for investigation",
)
llm_investigations = Counter(
    "alert_agent_llm_investigations_total",
    "LLM investigation outcomes",
    ["outcome"],  # "success", "fallback", "error"
)
slack_posts = Counter(
    "alert_agent_slack_posts_total",
    "Slack post outcomes",
    ["outcome"],  # "success", "error"
)
