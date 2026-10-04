import { connection } from "next/server";

import { PriceView } from "@/components/price-view";
import { SignalCard } from "@/components/signal-card";
import type { components } from "@/lib/api";
import { type CandleOut, type Interval, toChartCandle } from "@/lib/candles";

const API_URL = process.env.ORBIT_API_URL ?? "http://127.0.0.1:8000";
const MARKET = "KRW-BTC";

async function loadJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`);
    if (!res.ok) {
      console.error(`엔진 API ${path} 응답 ${res.status}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (error) {
    console.error(`엔진 API ${path} 요청 실패`, error);
    return null;
  }
}

const loadCandles = (interval: Interval) =>
  loadJson<CandleOut[]>(`/candles?market=${MARKET}&interval=${interval}`);

export default async function Page() {
  await connection();
  const [day, week, month, signals] = await Promise.all([
    loadCandles("day"),
    loadCandles("week"),
    loadCandles("month"),
    loadJson<components["schemas"]["SignalsOut"]>(`/signals?market=${MARKET}`),
  ]);
  const candles = day && week && month ? day : null;

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      {candles === null ? (
        <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />
      ) : candles.length < 2 ? (
        <Notice title="아직 받은 일봉이 없어요" command="uv run --project engine orbit sync-candles" />
      ) : (
        <div className="space-y-10">
          {signals && <SignalCard data={signals} />}
          <PriceView
            market={MARKET}
            daily={candles.map(toChartCandle)}
            byInterval={{
              day: candles.map(toChartCandle),
              week: week!.map(toChartCandle),
              month: month!.map(toChartCandle),
            }}
          />
        </div>
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
