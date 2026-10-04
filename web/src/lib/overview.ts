import type { Tile } from "@/components/market-switcher";
import type { components } from "@/lib/api";
import type { CandleOut } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { MARKETS, type MarketInfo } from "@/lib/markets";
import { dcaLine, type Line, signalLine } from "@/lib/summary";

const SPARKLINE_DAYS = 60; // 종목 타일 미니 차트 — 약 3개월

export type Verdict =
  | { kind: "signals"; data: components["schemas"]["SignalsOut"] }
  | { kind: "dca"; data: components["schemas"]["DcaOut"] };

// 코어 ETF 는 보유/현금 신호 대신 적립식 분석
export async function verdictOf(info: MarketInfo): Promise<Verdict | null> {
  if (info.core) {
    const data = await engineJson<components["schemas"]["DcaOut"] | null>(`/dca?market=${info.market}`);
    return data && { kind: "dca", data };
  }
  const data = await engineJson<components["schemas"]["SignalsOut"]>(`/signals?market=${info.market}`);
  return data && { kind: "signals", data };
}

const lineOf = (v: Verdict | null): Line | null =>
  !v ? null : v.kind === "dca" ? dcaLine(v.data) : v.data.signals.length > 0 ? signalLine(v.data) : null;

async function tileOf(info: MarketInfo): Promise<Tile | null> {
  const [candles, verdict] = await Promise.all([
    engineJson<CandleOut[]>(`/candles?market=${info.market}&interval=day&limit=${SPARKLINE_DAYS}`),
    verdictOf(info),
  ]);
  const closes = (candles ?? []).map((c) => Number(c.close));
  if (closes.length < 2) return null;
  const close = closes[closes.length - 1];
  return { close, change: close / closes[closes.length - 2] - 1, closes, line: lineOf(verdict) };
}

export async function allTiles(): Promise<Partial<Record<string, Tile>>> {
  const tiles = await Promise.all(MARKETS.map(async (m) => [m.market, await tileOf(m)] as const));
  return Object.fromEntries(tiles.flatMap(([market, tile]) => (tile ? [[market, tile]] : [])));
}
