"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState, useTransition } from "react";

import { type Currency, formatPercent, formatPrice } from "@/lib/format";
import { findMarket, GROUPS, MARKETS } from "@/lib/markets";
import { type Line, tone } from "@/lib/summary";

export type Tile = {
  close: number;
  change: number; // 전일 종가 대비 비율
  closes: number[]; // 미니 차트용 최근 종가
  line: Line | null;
};

const groupLabel = (value: string) => GROUPS.find((g) => g.value === value)?.label ?? "";

// 서버가 새 종목 화면을 그리는 동안에도 선택 표시는 바로 움직이고, 아래 내용은 흐리게 — 눌렀는데 반응이 없다고 느끼지 않게
export function MarketSwitcher({
  tiles,
  children,
}: {
  tiles: Partial<Record<string, Tile>>;
  children: ReactNode;
}) {
  const router = useRouter();
  const current = findMarket(useSearchParams().get("market") ?? undefined).market;
  const [pending, startTransition] = useTransition();
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = findMarket(pending && chosen ? chosen : current).market;

  const go = (market: string) => {
    if (market === current) return;
    setChosen(market);
    startTransition(() => router.push(`/?market=${market}`));
  };

  // 폰에서는 가로로 밀어 보고, 넓은 화면에서는 전 종목이 한 줄에
  return (
    <div className="space-y-8">
      <div
        className="no-scrollbar -mx-4 flex snap-x gap-2 overflow-x-auto px-4 lg:mx-0 lg:grid lg:grid-cols-6 lg:overflow-visible lg:px-0"
        role="tablist"
        aria-label="종목"
      >
        {MARKETS.map((m) => (
          <TileButton
            key={m.market}
            name={m.name}
            group={groupLabel(m.group)}
            currency={m.currency}
            tile={tiles[m.market]}
            selected={m.market === selected}
            onClick={() => go(m.market)}
          />
        ))}
      </div>
      <div className={`transition-opacity duration-200 ${pending ? "opacity-50" : ""}`} aria-busy={pending}>
        {children}
      </div>
    </div>
  );
}

function TileButton({
  name,
  group,
  currency,
  tile,
  selected,
  onClick,
}: {
  name: string;
  group: string;
  currency: Currency;
  tile: Tile | undefined;
  selected: boolean;
  onClick: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  // 폰에서 뒤쪽 종목을 열면 타일 줄도 그 종목이 보이게 — 가로로만 움직임
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected]);

  return (
    <button
      ref={ref}
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onClick}
      className={`flex w-40 shrink-0 snap-start flex-col justify-start gap-2 rounded-2xl bg-subtle p-3.5 text-left ring-1 transition-shadow lg:w-auto ${
        selected ? "ring-foreground/40" : "ring-transparent hover:ring-border"
      }`}
    >
      <div>
        <p className="text-[11px] text-muted">{group}</p>
        <p className="truncate text-sm font-semibold">{name}</p>
      </div>
      {tile ? (
        <>
          <div className="tabular-nums">
            <p className="truncate text-sm">{formatPrice(tile.close, currency)}</p>
            <p className={`text-xs ${tone(tile.change)}`}>{formatPercent(tile.change)}</p>
          </div>
          <Sparkline closes={tile.closes} />
          {tile.line && (
            <div className="space-y-0.5 text-xs">
              <p className={`font-medium ${tile.line.tone}`}>{tile.line.text}</p>
              {tile.line.sub && <p className={tile.line.sub.tone}>{tile.line.sub.text}</p>}
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-muted">시세 없음</p>
      )}
    </button>
  );
}

// 흐름만 보는 용도 — 손익 색은 숫자에만 쓰고 선은 중립색
function Sparkline({ closes }: { closes: number[] }) {
  if (closes.length < 2) return null;
  const min = Math.min(...closes);
  const span = Math.max(...closes) - min || 1;
  const points = closes.map((c, i) => `${(i / (closes.length - 1)) * 100},${30 - ((c - min) / span) * 28}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="h-8 w-full text-muted" aria-hidden>
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
