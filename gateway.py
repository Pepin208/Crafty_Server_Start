#!/usr/bin/env python3
"""
Gateway persistente para Minecraft con arranque/apagado on-demand.

Escucha SIEMPRE en MC_PUBLIC_PORT (el puerto que abrís en el router).

- Si el server real (Crafty + Java) está caído: dispara el arranque en
  background y responde a los clientes con un mensaje de "iniciando"
  (tanto en el ping de la lista de servidores como si intentan entrar).
- Si el server real ya está arriba: hace de proxy transparente hacia
  MC_INTERNAL_HOST:MC_INTERNAL_PORT, sin que el jugador note diferencia.

Además maneja los timers de apagado en cascada:
  - sin jugadores por IDLE_LIMIT_SECONDS -> apaga el server de Minecraft
  - sin nadie reconectando por otros CRAFTY_IDLE_SECONDS -> apaga Crafty
"""
import json
import logging
import os
import signal
import socket
import struct
import subprocess
import threading
import time

from logging.handlers import RotatingFileHandler

import requests
import urllib3
from mcstatus import JavaServer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- config FIJA: requiere reiniciar el gateway para tomar efecto ----------
# (credenciales, puertos, rutas de archivos de log ya abiertos, etc. - no es
# seguro/practico cambiarlos en caliente sin recrear sockets o handlers)
CRAFTY_URL = os.environ["CRAFTY_URL"]
CRAFTY_TOKEN = os.environ["CRAFTY_TOKEN"]
SERVER_ID = os.environ["SERVER_ID"]

MC_PUBLIC_PORT = int(os.environ["MC_PUBLIC_PORT"])
MC_HOST = os.environ["MC_INTERNAL_HOST"]
MC_PORT = int(os.environ["MC_INTERNAL_PORT"])

STARTUP_TIMEOUT = int(os.environ.get("STARTUP_TIMEOUT_SECONDS", 180))
CRAFTY_DIR = os.environ["CRAFTY_DIR"]

# ---------- helper: tamaños en KB/MB/GB además de bytes planos ----------
def parse_size(value, default_bytes):
    """Convierte cosas como '20 MB', '1024KB', '1 GB' o un número plano
    de bytes (ej: '10485760') a bytes. Acepta con o sin espacio, y es
    insensible a mayúsculas/minúsculas. Si no se puede parsear, usa el
    default."""
    if value is None:
        return default_bytes
    s = str(value).strip().upper()
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
    }
    # separa número de unidad, con o sin espacio: "20MB", "20 MB", "20"
    import re
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


# ---------- log: archivo con rotación (nunca crece sin límite) ----------
LOG_FILE = os.environ.get("LOG_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gateway.log"))
LOG_MAX_BYTES = parse_size(os.environ.get("LOG_MAX_BYTES"), 10 * 1024 * 1024)   # 10 MB por archivo por defecto
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 3))            # cuántos archivos viejos conservar
LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "1") == "1"              # además imprimir a stdout (útil con journalctl)

# ---------- log de Crafty (stdout/stderr del proceso Crafty): también con rotación ----------
CRAFTY_LOG_FILE = os.environ.get(
    "CRAFTY_LOG_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "crafty.log"),
)
CRAFTY_LOG_MAX_BYTES = parse_size(os.environ.get("CRAFTY_LOG_MAX_BYTES"), 20 * 1024 * 1024)  # 20 MB por defecto
CRAFTY_LOG_BACKUP_COUNT = int(os.environ.get("CRAFTY_LOG_BACKUP_COUNT", 3))

# =========================================================================
# ---------- CONFIG HOTSWAP: se recarga en caliente con SIGHUP ----------
# Estas son las ÚNICAS variables que el gateway puede releer sin reiniciar.
# Después de editar config.sh, mandale la señal al proceso:
#   kill -HUP $(cat /ruta/al/gateway.pid)      (o el PID que corresponda)
# y estos valores se actualizan solos en la próxima vuelta del loop.
#
# NO se agrega nada acá que ya esté "horneado" en un objeto creado al
# arrancar (rutas de log, tamaños/backups de rotación, puertos, credenciales
# de Crafty) - cambiar eso en caliente implicaría recrear handlers de
# logging o sockets ya abiertos, y no vale la complejidad. Ver comentario
# en reload_hotswap_config() más abajo.
# =========================================================================
CONFIG_FILE = os.environ.get(
    "CONFIG_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.sh")
)

IDLE_LIMIT = int(os.environ.get("IDLE_LIMIT_SECONDS", 600))            # [HOTSWAP]
CRAFTY_IDLE = int(os.environ.get("CRAFTY_IDLE_SECONDS", 300))          # [HOTSWAP]
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL_SECONDS", 20))     # [HOTSWAP]

CRAFTY_LOG_LEVEL = os.environ.get("CRAFTY_LOG_LEVEL", "INFO").strip().upper()  # [HOTSWAP]
if CRAFTY_LOG_LEVEL not in ("INFO", "WARNING"):
    CRAFTY_LOG_LEVEL = "INFO"


def _read_config_var(name):
    """Lee UNA sola variable de config.sh haciendo `source` en un sub-shell
    de bash aparte, sin tocar el entorno del proceso Python actual. Usado
    solo para la recarga en caliente vía SIGHUP."""
    try:
        result = subprocess.run(
            ["bash", "-c", f'source "{CONFIG_FILE}" >/dev/null 2>&1 && printf "%s" "${name}"'],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout if result.returncode == 0 and result.stdout else None
    except Exception:
        return None


def reload_hotswap_config(signum=None, frame=None):
    """Handler de SIGHUP: relee config.sh del disco y actualiza SOLO las
    variables marcadas [HOTSWAP] arriba. Todo lo demás (credenciales,
    puertos, rutas y tamaños de log) sigue necesitando reiniciar el
    gateway (Ctrl+C + ./start.sh) para tomar efecto."""
    global IDLE_LIMIT, CRAFTY_IDLE, CHECK_INTERVAL, CRAFTY_LOG_LEVEL

    raw_idle = _read_config_var("IDLE_LIMIT_SECONDS")
    raw_crafty_idle = _read_config_var("CRAFTY_IDLE_SECONDS")
    raw_check = _read_config_var("CHECK_INTERVAL_SECONDS")
    raw_level = _read_config_var("CRAFTY_LOG_LEVEL")

    if raw_idle is not None:
        try:
            IDLE_LIMIT = int(raw_idle)
        except ValueError:
            pass
    if raw_crafty_idle is not None:
        try:
            CRAFTY_IDLE = int(raw_crafty_idle)
        except ValueError:
            pass
    if raw_check is not None:
        try:
            CHECK_INTERVAL = int(raw_check)
        except ValueError:
            pass
    if raw_level is not None and raw_level.strip().upper() in ("INFO", "WARNING"):
        CRAFTY_LOG_LEVEL = raw_level.strip().upper()

    log(
        f"SIGHUP recibido: config hotswap recargada -> "
        f"IDLE_LIMIT={IDLE_LIMIT}s, CRAFTY_IDLE={CRAFTY_IDLE}s, "
        f"CHECK_INTERVAL={CHECK_INTERVAL}s, CRAFTY_LOG_LEVEL={CRAFTY_LOG_LEVEL}"
    )


signal.signal(signal.SIGHUP, reload_hotswap_config)

_logger = logging.getLogger("gateway")
_logger.setLevel(logging.INFO)

_file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
_logger.addHandler(_file_handler)

if LOG_TO_STDOUT:
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(_stream_handler)

# ---------- mensajes: plantillas dinámicas ----------
# Podés usar {idle_min} y {crafty_idle_min} dentro de los mensajes en config.sh:
# se reemplazan solos por los minutos calculados desde IDLE_LIMIT_SECONDS y
# CRAFTY_IDLE_SECONDS. Así, si cambiás los tiempos, el mensaje se actualiza
# solo, sin que tengas que retocar el texto a mano.
_TEMPLATE_VARS = {
    "idle_min": round(IDLE_LIMIT / 60, 1),
    "crafty_idle_min": round(CRAFTY_IDLE / 60, 1),
    "startup_timeout_seg": STARTUP_TIMEOUT,
}


def _render(template):
    try:
        return template.format(**_TEMPLATE_VARS)
    except (KeyError, IndexError):
        # si el usuario tipeó una llave que no existe, mostramos el texto
        # crudo en vez de romper el gateway
        return template


MOTD_DORMIDO = _render(os.environ.get("MOTD_DORMIDO", "Server dormido. Conectate para despertarlo."))
MOTD_INICIANDO = _render(os.environ.get("MOTD_INICIANDO", "El server se está iniciando, esperá un momento..."))
KICK_MENSAJE = _render(os.environ.get("KICK_MENSAJE", "El server se está iniciando. Reintentá en unos segundos."))

HEADERS = {"Authorization": f"Bearer {CRAFTY_TOKEN}"}


def log(msg):
    _logger.info(msg)


# ---------- supresión de spam de log por IP repetida ----------
# Si una misma IP golpea la puerta muchas veces seguidas (bots de escaneo,
# IPs baneadas que igual llegan al gateway, etc.), no queremos una línea
# de log por cada intento -> eso fue lo que hizo explotar el log a 27GB.
# En vez de loguear cada conexión, agrupamos por IP en ventanas de
# LOG_SUPPRESS_WINDOW segundos y mostramos un resumen.
LOG_SUPPRESS_WINDOW = int(os.environ.get("LOG_SUPPRESS_WINDOW_SECONDS", 60))

_conn_lock = threading.Lock()
_conn_tracker = {}  # ip -> {"first_seen": ts, "count": n, "logged_first": bool}


def log_connection_attempt(addr, extra_msg=""):
    """Loguea intentos de conexión con supresión de repetidos por IP."""
    ip = addr[0]
    now = time.time()
    with _conn_lock:
        entry = _conn_tracker.get(ip)
        if entry is None or (now - entry["window_start"]) > LOG_SUPPRESS_WINDOW:
            # primera vez que la vemos, o ya pasó la ventana: reseteamos y logueamos
            if entry is not None and entry["count"] > 1:
                log(f"IP {ip}: {entry['count']} intentos en los últimos "
                    f"{LOG_SUPPRESS_WINDOW}s (resumen antes de resetear).")
            _conn_tracker[ip] = {"window_start": now, "count": 1}
            log(f"Conexión de {addr}. {extra_msg}".strip())
        else:
            entry["count"] += 1
            # no logueamos cada una; solo la primera de la ventana


# ---------- estado compartido ----------
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.waking = False          # ya se disparó el arranque, evita duplicar
        self.mc_up = False
        self.crafty_pid = None
        self.monitor_thread = None


state = State()


# ---------- helpers Crafty API ----------
def is_crafty_up():
    try:
        r = requests.get(f"{CRAFTY_URL}/api/v2/servers", headers=HEADERS,
                          verify=False, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


_crafty_log_handler = RotatingFileHandler(
    CRAFTY_LOG_FILE, maxBytes=CRAFTY_LOG_MAX_BYTES, backupCount=CRAFTY_LOG_BACKUP_COUNT
)
_crafty_log_handler.setFormatter(logging.Formatter("%(message)s"))
_crafty_logger = logging.getLogger("crafty_proc")
_crafty_logger.setLevel(logging.INFO)
_crafty_logger.propagate = False
_crafty_logger.addHandler(_crafty_log_handler)


# Solo nos interesan las líneas con el formato real de log de Crafty:
#   [+] Crafty: 06/07/26 17:41:58 - INFO:	mensaje
# Todo lo demás (banner ASCII, aviso de "nueva versión disponible", líneas
# en blanco, el prompt "Crafty Controller v4.10.4 > ", etc.) se descarta.
import re as _re
_CRAFTY_LINE_RE = _re.compile(r"\[\+\]\s*Crafty:\s*\d{2}/\d{2}/\d{2}\s*-?\s*\d{2}:\d{2}:\d{2}\s*-\s*(\w+):")

# Niveles de Crafty que se consideran "warning o peor" cuando
# CRAFTY_LOG_LEVEL="WARNING" (se descartan los INFO)
_WARNING_OR_WORSE = {"WARNING", "WARN", "ERROR", "CRITICAL", "FATAL"}


def _pump_crafty_output(pipe):
    """Lee la salida del proceso Crafty linea a linea, descarta el ruido
    (banner, ASCII art, avisos de version, etc.) y solo escribe las lineas
    de log reales de Crafty a traves de un RotatingFileHandler, para que
    crafty.log nunca crezca sin limite (antes se abria con open(..., "ab")
    y podia llegar a varios GB). Si CRAFTY_LOG_LEVEL="WARNING", ademas
    descarta las lineas de nivel INFO y solo deja warnings/errores."""
    try:
        for raw_line in iter(pipe.readline, b""):
            try:
                line = raw_line.decode(errors="replace").rstrip("\n")
            except Exception:
                line = str(raw_line)
            stripped = line.strip()
            if not stripped:
                continue
            # a veces el prompt "Crafty Controller v4.10.4 > " viene pegado
            # antes de la línea real en la misma línea de output
            idx = stripped.find("[+] Crafty:")
            if idx != -1:
                stripped = stripped[idx:]
            match = _CRAFTY_LINE_RE.match(stripped)
            if not match:
                continue
            if CRAFTY_LOG_LEVEL == "WARNING" and match.group(1).upper() not in _WARNING_OR_WORSE:
                continue
            _crafty_logger.info(stripped)
    finally:
        pipe.close()


def start_crafty():
    log("Levantando Crafty Controller...")
    proc = subprocess.Popen(
        ["bash", "-c", "source venv/bin/activate && exec python3 main.py"],
        cwd=CRAFTY_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    threading.Thread(target=_pump_crafty_output, args=(proc.stdout,), daemon=True).start()
    state.crafty_pid = proc.pid
    for _ in range(30):
        if is_crafty_up():
            log("Crafty está up.")
            return True
        time.sleep(2)
    log("ERROR: Crafty no levantó a tiempo.")
    return False


def stop_crafty():
    if state.crafty_pid:
        log(f"Apagando Crafty (pid {state.crafty_pid})...")
        try:
            os.kill(state.crafty_pid, 15)
        except ProcessLookupError:
            pass
        state.crafty_pid = None
    else:
        # lo encontramos aunque no lo hayamos levantado nosotros
        subprocess.run(["pkill", "-f", f"{CRAFTY_DIR}/main.py"])


def start_mc_server():
    url = f"{CRAFTY_URL}/api/v2/servers/{SERVER_ID}/action/start_server"
    r = requests.post(url, headers=HEADERS, verify=False, timeout=10)
    log(f"Start MC solicitado -> {r.status_code}")
    return r.ok


def stop_mc_server():
    url = f"{CRAFTY_URL}/api/v2/servers/{SERVER_ID}/action/stop_server"
    r = requests.post(url, headers=HEADERS, verify=False, timeout=10)
    log(f"Stop MC solicitado -> {r.status_code}")
    return r.ok


def backend_reachable():
    try:
        s = socket.create_connection((MC_HOST, MC_PORT), timeout=1)
        s.close()
        return True
    except Exception:
        return False


def get_player_count():
    server = JavaServer.lookup(f"{MC_HOST}:{MC_PORT}")
    return server.status().players.online


# ---------- secuencia de arranque + monitor ----------
def wake_and_monitor():
    with state.lock:
        if state.waking:
            return
        state.waking = True

    try:
        if not is_crafty_up():
            if not start_crafty():
                return
        else:
            log("Crafty ya estaba corriendo.")

        if not backend_reachable():
            start_mc_server()

        log("Esperando a que el server de Minecraft responda...")
        waited = 0
        while waited < STARTUP_TIMEOUT:
            if backend_reachable():
                try:
                    get_player_count()
                    break
                except Exception:
                    pass
            time.sleep(3)
            waited += 3
        else:
            log("Timeout esperando el server. Abortando.")
            return

        log("Server de Minecraft arriba. A partir de ahora, proxy transparente.")
        state.mc_up = True

        # --- monitor de inactividad ---
        idle_time = 0
        while True:
            time.sleep(CHECK_INTERVAL)
            try:
                players = get_player_count()
            except Exception:
                log("El server dejó de responder, asumiendo que se cayó.")
                break

            if players == 0:
                idle_time += CHECK_INTERVAL
                log(f"Jugadores online: 0. Inactivo hace {idle_time}s / {IDLE_LIMIT}s.")
            else:
                idle_time = 0
                log(f"Jugadores online: {players}.")

            if idle_time >= IDLE_LIMIT:
                log("10 min sin jugadores. Apagando server de Minecraft.")
                stop_mc_server()
                break

        state.mc_up = False

        # --- ventana de gracia antes de apagar Crafty ---
        log(f"Esperando {CRAFTY_IDLE}s más por si alguien reconecta antes de apagar Crafty...")
        waited = 0
        while waited < CRAFTY_IDLE:
            time.sleep(CHECK_INTERVAL)
            waited += CHECK_INTERVAL
            with state.lock:
                if state.waking is False:
                    # alguien disparó una nueva wake sequence mientras esperábamos
                    return

        stop_crafty()
        log("Ciclo completo. Volviendo a esperar conexiones.")

    finally:
        with state.lock:
            state.waking = False


def trigger_wake():
    with state.lock:
        already = state.waking
    if not already:
        threading.Thread(target=wake_and_monitor, daemon=True).start()


# ---------- protocolo mínimo de Minecraft ----------
def read_varint(sock):
    value = 0
    position = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise ConnectionError("socket cerrado")
        byte = b[0]
        value |= (byte & 0x7F) << position
        if not (byte & 0x80):
            break
        position += 7
    return value


def write_varint(value):
    out = b""
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out += bytes([byte | 0x80])
        else:
            out += bytes([byte])
            break
    return out


def read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket cerrado")
        data += chunk
    return data


def read_string(sock):
    length = read_varint(sock)
    return read_exact(sock, length).decode("utf-8")


def pack_string(s):
    b = s.encode("utf-8")
    return write_varint(len(b)) + b


def send_packet(sock, packet_id, data):
    body = write_varint(packet_id) + data
    sock.sendall(write_varint(len(body)) + body)


def handle_status(sock):
    texto = MOTD_INICIANDO if state.waking else MOTD_DORMIDO
    motd = {
        "version": {"name": "Iniciando...", "protocol": 0},
        "players": {"max": 0, "online": 0},
        "description": {"text": texto},
    }
    read_varint(sock)  # largo del status request (vacío, packet id 0x00)
    send_packet(sock, 0x00, pack_string(json.dumps(motd)))
    # responder ping si llega
    try:
        length = read_varint(sock)
        pid = read_varint(sock)
        payload = read_exact(sock, 8)
        if pid == 0x01:
            send_packet(sock, 0x01, payload)
    except Exception:
        pass


def handle_login_kick(sock):
    msg = {"text": KICK_MENSAJE}
    send_packet(sock, 0x00, pack_string(json.dumps(msg)))


def relay(a, b):
    try:
        while True:
            data = a.recv(4096)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    finally:
        try:
            a.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            b.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass


def proxy_connection(client_sock, initial_bytes):
    try:
        backend = socket.create_connection((MC_HOST, MC_PORT), timeout=5)
    except Exception:
        client_sock.close()
        return
    backend.sendall(initial_bytes)
    t1 = threading.Thread(target=relay, args=(client_sock, backend), daemon=True)
    t2 = threading.Thread(target=relay, args=(backend, client_sock), daemon=True)
    t1.start()
    t2.start()


class RecordingSocket:
    """Envuelve un socket para poder reconstruir los bytes ya leídos del handshake."""
    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""

    def recv(self, n):
        data = self.sock.recv(n)
        self.buffer += data
        return data

    def sendall(self, data):
        self.sock.sendall(data)


def handle_client(raw_sock, addr):
    raw_sock.settimeout(10)
    rsock = RecordingSocket(raw_sock)
    try:
        if state.mc_up and backend_reachable():
            # server real arriba: leemos solo lo necesario para el handshake
            # y lo reenviamos íntegro al backend, luego proxy transparente
            length = read_varint(rsock)
            packet_id = read_varint(rsock)
            proto = read_varint(rsock)
            addr_str = read_string(rsock)
            port = read_exact(rsock, 2)
            next_state = read_varint(rsock)
            initial = rsock.buffer
            log_connection_attempt(addr, "-> proxy directo al backend.")
            proxy_connection(raw_sock, initial)
            return

        # server real no disponible: disparamos wake y respondemos "iniciando"
        length = read_varint(rsock)
        packet_id = read_varint(rsock)
        proto = read_varint(rsock)
        addr_str = read_string(rsock)
        port = read_exact(rsock, 2)
        next_state = read_varint(rsock)

        log_connection_attempt(addr, f"next_state={next_state}.")

        if next_state == 1:
            # solo ping de la lista de servidores: mostramos estado, NO despertamos
            handle_status(rsock)
        elif next_state == 2:
            # intento real de conectar: acá sí disparamos el arranque
            log("Intento de login detectado. Disparando wake si hace falta.")
            trigger_wake()
            handle_login_kick(rsock)
        raw_sock.close()
    except Exception as e:
        try:
            raw_sock.close()
        except Exception:
            pass


def graceful_shutdown(signum, frame):
    log("Ctrl+C detectado. Cerrando prolijamente...")
    try:
        if backend_reachable():
            log("Apagando server de Minecraft...")
            stop_mc_server()
            # esperamos a que realmente se apague antes de tocar Crafty
            waited = 0
            while backend_reachable() and waited < 60:
                time.sleep(2)
                waited += 2
        if is_crafty_up():
            log("Apagando Crafty Controller...")
            stop_crafty()
            waited = 0
            while is_crafty_up() and waited < 30:
                time.sleep(2)
                waited += 2
    except Exception as e:
        log(f"Hubo un problema cerrando ({e}), pero se sigue con la salida.")
    log("Todo ok. Cerrando.")
    os._exit(0)


def main():
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    log(f"Gateway escuchando en 0.0.0.0:{MC_PUBLIC_PORT} (backend real en {MC_HOST}:{MC_PORT})")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", MC_PUBLIC_PORT))
    srv.listen(20)

    while True:
        client_sock, addr = srv.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()


if __name__ == "__main__":
    main()
