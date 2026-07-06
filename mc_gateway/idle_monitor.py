import threading
import time

from mc_gateway.config import config
from mc_gateway.crafty_client import is_crafty_up, start_mc_server, stop_mc_server
from mc_gateway.crafty_process import crafty_process_manager
from mc_gateway.logging_setup import logger
from mc_gateway.mc_status import backend_reachable, get_player_count


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.waking = False
        self.mc_up = False


state = State()

# Dependency Injection for time.sleep to facilitate testing
def _default_sleep(seconds: float) -> None:
    time.sleep(seconds)

def wake_and_monitor(sleep_func=_default_sleep) -> None:
    with state.lock:
        if state.waking:
            return
        state.waking = True

    try:
        if not is_crafty_up():
            if not crafty_process_manager.start_crafty():
                return
        else:
            logger.info("Crafty ya estaba corriendo.")

        if not backend_reachable():
            start_mc_server()

        logger.info("Esperando a que el server de Minecraft responda...")
        waited = 0
        while waited < config.STARTUP_TIMEOUT_SECONDS:
            if backend_reachable():
                try:
                    get_player_count()
                    break
                except Exception:
                    pass
            sleep_func(3)
            waited += 3
        else:
            logger.info("Timeout esperando el server. Abortando.")
            return

        logger.info("Server de Minecraft arriba. A partir de ahora, proxy transparente.")
        state.mc_up = True

        idle_time = 0
        while True:
            sleep_func(config.CHECK_INTERVAL_SECONDS)
            try:
                players = get_player_count()
            except Exception:
                logger.info("El server dejó de responder, asumiendo que se cayó.")
                break

            if players == 0:
                idle_time += config.CHECK_INTERVAL_SECONDS
                logger.info(f"Jugadores online: 0. Inactivo hace {idle_time}s / {config.IDLE_LIMIT_SECONDS}s.")
            else:
                idle_time = 0
                logger.info(f"Jugadores online: {players}.")

            if idle_time >= config.IDLE_LIMIT_SECONDS:
                logger.info("Server inactivo. Apagando server de Minecraft.")
                stop_mc_server()
                break

        state.mc_up = False

        logger.info(f"Esperando {config.CRAFTY_IDLE_SECONDS}s más por si alguien reconecta antes de apagar Crafty...")
        waited = 0
        while waited < config.CRAFTY_IDLE_SECONDS:
            sleep_func(config.CHECK_INTERVAL_SECONDS)
            waited += config.CHECK_INTERVAL_SECONDS
            with state.lock:
                if state.waking is False:
                    # someone else started a new wake sequence
                    return

        crafty_process_manager.stop_crafty()
        logger.info("Ciclo completo. Volviendo a esperar conexiones.")

    finally:
        with state.lock:
            state.waking = False


def trigger_wake(sleep_func=_default_sleep) -> None:
    with state.lock:
        already = state.waking
    if not already:
        threading.Thread(target=wake_and_monitor, args=(sleep_func,), daemon=True).start()
