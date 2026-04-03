# ADsP YouTube Summary Blog Automation

유튜브 URL을 입력하면 ADsP 학습노트형 블로그 글과 대표 이미지를 생성하고, GitHub Pages에 배포하는 프로젝트입니다.

## What This Implements

- 입력: `workflow_dispatch`에서 `youtube_url`, `publish` 파라미터
- 처리:
  - URL 화이트리스트 검증
  - 자막 우선 전사, 실패 시 Whisper 전사
  - LLM 기반 학습노트형 요약 생성
  - 문단별 타임스탬프 출처 형식 검사
  - 글당 대표 이미지 1장 생성
  - 품질 게이트 통과 시 파일 생성
- 출력:
  - 초안: `_drafts/YYYY-MM-DD-*.md` (`publish=false`)
  - 발행: `_posts/YYYY-MM-DD-*.md` (`publish=true`)
  - 이미지: `assets/images/YYYYMMDD-*.png`

## Repository Structure

- `scripts/generate_post.py`: 생성 파이프라인 엔트리
- `scripts/quality.py`: 출처/길이/금칙어 품질 검사
- `config/whitelist.json`: 허용 채널/재생목록/키워드 정책
- `config/quality_rules.json`: 품질 기준
- `.github/workflows/generate-post.yml`: 수동 실행 생성 워크플로우
- `.github/workflows/deploy-pages.yml`: Pages 빌드/배포 워크플로우

## Required Secrets and Variables

GitHub repository settings에서 아래 값을 설정하세요.

- `Secrets`
  - `OPENAI_API_KEY`
- `Variables` (optional)
  - `OPENAI_SUMMARY_MODEL` (default: `gpt-5-mini`)
  - `OPENAI_IMAGE_MODEL` (default: `gpt-image-1`)
  - `WHISPER_MODEL` (default: `whisper-1`)

## Whitelist Setup

`config/whitelist.json`에서 실제 데이터에듀 채널/재생목록 정보를 설정하세요.

- `allowed_channel_ids`: 예) `["UCxxxx"]`
- `allowed_playlist_ids`: 예) `["PLxxxx"]`
- `allowed_title_keywords`: 초기값은 ADsP 1과목 키워드 기반
- `allowed_channel_name_keywords`: 채널명 키워드 기반 보조 필터
- `strict_channel_match`, `strict_playlist_match`: 엄격 검증 여부

초기 기본값은 키워드 필터 중심이며, 운영 시 채널/재생목록 ID를 채우는 것을 권장합니다.

## How To Run (GitHub Actions)

1. GitHub Actions에서 `Generate ADsP Post` 워크플로우 실행
2. `youtube_url` 입력
3. `publish=false`로 먼저 초안 PR 생성 및 검수
4. 승인 후 `publish=true`로 재실행하여 `_posts`에 발행

## 초보자 빠른 시작

GitHub를 막 시작했다면 `docs/SETUP_KR.md`를 먼저 따라가면 됩니다.

## Local Run (Optional)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
python scripts/generate_post.py --youtube-url "https://www.youtube.com/watch?v=..." --publish false
```

## Quality Gate Rules

`config/quality_rules.json`로 조정 가능합니다.

- 최소 본문 길이
- 최소 출처 개수
- 금칙어 목록
- 문단별 출처 형식 `[출처: 영상명, MM:SS]`
- `References` 섹션 내 영상 URL 필수

## Notes

- 원문 전사 전체를 공개하지 않고 요약 중심으로 작성합니다.
- 생성 글에는 AI 생성 고지를 포함합니다.
- 본 저장소는 Jekyll 기반 GitHub Pages를 사용합니다.
