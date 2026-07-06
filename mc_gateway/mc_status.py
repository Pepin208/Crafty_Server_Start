import socket

from mcstatus import JavaServer

from mc_gateway.config import config


def backend_reachable() -> bool:
    try:
        s = socket.create_connection((config.MC_INTERNAL_HOST, config.MC_INTERNAL_PORT), timeout=1)
        s.close()
        return True
    except Exception:
        return False


def get_player_count() -> int:
    server = JavaServer.lookup(f"{config.MC_INTERNAL_HOST}:{config.MC_INTERNAL_PORT}")
    return server.status().players.online
