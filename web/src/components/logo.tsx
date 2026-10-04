// 코어(가운데 구)와 그 둘레를 도는 위성 — 코어는 직접 사고 위성만 규칙으로 보는 구성
export function Logo({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={className}>
      <g transform="translate(32 32) rotate(-24)">
        <ellipse rx="25" ry="9.5" fill="none" stroke="currentColor" strokeOpacity=".38" strokeWidth="2.6" />
        <circle r="10.5" fill="currentColor" />
        <path d="M-25 0A25 9.5 0 0 0 25 0" fill="none" stroke="var(--background)" strokeWidth="6.5" />
        <path d="M-25 0A25 9.5 0 0 0 25 0" fill="none" stroke="currentColor" strokeWidth="2.6" />
        <circle cx="17.7" cy="6.7" r="4.6" fill="var(--background)" />
        <circle cx="17.7" cy="6.7" r="3.3" fill="currentColor" />
      </g>
    </svg>
  );
}
