# SEC EDGAR — 미국 기업 재무

> 확인일: 2026-10-17 · 출처: [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [Developer resources](https://www.sec.gov/about/developer-resources), [Privacy and Security Policy](https://www.sec.gov/privacy)

미국 상장사가 SEC 에 낸 연간(10-K)·분기(10-Q) 보고서의 숫자를 XBRL 로 모아 둔 공개 API. orbit 은 관심 종목의 PER·PBR·ROE·FCF 수익률·매출 성장과 "지난 5년 중 지금 위치" 를 여기서 계산한다.

## 재배포

- SEC.gov 의 정보는 공개 정보라 SEC 허락 없이 복사·재배포할 수 있다 (Privacy and Security Policy). 출처 표기는 권장
- **단, orbit 의 PER·PBR·FCF 수익률·5년 위치는 토스 가격을 곱한 값**이라 토스 데이터 이용 정책을 따른다 — 공개 문서·캡처에 싣지 않음. ROE·매출 성장처럼 공시 값만으로 계산한 숫자는 제약 없음

## 사용 방식

| 항목 | 내용 |
|---|---|
| 종목코드 → 회사 번호(CIK) | `https://www.sec.gov/files/company_tickers.json`. 주식 종류는 하이픈 (`BRK.B` → `BRK-B`) |
| 재무 값 | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (10자리) |
| 요청 조건 | 요청마다 연락처(이름·이메일)를 담은 User-Agent. **초당 10회 이하** — 넘으면 IP 가 막힘 |
| 설정 | `.env` 의 `SEC_USER_AGENT="Your Name you@example.com"` — HTTP 헤더라 **영문만** (개인정보라 레포에 두지 않음) |
| 실행 | `uv run orbit sync-fundamentals` — 요청 사이 0.15초 쉼. 하루 안에 받은 종목은 건너뜀 (분기 공시라) |

## 계산 규칙

- **보고서 하나 = 그 공시일에 시장이 알던 값 하나.** 나중에 정정된 값을 옛 시점에 섞지 않는다 (미래 데이터 금지)
- **최근 4분기(TTM)**: 분기 보고서는 연초부터 누적으로 공시한다 → `직전 연간 + 올해 누적 − 작년 같은 기간 누적`. 52·53주 회계연도라 기간 끝이 며칠씩 밀리는 것은 10일까지 같은 기간으로 본다
- **시가총액 = 수정 종가 × 표지 발행주식 수.** 같은 보고서의 가중평균 주식 수와 20~25% 넘게 다르면 쓰지 않는다 (주식 종류마다 1주의 가치가 다른 회사 등). 이때 PER·PBR·FCF 수익률은 비고 ROE·매출 성장만 보인다
- **표지 주식 수가 없으면** (주식 종류별로만 적는 회사 — 회사 단위 데이터에서 빠짐) 회사 전체 가중평균 주식 수로 대신한다. 종류마다 1주의 가치가 같을 때만 맞으므로, **종목코드에 주식 종류가 붙은 상장주(`.B` 등)는 대신하지 않고 비운다** — A주 1주가 B주 여러 주 가치인 회사는 B주 가격 × 회사 주식 수가 크게 틀림
- 표지에 0 으로 적은 보고서는 모름으로 본다
- **액면분할**: 보고서 사이 주식 수가 1.9배 이상 정수배(±3%)로 바뀌면 분할로 보고 옛 주식 수에 곱한다 — 가격이 수정주가라 그래야 시가총액이 이어짐
- **5년 위치**: 지난 5년 월말마다 그날 알던 보고서와 그날 종가로 PER·PBR 을 다시 계산해, 지금 값 이하인 달의 비율. 비교할 달이 36개 미만이면 보이지 않는다. 공시 당일 종가에는 그 보고서를 쓰지 않는다 (장중 공시일 수 있음)
- 적자면 PER 없음, 자본이 0 이하면 PBR·ROE 없음

## 쓰는 항목 (us-gaap)

| 값 | 이름 (앞쪽 우선) |
|---|---|
| 순이익 | `NetIncomeLoss` → `ProfitLoss` (어떤 해부터 ProfitLoss 로만 공시하는 회사가 있음, 소수주주 몫 포함) |
| 매출 | `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` → `SalesRevenueNet` |
| 영업현금흐름 | `NetCashProvidedByUsedInOperatingActivities` (→ `…ContinuingOperations`) |
| 설비투자 | `PaymentsToAcquirePropertyPlantAndEquipment` → `PaymentsToAcquireProductiveAssets` |
| 자본총계 | `StockholdersEquity` → `…IncludingPortionAttributableToNoncontrollingInterest` |
| 주식 수 | 표지 `dei:EntityCommonStockSharesOutstanding`, 교차 확인 `WeightedAverageNumberOfDilutedSharesOutstanding` (→ `…Basic`) |

## 한계

- **ETF·해외 공시 기업(20-F, IFRS)은 재무 없음** — 10-K·10-Q 만 읽음
- 회사가 위 이름이 아닌 자체 항목으로 공시하면 그 값이 빈다
- 주식 수를 종류별로만 적던 기간은 시가총액을 못 셈 → 그 기간이 길면 5년 위치가 비어 보인다
- 액면분할 직후 다음 분기 보고서가 나오기 전까지는 분할 전 주식 수 × 분할 뒤 가격이라 PER·PBR 이 분할 비율만큼 낮게 나온다 (공시일로 확인)
- SEC 데이터 반영이 늦어 최근 분기 보고서가 빠져 있을 수 있다 (화면의 "공시일" 로 확인)
- 금융사는 설비투자·매출 개념이 달라 FCF·매출 성장이 의미가 약하다
- 수정주가에 배당 조정이 들어 있으면 옛 시가총액이 그만큼 낮게 잡혀 과거 PER 이 약간 낮아진다
- 숫자가 싸다·비싸다를 말해 주지 않는다. 낮은 PER 은 시장이 이익 감소를 예상한다는 뜻일 수도 있다
