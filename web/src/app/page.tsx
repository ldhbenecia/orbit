import { connection } from "next/server";

import { PriceView } from "@/components/price-view";
import { type CandleOut, toChartCandle } from "@/lib/candles";

const API_URL = process.env.ORBIT_API_URL ?? "http://127.0.0.1:8000";
const MARKET = "KRW-BTC";

async function loadCandles(): Promise<CandleOut[] | null> {
  try {
    const res = await fetch(`${API_URL}/candles?market=${MARKET}`);
    return res.ok ? ((await res.json()) as CandleOut[]) : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  await connection();
  const candles = await loadCandles();

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      {candles === null ? (
        <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />
      ) : candles.length < 2 ? (
        <Notice title="아직 받은 일봉이 없어요" command="uv run --project engine orbit sync-candles" />
      ) : (
        <PriceView market={MARKET} candles={candles.map(toChartCandle)} />
      )}
    </main>
  );
}

function Notice({ title, command }: { title: string; command: string }) {
  return (
    <div className="space-y-2 rounded-2xl bg-subtle p-6">
      <p className="font-semibold">{title}</p>
      <p className="text-sm text-muted">레포 루트에서 아래 명령을 실행한 뒤 새로고침해 주세요.</p>
      <code className="block rounded-lg bg-background px-3 py-2 text-sm">{command}</code>
    </div>
  );
}
