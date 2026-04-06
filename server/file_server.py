from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Callable
import sys
import argparse

# Ensure repository root is on sys.path when run as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from protocols.protocol import Metadata, send_chunk, send_eof, send_metadata
    from utils.hash_utils import sha256_file
except ModuleNotFoundError:
    # Fallback if PYTHONPATH is not set and the script is run directly.
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from protocols.protocol import Metadata, send_chunk, send_eof, send_metadata
    from utils.hash_utils import sha256_file


EventCallback = Callable[[dict], None]


class TCPFileServer(threading.Thread):
    def __init__(
        self,
        host: str,
        port: int,
        file_path: str | Path,
        chunk_size: int,
        mode: str,
        speed_limit_bps: int,
        pause_event: threading.Event,
        stop_event: threading.Event,
        event_callback: EventCallback,
    ) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.file_path = Path(file_path)
        self.chunk_size = max(256, chunk_size)
        self.mode = mode
        self.speed_limit_bps = speed_limit_bps
        self.pause_event = pause_event
        self.stop_event = stop_event
        self.event_callback = event_callback
        self._server_socket: socket.socket | None = None

    def emit(self, event_type: str, **payload: object) -> None:
        self.event_callback({"source": "server", "type": event_type, **payload})

    def stop(self) -> None:
        self.stop_event.set()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass

    def _wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.05)

    def _chunk_order(self, total_chunks: int) -> list[int]:
        order = list(range(total_chunks))
        if self.mode == "out_of_order" and total_chunks >= 3:
            order[1], order[2] = order[2], order[1]
        return order

    def _throttle(self, bytes_sent: int) -> None:
        if self.speed_limit_bps <= 0:
            return
        delay = bytes_sent / float(self.speed_limit_bps)
        time.sleep(delay)

    def run(self) -> None:
        try:
            file_size = self.file_path.stat().st_size
            effective_chunk_size = file_size if self.mode == "no_chunking" else self.chunk_size
            total_chunks = max(1, (file_size + effective_chunk_size - 1) // effective_chunk_size)
            metadata = Metadata(
                filename=self.file_path.name,
                filesize=file_size,
                sha256=sha256_file(self.file_path),
                chunk_size=effective_chunk_size,
                total_chunks=total_chunks,
                mode=self.mode,
            )

            with open(self.file_path, "rb") as handle:
                chunks = []
                seq_no = 0
                while True:
                    piece = handle.read(effective_chunk_size)
                    if not piece:
                        break
                    chunks.append((seq_no, piece))
                    seq_no += 1

            send_order = self._chunk_order(len(chunks))

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self._server_socket = server_socket
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, self.port))
                server_socket.listen(1)
                self.emit("status", message=f"Listening on {self.host}:{self.port}", connected=False)
                try:
                    conn, addr = server_socket.accept()
                except OSError:
                    return

                with conn:
                    self.emit("client_connected", address=addr[0], port=addr[1], connected=True)
                    send_metadata(conn, metadata)
                    self.emit("metadata_sent", metadata=metadata)

                    for order_position, chunk_index in enumerate(send_order, start=1):
                        if self.stop_event.is_set():
                            break
                        self._wait_if_paused()
                        seq_no, data = chunks[chunk_index]
                        if self.mode == "packet_loss" and seq_no == 4:
                            self.emit(
                                "chunk_dropped",
                                seq_no=seq_no,
                                size=len(data),
                                order_position=order_position,
                            )
                            continue

                        send_chunk(conn, seq_no, data)
                        self.emit(
                            "chunk_sent",
                            seq_no=seq_no,
                            size=len(data),
                            order_position=order_position,
                            total_chunks=len(chunks),
                        )
                        self._throttle(len(data))

                    send_eof(conn)
                    self.emit("transfer_complete", message="EOF sent to client")
        except Exception as exc:
            self.emit("error", message=str(exc))


def _print_event(ev: dict) -> None:
    kind = ev.get("type", "event")
    src = ev.get("source", "server")
    msg = ev.get("message") or ev.get("metadata") or ev
    print(f"[{src}:{kind}] {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TCP file server (single transfer).")
    parser.add_argument("--host", default="127.0.0.1", help="Host/IP to bind")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind")
    parser.add_argument("--file", type=Path, required=False, default=None, help="Path to file to send")
    parser.add_argument("--chunk-size", type=int, default=1024, help="Chunk size in bytes")
    parser.add_argument("--mode", choices=["correct", "no_chunking", "no_hash_verification", "packet_loss", "out_of_order"], default="correct")
    parser.add_argument("--speed-limit-bps", type=int, default=0, help="Throttle bytes per second (0 = no throttle)")
    args = parser.parse_args()

    file_path = args.file
    if file_path is None:
        # Make a quick demo file in /tmp if none provided.
        demo_dir = Path("/tmp/tcp_sha_demo")
        demo_dir.mkdir(parents=True, exist_ok=True)
        file_path = demo_dir / "server_sample.bin"
        file_path.write_bytes(b"TCP SHA demo\n" * 4096)

    pause_event = threading.Event()
    stop_event = threading.Event()
    server = TCPFileServer(
        host=args.host,
        port=args.port,
        file_path=file_path,
        chunk_size=args.chunk_size,
        mode=args.mode,
        speed_limit_bps=args.speed_limit_bps,
        pause_event=pause_event,
        stop_event=stop_event,
        event_callback=_print_event,
    )
    server.start()
    server.join()


if __name__ == "__main__":
    main()
