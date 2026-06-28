import re

from alert_catalog import get_alert_meaning
from alert_context import AlertContext
from host_metrics import build_findings_bullets, default_host_actions
from kafka_metrics import build_findings_bullets as build_kafka_findings_bullets
from pod_metrics import build_findings_bullets as build_pod_findings_bullets


_REQUIRED_SECTIONS = [
    "alert summary",
    "subject",
    "metrics",
    "findings",
    "probable root cause",
    "recommended actions",
]

_NA_LINE = re.compile(
    r"^[\s*]*(Namespace|Pod):\s*N/A.*$",
    re.MULTILINE | re.IGNORECASE,
)

_TOOL_NAME = re.compile(
    r"\b(?:k8s|prom|loki|kafka)_[a-z_]+\b",
    re.IGNORECASE,
)

_LEADING_SUBJECT = re.compile(
    r"^(?:Namespace|Pod|Instance|Target|Topic|Consumer\s*Group|Module):\s*.+\n+",
    re.MULTILINE | re.IGNORECASE,
)

_FALSE_EXPORTER_DOWN = re.compile(
    r"^[\s•\-]*.*\b(node.exporter|node-exporter|scrape)\b.*\b(down|not retrievable|unavailable|failure|failed|issues)\b.*$",
    re.MULTILINE | re.IGNORECASE,
)

_FALSE_MISSING_LIMITS = re.compile(
    r"^[\s•\-]*.*\b(missing|no|without|unconfigured)\b.*\b(cpu|memory)\b.*\blimit",
    re.MULTILINE | re.IGNORECASE,
)

_METRICS_SECTION = re.compile(
    r"(\*Metrics:\*)(.*?)(?=\*Workload:\*|\*Findings:\*|\*Data gaps:\*|\*Probable root cause:\*|\*Recommended actions:\*|\Z)",
    re.DOTALL | re.IGNORECASE,
)

_FINDINGS_SECTION = re.compile(
    r"(\*Findings:\*)(.*?)(?=\*Data gaps:\*|\*Probable root cause:\*|\*Recommended actions:\*|\Z)",
    re.DOTALL | re.IGNORECASE,
)

_SECTION_ALIASES = {
    r"^[\s*]*Alert\s+[Ss]ummary:\s*$": "*Alert summary:*",
    r"^[\s*]*What\s+this\s+alert\s+means:\s*$": "*What this alert means:*",
    r"^[\s*]*Subject:\s*$": "*Subject:*",
    r"^[\s*]*Metrics[^:]*:\s*$": "*Metrics:*",
    r"^[\s*]*Workload:\s*$": "*Workload:*",
    r"^[\s*]*Findings:\s*$": "*Findings:*",
    r"^[\s*]*Data\s+gaps:\s*$": "*Data gaps:*",
    r"^[\s*]*Probable\s+[Rr]oot\s+[Cc]ause:\s*$": "*Probable root cause:*",
    r"^[\s*]*Recommended\s+[Aa]ctions:\s*$": "*Recommended actions:*",
}

_EMOJI_SECTIONS = {
    "*What this alert means:*": ":mag: *What this alert means:*",
    "*Metrics:*": ":bar_chart: *Metrics:*",
    "*Workload:*": ":package: *Workload:*",
    "*Findings:*": ":clipboard: *Findings:*",
    "*Probable root cause:*": ":dart: *Probable root cause:*",
    "*Recommended actions:*": ":wrench: *Recommended actions:*",
}


def _normalize_section_headers(text: str) -> str:
    lines = text.splitlines()
    normalized = []
    for line in lines:
        updated = line
        for pattern, replacement in _SECTION_ALIASES.items():
            if re.match(pattern, line.strip()):
                updated = replacement
                break
        normalized.append(updated)
    return "\n".join(normalized)


def _normalize_bullets(text: str) -> str:
    in_bullet_section = False
    lines = text.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        # Section headers use Slack bold format: *Section name:*
        # They start AND end with *, e.g. "*Metrics:*", "*Findings:*"
        if stripped.startswith("*") and stripped.endswith(":*"):
            in_bullet_section = stripped.lower() in (
                "*metrics:*",
                "*workload:*",
                "*findings:*",
                "*data gaps:*",
            )
            result.append(line)
            continue
        if in_bullet_section and stripped.startswith("- "):
            result.append("• " + stripped[2:])
        else:
            result.append(line)
    return "\n".join(result)


def _strip_leading_subject_lines(text: str) -> str:
    first_section = re.search(r"^\*Alert summary:\*", text, re.MULTILINE | re.IGNORECASE)
    if not first_section:
        return text
    prefix = text[: first_section.start()]
    if _LEADING_SUBJECT.search(prefix):
        return text[first_section.start() :]
    return text


def _missing_sections(text: str) -> list[str]:
    lower = text.lower()
    return [section for section in _REQUIRED_SECTIONS if section not in lower]


def _count_metric_bullets(text: str) -> int:
    match = _METRICS_SECTION.search(text)
    if not match:
        return 0
    section = match.group(2)
    return len(re.findall(r"^[\s]*[•\-]\s+", section, re.MULTILINE))


def _normalize_metric_key(line: str) -> str:
    cleaned = re.sub(r"^[\s•\-]+", "", line.strip()).lower()
    cleaned = re.sub(r"\s*\[from alert\]\s*$", "", cleaned)
    cleaned = re.sub(r"\s*\(threshold[^)]*\)\s*$", "", cleaned)
    return cleaned.split(":")[0].strip()


def _dedupe_bullet_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = _normalize_metric_key(line)
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def _strip_false_exporter_down(text: str, prefetched: dict | None) -> str:
    if not prefetched:
        return text
    up = prefetched.get("up")
    alert_valid = prefetched.get("alert_valid")
    if up != 1 and not alert_valid:
        return text
    lines = text.splitlines()
    return "\n".join(line for line in lines if not _FALSE_EXPORTER_DOWN.match(line))


def _strip_false_missing_limits(text: str, prefetched: dict | None, ctx: AlertContext) -> str:
    if ctx.alertname not in ("PODCPULimitsUage>=90", "PODMemoryLimitsUage>=90"):
        return text
    if not prefetched or not prefetched.get("alert_valid"):
        return text
    snapshot = prefetched.get("snapshot") or {}
    if snapshot.get("usage_percent") is None and not prefetched.get("bullets"):
        return text
    lines = text.splitlines()
    return "\n".join(line for line in lines if not _FALSE_MISSING_LIMITS.match(line))


def _should_remove_data_gaps(text: str, prefetched: dict | None) -> bool:
    if not prefetched:
        return False
    if prefetched.get("up") == 1:
        return True
    snapshot = prefetched.get("snapshot") or {}
    if snapshot.get("resource") == "kafka" and prefetched.get("alert_valid"):
        if snapshot.get("consumer_lag") is not None or prefetched.get("bullets"):
            return True
    if snapshot.get("resource") in ("cpu", "memory") and prefetched.get("alert_valid"):
        if snapshot.get("usage_percent") is not None or prefetched.get("bullets"):
            return True
    if prefetched.get("alert_valid") and _count_metric_bullets(text) >= 1:
        if snapshot.get("major_page_faults_per_sec") is not None or prefetched.get("bullets"):
            return _count_metric_bullets(text) >= 3
    return _count_metric_bullets(text) >= 3


def _remove_redundant_data_gaps(text: str, prefetched: dict | None) -> str:
    if not _should_remove_data_gaps(text, prefetched):
        return text
    return re.sub(
        r"\*Data gaps:\*.*?(?=\*Probable root cause:\*|\*Recommended actions:\*|\Z)",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()


def _replace_metrics_section(text: str, bullets: list[str]) -> str:
    if not bullets:
        return text
    bullet_lines = "\n".join(f"• {b}" for b in _dedupe_bullet_lines(bullets))
    if _METRICS_SECTION.search(text):
        return _METRICS_SECTION.sub(rf"\1\n{bullet_lines}\n", text, count=1)
    if re.search(r"\*Subject:\*", text, re.IGNORECASE):
        return re.sub(
            r"(\*Subject:\*.*?)(\n\*Workload:\*|\n\*Findings:\*|\n\*Data gaps:\*|\n\*Probable root cause:\*|\Z)",
            rf"\1\n\n*Metrics:*\n{bullet_lines}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return f"*Metrics:*\n{bullet_lines}\n\n{text}"


def _inject_section_after(
    text: str,
    after_header: str,
    new_header: str,
    bullets: list[str],
    before_headers: tuple[str, ...] = (
        "*Findings:*",
        "*Data gaps:*",
        "*Probable root cause:*",
        "*Recommended actions:*",
    ),
) -> str:
    if not bullets:
        return text
    if re.search(re.escape(new_header), text, re.IGNORECASE):
        return text

    bullet_lines = "\n".join(f"• {b}" for b in bullets)
    before_pattern = "|".join(re.escape(h) for h in before_headers)
    pattern = (
        rf"(\{re.escape(after_header)}.*?)"
        rf"(\n(?:{before_pattern})|\Z)"
    )
    if re.search(rf"\{re.escape(after_header)}", text, re.IGNORECASE):
        return re.sub(
            pattern,
            rf"\1\n\n{new_header}\n{bullet_lines}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return f"{text}\n\n{new_header}\n{bullet_lines}"


def _inject_alert_meaning(text: str, ctx: AlertContext, prefetched: dict | None) -> str:
    meaning = (prefetched or {}).get("alert_meaning") or get_alert_meaning(ctx.alertname)
    if not meaning:
        return text
    if re.search(r"\*What this alert means:\*", text, re.IGNORECASE):
        return text

    block = f"*What this alert means:*\n{meaning}"
    if re.search(r"\*Subject:\*", text, re.IGNORECASE):
        return re.sub(
            r"(\*Subject:\*.*?)(\n\*Metrics:\*|\n\*Workload:\*|\n\*Findings:\*|\Z)",
            rf"\1\n\n{block}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    if re.search(r"\*Alert summary:\*", text, re.IGNORECASE):
        return re.sub(
            r"(\*Alert summary:\*.*?)(\n\*Subject:\*|\n\*Metrics:\*|\Z)",
            rf"\1\n\n{block}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return f"{block}\n\n{text}"


def _inject_workload_section(text: str, prefetched: dict | None) -> str:
    bullets = list((prefetched or {}).get("workload_bullets") or [])
    if not bullets:
        workload = (prefetched or {}).get("workload") or {}
        bullets = list(workload.get("bullets") or [])
    if not bullets:
        return text
    return _inject_section_after(text, "*Metrics:*", "*Workload:*", bullets)


def _inject_findings(text: str, prefetched: dict | None, ctx: AlertContext) -> str:
    findings = list((prefetched or {}).get("findings") or [])
    if not findings and prefetched:
        snapshot = prefetched.get("snapshot") or {}
        if snapshot.get("resource") in ("cpu", "memory"):
            findings = build_pod_findings_bullets(ctx, prefetched)
        elif snapshot.get("resource") == "kafka":
            findings = build_kafka_findings_bullets(ctx, prefetched)
        else:
            findings = build_findings_bullets(ctx, prefetched)
    if not findings:
        return text

    if re.search(r"\*Findings:\*", text, re.IGNORECASE):
        return text

    bullet_lines = "\n".join(f"• {f}" for f in findings)
    if _METRICS_SECTION.search(text):
        return re.sub(
            r"(\*Metrics:\*.*?)(\n\*Workload:\*|\n\*Data gaps:\*|\n\*Probable root cause:\*|\n\*Recommended actions:\*|\Z)",
            rf"\1\n\n*Findings:*\n{bullet_lines}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    if re.search(r"\*Workload:\*", text, re.IGNORECASE):
        return re.sub(
            r"(\*Workload:\*.*?)(\n\*Data gaps:\*|\n\*Probable root cause:\*|\n\*Recommended actions:\*|\Z)",
            rf"\1\n\n*Findings:*\n{bullet_lines}\2",
            text,
            count=1,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return f"{text}\n\n*Findings:*\n{bullet_lines}"


def _merge_prefetched_metrics(text: str, prefetched: dict | None, ctx: AlertContext) -> str:
    if not prefetched or ctx.resource_type not in ("host", "kubernetes", "kafka"):
        return text
    bullets = prefetched.get("bullets") or []
    if not bullets:
        return text
    return _replace_metrics_section(text, bullets)


def _apply_emoji_sections(text: str) -> str:
    lines = text.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        result.append(_EMOJI_SECTIONS.get(stripped, line))
    return "\n".join(result)


def format_rca(
    rca: str,
    ctx: AlertContext,
    prefetched: dict | None = None,
) -> str:
    text = rca.strip()
    text = _NA_LINE.sub("", text)
    text = _TOOL_NAME.sub("metrics query", text)
    text = _strip_leading_subject_lines(text)
    text = _normalize_section_headers(text)
    text = _normalize_bullets(text)
    text = _strip_false_exporter_down(text, prefetched)
    text = _strip_false_missing_limits(text, prefetched, ctx)
    text = _merge_prefetched_metrics(text, prefetched, ctx)
    text = _inject_alert_meaning(text, ctx, prefetched)
    text = _inject_workload_section(text, prefetched)
    text = _inject_findings(text, prefetched, ctx)
    text = _remove_redundant_data_gaps(text, prefetched)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = _apply_emoji_sections(text)

    missing = _missing_sections(text)
    if missing:
        text = f"[structure incomplete: missing {', '.join(missing)}]\n\n{text}"

    return text
