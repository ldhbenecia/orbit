import { connection } from "next/server";

import { DcaCard } from "@/components/dca-card";
import { MarketSwitcher } from "@/components/market-switcher";
import { PriceView } from "@/components/price-view";
import { SignalCard } from "@/components/signal-card";
import type { components } from "@/lib/api";
import { type CandleOut, toChartCandle } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { findMarket, MARKETS } from "@/lib/markets";
import { dcaLine, signalLine } from "@/lib/summary";

const RECENT_DAILY = 750; // 처음 화면엔 최근 약 2~3년 일봉만 — 나머지는 과거로 밀 때 받음

export default async function Page(props: PageProps<"/">) {
  await connection();
  const info = findMarket((await props.searchParams).market);
  const market = info.market;
  const [candles, summary, runs, verdicts] = await Promise.all([
    engineJson<CandleOut[]>(`/candles?market=${market}&interval=day&limit=${RECENT_DAILY}`),
    engineJson<components["schemas"]["CandlesSummaryOut"] | null>(`/candles/summary?market=${market}`),
    engineJson<components["schemas"]["RunOut"][]>(`/backtests?market=${market}`),
    allVerdicts(),
  ]);
  const verdict = verdicts.get(market);
  const lines = Object.fromEntries(
    [...verdicts].flatMap(([key, v]) => {
      const line = v.kind === "dca" ? dcaLine(v.data) : v.data.signals.length > 0 ? signalLine(v.data) : null;
      return line ? [[key, line]] : [];
    }),
  );

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      <MarketSwitcher current={market} lines={lines}>
      {candles === null ? (
        <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />
      ) : candles.length < 2 ? (
        <Notice title="아직 받은 일봉이 없어요" command={`uv run --project engine orbit sync-candles --market ${market}`} />
      ) : (
        <div className="space-y-10">
          {verdict?.kind === "dca" && <DcaCard info={info} data={verdict.data} />}
          {verdict?.kind === "signals" && <SignalCard info={info} data={verdict.data} />}
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

type Verdict =
  | { kind: "signals"; data: components["schemas"]["SignalsOut"] }
  | { kind: "dca"; data: components["schemas"]["DcaOut"] };

// 위쪽 전 종목 한 줄과 아래 카드가 같은 응답을 씀 — 엔진이 종목마다 수 ms~0.2초라 매번 전 종목을 받아도 충분히 빠름
async function allVerdicts(): Promise<Map<string, Verdict>> {
  const entries = await Promise.all(
    MARKETS.map(async (m): Promise<[string, Verdict | null]> => {
      // 코어 ETF 는 보유/현금 신호 대신 적립식 분석
      if (m.core) {
        const data = await engineJson<components["schemas"]["DcaOut"] | null>(`/dca?market=${m.market}`);
        return [m.market, data && { kind: "dca", data }];
      }
      const data = await engineJson<components["schemas"]["SignalsOut"]>(`/signals?market=${m.market}`);
      return [m.market, data && { kind: "signals", data }];
    }),
  );
  return new Map(entries.filter((e): e is [string, Verdict] => e[1] !== null));
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
