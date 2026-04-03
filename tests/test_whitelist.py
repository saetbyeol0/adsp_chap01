from scripts.generate_post import get_playlist_id
from scripts.generate_post import validate_whitelist


def test_get_playlist_id_from_url() -> None:
    url = "https://www.youtube.com/watch?v=abc123&list=PL_TEST_1"
    assert get_playlist_id(url) == "PL_TEST_1"


def test_validate_whitelist_accepts_matching_metadata() -> None:
    whitelist = {
        "allowed_channel_ids": [],
        "allowed_playlist_ids": [],
        "allowed_title_keywords": ["ADsP", "데이터 이해"],
        "allowed_channel_name_keywords": ["데이터에듀"],
        "strict_channel_match": False,
        "strict_playlist_match": False,
    }
    metadata = {"channel": "데이터에듀 공식채널", "title": "ADsP 1과목 데이터 이해 1강"}
    validate_whitelist("https://www.youtube.com/watch?v=abc123", metadata, whitelist)
