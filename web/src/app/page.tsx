import { connection } from "next/server";

import { MarketSwitcher } from "@/components/market-switcher";
import { PriceView } from "@/components/price-view";
import { SignalCard } from "@/components/signal-card";
import type { components } from "@/lib/api";
import { type CandleOut, type Interval, toChartCandle } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { findCoinMarket } from "@/lib/markets";

const loadCandles = (market: string, interval: Interval) =>
  engineJson<CandleOut[]>(`/candles?market=${market}&interval=${interval}`);

export default async function Page(props: PageProps<"/">) {
  await connection();
  const coin = findCoinMarket((await props.searchParams).market);
  const market = coin.market;
  const [day, week, month, signals, runs] = await Promise.all([
    loadCandles(market, "day"),
    loadCandles(market, "week"),
    loadCandles(market, "month"),
    engineJson<components["schemas"]["SignalsOut"]>(`/signals?market=${market}`),
    engineJson<components["schemas"]["RunOut"][]>(`/backtests?market=${market}`),
  ]);
  const candles = day && week && month ? day : null;
  // 같은 배열을 두 prop 에 넘김 — 따로 map 하면 화면 데이터에 일봉이 두 번 실림
  const daily = candles?.map(toChartCandle) ?? [];

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      <MarketSwitcher current={market}>
      {candles === null ? (
        <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />
      ) : candles.length < 2 ? (
        <Notice title="아직 받은 일봉이 없어요" command={`uv run --project engine orbit sync-candles --market ${market}`} />
      ) : (
        <div className="space-y-10">
          {signals && <SignalCard name={coin.name} data={signals} />}
          <PriceView
            key={market}
            market={market}
            name={coin.name}
            runs={runs ?? []}
            daily={daily}
            byInterval={{
              day: daily,
              week: week!.map(toChartCandle),
              month: month!.map(toChartCandle),
            }}
          />
        </div>
      )}
      </MarketSwitcher>
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
