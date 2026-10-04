import type { NextRequest } from "next/server";

import type { components } from "@/lib/api";
import { engineJson } from "@/lib/engine";

export async function GET(_req: NextRequest, ctx: RouteContext<"/api/backtests/[id]/trades">) {
  const { id } = await ctx.params;
  if (!/^\d+$/.test(id)) return Response.json({ error: "잘못된 실행 id" }, { status: 400 });
  const trades = await engineJson<components["schemas"]["TradeOut"][]>(`/backtests/${id}/trades`);
  if (trades === null) return Response.json({ error: "엔진 API 에 연결할 수 없음" }, { status: 502 });
  return Response.json(trades);
}
