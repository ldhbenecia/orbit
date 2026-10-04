import Link from "next/link";
import { connection } from "next/server";

import { PriceView } from "@/components/price-view";
import { SignalCard } from "@/components/signal-card";
import type { components } from "@/lib/api";
import { type CandleOut, type Interval, toChartCandle } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { COIN_MARKETS, findCoinMarket } from "@/lib/markets";

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

  return (
    <main className="mx-auto w-full max-w-2xl space-y-6 px-4 py-8 sm:py-12">
      <nav className="flex gap-1 rounded-xl bg-subtle p-1" aria-label="종목">
        {COIN_MARKETS.map((m) => (
          <Link
            key={m.market}
            href={`/?market=${m.market}`}
            aria-current={m.market === market ? "page" : undefined}
            className={`flex-1 rounded-lg py-2 text-center text-sm font-medium transition-colors ${
              m.market === market ? "bg-background text-foreground shadow-sm" : "text-muted hover:text-foreground"
            }`}
          >
            {m.name}
          </Link>
        ))}
      </nav>
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
