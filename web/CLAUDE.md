# web/ — Next.js 대시보드

웹 작업 규칙은 루트 [`.claude/rules/web-conventions.md`](../.claude/rules/web-conventions.md). 아래는 이 폴더에서 자주 걸리는 것만.

- API 타입: 엔진 응답을 바꾸면 `pnpm gen:api` — 응답 타입을 손으로 쓰지 않음
- 타입 검사: `pnpm typecheck` (`next typegen` 후 `tsc` — `PageProps`·`RouteContext` 같은 전역 타입이 생성돼야 함)
- 포맷 도구 설정이 없음 — prettier 등을 돌리지 않음 (손댄 줄 밖까지 줄바꿈이 바뀜)
- 엔진 API 는 루프백 전용 — 브라우저는 Next 라우트(`src/app/api/`)를 거쳐 받음
- README 캡처는 **가상 데이터로만** — 거래소 약관상 실제 시세를 공개할 수 없음. `uv run --project engine orbit demo-data` → `uv run --project engine orbit serve --demo --db data/demo.sqlite` + `NEXT_PUBLIC_ORBIT_DEMO=1 pnpm dev`, headless Chrome `--force-device-scale-factor=2`

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
