import re

from alert_context import AlertContext


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

_SECTION_ALIASES = {
    r"^[\s*]*Alert\s+[Ss]ummary:\s*$": "*Alert summary:*",
    r"^[\s*]*Subject:\s*$": "*Subject:*",
    r"^[\s*]*Metrics[^:]*:\s*$": "*Metrics:*",
    r"^[\s*]*Findings:\s*$": "*Findings:*",
    r"^[\s*]*Data\s+gaps:\s*$": "*Data gaps:*",
    r"^[\s*]*Probable\s+[Rr]oot\s+[Cc]ause:\s*$": "*Probable root cause:*",
    r"^[\s*]*Recommended\s+[Aa]ctions:\s*$": "*Recommended actions:*",
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
        if stripped.startswith("*") and stripped.endswith("*:"):
            in_bullet_section = stripped.lower() in (
                "*metrics:*",
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
    match = re.search(
        r"\*Metrics:\*(.*?)(?=\*Findings:\*|\*Data gaps:\*|\*Probable root cause:\*|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return 0
    section = match.group(1)
    return len(re.findall(r"^[\s]*[•\-]\s+", section, re.MULTILINE))


def _strip_false_exporter_down(text: str, prefetched: dict | None) -> str:
    if not prefetched:
        return text
    up = prefetched.get("up")
    alert_valid = prefetched.get("alert_valid")
    if up != 1 and not alert_valid:
        return text
    lines = text.splitlines()
    return "\n".join(line for line in lines if not _FALSE_EXPORTER_DOWN.match(line))


def _remove_redundant_data_gaps(text: str, prefetched: dict | None) -> str:
    if not prefetched or not prefetched.get("bullets"):
        return text
    if _count_metric_bullets(text) >= 3:
        return re.sub(
            r"\*Data gaps:\*.*?(?=\*Probable root cause:\*|\*Recommended actions:\*|\Z)",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()
    return text


def _inject_prefetched_metrics(text: str, prefetched: dict | None, ctx: AlertContext) -> str:
    if not prefetched or ctx.resource_type != "host":
        return text
    bullets = prefetched.get("bullets") or []
    if not bullets:
        return text

    existing = _count_metric_bullets(text)
    if existing >= 3:
        return text

    bullet_lines = "\n".join(f"• {b}" for b in bullets)
    metrics_match = re.search(r"\*Metrics:\*", text, re.IGNORECASE)
    if metrics_match:
        insert_at = metrics_match.end()
        return text[:insert_at] + "\n" + bullet_lines + text[insert_at:]

    summary_match = re.search(r"\*Alert summary:\*", text, re.IGNORECASE)
    if summary_match:
        block = f"\n\n*Metrics:*\n{bullet_lines}"
        end = text.find("\n", summary_match.end())
        if end == -1:
            return text + block
        return text[: end + 1] + block + text[end + 1 :]

    return f"*Metrics:*\n{bullet_lines}\n\n{text}"


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
    text = _inject_prefetched_metrics(text, prefetched, ctx)
    text = _remove_redundant_data_gaps(text, prefetched)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    missing = _missing_sections(text)
    if missing:
        text = f"[structure incomplete: missing {', '.join(missing)}]\n\n{text}"

    if ctx.resource_type == "host" and prefetched:
        metric_count = _count_metric_bullets(text)
        if metric_count < 2 and prefetched.get("bullets"):
            text = f"[metrics incomplete]\n\n{text}"

    return text
