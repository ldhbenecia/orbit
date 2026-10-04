# Git / 커밋 / PR 컨벤션

## 브랜치 (GitHub Flow)

- `main` 단일 트렁크, 직접 push 금지
- 작업 브랜치: `feature/<slug>`, `fix/<slug>`, `refactor/<slug>`, `docs/<slug>`, `chore/<slug>`
- 브랜치는 upstream 을 main 으로 잡지 않는다: `git switch -c <branch> --no-track origin/main`, 첫 push 는 `git push -u origin <branch>`
- 머지: merge commit (squash·rebase X). 머지 후 브랜치는 보관

## 커밋 (Conventional Commits)

- 형식: `type(scope): 한국어 주제`
- scope 예: `strategy`, `backtest`, `ledger`, `risk`, `broker`, `upbit`, `toss`, `data`, `api`, `web`, `notify`, `ops`, `harness`
- subject: 한국어 명사구 또는 한국어 동사 마무리. 영어 명령형 동사(`add`, `update`) 피함
- body: bullet(`- `)로 WHY 위주
- 의미 단위로 잘게. 한 커밋 = 한 변경 + 테스트 통과 상태
- 커밋 메시지에 금액·잔고·계좌 정보 금지 (→ [secrets-and-privacy](secrets-and-privacy.md))

## PR

- 제목도 Conventional Commits 형식
- 본문은 `.github/pull_request_template.md` 양식 (요약 / 작업 사항 / 체크리스트)
- assignee: `ldhbenecia`
- 한 PR = 실질 기능 하나 (코드 + 테스트 + 필요 시 화면). 너무 잘게 쪼개지 않는다
- 직렬화: 다음 작업은 직전 PR 머지 확인 후

## 버전

- patch 기본, 체감 기능 묶음당 minor 1회, docs·CI 만이면 bump 없음
