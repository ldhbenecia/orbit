import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from orbit.marketdata.candle import Candle, find_missing_days
from orbit.marketdata.instruments import Instrument
from orbit.marketdata.store import CandleStore
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
    replaced: bool = False  # 수정주가가 바뀌어 전 기간을 다시 받음


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


class StockCandles(Protocol):
    def daily_candles(
        self, symbol: str, market: str, exchange_tz: ZoneInfo, since: date
    ) -> list[Candle]: ...


def sync_stock_daily(
    api: StockCandles, store: CandleStore, instrument: Instrument, now: datetime
) -> SyncResult:
    market = instrument.market

    def fetch(since: datetime) -> list[Candle]:
        return api.daily_candles(instrument.symbol, market, instrument.exchange_tz, since.date())

    latest = store.latest_start(market)
    # 마지막 저장 봉부터 다시 받음 — 그 봉이 겹쳐서 수정주가가 바뀌었는지 볼 수 있음
    fetched = fetch(latest or STOCK_EARLIEST)
    stored = next((c for c in store.load(market) if c.start == latest), None)
    again = next((c for c in fetched if c.start == latest), None)
    adjusted = stored is not None and again is not None and again != stored
    if adjusted:
        # 액면분할 등으로 수정주가가 다시 계산됨 — 저장된 옛 봉도 전부 바뀌었으므로
        # 이어 붙이면 분할일에 폭락·폭등처럼 보임. 전 기간을 다시 받아 통째로 바꿈
        fetched = fetch(STOCK_EARLIEST)
    # 주식은 주말·휴장일에 봉이 없는 게 정상 — 빠진 날 검사는 24시간 거래하는 코인만
    return _save(store, market, fetched, now, check_gaps=False, replace=adjusted)


def _save(
    store: CandleStore,
    market: str,
    fetched: list[Candle],
    now: datetime,
    check_gaps: bool = True,
    replace: bool = False,
) -> SyncResult:
    # 거래일 다음 날 UTC 0시 전 봉은 진행 중일 수 있음 — 확정 판단이 늦는 쪽으로 보수적
    # (미국은 뉴욕 장 마감 16시 이후, 한국 주식은 다음 날 아침)
    closed = [c for c in fetched if c.is_closed(now)]
    if replace:
        store.replace(market, closed, fetched_at=now)
    else:
        store.upsert(closed, fetched_at=now)

    starts = [c.start for c in store.load(market)]
    return SyncResult(
        saved=len(closed),
        skipped_open=len(fetched) - len(closed),
        total=len(starts),
        first=starts[0] if starts else None,
        last=starts[-1] if starts else None,
        missing_days=find_missing_days(starts) if check_gaps else [],
        replaced=replace,
    )
