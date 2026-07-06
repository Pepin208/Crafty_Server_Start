
from mc_gateway.proxy import read_varint, write_varint, pack_string, RecordingSocket

class MockSocket:
    def __init__(self, data=b""):
        self.data = data
        self.sent = b""
        self.index = 0

    def recv(self, n):
        if self.index >= len(self.data):
            return b""
        chunk = self.data[self.index : self.index + n]
        self.index += n
        return chunk

    def sendall(self, data):
        self.sent += data


def test_varint():
    # Write and read back a small number
    encoded = write_varint(255)
    sock = MockSocket(encoded)
    assert read_varint(sock) == 255

    # Write and read back a larger number
    encoded2 = write_varint(25565)
    sock2 = MockSocket(encoded2)
    assert read_varint(sock2) == 25565


def test_pack_string():
    encoded = pack_string("localhost")
    # length of "localhost" is 9. Varint for 9 is \x09.
    assert encoded == b"\x09localhost"


def test_recording_socket():
    raw_socket = MockSocket(b"\x01\x02\x03")
    rec_socket = RecordingSocket(raw_socket)

    data = rec_socket.recv(2)
    assert data == b"\x01\x02"
    assert rec_socket.buffer == b"\x01\x02"
