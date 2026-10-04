# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- For multi-step tasks, state a brief plan with a verify step per item.

## 5. Verify Before Claiming

**Never report success or "no bugs" without evidence. Run the check.**

- Before saying "done": run the relevant tests / typecheck / build and state the result. If you couldn't run it, say so.
- Report outcomes faithfully: failing tests are shown, skipped steps are named.
- For outward-facing / costly / irreversible actions, confirm scope first and don't claim it happened until verified.

---

## orbit — 프로젝트 개요

코어(국내 상장 미국 ETF)는 사용자가 직접 매수하고, **위성(satellite) 포트폴리오만** 규칙 기반으로 자동매매하는 개인용 도구. 동시에 사용자가 **퀀트 트레이딩을 만들면서 배우는 연습장** — 결과물만큼 이해가 목표다 (→ [learning-mode](.claude/rules/learning-mode.md)).

- 대상: **BTC (최대 ETH 까지)** — 업비트 / **미국 개별주** — 토스증권 Open API
- 범위 밖: 국내 상장 ETF 매수(사용자 수동), 알트코인, 레버리지·공매도·선물·마진
- 구성: `engine/` Python (전략·백테스트·브로커 어댑터·가상 장부·스케줄러·FastAPI) + `web/` Next.js 대시보드
- 공개 레포 (GitHub public)

## 절대 규칙 (어기면 실제 돈이 사라짐)

**관련 영역을 건드리기 전에 해당 룰을 먼저 읽는다.**

- **돈 안전장치가 최우선** — [.claude/rules/money-safety.md](.claude/rules/money-safety.md): 금액은 `Decimal`, 가상 장부 예산 밖의 돈·직접 산 종목은 절대 손대지 않음, 기본값 dry-run, **실거래 전환·한도 상향은 사람만**. Claude 는 실주문을 실행하지 않는다.
- **공개 레포 보안** — [.claude/rules/secrets-and-privacy.md](.claude/rules/secrets-and-privacy.md): 키·계좌번호·잔고·매매 내역·개인 예산을 커밋·로그·PR·이슈 어디에도 남기지 않음.
- **전략 무결성** — [.claude/rules/strategy-rules.md](.claude/rules/strategy-rules.md): 전략은 순수 함수, 백테스트와 실거래가 같은 코드, 미래 데이터 참조 금지, 수수료·슬리피지 포함.
- **시간과 장 시간** — [.claude/rules/time-and-markets.md](.claude/rules/time-and-markets.md): 저장은 UTC, 장 경계는 거래소 타임존(`zoneinfo`), 오프셋 하드코딩 금지.
- **작업 시작 시 맥락 확인** — [.claude/rules/work-start-checklist.md](.claude/rules/work-start-checklist.md)

## 룰 인덱스

| 룰 | 언제 읽나 |
|---|---|
| [money-safety](.claude/rules/money-safety.md) | 주문·장부·리스크·브로커 코드 |
| [learning-mode](.claude/rules/learning-mode.md) | 새 개념 도입·실험·설명할 때 |
| [secrets-and-privacy](.claude/rules/secrets-and-privacy.md) | 설정·로그·커밋·문서 작성 |
| [strategy-rules](.claude/rules/strategy-rules.md) | 전략·백테스트·지표 |
| [time-and-markets](.claude/rules/time-and-markets.md) | 스케줄·캔들·날짜 로직 |
| [python-conventions](.claude/rules/python-conventions.md) | `engine/` |
| [web-conventions](.claude/rules/web-conventions.md) | `web/` (디자인 원칙 포함) |
| [git-conventions](.claude/rules/git-conventions.md) | 브랜치·커밋·PR |
| [code-comments](.claude/rules/code-comments.md) | 모든 코드 |
| [decisions-workflow](.claude/rules/decisions-workflow.md) | 비자명한 결정 |
| [incident-workflow](.claude/rules/incident-workflow.md) | 돈·주문·데이터 사고 |
| [progress-update](.claude/rules/progress-update.md) | 작업 일지 |

## 스킬

| 스킬 | 용도 |
|---|---|
| `new-strategy` | 전략 추가 (순수 함수 + 테스트 + 백테스트 등록 + 지식 문서 연결) |
| `backtest-review` | 백테스트 결과를 함정 체크리스트로 검증하고 비교 정리 |
| `go-live-check` | dry-run → 실거래 전환 전 점검표 (전환 자체는 사람이) |
| `incident` | 사고 대응 절차 + incident 문서 작성 |
| `new-decision` | ADR 작성 |

## 지식 베이스 (공개)

투자 법칙·전략·용어는 코드 작성 전에 여기서 확인한다. 사용자는 퀀트 비전문가 — 개념을 쓸 때는 쉬운 말로 설명한다.

- [docs/knowledge/strategies.md](docs/knowledge/strategies.md) — 알려진 투자 규칙·전략 카탈로그 (근거 수준·구현 난이도)
- [docs/knowledge/risk-management.md](docs/knowledge/risk-management.md) — 자금·리스크 관리 규칙
- [docs/knowledge/backtest-pitfalls.md](docs/knowledge/backtest-pitfalls.md) — 백테스트 함정
- [docs/knowledge/glossary.md](docs/knowledge/glossary.md) — 용어집
- [docs/knowledge/learning-path.md](docs/knowledge/learning-path.md) — 만들면서 배우는 단계별 학습 경로

> 투자 자문 금지: 특정 종목·비중·금액을 추천하지 않는다. 사용자의 결정을 구현하고, 근거와 위험을 사실대로 보여준다.

## 내부 문서 (로컬 전용, gitignore)

`docs/decisions/` (ADR) · `docs/plans/` · `docs/progress/` · `docs/incidents/` · `docs/policy/` (개인 투자 정책 — 예산·허용 자산·금지 행위). 메인테이너 로컬에만 있고 공개 레포에는 없다. 링크는 로컬에서 열린다.
