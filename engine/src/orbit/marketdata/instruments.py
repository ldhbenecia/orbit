from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Instrument:
    market: str  # 저장·API 키 — 앞부분이 거래소 (US-·KRX-)
    symbol: str  # 토스 종목 심볼
    name: str
    exchange_tz: ZoneInfo  # 일봉 날짜를 정하는 거래소 시간대


NEW_YORK = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")

# 종목코드는 토스 종목 정보 조회로 확인한 값
STOCK_INSTRUMENTS = (
    Instrument("US-QQQ", "QQQ", "QQQ", NEW_YORK),
    Instrument("US-SPY", "SPY", "SPY", NEW_YORK),
    Instrument("KRX-367380", "367380", "ACE 미국나스닥100", SEOUL),
    Instrument("KRX-360750", "360750", "TIGER 미국S&P500", SEOUL),
)


def find_instrument(market: str) -> Instrument:
    for instrument in STOCK_INSTRUMENTS:
        if instrument.market == market:
            return instrument
    raise ValueError(f"등록되지 않은 종목: {market}")
