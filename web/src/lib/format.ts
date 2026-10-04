const won = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

export const formatWon = (value: number) => `${won.format(value)}원`;

export const formatSignedWon = (value: number) =>
  `${value > 0 ? "+" : ""}${won.format(value)}원`;

export const formatPercent = (ratio: number) => percent.format(ratio);

export const formatDate = (day: string) => {
  const [y, m, d] = day.split("-").map(Number);
  return `${y}년 ${m}월 ${d}일`;
};

const compactWon = [1, 2, 3, 4].map(
  (digits) => new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: digits }),
);

// 범위가 좁으면 소수 1자리로는 눈금이 같은 글자로 겹침 — 서로 구분될 때까지 자릿수를 늘림
export const formatCompactWonTicks = (values: number[]) => {
  for (const format of compactWon) {
    const labels = values.map(format.format);
    if (new Set(labels).size === labels.length) return labels;
  }
  return values.map(formatWon);
};

export type Currency = "KRW" | "USD";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const formatPrice = (value: number, currency: Currency) =>
  currency === "USD" ? usd.format(value) : formatWon(value);

export const formatSignedPrice = (value: number, currency: Currency) =>
  currency === "USD" ? `${value > 0 ? "+" : ""}${usd.format(value)}` : formatSignedWon(value);

const usdTicks = [0, 2].map(
  (digits) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }),
);

// 축 눈금 — 원은 억·만 축약, 달러는 정수로 구분되면 정수로
export const formatPriceTicks = (currency: Currency) => (values: number[]) => {
  if (currency === "KRW") return formatCompactWonTicks(values);
  for (const format of usdTicks) {
    const labels = values.map(format.format);
    if (new Set(labels).size === labels.length) return labels;
  }
  return values.map(usd.format);
};
