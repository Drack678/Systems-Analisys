from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ORS_API_KEY: str = ""
    OPENWEATHER_API_KEY: str = ""
    ENVIRONMENT: str = "development"

    # ACO tuning (W1/W4 calibration)
    ACO_N_ANTS: int = 50
    ACO_MAX_ITERATIONS: int = 100
    ACO_ALPHA: float = 1.0
    ACO_BETA: float = 2.0
    ACO_RHO: float = 0.1
    ACO_RAIN_MULTIPLIER: float = 1.63
    ACO_RAIN_THRESHOLD_MMH: float = 2.0

    RAIN_ALERT_THRESHOLD_MMH: float = 2.0
    RAIN_LEAD_TIME_MINUTES: int = 10
    CONGESTION_THRESHOLD: float = 0.75

    GTFS_PATH: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Ruta GTFS por defecto
if not settings.GTFS_PATH:
    from pathlib import Path
    settings.GTFS_PATH = str(Path(__file__).resolve().parents[2] / "data" / "gtfs")