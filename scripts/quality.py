import re
from dataclasses import dataclass


CITATION_PATTERN = re.compile(r"\[출처:\s*.+?,\s*\d{1,2}:\d{2}\]")


@dataclass
class QualityReport:
    ok: bool
    failures: list[str]


def _is_noncontent_block(block: str) -> bool:
    stripped = block.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith("```"):
        return True
    if stripped.startswith("- "):
        return True
    return False


def _split_blocks(markdown_text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", markdown_text) if chunk.strip()]


def _has_required_references(markdown_text: str) -> bool:
    has_ref_header = "## References" in markdown_text
    has_url = ("https://www.youtube.com/" in markdown_text) or ("https://youtu.be/" in markdown_text)
    return has_ref_header and has_url


def validate_markdown(markdown_text: str, min_body_chars: int, min_citation_count: int, banned_terms: list[str]) -> QualityReport:
    failures: list[str] = []

    body_chars = len(markdown_text.strip())
    if body_chars < min_body_chars:
        failures.append(f"Body too short: {body_chars} < {min_body_chars}")

    citations = CITATION_PATTERN.findall(markdown_text)
    if len(citations) < min_citation_count:
        failures.append(f"Not enough citations: {len(citations)} < {min_citation_count}")

    for block in _split_blocks(markdown_text):
        if _is_noncontent_block(block):
            continue
        if "References" in block:
            continue
        if not CITATION_PATTERN.search(block):
            preview = block.replace("\n", " ")[:80]
            failures.append(f"Paragraph missing citation: {preview}")

    if not _has_required_references(markdown_text):
        failures.append("References section with source URL is required.")

    lowered = markdown_text.lower()
    for term in banned_terms:
        if term.lower() in lowered:
            failures.append(f"Banned term found: {term}")

    return QualityReport(ok=not failures, failures=failures)
