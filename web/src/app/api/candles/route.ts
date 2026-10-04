import type { NextRequest } from "next/server";

import type { CandleOut } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { MARKETS } from "@/lib/markets";

const INTERVALS = new Set(["day", "week", "month"]);

// 주봉·월봉과 오래된 일봉은 처음 화면에 싣지 않고 필요할 때 이 경로로 받음
export async function GET(req: NextRequest) {
  const market = req.nextUrl.searchParams.get("market") ?? "";
  const interval = req.nextUrl.searchParams.get("interval") ?? "";
  if (!MARKETS.some((m) => m.market === market) || !INTERVALS.has(interval)) {
    return Response.json({ error: "잘못된 종목 또는 막대 단위" }, { status: 400 });
  }
  const candles = await engineJson<CandleOut[]>(`/candles?market=${market}&interval=${interval}`);
  if (candles === null) return Response.json({ error: "엔진 API 에 연결할 수 없음" }, { status: 502 });
  return Response.json(candles);
}
