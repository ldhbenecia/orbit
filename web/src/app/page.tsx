import { connection } from "next/server";

import { DcaCard } from "@/components/dca-card";
import { NextOpenCard } from "@/components/next-open-card";
import { PriceView } from "@/components/price-view";
import { RuleCheckCard } from "@/components/rule-check-card";
import { SignalCard } from "@/components/signal-card";
import { WalletCard } from "@/components/wallet-card";
import type { components } from "@/lib/api";
import { type CandleOut, toChartCandle } from "@/lib/candles";
import { engineJson } from "@/lib/engine";
import { findMarket } from "@/lib/markets";
import { verdictOf } from "@/lib/overview";

const RECENT_DAILY = 750; // 처음 화면엔 최근 약 2~3년 일봉만 — 나머지는 과거로 밀 때 받음

export default async function Page(props: PageProps<"/">) {
  await connection();
  const info = findMarket((await props.searchParams).market);
  const market = info.market;
  const [candles, summary, runs, verdict, nextOpen, checks, wallet] = await Promise.all([
    engineJson<CandleOut[]>(`/candles?market=${market}&interval=day&limit=${RECENT_DAILY}`),
    engineJson<components["schemas"]["CandlesSummaryOut"] | null>(`/candles/summary?market=${market}`),
    engineJson<components["schemas"]["RunOut"][]>(`/backtests?market=${market}`),
    verdictOf(info),
    // 국내 상장 미국 ETF 만 — 엔진이 대상이 아니면 비워 보냄
    market.startsWith("KRX-")
      ? engineJson<components["schemas"]["NextOpenOut"] | null>(`/next-open?market=${market}`)
      : null,
    info.core ? null : engineJson<components["schemas"]["RuleChecksOut"] | null>(`/rule-checks?market=${market}`),
    // 가상 장부는 지금 코인만
    info.group === "coin" ? engineJson<components["schemas"]["WalletOut"]>("/wallet") : null,
  ]);
  const slots = wallet?.slots.filter((s) => s.market === market) ?? [];

  if (candles === null) return <Notice title="엔진 API 에 연결할 수 없어요" command="uv run --project engine orbit serve" />;
  if (candles.length < 2)
    return <Notice title="아직 받은 일봉이 없어요" command={`uv run --project engine orbit sync-candles --market ${market}`} />;

  // 넓은 화면은 토스증권처럼 왼쪽 차트·오른쪽 판단, 폰은 판단을 먼저
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-8">
      <div className="space-y-4 lg:sticky lg:top-6 lg:order-2 lg:self-start">
        {nextOpen && <NextOpenCard info={info} data={nextOpen} />}
        {verdict?.kind === "dca" && <DcaCard info={info} data={verdict.data} />}
        {verdict?.kind === "signals" && <SignalCard info={info} data={verdict.data} />}
        {slots.length > 0 && <WalletCard info={info} slots={slots} />}
      </div>
      <div className="min-w-0 space-y-10 lg:order-1">
        <PriceView
          key={market}
          info={info}
          runs={runs ?? []}
          recentDaily={candles.map(toChartCandle)}
          dailyCount={summary?.count ?? candles.length}
          firstDay={(summary?.first ?? candles[0].start).slice(0, 10)}
        />
        {checks && <RuleCheckCard info={info} data={checks} />}
      </div>
    </div>
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
