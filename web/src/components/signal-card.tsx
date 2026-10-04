import type { components } from "@/lib/api";
import { formatDate, formatWon } from "@/lib/format";
import { ruleName } from "@/lib/rules";

type Signals = components["schemas"]["SignalsOut"];
type Signal = components["schemas"]["SignalOut"];
type Stance = components["schemas"]["Stance"];

const STANCE: Record<Stance, { label: string; tone: string; buySide: boolean }> = {
  hold: { label: "보유 구간", tone: "text-up", buySide: true },
  cash: { label: "현금 구간", tone: "text-down", buySide: false },
  breakout_hit: { label: "오늘 돌파함", tone: "text-up", buySide: true },
  breakout_wait: { label: "돌파 대기", tone: "text-muted", buySide: false },
};

export function SignalCard({ name, data }: { name: string; data: Signals }) {
  const buySide = data.signals.filter((s) => STANCE[s.stance].buySide).length;
  const total = data.signals.length;

  return (
    <section className="space-y-3 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">오늘의 규칙 신호 · {name}</p>
        <p className="text-xl font-bold">
          규칙 {total}개 중 {buySide}개가 매수 쪽
        </p>
        <p className="text-xs text-muted">
          {formatDate(data.as_of.slice(0, 10))} 확정 봉 기준
          {data.price ? ` · 현재가 ${formatWon(Number(data.price))}` : " · 현재가를 못 받아 돌파 여부 제외"}
        </p>
      </div>

      <ul className="divide-y divide-border">
        {data.signals.map((s) => (
          <SignalRow key={s.strategy} signal={s} />
        ))}
      </ul>

      <p className="text-xs leading-relaxed text-muted">
        내가 고른 규칙이 지금 무엇을 말하는지일 뿐 투자 권유가 아니에요. 실험 중인 규칙은 아직 검증 전이에요.
      </p>
    </section>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  const stance = STANCE[signal.stance];
  const detail = signal.trigger
    ? `기준선 ${formatWon(Number(signal.trigger))}`
    : signal.days
      ? `${signal.days}일째`
      : null;

  return (
    <li className="space-y-1 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-medium">
          {ruleName(signal.strategy)}
          <span className="ml-2 rounded-md bg-background px-1.5 py-0.5 text-xs font-normal text-muted">
            {signal.status}
          </span>
        </p>
        <p className={`shrink-0 text-sm font-semibold ${stance.tone}`}>
          {stance.label}
          {detail && <span className="ml-1 font-normal text-muted tabular-nums">· {detail}</span>}
        </p>
      </div>
      <p className="text-xs text-muted tabular-nums">{signal.reason}</p>
    </li>
  );
}
