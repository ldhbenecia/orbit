import type { components } from "@/lib/api";
import { type Currency, formatDate, formatPrice } from "@/lib/format";
import type { MarketInfo } from "@/lib/markets";
import { ruleDescription, ruleParam, ruleShortName } from "@/lib/rules";

type Signals = components["schemas"]["SignalsOut"];
type Signal = components["schemas"]["SignalOut"];
type Stance = components["schemas"]["Stance"];

const STANCE: Record<Stance, { label: string; tone: string; buySide: boolean }> = {
  hold: { label: "보유 구간", tone: "text-up", buySide: true },
  cash: { label: "현금 구간", tone: "text-down", buySide: false },
  breakout_hit: { label: "오늘 돌파함", tone: "text-up", buySide: true },
  breakout_wait: { label: "돌파 대기", tone: "text-muted", buySide: false },
};

export function SignalCard({ info, data }: { info: MarketInfo; data: Signals }) {
  const buySide = data.signals.filter((s) => STANCE[s.stance].buySide).length;
  const total = data.signals.length;

  return (
    <section className="space-y-3 rounded-2xl bg-subtle p-5">
      <div className="space-y-1">
        <p className="text-sm text-muted">오늘의 규칙 신호 · {info.name}</p>
        <p className="text-xl font-bold">
          규칙 {total}개 중 {buySide}개가 매수 쪽
        </p>
        <p className="text-xs text-muted">
          {formatDate(data.as_of.slice(0, 10))} 확정 봉 기준
          {data.price
            ? ` · 현재가 ${formatPrice(Number(data.price), info.currency)}`
            : info.group === "coin"
              ? " · 현재가를 못 받아 돌파 여부 제외"
              : ""}
        </p>
      </div>

      <ul className="divide-y divide-border">
        {data.signals.map((s) => (
          <SignalRow key={s.strategy} signal={s} info={info} />
        ))}
      </ul>

      <p className="text-xs leading-relaxed text-muted">
        내가 고른 규칙이 지금 무엇을 말하는지일 뿐 투자 권유가 아니에요. 실험 중인 규칙은 아직 검증 전이에요.
      </p>
    </section>
  );
}

function SignalRow({ signal, info }: { signal: Signal; info: MarketInfo }) {
  const currency: Currency = info.currency;
  const price = (value: string) => formatPrice(Number(value), currency);
  const stance = STANCE[signal.stance];
  const detail = signal.days ? `${signal.days}일째` : null;

  const meta = [ruleParam(signal.strategy, info.group), signal.status, detail].filter(Boolean).join(" · ");

  // 좁은 화면에서 이름·상태가 줄바꿈으로 쪼개지지 않게 첫 줄엔 짧은 이름과 상태만
  return (
    <li className="space-y-1.5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 font-medium">{ruleShortName(signal.strategy, info.group)}</p>
        <p className={`shrink-0 text-sm font-semibold ${stance.tone}`}>{stance.label}</p>
      </div>
      <p className="text-xs text-muted tabular-nums">{meta}</p>
      <p className="text-xs text-muted">{ruleDescription(signal.strategy)}</p>
      {signal.reference ? (
        <ReferenceLine close={price(signal.close)} reference={price(signal.reference)} gap={Number(signal.close) / Number(signal.reference) - 1} />
      ) : signal.trigger ? (
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm tabular-nums">
          <span>
            <span className="text-xs text-muted">오늘 기준선 </span>
            {price(signal.trigger)}
          </span>
        </p>
      ) : null}
    </li>
  );
}

// 근거 문장 대신 숫자를 라벨과 함께, 평균과의 차이는 기호가 아니라 말과 색으로
function ReferenceLine({ close, reference, gap }: { close: string; reference: string; gap: number }) {
  const above = gap >= 0;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm tabular-nums">
      <span>
        <span className="text-xs text-muted">지금 </span>
        {close}
      </span>
      <span>
        <span className="text-xs text-muted">평균 </span>
        {reference}
      </span>
      <span
        className={`rounded-md bg-background px-2 py-0.5 text-xs font-medium ${above ? "text-up" : "text-down"}`}
      >
        평균보다 {Math.abs(gap * 100).toFixed(1)}% {above ? "높음" : "낮음"}
      </span>
    </div>
  );
}
