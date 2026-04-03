from scripts.quality import validate_markdown


def test_quality_passes_with_citations_and_references() -> None:
    md = """
# 테스트

핵심 개념 설명입니다. [출처: 예시 영상, 01:10]

추가 설명입니다. [출처: 예시 영상, 02:20]

## References
- 채널명: 테스트
- 영상 URL: https://www.youtube.com/watch?v=abc123
"""
    report = validate_markdown(md, min_body_chars=10, min_citation_count=2, banned_terms=[])
    assert report.ok


def test_quality_fails_without_references() -> None:
    md = """
# 테스트

핵심 개념 설명입니다. [출처: 예시 영상, 01:10]
"""
    report = validate_markdown(md, min_body_chars=10, min_citation_count=1, banned_terms=[])
    assert not report.ok
    assert any("References" in failure for failure in report.failures)
