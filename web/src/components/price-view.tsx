"use client";

import { useMemo, useState } from "react";

import { CandleChart } from "@/components/candle-chart";
import type { ChartCandle } from "@/lib/candles";
import { formatDate, formatPercent, formatSignedWon, formatWon } from "@/lib/format";

const PERIODS = [
  { label: "1개월", days: 30 },
  { label: "3개월", days: 90 },
  { label: "1년", days: 365 },
  { label: "전체", days: null },
] as const;

type Period = (typeof PERIODS)[number];

const tone = (value: number) => (value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted");

export function PriceView({ market, candles }: { market: string; candles: ChartCandle[] }) {
  const [period, setPeriod] = useState<Period>(PERIODS[2]);

  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const change = prev ? last.close - prev.close : 0;
  const changeRatio = prev ? change / prev.close : 0;

  const stats = useMemo(() => {
    const range = period.days === null ? candles : candles.slice(-(period.days + 1));
    const first = range[0];
    return {
      ratio: last.close / first.close - 1,
      high: Math.max(...range.map((c) => c.high)),
      low: Math.min(...range.map((c) => c.low)),
    };
  }, [candles, period, last]);

  return (
    <div className="space-y-8">
      <section className="space-y-1">
        <p className="text-sm text-muted">비트코인 · {market}</p>
        <p className="text-4xl font-bold tracking-tight tabular-nums">{formatWon(last.close)}</p>
        <p className={`text-sm font-medium tabular-nums ${tone(change)}`}>
          {formatSignedWon(change)} ({formatPercent(changeRatio)})
          <span className="ml-1 font-normal text-muted">전일 대비</span>
        </p>
        <p className="pt-1 text-xs text-muted">{formatDate(last.day)} 종가 기준</p>
      </section>

      <section className="space-y-3">
        <div className="flex gap-1 rounded-xl bg-subtle p-1" role="tablist" aria-label="기간">
          {PERIODS.map((p) => (
            <button
              key={p.label}
              type="button"
              role="tab"
              aria-selected={p === period}
              onClick={() => setPeriod(p)}
              className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                p === period ? "bg-background text-foreground shadow-sm" : "text-muted hover:text-foreground"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <CandleChart candles={candles} visibleDays={period.days} />
      </section>

      <section className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Stat label={`${period.label} 수익률`} value={formatPercent(stats.ratio)} className={tone(stats.ratio)} />
        <Stat label="최고가" value={formatWon(stats.high)} />
        <Stat label="최저가" value={formatWon(stats.low)} />
      </section>

      <p className="text-xs leading-relaxed text-muted">
        업비트 원화 일봉 {formatDate(candles[0].day)}부터 {formatDate(last.day)}까지 {candles.length.toLocaleString("ko-KR")}일.
        하루가 끝나 확정된 봉만 보여주고, 아직 진행 중인 오늘 봉은 빼요.
      </p>
    </div>
  );
}

function Stat({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between rounded-xl bg-subtle px-4 py-3 sm:block">
      <p className="text-sm text-muted sm:text-xs">{label}</p>
      <p className={`font-semibold tabular-nums sm:mt-1 sm:truncate sm:text-sm ${className}`}>{value}</p>
    </div>
  );
}
