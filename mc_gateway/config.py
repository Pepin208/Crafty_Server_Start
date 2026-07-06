import os
import re
from typing import Literal

from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_size(value: str | int | None, default_bytes: int) -> int:
    """Parses sizes like '20 MB', '1024KB', '1 GB' or flat bytes."""
    if value is None:
        return default_bytes
    if isinstance(value, int):
        return value
    s = str(value).strip().upper()
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
    }
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([A-Z]*)$", s)
    if not m:
        return default_bytes
    number_str, unit = m.groups()
    unit = unit or "B"
    if unit not in units:
        return default_bytes
    try:
        return int(float(number_str) * units[unit])
    except ValueError:
        return default_bytes


class Config(BaseSettings):
    # Crafty connection
    CRAFTY_URL: str
    CRAFTY_TOKEN: str
    SERVER_ID: str
    CRAFTY_DIR: str

    # Ports
    MC_PUBLIC_PORT: int
    MC_INTERNAL_HOST: str = "127.0.0.1"
    MC_INTERNAL_PORT: int = 25565

    # Timers
    IDLE_LIMIT_SECONDS: int = 600
    CRAFTY_IDLE_SECONDS: int = 300
    CHECK_INTERVAL_SECONDS: int = 20
    STARTUP_TIMEOUT_SECONDS: int = 180

    # Messages
    MOTD_DORMIDO: str = "Server dormido. Conectate para despertarlo."
    MOTD_INICIANDO: str = "El server se está iniciando, esperá un momento..."
    KICK_MENSAJE: str = "El server se está iniciando. Reintentá en unos segundos."

    # Logging
    LOG_FILE: str = "gateway.log"
    LOG_MAX_BYTES: int | str = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 3
    LOG_TO_STDOUT: bool = True
    LOG_SUPPRESS_WINDOW_SECONDS: int = 60
    LOG_FORMAT: Literal["text", "json"] = "text"

    # Crafty Logging
    CRAFTY_LOG_FILE: str = "crafty.log"
    CRAFTY_LOG_MAX_BYTES: int | str = 20 * 1024 * 1024
    CRAFTY_LOG_BACKUP_COUNT: int = 3
    CRAFTY_LOG_LEVEL: Literal["INFO", "WARNING"] = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # We also read from TOML, but env vars have higher precedence natively in pydantic-settings
        toml_file=os.environ.get("CONFIG_FILE", "config.toml"),
    )

    @field_validator("CRAFTY_DIR", "LOG_FILE", "CRAFTY_LOG_FILE", mode="before")
    @classmethod
    def expand_paths(cls, v: str) -> str:
        if v:
            return os.path.expandvars(os.path.expanduser(str(v)))
        return v

    @field_validator("LOG_MAX_BYTES", "CRAFTY_LOG_MAX_BYTES", mode="before")
    @classmethod
    def parse_size_strings(cls, v: str | int | None, info: ValidationInfo) -> int:
        if info.field_name == "LOG_MAX_BYTES":
            return parse_size(v, 10 * 1024 * 1024)
        if info.field_name == "CRAFTY_LOG_MAX_BYTES":
            return parse_size(v, 20 * 1024 * 1024)
        return parse_size(v, 0)

    @field_validator("CRAFTY_LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip().upper()
            if v not in ("INFO", "WARNING"):
                return "INFO"
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        try:
            from pydantic_settings import TomlConfigSettingsSource

            toml_settings = TomlConfigSettingsSource(settings_cls)
        except ImportError:
            toml_settings = None

        sources = [
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ]
        if toml_settings:
            # We insert TOML before file_secret but after env vars so env vars override TOML
            sources.insert(3, toml_settings)

        return tuple(sources)


def load_config() -> Config:
    """Loads configuration, respecting precedence: Init -> Env Vars -> TOML."""
    config = Config(**{})

    # Check which config fields came from env vars
    overridden_keys = [key for key in Config.model_fields.keys() if key in os.environ]

    toml_path = os.environ.get("CONFIG_FILE", "config.toml")

    # We will log after setting up the logger to avoid circular imports.
    # We can store the info needed on the config object for now, or just import logger here.
    # Wait, if we import logger here locally inside load_config, it's called at module level.
    # So it still causes a circular import if logging_setup imports config.
    # Let's import it locally inside the function and handle it gracefully.
    try:
        from mc_gateway.logging_setup import logger
        if os.path.exists(toml_path):
            logger.info(f"Config loaded: source=toml file={toml_path} (env var overrides applied: {overridden_keys})")
        else:
            logger.info(f"Config loaded: source=env (env vars applied: {overridden_keys})")
    except ImportError:
        pass

    # Warn if TOML file is world-readable
    if os.path.exists(toml_path):
        import stat
        st = os.stat(toml_path)
        if bool(st.st_mode & stat.S_IROTH):
            try:
                from mc_gateway.logging_setup import logger
                logger.warning(
                    f"WARNING: {toml_path} is world-readable and contains a secret token. "
                    f"Run: chmod 600 {toml_path}"
                )
            except ImportError:
                print(f"WARNING: {toml_path} is world-readable and contains a secret token. "
                      f"Run: chmod 600 {toml_path}")

    # Validate that CRAFTY_DIR looks valid
    crafty_main = os.path.join(config.CRAFTY_DIR, "main.py")
    crafty_venv = os.path.join(config.CRAFTY_DIR, "venv")
    if not (os.path.exists(crafty_main) and os.path.isdir(crafty_venv)):
        print(f"ERROR: CRAFTY_DIR '{config.CRAFTY_DIR}' does not appear to be a valid Crafty 4 installation "
              "(missing main.py or venv/). Please check your configuration.")
        import sys
        sys.exit(1)

    return config

# Global config singleton
config = load_config()
