import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from orbit.marketdata.candle import find_missing_days
from orbit.marketdata.store import CandleStore
from orbit.marketdata.upbit_candles import fetch_daily_candles

EARLIEST = datetime(2017, 1, 1, tzinfo=UTC)  # 업비트 원화 마켓 개장 이전


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
    closed = [c for c in fetched if c.is_closed(now)]
    store.upsert(closed)

    starts = [c.start for c in store.load(market)]
    return SyncResult(
        saved=len(closed),
        skipped_open=len(fetched) - len(closed),
        total=len(starts),
        first=starts[0] if starts else None,
        last=starts[-1] if starts else None,
        missing_days=find_missing_days(starts),
    )
