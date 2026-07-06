import json
import socket
import threading
from typing import Any

from mc_gateway.config import config
from mc_gateway.messages import get_kick_mensaje, get_motd_dormido, get_motd_iniciando


def read_varint(sock: Any) -> int:
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
    return int(value)


def write_varint(value: int) -> bytes:
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


def read_exact(sock: Any, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket cerrado")
        data += chunk
    return data


def read_string(sock: Any) -> str:
    length = read_varint(sock)
    return read_exact(sock, length).decode("utf-8")


def pack_string(s: str) -> bytes:
    b = s.encode("utf-8")
    return write_varint(len(b)) + b


def send_packet(sock: Any, packet_id: int, data: bytes) -> None:
    body = write_varint(packet_id) + data
    sock.sendall(write_varint(len(body)) + body)


def handle_status(sock: Any, is_waking: bool) -> None:
    texto = get_motd_iniciando() if is_waking else get_motd_dormido()
    motd = {
        "version": {"name": "Iniciando...", "protocol": 0},
        "players": {"max": 0, "online": 0},
        "description": {"text": texto},
    }
    read_varint(sock)  # largo del status request
    send_packet(sock, 0x00, pack_string(json.dumps(motd)))
    try:
        read_varint(sock)  # length
        pid = read_varint(sock)
        payload = read_exact(sock, 8)
        if pid == 0x01:
            send_packet(sock, 0x01, payload)
    except Exception:
        pass


def handle_login_kick(sock: Any) -> None:
    msg = {"text": get_kick_mensaje()}
    send_packet(sock, 0x00, pack_string(json.dumps(msg)))


def relay(a: socket.socket, b: socket.socket) -> None:
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


def proxy_connection(client_sock: socket.socket, initial_bytes: bytes) -> None:
    try:
        backend = socket.create_connection((config.MC_INTERNAL_HOST, config.MC_INTERNAL_PORT), timeout=5)
    except Exception:
        client_sock.close()
        return
    backend.sendall(initial_bytes)
    t1 = threading.Thread(target=relay, args=(client_sock, backend), daemon=True)
    t2 = threading.Thread(target=relay, args=(backend, client_sock), daemon=True)
    t1.start()
    t2.start()


class RecordingSocket:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buffer = b""

    def recv(self, n: int) -> bytes:
        data = self.sock.recv(n)
        self.buffer += data
        return data

    def sendall(self, data: bytes) -> None:
        self.sock.sendall(data)
