"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useState, useTransition } from "react";

import { SegmentedControl } from "@/components/segmented-control";
import { findMarket, GROUPS, type MarketGroup, marketsOf } from "@/lib/markets";

// 서버가 새 종목 화면을 그리는 동안에도 선택 표시는 바로 움직이고, 아래 내용은 흐리게 — 눌렀는데 반응이 없다고 느끼지 않게
export function MarketSwitcher({ current, children }: { current: string; children: ReactNode }) {
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
      <div className="space-y-2">
        <SegmentedControl
          label="자산"
          options={GROUPS}
          value={selected.group}
          onChange={(group: MarketGroup) => go(marketsOf(group)[0].market)}
        />
        <SegmentedControl
          key={selected.group}
          label="종목"
          options={marketsOf(selected.group).map((m) => ({ value: m.market, label: m.name }))}
          value={selected.market}
          onChange={go}
        />
      </div>
      <div className={`transition-opacity duration-200 ${pending ? "opacity-50" : ""}`} aria-busy={pending}>
        {children}
      </div>
    </div>
  );
}
