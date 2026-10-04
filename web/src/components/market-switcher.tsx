"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useState, useTransition } from "react";

import { SegmentedControl } from "@/components/segmented-control";
import { COIN_MARKETS } from "@/lib/markets";

type Market = (typeof COIN_MARKETS)[number]["market"];

const OPTIONS = COIN_MARKETS.map((m) => ({ value: m.market, label: m.name }));

// 서버가 새 종목 화면을 그리는 동안에도 선택 표시는 바로 움직이고, 아래 내용은 흐리게 — 눌렀는데 반응이 없다고 느끼지 않게
export function MarketSwitcher({ current, children }: { current: Market; children: ReactNode }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [chosen, setChosen] = useState<Market | null>(null);
  const selected = pending && chosen ? chosen : current;

  return (
    <div className="space-y-6">
      <SegmentedControl
        label="종목"
        options={OPTIONS}
        value={selected}
        onChange={(market) => {
          if (market === current) return;
          setChosen(market);
          startTransition(() => router.push(`/?market=${market}`));
        }}
      />
      <div className={`transition-opacity duration-200 ${pending ? "opacity-50" : ""}`} aria-busy={pending}>
        {children}
      </div>
    </div>
  );
}
