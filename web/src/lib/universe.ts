import type { components } from "@/lib/api";
import { engineJson } from "@/lib/engine";
import { COIN_FALLBACK, type MarketInfo, toMarketInfo } from "@/lib/markets";

// 종목 목록은 엔진이 로컬 설정에서 읽어 줌 — 엔진이 꺼져 있으면 코인만
export async function getMarkets(): Promise<readonly MarketInfo[]> {
  const rows = await engineJson<components["schemas"]["MarketOut"][]>("/markets");
  return rows ? rows.map(toMarketInfo) : COIN_FALLBACK;
}
