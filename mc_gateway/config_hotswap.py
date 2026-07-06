import os

from mc_gateway.config import config, load_config
from mc_gateway.logging_setup import logger


def reload_hotswap_config(signum=None, frame=None) -> None:
    """
    SIGHUP Handler: reloads config fields that are marked for hotswapping.
    It reads them from the configured toml file. If the user is on the old env-var
    only setup without a toml file, we log a warning since we don't
    resort to bash sourcing hacks anymore.
    """
    toml_path = os.environ.get("CONFIG_FILE", "config.toml")
    if not os.path.exists(toml_path):
        logger.warning(
            f"Hot-reload requires a TOML config file ({toml_path}). Migrate your configuration "
            "to enable this feature (fallback to env-vars does not support hotswap)."
        )
        return

    try:
        new_config = load_config()
    except Exception as e:
        logger.error(f"Error parseando {toml_path} en SIGHUP: {e}")
        return

    # Update only the allowed hot-swappable fields
    config.IDLE_LIMIT_SECONDS = new_config.IDLE_LIMIT_SECONDS
    config.CRAFTY_IDLE_SECONDS = new_config.CRAFTY_IDLE_SECONDS
    config.CHECK_INTERVAL_SECONDS = new_config.CHECK_INTERVAL_SECONDS
    config.CRAFTY_LOG_LEVEL = new_config.CRAFTY_LOG_LEVEL

    logger.info(
        f"SIGHUP recibido: config hotswap recargada -> "
        f"IDLE_LIMIT={config.IDLE_LIMIT_SECONDS}s, CRAFTY_IDLE={config.CRAFTY_IDLE_SECONDS}s, "
        f"CHECK_INTERVAL={config.CHECK_INTERVAL_SECONDS}s, CRAFTY_LOG_LEVEL={config.CRAFTY_LOG_LEVEL}"
    )
