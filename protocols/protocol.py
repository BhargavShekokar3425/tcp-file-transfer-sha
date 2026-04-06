import json
import socket
import struct
from dataclasses import dataclass


HEADER_ENCODING = "utf-8"
HEADER_TERMINATOR = b"\n"
EOF_MARKER = b"EOF"
FRAME_SIZE_STRUCT = struct.Struct("!I")
SEQ_STRUCT = struct.Struct("!I")


@dataclass(slots=True)
class Metadata:
    filename: str
    filesize: int
    sha256: str
    chunk_size: int
    total_chunks: int
    mode: str

    def encode(self) -> bytes:
        payload = {
            "filename": self.filename,
            "filesize": self.filesize,
            "sha256": self.sha256,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "mode": self.mode,
        }
        return json.dumps(payload).encode(HEADER_ENCODING) + HEADER_TERMINATOR

    @classmethod
    def decode(cls, raw: bytes) -> "Metadata":
        payload = json.loads(raw.decode(HEADER_ENCODING))
        return cls(**payload)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            raise ConnectionError("Socket closed before expected bytes were received.")
        data.extend(packet)
    return bytes(data)


def recv_metadata(sock: socket.socket) -> Metadata:
    buffer = bytearray()
    while True:
        byte = sock.recv(1)
        if not byte:
            raise ConnectionError("Socket closed while waiting for metadata.")
        if byte == HEADER_TERMINATOR:
            return Metadata.decode(bytes(buffer))
        buffer.extend(byte)


def send_metadata(sock: socket.socket, metadata: Metadata) -> None:
    sock.sendall(metadata.encode())


def pack_chunk(seq_no: int, data: bytes) -> bytes:
    payload = SEQ_STRUCT.pack(seq_no) + data
    return FRAME_SIZE_STRUCT.pack(len(payload)) + payload


def send_chunk(sock: socket.socket, seq_no: int, data: bytes) -> None:
    sock.sendall(pack_chunk(seq_no, data))


def recv_chunk(sock: socket.socket) -> tuple[int, bytes] | None:
    marker = sock.recv(len(EOF_MARKER), socket.MSG_PEEK)
    if marker == EOF_MARKER:
        return None
    prefix = recv_exact(sock, FRAME_SIZE_STRUCT.size)
    frame_size = FRAME_SIZE_STRUCT.unpack(prefix)[0]
    payload = recv_exact(sock, frame_size)
    seq_no = SEQ_STRUCT.unpack(payload[: SEQ_STRUCT.size])[0]
    return seq_no, payload[SEQ_STRUCT.size :]


def send_eof(sock: socket.socket) -> None:
    sock.sendall(EOF_MARKER)


def recv_eof(sock: socket.socket) -> bool:
    marker = recv_exact(sock, len(EOF_MARKER))
    return marker == EOF_MARKER
