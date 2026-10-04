# 시크릿 · 개인정보 (공개 레포)

orbit 은 GitHub public 레포다. 커밋된 것은 지워도 이력·포크·캐시에 남는다고 가정한다.

## 절대 커밋·노출 금지

- API 키·시크릿·토큰 (업비트, 토스, 텔레그램 봇 등)
- 계좌번호, 고객 식별자, 이메일, 전화번호
- 실제 잔고·보유 수량·주문·체결 내역, 개인 예산 금액
- 서버 IP·호스트명·SSH 정보
- 절대경로 (`/Users/...`)

"커밋 금지"는 코드뿐 아니라 **로그, 에러 메시지, 테스트 픽스처, 노트북 출력, PR 본문, 이슈, 커밋 메시지** 전부에 적용된다.

## 어디에 두나

| 종류 | 위치 | 커밋 |
|---|---|---|
| 키·시크릿 | `.env` (서버 env) | ✗ — `.env.example` 에 키 이름만 |
| 개인 설정 (예산·한도·허용 자산) | `config/orbit.local.yaml` | ✗ — `config/orbit.example.yaml` 에 예시값 |
| 장부·주문·캔들 캐시 | `data/` (SQLite) | ✗ |
| 백테스트 산출물 | `reports/` | ✗ |
| 개인 투자 정책·사고 기록 | `docs/policy/`, `docs/incidents/` | ✗ (로컬 전용) |

## 규칙

- 로그는 키·계좌번호를 마스킹하는 필터를 거친다. 요청/응답 원문 덤프 금지 (헤더에 토큰이 있음)
- 테스트 픽스처는 가짜 계좌·가짜 금액만. 실제 API 응답을 녹화해 쓸 때는 식별자·금액을 치환한 뒤 커밋
- Jupyter 노트북은 출력 셀을 지우고 커밋 (잔고·체결이 출력에 남음)
- 커밋 전 gitleaks 검사. GitHub secret scanning + push protection 켜둠
- Claude 는 `.env`, `config/*.local.yaml`, `data/` 를 읽지 않는다 (`.claude/settings.json` deny). 값이 필요하면 사용자에게 키 이름만 묻는다

## 사고 시

키가 커밋·노출되면 **커밋 삭제가 아니라 키 폐기·재발급이 먼저**. 그다음 이력 정리 → [incident-workflow](incident-workflow.md)
