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
    """Remove subject identity lines before the first section header."""
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


def format_rca(rca: str, ctx: AlertContext) -> str:
    text = rca.strip()
    text = _NA_LINE.sub("", text)
    text = _TOOL_NAME.sub("metrics query", text)
    text = _strip_leading_subject_lines(text)
    text = _normalize_section_headers(text)
    text = _normalize_bullets(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    missing = _missing_sections(text)
    if missing:
        text = f"[structure incomplete: missing {', '.join(missing)}]\n\n{text}"

    return text
