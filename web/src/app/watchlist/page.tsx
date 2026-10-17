import Link from "next/link";
import { connection } from "next/server";

import type { components } from "@/lib/api";
import { engineJson } from "@/lib/engine";
import { formatDate, formatPercent1, formatPrice } from "@/lib/format";
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
  const asOf = rows.find((r) => r.as_of)?.as_of;

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">관심 종목</h1>
        <p className="text-sm text-muted">
          가격이 어디쯤인지와 추세만 보여줘요 — 추천이 아니에요. 추세는 대시보드 신호와 같은 이동평균 규칙이에요.
          {asOf && ` ${formatDate(asOf)} 종가 기준.`}
        </p>
      </div>
      {sectors.map((sector) => (
        <section key={sector} className="space-y-2">
          <h2 className="text-sm font-semibold text-muted">{sector}</h2>
          <div className="overflow-hidden rounded-2xl bg-subtle">
            <table className="w-full table-fixed text-sm tabular-nums">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="w-[40%] px-4 py-2 text-left font-normal sm:w-[36%]">종목</th>
                  <th className="w-[26%] px-2 py-2 text-right font-normal sm:w-[22%]">가격 · 하루</th>
                  <th className="hidden w-[12%] px-2 py-2 text-right font-normal sm:table-cell">1년</th>
                  <th className="w-[16%] px-2 py-2 text-right font-normal sm:w-[14%]">고점 대비</th>
                  <th className="w-[18%] px-4 py-2 text-right font-normal sm:w-[16%]">추세</th>
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
        있어요. 추세 점은 왼쪽부터 60·120·200거래일 평균 위(빨강)·아래(파랑)예요.
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
            <span>{formatPrice(Number(row.close), currency)}</span>
            {row.change !== null && (
              <span className={`ml-1.5 text-xs ${tone(Number(row.change))}`}>{formatPercent1(Number(row.change))}</span>
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
            <span className="ml-1 text-xs text-muted">
              {above}/{row.trend.length}
            </span>
          </span>
        )}
      </td>
    </tr>
  );
}
