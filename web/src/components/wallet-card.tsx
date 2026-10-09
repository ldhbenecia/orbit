import type { components } from "@/lib/api";
import { formatDate, formatPercent1, formatWon } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { ruleShortName } from "@/lib/rules";
import { tone } from "@/lib/summary";

type Slot = components["schemas"]["WalletSlotOut"];

// 규칙대로 사고팔았다면 지금 어떤지 — 실제 주문 없이 엔진 장부에만 기록한 결과
export function WalletCard({ info, slots }: { info: MarketInfo; slots: Slot[] }) {
  return (
    <section className="space-y-4 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">가상 지갑 · {info.name}</p>
        <p className="text-xs text-muted">규칙대로 사고팔았다면 — 실제 주문 없이 장부에만 기록 (dry-run)</p>
      </div>
      {slots.map((slot) => (
        <SlotView key={slot.slot} slot={slot} info={info} />
      ))}
    </section>
  );
}

function SlotView({ slot, info }: { slot: Slot; info: MarketInfo }) {
  const budget = Number(slot.budget);
  const value = Number(slot.value);
  const change = budget ? value / budget - 1 : 0;
  const qty = Number(slot.qty);
  return (
    <div className="space-y-3">
      <p className="font-medium">{ruleShortName(slot.strategy, info.group)}</p>
      <div className="rounded-xl bg-background px-4 py-3">
        <p className="text-xs text-muted">예산 {formatWon(budget)} → 지금</p>
        <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
          <span className="text-2xl font-bold tabular-nums">{formatWon(Math.round(value))}</span>
          <span className={`text-sm font-semibold tabular-nums ${tone(change)}`}>{formatPercent1(change)}</span>
        </p>
      </div>
      <dl className="grid grid-cols-3 gap-2 text-sm tabular-nums">
        <Stat label="현금" value={formatWon(Math.round(Number(slot.cash)))} />
        <Stat label="보유" value={qty > 0 ? qty.toLocaleString("ko-KR", { maximumFractionDigits: 8 }) : "없음"} />
        <Stat
          label="실현 손익"
          value={formatWon(Math.round(Number(slot.realized)))}
          className={tone(Number(slot.realized))}
        />
      </dl>
      {slot.fills.length > 0 ? (
        <ul className="divide-y divide-border text-xs">
          {slot.fills.map((f, i) => (
            <li key={i} className="space-y-0.5 py-2">
              <p className="flex justify-between gap-2 tabular-nums">
                <span className={f.side === "buy" ? "text-up" : "text-down"}>{f.side === "buy" ? "매수" : "매도"}</span>
                <span className="text-muted">{formatDate(f.at.slice(0, 10))}</span>
              </p>
              <p className="tabular-nums">
                {Number(f.qty).toLocaleString("ko-KR", { maximumFractionDigits: 8 })} @ {formatWon(Number(f.price))}
                <span className="ml-1 text-muted">수수료 {formatWon(Number(f.fee))}</span>
              </p>
              <p className="truncate text-muted" title={f.reason}>
                {f.reason}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted">아직 사고판 기록이 없어요.</p>
      )}
    </div>
  );
}

function Stat({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="min-w-0 rounded-lg bg-background px-3 py-2">
      <dt className="text-[11px] text-muted">{label}</dt>
      <dd className={`truncate font-medium ${className}`}>{value}</dd>
    </div>
  );
}
