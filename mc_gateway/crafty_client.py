import urllib3
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from mc_gateway.config import config
from mc_gateway.logging_setup import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {"Authorization": f"Bearer {config.CRAFTY_TOKEN}"}


def is_crafty_up() -> bool:
    try:
        r = requests.get(
            f"{config.CRAFTY_URL}/api/v2/servers",
            headers=HEADERS,
            verify=False,
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def start_mc_server() -> bool:
    url = f"{config.CRAFTY_URL}/api/v2/servers/{config.SERVER_ID}/action/start_server"
    r = requests.post(url, headers=HEADERS, verify=False, timeout=10)
    logger.info(f"Start MC solicitado -> {r.status_code}")
    r.raise_for_status()
    return r.ok


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def stop_mc_server() -> bool:
    url = f"{config.CRAFTY_URL}/api/v2/servers/{config.SERVER_ID}/action/stop_server"
    r = requests.post(url, headers=HEADERS, verify=False, timeout=10)
    logger.info(f"Stop MC solicitado -> {r.status_code}")
    r.raise_for_status()
    return r.ok
