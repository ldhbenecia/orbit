import Link from "next/link";
import { connection } from "next/server";

import type { components } from "@/lib/api";
import { engineJson } from "@/lib/engine";
import { rankLabel } from "@/components/fundamentals-card";
import { CHECK_LABEL, checkState } from "@/components/trend-template-card";
import { formatDate, formatMultiple, formatPercent1, formatPrice } from "@/lib/format";
import { DEMO, type MarketInfo } from "@/lib/markets";
import { tone } from "@/lib/summary";
import { getMarkets } from "@/lib/universe";

type Row = components["schemas"]["WatchRowOut"];

export const metadata = { title: "관심 종목 · orbit" };

// 사라·말라가 아니라 사실만 — 가격이 어디쯤인지(고점 대비), 추세가 어떤지(평균 위·아래)
export default async function WatchlistPage() {
  await connection();
  const [rows, markets] = await Promise.all([engineJson<Row[]>("/watchlist"), getMarkets()]);
  const info = new Map(markets.map((m) => [m.market, m]));

  if (rows === null) {
    return <p className="rounded-2xl bg-subtle p-6 text-sm">엔진 API 에 연결할 수 없어요.</p>;
  }
  if (rows.length === 0) {
    return (
      <div className="space-y-2 rounded-2xl bg-subtle p-6 text-sm">
        <p className="font-semibold">관심 종목이 없어요</p>
        <p className="text-muted">
          <code>config/markets.local.yaml</code> 의 <code>watchlist</code> 에 분야별 종목 코드를 적고{" "}
          <code>uv run orbit sync-stocks</code> 로 시세를 받으세요.
        </p>
      </div>
    );
  }

  const sectors = [...new Set(rows.map((r) => r.sector))];

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">관심 종목</h1>
        <p className="text-sm text-muted">
          가격이 어디쯤인지와 추세만 보여줘요 — 추천이 아니에요. 추세는 대시보드 신호와 같은 이동평균 규칙이에요. 가격은
          종목마다 그 거래소의 마지막 종가예요 (가격에 마우스를 올리면 날짜).
        </p>
      </div>
      {sectors.map((sector) => (
        <section key={sector} className="space-y-2">
          <h2 className="text-sm font-semibold text-muted">{sector}</h2>
          <div className="overflow-hidden rounded-2xl bg-subtle">
            <table className="w-full table-fixed text-sm tabular-nums">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="w-[30%] px-4 py-2 text-left font-normal">종목</th>
                  <th className="w-[24%] px-2 py-2 text-right font-normal sm:w-[20%]">가격 · 하루</th>
                  <th className="hidden w-[10%] px-2 py-2 text-right font-normal sm:table-cell">1년</th>
                  <th className="w-[14%] px-2 py-2 text-right font-normal sm:w-[12%]">고점 대비</th>
                  <th className="w-[14%] px-2 py-2 text-right font-normal sm:w-[13%]" title="아래 줄은 지난 5년 월말 PER 중 지금 위치">
                    PER
                  </th>
                  <th className="w-[18%] px-4 py-2 text-right font-normal sm:w-[15%]">추세</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows
                  .filter((r) => r.sector === sector)
                  .map((r) => (
                    <WatchRow key={r.market} row={r} info={info.get(r.market)} />
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      <p className="text-xs leading-relaxed text-muted">
        고점 대비는 최근 52주(1년) 최고 종가에서 얼마나 내려와 있는지예요. 많이 내려왔다고 싼 건 아니에요 — 이익이 같이 줄었을 수
        있어요. PER 은 시가총액 ÷ 최근 4분기 순이익(SEC 공시)이고, 아래 줄은 지난 5년 월말 PER 중 지금 위치예요 —
        ETF·해외 공시 기업은 없어요. 추세 점은 왼쪽부터 60·120·200거래일 평균 위(빨강)·아래(파랑)예요. 아래 줄 템플릿 N/8 은 마크 미너비니의 상승 추세 조건 8개 중 몇 개를 갖췄는지예요 (마우스를 올리면 조건별, 종목 화면에서 자세히).
      </p>
    </div>
  );
}

function WatchRow({ row, info }: { row: Row; info: MarketInfo | undefined }) {
  const currency = row.currency;
  const above = row.trend.filter((t) => t.above).length;
  return (
    <tr className="hover:bg-background/40">
      <td className="px-4 py-2.5">
        <Link href={`/?market=${row.market}`} className="block truncate font-medium hover:underline">
          {info?.name ?? row.market}
          {!DEMO && <span className="ml-1.5 text-xs font-normal text-muted">{row.market.split("-").slice(1).join("-")}</span>}
        </Link>
      </td>
      <td className="px-2 py-2.5 text-right">
        {row.close === null ? (
          <span className="text-muted">시세 없음</span>
        ) : (
          <>
            <span title={row.as_of ? `${formatDate(row.as_of)} 종가` : undefined}>
              {formatPrice(Number(row.close), currency)}
            </span>
            {row.change !== null && (
              <span className={`block text-xs sm:ml-1.5 sm:inline ${tone(Number(row.change))}`}>{formatPercent1(Number(row.change))}</span>
            )}
          </>
        )}
      </td>
      <td className={`hidden px-2 py-2.5 text-right sm:table-cell ${tone(Number(row.return_1y ?? 0))}`}>
        {row.return_1y === null ? "—" : formatPercent1(Number(row.return_1y))}
      </td>
      <td className="px-2 py-2.5 text-right">
        {row.from_high === null ? "—" : Number(row.from_high) > -0.0005 ? "고점" : formatPercent1(Number(row.from_high))}
      </td>
      <td className="px-2 py-2.5 text-right">
        <Per row={row} />
      </td>
      <td className="px-4 py-2.5 text-right">
        {row.trend.length === 0 ? (
          <span className="text-xs text-muted">데이터 부족</span>
        ) : (
          <span className="inline-flex items-center gap-1" title={`${row.trend.length}개 중 ${above}개 평균 위`}>
            {row.trend.map((t) => (
              <span
                key={t.window}
                className={`inline-block size-2 rounded-full ${t.above ? "bg-up" : "bg-down"}`}
                aria-label={`${t.window}거래일 평균 ${t.above ? "위" : "아래"}`}
              />
            ))}
            <span className="ml-1 hidden text-xs text-muted sm:inline">
              {above}/{row.trend.length}
            </span>
          </span>
        )}
        {row.template && (
          <span
            className="block whitespace-nowrap text-[11px] text-muted"
            title={row.template.checks
              .map((c) => `${CHECK_LABEL[c.check]}: ${checkState(c.passed)}`)
              .join("\n")}
          >
            템플릿 {row.template.passed}/{row.template.known}
          </span>
        )}
      </td>
    </tr>
  );
}

function Per({ row }: { row: Row }) {
  const f = row.fundamentals;
  if (!f) return <span className="text-muted">—</span>;
  if (f.per === null) return <span className="text-xs text-muted">{f.loss ? "적자" : "—"}</span>;
  return (
    <span title={`${formatDate(f.period_end)}까지 최근 4분기 · ${formatDate(f.filed)} 공시`}>
      {formatMultiple(f.per)}
      {f.per_5y && <span className="block whitespace-nowrap text-[11px] text-muted">{rankLabel(f.per_5y)}</span>}
    </span>
  );
}
