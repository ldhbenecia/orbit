import type { Interval } from "@/lib/candles";
import type { MarketGroup } from "@/lib/markets";

// 화면 표시용 — 판단·주문에는 쓰지 않음 (float)

// 고점 대비 가장 크게 내린 비율 (0 이하)
export const maxDrawdown = (closes: number[]) => {
  let peak = -Infinity;
  let worst = 0;
  for (const close of closes) {
    peak = Math.max(peak, close);
    worst = Math.min(worst, close / peak - 1);
  }
  return worst;
};

// 1년에 봉이 몇 개인지 — 주식은 휴장일이 빠져 약 252거래일, 코인은 365일
export const periodsPerYear = (interval: Interval, group: MarketGroup) =>
  interval === "week" ? 52 : interval === "month" ? 12 : group === "stock" ? 252 : 365;

// 봉 수익률 표준편차 × √(1년 봉 수). 봉이 너무 적으면 의미가 없어 계산하지 않음
export const annualVolatility = (closes: number[], perYear: number) => {
  if (closes.length < 10) return null;
  const returns = closes.slice(1).map((c, i) => c / closes[i] - 1);
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) / (returns.length - 1);
  return Math.sqrt(variance * perYear);
};
