import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from orbit.marketdata.candle import Candle, find_missing_days
from orbit.marketdata.instruments import Instrument
from orbit.marketdata.store import CandleStore
from orbit.marketdata.toss import TossMarketData
from orbit.marketdata.upbit_candles import fetch_daily_candles

EARLIEST = datetime(2017, 1, 1, tzinfo=UTC)  # 업비트 원화 마켓 개장 이전
STOCK_EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)  # 닷컴·금융위기 하락장까지 포함


@dataclass(frozen=True, slots=True)
class SyncResult:
    saved: int
    skipped_open: int  # 진행 중이라 버린 봉 수
    total: int
    first: datetime | None
    last: datetime | None
    missing_days: list[datetime]


def sync_daily_candles(
    client: httpx.Client,
    store: CandleStore,
    market: str,
    now: datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> SyncResult:
    # 마지막 저장 봉부터 다시 받음 — upsert 라 중복 없이 이어 붙음
    since = store.latest_start(market) or EARLIEST
    fetched = fetch_daily_candles(client, market, since, sleep)
    return _save(store, market, fetched, now)


def sync_stock_daily(
    api: TossMarketData, store: CandleStore, instrument: Instrument, now: datetime
) -> SyncResult:
    since = store.latest_start(instrument.market) or STOCK_EARLIEST
    fetched = api.daily_candles(
        instrument.symbol, instrument.market, instrument.exchange_tz, since.date()
    )
    # 주식은 주말·휴장일에 봉이 없는 게 정상 — 빠진 날 검사는 24시간 거래하는 코인만
    return _save(store, instrument.market, fetched, now, check_gaps=False)


def _save(
    store: CandleStore,
    market: str,
    fetched: list[Candle],
    now: datetime,
    check_gaps: bool = True,
) -> SyncResult:
    # 거래일 다음 날 UTC 0시 전 봉은 진행 중일 수 있음 — 확정 판단이 늦는 쪽으로 보수적
    # (미국은 뉴욕 장 마감 16시 이후, 한국 주식은 다음 날 아침)
    closed = [c for c in fetched if c.is_closed(now)]
    store.upsert(closed, fetched_at=now)

    starts = [c.start for c in store.load(market)]
    return SyncResult(
        saved=len(closed),
        skipped_open=len(fetched) - len(closed),
        total=len(starts),
        first=starts[0] if starts else None,
        last=starts[-1] if starts else None,
        missing_days=find_missing_days(starts) if check_gaps else [],
    )
