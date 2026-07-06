from typing import Any

from mc_gateway.config import config


def render_message(template: str, current_config: Any = config) -> str:
    """
    Renders MOTD and kick messages by injecting configuration variables.
    Supports {idle_min}, {crafty_idle_min}, and {startup_timeout_seg}.
    If an unknown variable is passed, it falls back to showing the raw template.
    """
    try:
        template_vars = {
            "idle_min": round(current_config.IDLE_LIMIT_SECONDS / 60, 1),
            "crafty_idle_min": round(current_config.CRAFTY_IDLE_SECONDS / 60, 1),
            "startup_timeout_seg": current_config.STARTUP_TIMEOUT_SECONDS,
        }
        return template.format(**template_vars)
    except (KeyError, IndexError):
        return template


def get_motd_dormido(current_config: Any = config) -> str:
    return render_message(current_config.MOTD_DORMIDO, current_config)


def get_motd_iniciando(current_config: Any = config) -> str:
    return render_message(current_config.MOTD_INICIANDO, current_config)


def get_kick_mensaje(current_config: Any = config) -> str:
    return render_message(current_config.KICK_MENSAJE, current_config)
