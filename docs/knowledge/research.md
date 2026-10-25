# 연구 목록 — orbit 에서 검증할 가설

> 해외 연구에서 가져온 아이디어를 **orbit 에서 직접 검증할 가설**로 정리한다. 논문이 그랬다고 우리 데이터·비용에서도 그렇다는 보장은 없다 — 단순 보유와 비교, 비용 포함, 기간 분리·민감도 검증을 거친다. 투자 권유가 아니다.
> 출처는 저자·연도·제목. 원문은 제목으로 검색하면 무료 원고(SSRN·저자 홈페이지)가 대부분 있다.

## 추세추종 · 모멘텀

| 연구 | 핵심 | orbit 에서 | 상태 |
|---|---|---|---|
| Faber (2007), "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth Management* | 10개월 이동평균 위면 보유·아래면 현금 → 수익은 비슷, 최대 낙폭은 크게 줄었음 | 이동평균 규칙(`ma-N`)의 원형. 월봉 10개월 규칙도 비교 | 일봉 규칙 구현·검증 |
| Moskowitz·Ooi·Pedersen (2012), "Time Series Momentum", *Journal of Financial Economics* | 자기 과거 수익이 플러스면 계속 오르는 경향 (시계열 모멘텀), 여러 자산·수십 년에서 | 1·3·12개월 수익 부호로 보유 | ✅ `mom-N` (12개월 신호, 3~12개월 검증) |
| Hurst·Ooi·Pedersen (2017), "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management* | 추세추종이 100년 넘게 유지, 여러 기간 신호를 섞으면 더 안정적 | 신호 카드의 "규칙 N개 중 M개" 를 그 비율만큼 보유하는 규칙으로 | 예정 |
| Jegadeesh·Titman (1993), "Returns to Buying Winners and Selling Losers", *Journal of Finance* | 종목끼리 비교해 최근 많이 오른 쪽이 계속 나음 (횡단면 모멘텀) | 미국 개별주가 여러 개 생기면 | 나중 |
| Liu·Tsyvinski (2021), "Risks and Returns of Cryptocurrency", *Review of Financial Studies* · Liu·Tsyvinski·Wu (2022), "Common Risk Factors in Cryptocurrency", *Journal of Finance* | 코인은 주식과 다른 요인으로 움직이고 1~4주 단기 모멘텀이 강함 | 코인 전용 1~4주 모멘텀 규칙 | 예정 |

## 위험 조절 · 크기

| 연구 | 핵심 | orbit 에서 | 상태 |
|---|---|---|---|
| Moreira·Muir (2017), "Volatility-Managed Portfolios", *Journal of Finance* · Harvey 외 (2018), "The Impact of Volatility Targeting", *Journal of Portfolio Management* | 변동성이 클 때 덜, 작을 때 더 들면 위험 대비 수익이 좋아지고 큰 하락이 줄어듦 | "전액 보유/현금" 대신 목표 변동성 ÷ 최근 변동성 만큼 보유 | 예정 |
| Kelly (1956), "A New Interpretation of Information Rate" · 분수 켈리 | 이길 확률·손익비로 최적 비율. 실전은 절반 이하로 | 포지션 크기 학습용 | 나중 |

## 검증 · 과최적화

| 연구 | 핵심 | orbit 에서 | 상태 |
|---|---|---|---|
| Harvey·Liu·Zhu (2016), "…and the Cross-Section of Expected Returns", *Review of Financial Studies* | 여러 개를 시험하면 우연히 좋은 게 나옴 — 시험 횟수만큼 기준을 높여야 | 규칙 검증에 시험 횟수 표시 | ✅ |
| Bailey·López de Prado (2014), "The Deflated Sharpe Ratio", *Journal of Portfolio Management* | 시험 횟수·수익 분포(치우침·두꺼운 꼬리)를 감안해 샤프 비율이 우연이 아닐 확률 | 규칙마다 "샤프가 보유보다 높은 게 우연이 아닐 확률" — 기준선을 보유 샤프로 | ✅ |
| López de Prado (2018), 『Advances in Financial Machine Learning』 | 한 번 나누는 검증은 부족 — 굴려가며 반복(워크포워드), 정보 누설 방지 | 반씩 나누기 → 여러 구간 워크포워드 | ✅ 해마다 직전 3년으로 고르고 다음 1년 써 봄 |

## 적립 · 기타

| 연구 | 핵심 | orbit 에서 | 상태 |
|---|---|---|---|
| Vanguard (2012), "Dollar-cost averaging just means taking risk later" | 일시 투입이 적립식보다 약 2/3 확률로 나았음. 적립식은 최악의 순간이 덜 아픔 | 적립식 분석에 같은 돈 일시 투입 비교 | 예정 |
| Maggiulli (2019), "Even God Couldn't Beat Dollar-Cost Averaging", *Of Dollars And Data* (블로그 분석) | 바닥을 미리 알고 모아 둔 돈을 넣어도 대부분의 기간에 단순 적립보다 못했음 — 기다리는 동안 시장이 오름 | 월급날 규칙 비교 ("떨어지면 더" vs 단순 적립, 5년 구간별 비율) | ✅ |
| Lou·Polk·Skouras (2019), "A Tug of War: Overnight versus Intraday Expected Returns", *Journal of Financial Economics* | 미국 주식 수익의 상당 부분이 밤사이 | 아이디어 보관함(종가 매수 → 시가 매도) — 왕복 비용이 더 큼 | 기록만 |
