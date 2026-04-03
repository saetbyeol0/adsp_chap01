# 초보자용 GitHub Pages 배포 가이드 (이 프로젝트 기준)

이 문서는 GitHub를 막 시작한 분이 이 저장소를 **GitHub Pages로 배포**하고, **유튜브 URL로 글을 생성**할 수 있게 만드는 최소 절차입니다.

## 1) GitHub 저장소 만들기 (웹에서)

1. GitHub 로그인 후 우측 상단 `+` → `New repository`
2. Repository name 예: `adsp-study-blog`
3. Public 권장 (Pages 접근이 쉬움)
4. `Add a README`는 체크하지 않기 (이미 로컬에 있음)
5. `Create repository`

## 2) 파일 업로드 (Git을 몰라도 되는 방식)

1. 방금 만든 저장소 페이지에서 `Add file` → `Upload files`
2. 이 프로젝트 폴더(`test_day2`)의 파일/폴더를 드래그해서 업로드
3. 커밋 메시지 예: `initial import`
4. `Commit changes`

## 3) GitHub Pages 켜기

1. 저장소 `Settings` → `Pages`
2. `Build and deployment`에서 `Source`가 **GitHub Actions**인지 확인
3. 배포 워크플로우는 `.github/workflows/deploy-pages.yml`가 담당
4. `Actions` 탭에서 `Deploy GitHub Pages`가 성공하면 Pages URL이 생성됨

## 4) OpenAI API Key 등록 (필수)

1. 저장소 `Settings` → `Secrets and variables` → `Actions`
2. `New repository secret`
3. Name: `OPENAI_API_KEY`
4. Value: 본인 OpenAI API Key

## 5) (권장) 모델 변수 설정

같은 화면에서 `Variables` 탭에서 아래를 추가할 수 있습니다(없으면 기본값 사용).

- `OPENAI_SUMMARY_MODEL` (기본 `gpt-5-mini`)
- `OPENAI_IMAGE_MODEL` (기본 `gpt-image-1`)
- `WHISPER_MODEL` (기본 `whisper-1`)

## 6) 화이트리스트 채우기 (권장: 채널/플레이리스트 ID 고정)

초기 기본값은 키워드/채널명 키워드 필터라 느슨합니다. 운영할 때는 ID를 채우는 것을 권장합니다.

1. 로컬에서 아래 실행:

```bash
py scripts/inspect_youtube.py --youtube-url "유튜브_영상_URL"
```

2. 출력된 `channel_id`, `playlist_id`를 `config/whitelist.json`에 넣기
3. `allowed_channel_ids` / `allowed_playlist_ids`를 채우면 자동으로 해당 ID만 허용합니다
4. `strict_playlist_match=true`를 켜면 URL에 `list=...`가 없는 경우도 차단해서 더 엄격해집니다

## 7) 글 생성 실행 (Actions)

1. `Actions` → `Generate ADsP Post`
2. `Run workflow`
3. `youtube_url` 입력
4. `publish`는 처음엔 `false` 권장(초안 PR로 검수)
5. PR 검수 후 `publish=true`로 다시 실행하면 `_posts`로 발행

## 트러블슈팅

- 워크플로우에서 Whisper fallback이 실패하면: FFmpeg 설치가 필요합니다(워크플로우에 포함됨).
- 화이트리스트가 너무 빡빡하면: `config/whitelist.json`에서 키워드/ID 정책을 조정하세요.
