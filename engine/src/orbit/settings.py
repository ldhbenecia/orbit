from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # SecretStr 은 출력·로그에 ********** 로만 보임 — 키 값이 새지 않게
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    toss_client_id: SecretStr | None = None
    toss_client_secret: SecretStr | None = None
