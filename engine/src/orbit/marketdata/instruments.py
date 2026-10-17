import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ValidationError, field_validator

from orbit.settings import REPO_ROOT

log = logging.getLogger(__name__)

NEW_YORK = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")

# 종목 목록은 레포에 두지 않음 — 무엇을 사고 보는지가 공개 레포에 드러나지 않게 로컬 설정에만
DEFAULT_MARKETS_PATH = REPO_ROOT / "config" / "markets.local.yaml"
EXAMPLE_MARKETS_PATH = REPO_ROOT / "config" / "markets.example.yaml"

# 코인은 투자 정책상 BTC·ETH 고정
COINS = (("KRW-BTC", "비트코인"), ("KRW-ETH", "이더리움"))

_KRX_CODE = re.compile(r"[0-9][0-9A-Z]{5}")  # 국내 종목코드 6자리 (예: 0000A0 같은 신형 코드 포함)
_US_TICKER = re.compile(r"[A-Z][A-Z.\-]{0,9}")


@dataclass(frozen=True, slots=True)
class NextOpenSpec:
    # 국내 상장 해외 ETF 의 다음 개장 추정 — 같은 지수 미국 ETF 로 근사하거나 운용사 구성 종목으로
    proxy: str | None = None
    holdings_fund: str | None = None  # TIGER 운용사 펀드 코드 (ksdFund)
    nav: tuple[Literal["tiger", "ace"], str] | None = None  # 기준가 공시 운용사·펀드 코드


@dataclass(frozen=True, slots=True)
class Instrument:
    market: str  # 저장·API 키 — 앞부분이 거래소 (US-·KRX-)
    symbol: str  # 토스 종목 심볼
    exchange_tz: ZoneInfo  # 일봉 날짜를 정하는 거래소 시간대
    dashboard: bool = False  # 맨 위 타일에 보이는 종목
    dca: bool = False  # 매달 적립 — 보유/현금 신호 대신 적립식 분석
    sector: str | None = None  # 관심 종목 분야
    next_open: NextOpenSpec | None = None


def market_key(symbol: str) -> tuple[str, ZoneInfo]:
    # 종목코드 모양으로 거래소를 정함 — 토스 조회 없이도 저장 키·시간대가 정해지게
    if _KRX_CODE.fullmatch(symbol):
        return f"KRX-{symbol}", SEOUL
    if _US_TICKER.fullmatch(symbol):
        return f"US-{symbol}", NEW_YORK
    raise ValueError(f"종목코드 모양을 알 수 없음: {symbol}")


class _NavConfig(BaseModel):
    source: Literal["tiger", "ace"]
    fund: str


class _NextOpenConfig(BaseModel):
    proxy: str | None = None
    holdings: str | None = None  # TIGER 운용사 펀드 코드 — 구성 종목으로 계산
    nav: _NavConfig | None = None


class _DashboardEntry(BaseModel):
    symbol: str
    dca: bool = False
    next_open: _NextOpenConfig | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        return str(value)  # YAML 이 069500 같은 코드를 숫자로 읽지 않게


class _MarketsConfig(BaseModel):
    dashboard: list[_DashboardEntry] = []
    watchlist: dict[str, list[str]] = {}  # 분야: [종목 코드]

    @field_validator("watchlist", mode="before")
    @classmethod
    def _texts(cls, value: object) -> object:
        if isinstance(value, dict):
            return {str(k): [str(s) for s in (v or [])] for k, v in value.items()}
        return value


@dataclass(frozen=True, slots=True)
class Universe:
    instruments: tuple[Instrument, ...] = field(default_factory=tuple)
    sectors: tuple[str, ...] = ()  # 관심 종목 분야 — 설정에 적은 순서

    def watchlist(self) -> list[Instrument]:
        # 분야가 있는 종목을 분야 순서대로 (설정 순서, 없으면 처음 나온 순서)
        order = list(self.sectors)
        for i in self.instruments:
            if i.sector is not None and i.sector not in order:
                order.append(i.sector)
        return [i for sector in order for i in self.instruments if i.sector == sector]

    def find(self, market: str) -> Instrument | None:
        return next((i for i in self.instruments if i.market == market), None)

    @property
    def markets(self) -> list[str]:
        return [i.market for i in self.instruments]


def load_universe(path: Path = DEFAULT_MARKETS_PATH) -> Universe:
    # 없거나 깨지면 코인만 — 종목 목록은 개인 정보라 값은 로그에 남기지 않음
    try:
        config = _MarketsConfig.model_validate(yaml.safe_load(path.read_text()) or {})
        return _build(config)
    except FileNotFoundError:
        log.warning("종목 설정 없음: %s — 코인만", path.name)
    except (yaml.YAMLError, ValidationError, ValueError) as error:
        log.error("종목 설정을 읽을 수 없음 (%s) — 코인만", type(error).__name__)
    return Universe()


def _build(config: _MarketsConfig) -> Universe:
    sectors: dict[str, str] = {}
    for sector, symbols in config.watchlist.items():
        for symbol in symbols:
            sectors.setdefault(symbol, sector)
    instruments: list[Instrument] = []
    seen: set[str] = set()
    for entry in config.dashboard:
        market, tz = market_key(entry.symbol)
        spec = entry.next_open
        next_open = (
            NextOpenSpec(
                proxy=spec.proxy,
                holdings_fund=spec.holdings,
                nav=(spec.nav.source, spec.nav.fund) if spec.nav else None,
            )
            if spec and (spec.proxy or spec.holdings)
            else None
        )
        instruments.append(
            Instrument(
                market, entry.symbol, tz, True, entry.dca, sectors.get(entry.symbol), next_open
            )
        )
        seen.add(entry.symbol)
    for symbol, sector in sectors.items():
        if symbol in seen:
            continue
        market, tz = market_key(symbol)
        instruments.append(Instrument(market, symbol, tz, sector=sector))
    return Universe(tuple(instruments), tuple(config.watchlist))
