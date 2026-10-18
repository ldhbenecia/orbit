# 투자 방법론 — 누가, 어떤 생각으로, 지금도 통하나

> 확인일: 2026-10-17. 처음 보는 사람이 "이 규칙은 누구의 어떤 생각인지" 를 알 수 있게 쓴다. 대시보드의 "이 규칙은 어디서 왔나요?" 는 이 문서를 줄인 것 (`web/src/lib/rule-stories.ts`) — 한쪽을 고치면 같이 고친다.
> 기준: **2020년대 데이터로 지금도 통한다는 근거**가 있고, **orbit 이 가진 데이터(일봉·거래량·SEC 공시)로 계산할 수 있는 것**. 오래된 이름이라도 지금 근거가 있으면 남기고, 근거가 사라진 공식은 "주의" 로 둔다.

## 먼저 — 알려진 기법은 약해진다

- 논문으로 발표된 수익 패턴은 발표 뒤 수익이 평균 절반쯤으로 줄었다 (McLean·Pontiff 2016, 이후 여러 번 재확인). 엄격하게 다시 검증하면 살아남는 패턴은 3분의 1 남짓
- 이유: 모두가 같은 신호를 보면 먼저 사는 사람이 이익을 가져가고, 원래 우연이었던 것도 섞여 있음 (과최적화)
- 그래서 오래 남는 건 **사람의 심리나 시장 구조 때문에 쉽게 안 없어지는 것** — 좋은 소식에 늦게 반응하고 몰려가는 습성(추세·모멘텀), 위험을 떠안는 대가(주식 위험 프리미엄)
- 분·초 단위 패턴은 기관 알고리즘이 먼저 가져감 → 개인이 남는 곳은 **일봉으로 판단하고 며칠~몇 달 들고 가는** 영역 (orbit 의 방식)

## 2026년 시장이 예전과 다른 점

| 변화 | 뜻 | orbit 에 주는 것 |
|---|---|---|
| AI 쏠림 — S&P 500 에서 대형 기술주 7개 비중 약 31~32% (2022년 11월 약 22%) | 지수 ETF 를 사도 사실상 소수 종목에 크게 걸림. 2022년엔 이 7개가 약 −40% 일 때 지수는 약 −18% | 코어 ETF 의 쏠림을 아는 것. 2026년엔 쏠림이 풀리며 종목 간 차이가 커짐 → 관심 종목의 추세·재무를 종목별로 보는 의미가 커짐 |
| 비트코인 현물 ETF (2024년 1월) | 기계적으로 들어오는 수요가 생겨 옛 온체인 지표(MVRV 등)의 "과열" 기준이 예전처럼 맞지 않는다는 분석. ETF 유입액엔 차익거래용 매수도 섞임 | 비트코인 4년 주기·Stock-to-Flow 같은 옛 공식에 기대지 않음. 가격 추세 규칙 + 기간 분리 검증 |
| 모멘텀 강세와 급락 | 2024~2025 미국 모멘텀 종목의 초과 성과가 역사적으로 극단적. 동시에 2025년 봄 추세 추종 펀드는 1년 −18% 대 | 추세 규칙은 쓰되 "아픈 구간이 반드시 온다" 를 결과 화면에 함께 보여줌 |

## 지금 쓰는 규칙

### 추세 추종 — 이동평균 (`ma-N`, 월급날 "추세 아래면 대기")

- **누구**: 멥 페이버 (2007 논문 "A Quantitative Approach to Tactical Asset Allocation" — 10개월 평균 위면 보유), 스탠 와인스타인 (1988 책, 주가는 바닥 → 상승 → 천장 → 하락 네 단계를 돌고 30주 평균이 경계)
- **생각**: 사람들은 좋은 소식에 처음엔 덜 반응하고 나중에 몰림 → 추세가 생각보다 오래감. 평균선은 추세가 살아 있는지 보는 가장 단순한 잣대
- **규칙**: 확정 종가가 최근 N일 평균보다 높으면 보유, 낮으면 현금
- **깨지는 때**: 횡보장에서 평균선을 넘나들며 헛매매, 급락 뒤 급반등 초반을 놓침
- **2020년대 근거**: 2008년 이후에도 3~12개월 추세 신호의 성과가 그 전과 비슷 (2025 연구). 근거 수준 **높음**

### 변동성 돌파 (`vb-k`)

- **누구**: 래리 윌리엄스 — 1987년 실전 매매 대회에서 1만 달러를 1년 만에 100만 달러 넘게 불림. 한국 코인 투자자 사이에 "k = 0.5" 로 퍼짐
- **생각**: 어제 움직인 폭의 일정 비율 이상 오르는 날은 사는 힘이 강한 날 → 올라타고 다음 날 아침에 내림
- **규칙**: 오늘 가격 > 오늘 시가 + (어제 고가 − 어제 저가) × k 이면 매수, 다음 날 시가 매도
- **깨지는 때**: 매일 매매라 수수료·슬리피지가 쌓임. 짧은 주기 신호일수록 비용을 빼면 약함
- **근거 수준**: **낮음~중간** — orbit 규칙 검증(기간 분리)으로 직접 확인

### 적립식 (월급날 "단순 적립")

- **누구**: 한 사람의 기법이 아니라 연금·월급 투자의 기본형. 뱅가드 2012 "Dollar-cost averaging just means taking risk later"
- **생각**: 언제가 싼지 맞히지 않고 매달 같은 돈 → 비쌀 땐 적게, 쌀 땐 많이. 감정에 덜 흔들림
- **깨지는 때**: 돈이 한꺼번에 있으면, 오르는 시장에선 처음에 다 넣는 쪽이 약 3번 중 2번 더 벌었음
- **근거 수준**: **높음** (수익보다 꾸준함). 단순해서 "알려져서 사라지는" 효과 없음

### 떨어지면 더 (월급날)

- **누구**: 흔한 직관. 닉 마지울리 2019 "Even God Couldn't Beat Dollar-Cost Averaging" — 바닥을 미리 알아도 대부분 단순 적립보다 못했다는 분석
- **깨지는 때**: 기다리는 동안 오르면 모아 둔 돈이 그 상승을 놓침 (현금 대기 비용)
- **근거 수준**: 단순 적립보다 낫다는 근거 **약함** — orbit 이 5년 구간별로 직접 비교

### 가치 — PER·PBR (재무 카드)

- **누구**: 벤저민 그레이엄 1949 『현명한 투자자』 — 버는 돈·가진 재산에 비해 싸게 사서 실수의 여유(안전마진)를 둠
- **orbit**: 판단 없이 숫자와 "지난 5년 중 지금 위치" 만
- **깨지는 때**: 싼 데는 이유가 있을 수 있음 (가치 함정). 이익이 빠르게 느는 회사는 늘 비싸 보임
- **2020년대 근거**: 2010년대엔 싼 주식이 성장주에 오래 뒤처짐. 장기적으론 높음, 최근 10여 년은 **약함**

### 추세 템플릿 — 마크 미너비니 (관심 종목 표 "템플릿 N/8", 종목 화면 카드)

- **누구**: 지금도 활동하는 미국 주식 트레이더. "큰 상승은 이미 상승 추세(와인스타인의 2단계)에 들어선 종목에서 나온다"
- **규칙** (책 대신 여러 정리본 기준 — 숫자는 출처마다 조금 다름. orbit 은 종가 기준, 아래 숫자로 고정)
  1. 주가 > 150일·200일 평균
  2. 150일 평균 > 200일 평균
  3. 200일 평균이 최소 1개월 이상 오름 (4~5개월이면 더 좋음)
  4. 50일 평균 > 150일·200일 평균
  5. 주가 > 50일 평균
  6. 52주 저점보다 30% 이상 위 (정리본에 따라 25%)
  7. 52주 고점에서 25% 이내
  8. 상대강도 높음 (원래 IBD 유료 점수 70 이상 → orbit 은 등록한 미국 종목 안 1년 수익률 순위로 대신)
- **orbit 에서**: 사라는 신호가 아니라 "몇 개 충족" 으로 지금 추세 상태를 사실로 보여줌. 1년치 일봉이 없으면 판단 안 함
- **상대강도**: 등록한 미국 종목(대시보드·관심 종목, ETF 포함) 중 1년치 일봉이 있고 마지막 거래일이 같은 종목끼리 1년 수익률을 비교해 "나보다 낮은 종목 비율" 0.7 이상. 5종목 미만이면 모름 (그때는 7개 조건 중으로 표시). 국내 종목은 원화 수익(환율 포함)·다른 거래일이라 빼고, 추세 템플릿 자체도 미국 종목만. 원래 IBD 점수(전 종목 비교)보다 뜻이 좁음
- **깨지는 때**: 조건을 다 갖춘 건 이미 많이 오른 종목 — 추세가 꺾이면 빠르게 떨어질 수 있음
- **근거 수준**: **중간** — 8개 조건 전체를 엄격히 검증한 학술 연구는 드묾. 바탕인 추세·모멘텀 근거는 강함

### 시계열 모멘텀 — 12개월 수익률 (`mom-N`, 오늘의 신호·규칙 검증)

- **누구**: Moskowitz·Ooi·Pedersen 2012 "Time Series Momentum" — 지난 12개월이 플러스면 보유, 마이너스면 현금. 기관 추세 추종(CTA) 펀드의 기본
- **2020년대 근거**: 2008년 이후에도 유지 (2025 연구), 2025년 3분기 코인에서도 모멘텀이 가장 성과 좋은 팩터
- **규칙**: 지금 종가 > 약 12개월 전 종가(코인 365일, 주식 252거래일)면 보유, 아니면 현금. 최근 1개월을 빼는 변형(12-1)은 쓰지 않음
- **orbit 에서**: 이동평균과 같은 계열이라 "추가로 나은가" 를 기간 분리와 3·6·9·12개월 민감도로 검증
- **깨지는 때**: 급락 뒤 급반등장 — 1년 전보다 아직 낮아 반등 초반을 놓침
- **근거 수준**: **높음**

### 큰 갭 상승 — 크리스티안 쿨라매기의 에피소드 피벗 (미국 종목 화면 기록, 관심 종목 표시)

- **누구**: 2020년대 개인 계좌로 크게 불려 유명해진 스윙 트레이더, 방송·인터뷰로 방법 공개
- **생각**: 시장이 무시하던 종목이 예상 밖 뉴스(실적 서프라이즈 등)로 크게 갭 상승하고 거래량이 터지면 몇 달짜리 상승의 시작일 수 있음 — 이익이 갑자기 바뀌는 AI 시대와 맞음
- **규칙** (2차 정리본 기준 — 추정): 10% 이상 갭·급등 + 평소보다 큰 거래량 + 직전 3~6개월 크게 오르지 않음
- **orbit 에서**: 판단 없이 기록만 — 시가 갭 10% 이상 + 거래량 직전 50일 평균의 3배 이상인 날, 직전 6개월 수익, 갭 직후 첫 분기 보고서 공시일(SEC), 그 뒤 1개월 수익(지나고 보니). "직전 3~6개월 크게 오르지 않음" 은 거르는 조건이 아니라 사실로 보여줌
- **깨지는 때**: 갭 뒤 바로 되밀리는 경우가 많음 — 쿨라매기도 그날 저가 아래면 바로 정리하는 손절을 함께 씀
- **근거 수준**: **낮음~중간** — 실적 발표 뒤 그 방향으로 더 움직이는 현상(PEAD)은 오래 알려졌지만 알려진 뒤 약해졌다는 연구가 많고, 갭 + 거래량 조합을 엄격히 검증한 연구는 드묾

## 다음 후보 (지금 근거가 있고 orbit 데이터로 계산 가능)

- 지금은 없음 — 새 후보는 [research.md](research.md) 에서 2020년대 근거와 함께 고름

## 주의 — 근거가 사라졌거나 orbit 에 안 맞는 것

- **Stock-to-Flow (비트코인)**: 2021~2022 예측이 크게 빗나감. 공급량만으로 가격을 설명하는 모델
- **비트코인 4년 반감기 주기**: 현물 ETF 이후 수요 구조가 바뀌어 과거 주기를 그대로 믿기 어려움
- **분·초봉 패턴, 호가 분석**: 기관 알고리즘의 영역이고 orbit 범위 밖 (거래소 앱이 더 잘함)
- **레버리지·공매도 기법**: orbit 범위 밖

## 출처

- McLean·Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance* · 재확인: [Publication Bias in Asset Pricing Research](https://arxiv.org/pdf/2209.13623), [Why and how systematic strategies decay](https://arxiv.org/pdf/2105.01380)
- [Revisiting the Structure of Trend Premia (2025)](https://arxiv.org/pdf/2510.23150) · [Man Group — Trend Following and Drawdowns](https://www.man.com/insights/is-this-time-different) · [Pzena 2025 Q4](https://www.pzena.com/americas/institutional-investors/insights/finding-value-in-a-momentum-driven-market-4q-2025/) · [CF Benchmarks — crypto momentum](https://www.cfbenchmarks.com/blog/momentum-outperforms-following-new-highs)
- Faber (2007), "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth Management* · Weinstein (1988), 『Secrets for Profiting in Bull and Bear Markets』
- Moskowitz·Ooi·Pedersen (2012), "Time Series Momentum", *Journal of Financial Economics*
- Vanguard (2012), "Dollar-cost averaging just means taking risk later" · Maggiulli (2019), "Even God Couldn't Beat Dollar-Cost Averaging", *Of Dollars And Data*
- Graham (1949), 『The Intelligent Investor』
- 미너비니 추세 템플릿 정리: [sharpely](https://sharpely.in/blogs/minervini-trend-template-for-stage2-stocks/), [TradingView](https://www.tradingview.com/ideas/trend-template/) · 쿨라매기: [인터뷰 노트](https://tradingresourcehub.substack.com/i/132995655/introduction), [정리 스레드](https://en.rattibha.com/thread/2037090511950139480)
- 시장 구조: [Australian Retirement Trust — Magnificent Seven and AI](https://www.australianretirementtrust.com.au/investments/market-watch/magnificent-seven-and-ai), [Yahoo Finance — Mag 7 −40% vs S&P −18%](https://finance.yahoo.com/markets/stocks/articles/magnificent-seven-fell-40-while-015554114.html), [Allspring — AI at a crossroads](https://www.allspringglobal.com/insights/articles/ai-at-a-crossroads-concentration-capex-and-what-comes-next/), [Bitcoin on-chain signals post-ETF](https://cryptoaimeta.com/crypto/bitcoin-etfs-are-rewriting-on-chain-signals-which-metrics-still-work/)
