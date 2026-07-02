"""Prometheus counters for Dozee Alert Intelligence (DAI)."""
from prometheus_client import Counter

alerts_received = Counter(
    "dai_alerts_received_total",
    "Total alerts received from Alertmanager",
    ["alertname"],
)
alerts_deduplicated = Counter(
    "dai_alerts_deduplicated_total",
    "Duplicate alerts dropped by dedup cache",
)
alerts_skipped = Counter(
    "dai_alerts_skipped_total",
    "Alerts skipped (non-firing status or filtered by allowlist)",
)
alerts_silenced = Counter(
    "dai_alerts_silenced_total",
    "Alerts suppressed by an active silence rule",
)
alerts_accepted = Counter(
    "dai_alerts_accepted_total",
    "Alerts accepted and queued for investigation",
)
llm_investigations = Counter(
    "dai_llm_investigations_total",
    "LLM investigation outcomes",
    ["outcome"],
)
slack_posts = Counter(
    "dai_slack_posts_total",
    "Slack post outcomes",
    ["outcome"],
)
