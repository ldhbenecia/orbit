"use client";

import { useMemo, useState } from "react";

import { CandleChart } from "@/components/candle-chart";
import type { ChartCandle, Interval } from "@/lib/candles";
import { formatDate, formatPercent, formatSignedWon, formatWon } from "@/lib/format";

const INTERVALS: { value: Interval; label: string; initialBars: number | null }[] = [
  { value: "day", label: "일", initialBars: 90 },
  { value: "week", label: "주", initialBars: 78 },
  { value: "month", label: "월", initialBars: null },
];

const tone = (value: number) => (value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted");

const barLabel = (day: string, interval: Interval) => {
  if (interval === "month") return formatDate(day).replace(/ \d+일$/, "");
  return interval === "week" ? `${formatDate(day)} 주` : formatDate(day);
};

type Props = {
  market: string;
  daily: ChartCandle[];
  byInterval: Record<Interval, ChartCandle[]>;
};

export function PriceView({ market, daily, byInterval }: Props) {
  const [interval, setInterval] = useState<Interval>("day");
  // 막대 위치는 단위마다 다름 — 어느 단위의 위치인지 같이 저장해 단위를 바꾼 직후 옛 위치를 쓰지 않음
  const [visibleState, setVisible] = useState<{ interval: Interval; from: number; to: number } | null>(null);
  const [hoverState, setHover] = useState<{ interval: Interval; index: number } | null>(null);

  const candles = byInterval[interval];
  const option = INTERVALS.find((o) => o.value === interval)!;
  const visible = visibleState?.interval === interval ? visibleState : null;
  const hover = hoverState?.interval === interval ? hoverState.index : null;

  const last = daily[daily.length - 1];
  const prev = daily[daily.length - 2];
  const change = last.close - prev.close;

  const legend = candles[hover ?? candles.length - 1];
  const legendChange = legend.close - legend.open;

  const stats = useMemo(() => {
    if (!visible) return null;
    const range = candles.slice(visible.from, visible.to + 1);
    return {
      from: range[0].day,
      to: range[range.length - 1].day,
      ratio: range[range.length - 1].close / range[0].open - 1,
      high: Math.max(...range.map((c) => c.high)),
      low: Math.min(...range.map((c) => c.low)),
    };
  }, [candles, visible]);

  return (
    <div className="space-y-8">
      <section className="space-y-1">
        <p className="text-sm text-muted">비트코인 · {market}</p>
        <p className="text-4xl font-bold tracking-tight tabular-nums">{formatWon(last.close)}</p>
        <p className={`text-sm font-medium tabular-nums ${tone(change)}`}>
          {formatSignedWon(change)} ({formatPercent(change / prev.close)})
          <span className="ml-1 font-normal text-muted">전일 대비</span>
        </p>
        <p className="pt-1 text-xs text-muted">{formatDate(last.day)} 종가 기준</p>
      </section>

      <section className="space-y-3">
        <div className="flex items-center">
          <div className="flex gap-1 rounded-xl bg-subtle p-1" role="tablist" aria-label="막대 단위">
            {INTERVALS.map((o) => (
              <button
                key={o.value}
                type="button"
                role="tab"
                aria-selected={o.value === interval}
                onClick={() => setInterval(o.value)}
                className={`w-12 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                  o.value === interval ? "bg-background text-foreground shadow-sm" : "text-muted hover:text-foreground"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs tabular-nums">
          <span className="font-medium">{barLabel(legend.day, interval)}</span>
          <span className="text-muted">
            시 <span className="text-foreground">{formatWon(legend.open)}</span>
          </span>
          <span className="text-muted">
            고 <span className="text-up">{formatWon(legend.high)}</span>
          </span>
          <span className="text-muted">
            저 <span className="text-down">{formatWon(legend.low)}</span>
          </span>
          <span className="text-muted">
            종 <span className={tone(legendChange)}>{formatWon(legend.close)}</span>
          </span>
        </div>

        <CandleChart
          candles={candles}
          initialBars={option.initialBars}
          onVisibleChange={(from, to) => setVisible({ interval, from, to })}
          onHover={(index) => setHover(index === null ? null : { interval, index })}
        />
      </section>

      {stats && (
        <section className="space-y-2">
          <p className="text-xs text-muted">
            보이는 구간 {formatDate(stats.from)} ~ {formatDate(stats.to)}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Stat label="구간 수익률" value={formatPercent(stats.ratio)} className={tone(stats.ratio)} />
            <Stat label="최고가" value={formatWon(stats.high)} />
            <Stat label="최저가" value={formatWon(stats.low)} />
          </div>
        </section>
      )}

      <p className="text-xs leading-relaxed text-muted">
        업비트 원화 시세 {formatDate(daily[0].day)}부터 {formatDate(last.day)}까지. 하루가 끝나 확정된 봉만
        보여주고, 아직 진행 중인 오늘 봉은 빼요. 주봉·월봉은 업비트와 같은 기준(월요일·1일 시작)으로 일봉을 묶어요.
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
