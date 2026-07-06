import signal
import socket
import threading
import time
from typing import Any

from mc_gateway.config import config
from mc_gateway.config_hotswap import reload_hotswap_config
from mc_gateway.idle_monitor import state, trigger_wake
from mc_gateway.logging_setup import logger
from mc_gateway.mc_status import backend_reachable
from mc_gateway.proxy import (
    RecordingSocket,
    handle_login_kick,
    handle_status,
    proxy_connection,
    read_exact,
    read_string,
    read_varint,
)
from mc_gateway.shutdown import graceful_shutdown

_conn_lock = threading.Lock()
_conn_tracker: dict[str, dict[str, Any]] = {}


def log_connection_attempt(addr, extra_msg=""):
    """Logs connection attempts with ip-based suppression based on config window."""
    ip = addr[0]
    now = time.time()
    with _conn_lock:
        entry = _conn_tracker.get(ip)
        if entry is None or (now - entry["window_start"]) > config.LOG_SUPPRESS_WINDOW_SECONDS:
            if entry is not None and entry["count"] > 1:
                logger.info(
                    f"IP {ip}: {entry['count']} intentos en los últimos "
                    f"{config.LOG_SUPPRESS_WINDOW_SECONDS}s (resumen antes de resetear)."
                )
            _conn_tracker[ip] = {"window_start": now, "count": 1}
            logger.info(f"Conexión de {addr}. {extra_msg}".strip())
        else:
            entry["count"] += 1


def handle_client(raw_sock, addr):
    raw_sock.settimeout(10)
    rsock = RecordingSocket(raw_sock)
    try:
        if state.mc_up and backend_reachable():
            # Real server up: Read handshake and proxy to backend
            _length = read_varint(rsock)
            _packet_id = read_varint(rsock)
            _proto = read_varint(rsock)
            _addr_str = read_string(rsock)
            _port = read_exact(rsock, 2)
            _next_state = read_varint(rsock)
            initial = rsock.buffer
            log_connection_attempt(addr, "-> proxy directo al backend.")
            proxy_connection(raw_sock, initial)
            return

        # Server down: Wake logic and response
        _length = read_varint(rsock)
        _packet_id = read_varint(rsock)
        _proto = read_varint(rsock)
        _addr_str = read_string(rsock)
        _port = read_exact(rsock, 2)
        next_state = read_varint(rsock)

        log_connection_attempt(addr, f"next_state={next_state}.")

        if next_state == 1:
            # Server list ping (status)
            handle_status(rsock, is_waking=state.waking)
        elif next_state == 2:
            # Actual login attempt
            logger.info("Intento de login detectado. Disparando wake si hace falta.")
            trigger_wake()
            handle_login_kick(rsock)
        raw_sock.close()
    except Exception:
        try:
            raw_sock.close()
        except Exception:
            pass


def main():
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGHUP, reload_hotswap_config)

    logger.info(f"Gateway escuchando en 0.0.0.0:{config.MC_PUBLIC_PORT} (backend real en {config.MC_INTERNAL_HOST}:{config.MC_INTERNAL_PORT})")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", config.MC_PUBLIC_PORT))
    srv.listen(20)

    while True:
        try:
            client_sock, addr = srv.accept()
            threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()
        except KeyboardInterrupt:
            graceful_shutdown(None, None)
        except Exception as e:
            logger.error(f"Error aceptando conexion: {e}")

if __name__ == "__main__":
    main()
