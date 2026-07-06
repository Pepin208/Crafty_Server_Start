import os
import time

from mc_gateway.crafty_client import is_crafty_up, stop_mc_server
from mc_gateway.crafty_process import crafty_process_manager
from mc_gateway.logging_setup import logger
from mc_gateway.mc_status import backend_reachable


def graceful_shutdown(signum, frame) -> None:
    logger.info("Ctrl+C detectado. Cerrando prolijamente...")
    try:
        if backend_reachable():
            logger.info("Apagando server de Minecraft...")
            try:
                stop_mc_server()
            except Exception as e:
                logger.warning(f"No se pudo apagar MC: {e}")
            waited = 0
            while backend_reachable() and waited < 60:
                time.sleep(2)
                waited += 2

        if is_crafty_up():
            logger.info("Apagando Crafty Controller...")
            try:
                crafty_process_manager.stop_crafty()
            except Exception as e:
                logger.warning(f"No se pudo apagar Crafty: {e}")
            waited = 0
            while is_crafty_up() and waited < 30:
                time.sleep(2)
                waited += 2
    except Exception as e:
        logger.info(f"Hubo un problema cerrando ({e}), pero se sigue con la salida.")

    logger.info("Todo ok. Cerrando.")
    os._exit(0)
