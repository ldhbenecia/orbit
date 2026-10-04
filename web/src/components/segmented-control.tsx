"use client";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  label: string;
  options: readonly Option<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
};

// 선택 표시 하나가 눌린 칸으로 미끄러짐 — 칸 너비가 같아서 자기 너비의 index 배만큼 이동하면 됨
export function SegmentedControl<T extends string>({ label, options, value, onChange, className = "" }: Props<T>) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));

  return (
    <div
      role="tablist"
      aria-label={label}
      className={`relative grid rounded-xl bg-subtle p-1 ${className}`}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-1 left-1 rounded-lg bg-background shadow-sm transition-transform duration-300 ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:transition-none"
        style={{ width: `calc((100% - 0.5rem) / ${options.length})`, transform: `translateX(${index * 100}%)` }}
      />
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`relative rounded-lg py-1.5 text-sm font-medium transition-colors ${
            o.value === value ? "text-foreground" : "text-muted hover:text-foreground"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
