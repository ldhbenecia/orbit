import type { components } from "@/lib/api";
import type { Interval } from "@/lib/candles";

// 백테스트 매매와 이후 장부 체결이 같은 모양 — 차트는 출처를 몰라도 됨
export type ChartTrade = {
  day: string; // YYYY-MM-DD, 체결일 봉 (UTC)
  side: "buy" | "sell";
  price: number; // 표시 전용
  reason: string;
};

export type BarTrades = { buys: ChartTrade[]; sells: ChartTrade[] };

export const toChartTrade = (t: components["schemas"]["TradeOut"]): ChartTrade => ({
  day: t.day.slice(0, 10),
  side: t.side,
  price: Number(t.price),
  reason: t.reason,
});

// 엔진 aggregate.period_start 와 같은 기준 — 주봉은 월요일, 월봉은 1일 (UTC)
export function barStart(day: string, interval: Interval): string {
  if (interval === "month") return `${day.slice(0, 8)}01`;
  if (interval === "week") {
    const date = new Date(`${day}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
    return date.toISOString().slice(0, 10);
  }
  return day;
}

export function groupByBar(trades: ChartTrade[], interval: Interval): Map<string, BarTrades> {
  const bars = new Map<string, BarTrades>();
  for (const t of trades) {
    const key = barStart(t.day, interval);
    const bar = bars.get(key) ?? { buys: [], sells: [] };
    (t.side === "buy" ? bar.buys : bar.sells).push(t);
    bars.set(key, bar);
  }
  return bars;
}
