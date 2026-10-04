"use client";

import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { ChartCandle } from "@/lib/candles";
import { formatCompactWonTicks, formatDate, formatWon } from "@/lib/format";

export type ChartMarker = { day: string; side: "buy" | "sell"; count: number }; // day 는 막대 시작일

type Props = {
  candles: ChartCandle[];
  markers: ChartMarker[];
  initialBars: number | null; // 처음 보여줄 최근 막대 수, null 이면 전체
  onVisibleChange: (from: number, to: number) => void; // 화면에 보이는 막대 인덱스 구간
  onHover: (index: number | null) => void;
};

const ZOOM_SPEED = 0.03; // 라이브러리 기본 휠 줌은 트랙패드 핀치에 너무 느림
const MIN_VISIBLE_BARS = 7;

const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const formatTime = (time: Time) => {
  if (typeof time === "string") return formatDate(time);
  if (typeof time === "number") return formatDate(new Date(time * 1000).toISOString().slice(0, 10));
  return `${time.year}년 ${time.month}월 ${time.day}일`;
};

export function CandleChart({ candles, markers, initialBars, onVisibleChange, onHover }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onVisibleChange, onHover, count: candles.length });
  useEffect(() => {
    callbacks.current = { onVisibleChange, onHover, count: candles.length };
  });
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    const el = container.current;
    if (!el) return;

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: cssVar("--muted"),
        fontFamily: "inherit",
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: cssVar("--border") } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: {
        locale: "ko-KR",
        priceFormatter: formatWon,
        tickmarksPriceFormatter: formatCompactWonTicks,
        timeFormatter: formatTime,
      },
      handleScale: { mouseWheel: false },
      crosshair: { horzLine: { labelVisible: true }, vertLine: { labelVisible: true } },
    });
    const up = cssVar("--up");
    const down = cssVar("--down");
    const series = chart.addSeries(CandlestickSeries, {
      upColor: up,
      downColor: down,
      wickUpColor: up,
      wickDownColor: down,
      borderVisible: false,
    });

    // 트랙패드 핀치는 ctrl+wheel 로 들어옴 — 커서 위치를 중심으로 직접 확대·축소
    // 새 구간은 다음 프레임에 적용됨 — 한 프레임에 몰린 이벤트가 서로 덮어쓰지 않게 마지막 요청 구간을 기준으로 누적
    let pending: { from: number; to: number } | null = null;
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      pending = null;
      const { count, onVisibleChange } = callbacks.current;
      if (!range || count === 0) return;
      const from = Math.min(count - 1, Math.max(0, Math.ceil(range.from)));
      const to = Math.max(from, Math.min(count - 1, Math.floor(range.to)));
      onVisibleChange(from, to);
    });
    chart.subscribeCrosshairMove((param) => {
      const index = param.logical;
      const inside = param.point !== undefined && index !== undefined && index >= 0 && index < callbacks.current.count;
      callbacks.current.onHover(inside ? Math.round(index) : null);
    });
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      const timeScale = chart.timeScale();
      const range = pending ?? timeScale.getVisibleLogicalRange();
      if (!range) return;
      const ratio = Math.min(1, Math.max(0, (event.clientX - el.getBoundingClientRect().left) / timeScale.width()));
      const oldSpan = range.to - range.from;
      const anchor = range.from + oldSpan * ratio;
      const span = Math.max(MIN_VISIBLE_BARS, oldSpan * Math.exp(event.deltaY * ZOOM_SPEED));
      pending = { from: anchor - span * ratio, to: anchor + span * (1 - ratio) };
      timeScale.setVisibleLogicalRange(pending);
    };
    el.addEventListener("wheel", onWheel, { passive: false });

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = createSeriesMarkers(series, []);
    return () => {
      el.removeEventListener("wheel", onWheel);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, []);

  // 막대 단위가 바뀌면 데이터와 처음 보이는 구간을 같이 다시 잡음
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;
    series.setData(
      candles.map((c) => ({ time: c.day, open: c.open, high: c.high, low: c.low, close: c.close })),
    );
    if (initialBars === null) {
      chart.timeScale().fitContent();
    } else {
      const last = candles.length - 1;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, last - initialBars), to: last + 1 });
    }
  }, [candles, initialBars]);

  // 토스증권 "구매·판매 표시" 처럼 B·S 글자 — 매수는 막대 아래, 매도는 막대 위
  useEffect(() => {
    const up = cssVar("--up");
    const down = cssVar("--down");
    markersRef.current?.setMarkers(
      markers.map((m) => ({
        time: m.day,
        position: m.side === "buy" ? "belowBar" : "aboveBar",
        shape: m.side === "buy" ? "arrowUp" : "arrowDown",
        color: m.side === "buy" ? up : down,
        text: `${m.side === "buy" ? "B" : "S"}${m.count > 1 ? ` ${m.count}` : ""}`,
      })),
    );
  }, [candles, markers]);

  return <div ref={container} className="h-80 w-full sm:h-[26rem]" />;
}
