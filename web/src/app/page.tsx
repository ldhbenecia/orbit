import { connection } from "next/server";

import { DcaCard } from "@/components/dca-card";
import { MarketSwitcher } from "@/components/market-switcher";
import { PriceView } from "@/components/price-view";
import { SignalCard } from "@/components/signal-card";
import type { components } from "@/lib/api";
import { type CandleOut, toChartCandle } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { findMarket } from "@/lib/markets";

const RECENT_DAILY = 750; // 처음 화면엔 최근 약 2~3년 일봉만 — 나머지는 과거로 밀 때 받음

export default async function Page(props: PageProps<"/">) {
  await connection();
  const info = findMarket((await props.searchParams).market);
  const market = info.market;
  const [candles, summary, signals, runs, dca] = await Promise.all([
    engineJson<CandleOut[]>(`/candles?market=${market}&interval=day&limit=${RECENT_DAILY}`),
    engineJson<components["schemas"]["CandlesSummaryOut"] | null>(`/candles/summary?market=${market}`),
    engineJson<components["schemas"]["SignalsOut"]>(`/signals?market=${market}`),
    engineJson<components["schemas"]["RunOut"][]>(`/backtests?market=${market}`),
    // 코어 ETF 는 보유/현금 신호 대신 적립식 분석
    info.core ? engineJson<components["schemas"]["DcaOut"] | null>(`/dca?market=${market}`) : null,
  ]);

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      <MarketSwitcher current={market}>
      {candles === null ? (
        <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />
      ) : candles.length < 2 ? (
        <Notice title="아직 받은 일봉이 없어요" command={`uv run --project engine orbit sync-candles --market ${market}`} />
      ) : (
        <div className="space-y-10">
          {info.core ? dca && <DcaCard info={info} data={dca} /> : signals && <SignalCard info={info} data={signals} />}
          <PriceView
            key={market}
            info={info}
            runs={runs ?? []}
            recentDaily={candles.map(toChartCandle)}
            dailyCount={summary?.count ?? candles.length}
            firstDay={(summary?.first ?? candles[0].start).slice(0, 10)}
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
