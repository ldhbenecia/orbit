"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useLayoutEffect, useRef, useState, useTransition } from "react";

import { findMarket, GROUPS, MARKETS, type MarketGroup, marketsOf } from "@/lib/markets";
import type { Line } from "@/lib/summary";

// 서버가 새 종목 화면을 그리는 동안에도 선택 표시는 바로 움직이고, 아래 내용은 흐리게 — 눌렀는데 반응이 없다고 느끼지 않게
export function MarketSwitcher({
  current,
  lines,
  children,
}: {
  current: string;
  lines: Partial<Record<string, Line>>;
  children: ReactNode;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = findMarket(pending && chosen ? chosen : current);

  const go = (market: string) => {
    if (market === current) return;
    setChosen(market);
    startTransition(() => router.push(`/?market=${market}`));
  };

  return (
    <div className="space-y-6">
      <Overview selected={selected.market} lines={lines} onSelect={go} />
      <div className="space-y-3">
        <GroupTabs value={selected.group} onChange={(group) => go(marketsOf(group)[0].market)} />
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4" role="tablist" aria-label="종목">
          {marketsOf(selected.group).map((m) => (
            <button
              key={m.market}
              type="button"
              role="tab"
              aria-selected={m.market === selected.market}
              onClick={() => go(m.market)}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                m.market === selected.market
                  ? "bg-foreground text-background"
                  : "bg-subtle text-muted hover:text-foreground"
              }`}
            >
              {m.name}
            </button>
          ))}
        </div>
      </div>
      <div className={`transition-opacity duration-200 ${pending ? "opacity-50" : ""}`} aria-busy={pending}>
        {children}
      </div>
    </div>
  );
}

// 전 종목을 한 줄씩 — 신호를 못 받은 종목은 줄을 비워 둠
function Overview({
  selected,
  lines,
  onSelect,
}: {
  selected: string;
  lines: Partial<Record<string, Line>>;
  onSelect: (market: string) => void;
}) {
  if (Object.keys(lines).length === 0) return null;
  return (
    <section className="space-y-1">
      <p className="px-1 text-xs text-muted">전 종목 한 줄 신호</p>
      <ul>
        {MARKETS.map((m) => {
          const line = lines[m.market];
          return (
            <li key={m.market}>
              <button
                type="button"
                onClick={() => onSelect(m.market)}
                aria-current={m.market === selected}
                className={`flex w-full items-baseline justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                  m.market === selected ? "bg-subtle" : "hover:bg-subtle"
                }`}
              >
                <span className="min-w-0 truncate text-sm font-medium">{m.name}</span>
                <span className={`shrink-0 text-sm tabular-nums ${line?.tone ?? "text-muted"}`}>
                  {line?.text ?? "—"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// 글자 길이가 달라 밑줄 위치·너비를 실제 버튼 크기로 잡음
function GroupTabs({ value, onChange }: { value: MarketGroup; onChange: (group: MarketGroup) => void }) {
  const buttons = useRef<Partial<Record<MarketGroup, HTMLButtonElement | null>>>({});
  const [line, setLine] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const el = buttons.current[value];
    if (el) setLine({ left: el.offsetLeft, width: el.offsetWidth });
  }, [value]);

  return (
    <div className="relative flex gap-5 border-b border-border" role="tablist" aria-label="자산">
      {GROUPS.map((g) => (
        <button
          key={g.value}
          ref={(el) => {
            buttons.current[g.value] = el;
          }}
          type="button"
          role="tab"
          aria-selected={g.value === value}
          onClick={() => onChange(g.value)}
          className={`pb-2.5 text-lg font-bold transition-colors ${
            g.value === value ? "text-foreground" : "text-muted hover:text-foreground"
          }`}
        >
          {g.label}
        </button>
      ))}
      {line && (
        <span
          aria-hidden
          className="absolute -bottom-px h-0.5 rounded-full bg-foreground transition-all duration-300 ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:transition-none"
          style={{ left: line.left, width: line.width }}
        />
      )}
    </div>
  );
}
