import { cache } from "react";

import type { components } from "@/lib/api";
import { engineJson } from "@/lib/engine";
import { COIN_FALLBACK, type MarketInfo, toMarketInfo } from "@/lib/markets";

// 종목 목록은 엔진이 로컬 설정에서 읽어 줌 — 엔진이 꺼져 있으면 코인만
// 한 요청 안에서 레이아웃과 화면이 같은 결과를 나눠 씀
export const getMarkets = cache(async (): Promise<readonly MarketInfo[]> => {
  const rows = await engineJson<components["schemas"]["MarketOut"][]>("/markets");
  return rows ? rows.map(toMarketInfo) : COIN_FALLBACK;
});
