import type { Metadata } from "next";
import localFont from "next/font/local";
import { connection } from "next/server";

import { Logo } from "@/components/logo";
import { MarketSwitcher } from "@/components/market-switcher";
import { allTiles } from "@/lib/overview";

import "./globals.css";

const pretendard = localFont({
  src: "../../node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2",
  variable: "--font-pretendard",
  weight: "45 920",
  display: "swap",
});

export const metadata: Metadata = {
  title: "orbit",
  description: "규칙 기반 소액 자동매매 대시보드",
};

// 레이아웃은 종목을 바꿔도 다시 그려지지 않음 — 전 종목 타일은 처음 열 때 한 번만 받고, 종목 전환 때는 그 종목 것만 받음
export default async function RootLayout({ children }: LayoutProps<"/">) {
  await connection();
  const tiles = await allTiles();
  return (
    <html lang="ko" className={`${pretendard.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:py-8">
          <header className="mb-6 flex items-center gap-2">
            <Logo className="size-7" />
            <span className="text-lg font-bold tracking-tight">orbit</span>
          </header>
          <MarketSwitcher tiles={tiles}>{children}</MarketSwitcher>
        </main>
      </body>
    </html>
  );
}
