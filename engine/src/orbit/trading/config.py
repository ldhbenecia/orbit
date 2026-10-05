import logging
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from orbit.settings import REPO_ROOT

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "orbit.local.yaml"
# 투자 정책상 코인은 BTC·ETH 만 — 화이트리스트 추가는 사람만
ALLOWED_MARKETS = frozenset({"KRW-BTC", "KRW-ETH"})


class Mode(StrEnum):
    DRY_RUN = "dry-run"
    LIVE = "live"


class Limits(BaseModel):
    max_order_krw: Decimal = Field(gt=0)  # 1회 주문 금액 상한
    max_orders_per_day: int = Field(gt=0)


class RuleConfig(BaseModel):
    market: str
    strategy: str
    weight: Decimal = Field(gt=0, le=1)  # 예산 중 이 규칙 몫

    @field_validator("market")
    @classmethod
    def _allowed(cls, market: str) -> str:
        if market not in ALLOWED_MARKETS:
            raise ValueError(f"허용되지 않은 종목: {market}")
        return market

    @field_validator("strategy")
    @classmethod
    def _target_weight_only(cls, strategy: str) -> str:
        # 변동성 돌파는 장중에 기준선을 지켜봐야 해서 하루 한 번 실행으로는 못 따라감
        name, _, arg = strategy.partition("-")
        if not (strategy == "hold" or (name == "ma" and arg.isdigit() and int(arg) > 0)):
            raise ValueError(f"하루 한 번 실행에 쓸 수 없는 규칙: {strategy}")
        return strategy

    @property
    def slot(self) -> str:
        return f"{self.market}:{self.strategy}"

    def budget(self, total: Decimal) -> Decimal:
        # 원 단위 내림 — 칸 예산 합이 총 예산을 넘지 않게
        return (total * self.weight).to_integral_value(rounding="ROUND_FLOOR")


class TradingConfig(BaseModel):
    mode: Mode = Mode.DRY_RUN
    budget_krw: Decimal = Field(gt=0)  # 자동매매 배정 예산 — 계좌 잔고가 아님
    reinvest_profit: bool = False  # 실현 수익을 예산에 다시 넣을지 (기본: 안 넣음)
    limits: Limits
    rules: list[RuleConfig]

    @property
    def ledger_mode(self) -> Literal["dry-run", "live"]:
        return "live" if self.mode is Mode.LIVE else "dry-run"

    @model_validator(mode="after")
    def _weights(self) -> "TradingConfig":
        if sum((r.weight for r in self.rules), Decimal(0)) > 1:
            raise ValueError("규칙 비중 합이 1 을 넘음")
        if len({r.slot for r in self.rules}) != len(self.rules):
            raise ValueError("같은 종목·규칙이 두 번 있음")
        return self


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> TradingConfig | None:
    # 없거나 읽을 수 없으면 아무것도 하지 않음 (fail-safe). 값은 로그에 남기지 않음 — 개인 예산
    try:
        raw = yaml.safe_load(path.read_text())
        config = TradingConfig.model_validate(raw)
    except FileNotFoundError:
        log.warning("자동매매 설정 없음: %s — 아무것도 하지 않음", path.name)
        return None
    except (yaml.YAMLError, ValidationError) as error:
        log.error("자동매매 설정을 읽을 수 없음 (%s) — 아무것도 하지 않음", type(error).__name__)
        return None
    if config.mode is Mode.LIVE:
        # 실거래 경로가 아직 없음. 생겨도 전환은 사람이 점검표(go-live-check)를 거친 뒤
        log.error("실거래 모드는 아직 없음 — dry-run 으로 실행")
        config = config.model_copy(update={"mode": Mode.DRY_RUN})
    return config
