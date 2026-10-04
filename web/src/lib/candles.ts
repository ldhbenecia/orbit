import type { components } from "@/lib/api";

export type CandleOut = components["schemas"]["CandleOut"];
export type Interval = components["schemas"]["Interval"];

// 화면 표시·차트 전용 — 금액 계산·주문에는 쓰지 않음 (float 오차)
export type ChartCandle = {
  day: string; // YYYY-MM-DD, 거래일 (UTC 날짜 키)
  open: number;
  high: number;
  low: number;
  close: number;
};

export const toChartCandle = (c: CandleOut): ChartCandle => ({
  day: c.start.slice(0, 10),
  open: Number(c.open),
  high: Number(c.high),
  low: Number(c.low),
  close: Number(c.close),
});
