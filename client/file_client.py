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
    from protocols.protocol import recv_chunk, recv_eof, recv_metadata
    from utils.hash_utils import sha256_bytes
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from protocols.protocol import recv_chunk, recv_eof, recv_metadata
    from utils.hash_utils import sha256_bytes


EventCallback = Callable[[dict], None]


class TCPFileClient(threading.Thread):
    def __init__(
        self,
        host: str,
        port: int,
        output_dir: str | Path,
        mode: str,
        stop_event: threading.Event,
        event_callback: EventCallback,
    ) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.output_dir = Path(output_dir)
        self.mode = mode
        self.stop_event = stop_event
        self.event_callback = event_callback

    def emit(self, event_type: str, **payload: object) -> None:
        self.event_callback({"source": "client", "type": event_type, **payload})

    def run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                start_wait = time.perf_counter()
                while True:
                    try:
                        sock.connect((self.host, self.port))
                        break
                    except ConnectionRefusedError:
                        if time.perf_counter() - start_wait > 5:
                            raise
                        time.sleep(0.1)

                self.emit("connected", host=self.host, port=self.port)
                metadata = recv_metadata(sock)
                self.emit("metadata_received", metadata=metadata)
                expected_chunks = metadata.total_chunks
                arrived_chunks: list[tuple[int, bytes]] = []
                ordered_chunks: dict[int, bytes] = {}
                bytes_received = 0
                samples: list[tuple[float, float]] = []
                started_at = time.perf_counter()

                while len(arrived_chunks) < expected_chunks and not self.stop_event.is_set():
                    chunk = recv_chunk(sock)
                    if chunk is None:
                        break
                    seq_no, data = chunk
                    arrived_chunks.append((seq_no, data))
                    ordered_chunks[seq_no] = data
                    bytes_received += len(data)
                    elapsed = max(time.perf_counter() - started_at, 1e-6)
                    throughput = bytes_received / elapsed
                    samples.append((elapsed, throughput))
                    self.emit(
                        "chunk_received",
                        seq_no=seq_no,
                        size=len(data),
                        received_chunks=len(arrived_chunks),
                        total_chunks=expected_chunks,
                        bytes_received=bytes_received,
                        elapsed=elapsed,
                        throughput=throughput,
                    )

                eof_ok = recv_eof(sock)
                self.emit("eof_received", ok=eof_ok)

                if self.mode == "out_of_order":
                    assembled = b"".join(data for _, data in arrived_chunks)
                else:
                    assembled = b"".join(ordered_chunks[index] for index in sorted(ordered_chunks))

                self.output_dir.mkdir(parents=True, exist_ok=True)
                output_path = self.output_dir / f"received_{metadata.filename}"
                with open(output_path, "wb") as handle:
                    handle.write(assembled)

                finished_at = time.perf_counter()
                duration = max(finished_at - started_at, 1e-6)
                actual_hash = sha256_bytes(assembled)
                size_match = len(assembled) == metadata.filesize
                hash_match = actual_hash == metadata.sha256 if self.mode != "no_hash_verification" else None

                self.emit(
                    "verification_complete",
                    output_path=str(output_path),
                    expected_hash=metadata.sha256,
                    actual_hash=actual_hash,
                    size_match=size_match,
                    hash_match=hash_match,
                    bytes_received=len(assembled),
                    expected_size=metadata.filesize,
                    duration=duration,
                    throughput=(len(assembled) / duration),
                    samples=samples,
                )
        except Exception as exc:
            self.emit("error", message=str(exc))


def _print_event(ev: dict) -> None:
    kind = ev.get("type", "event")
    src = ev.get("source", "client")
    msg = ev.get("message") or ev
    print(f"[{src}:{kind}] {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TCP file client (single transfer).")
    parser.add_argument("--host", default="127.0.0.1", help="Server host/IP")
    parser.add_argument("--port", type=int, default=5001, help="Server port")
    parser.add_argument("--out", type=Path, default=Path("/tmp/tcp_sha_client"), help="Output directory")
    parser.add_argument("--mode", choices=["correct", "no_chunking", "no_hash_verification", "packet_loss", "out_of_order"], default="correct")
    args = parser.parse_args()

    stop_event = threading.Event()
    client = TCPFileClient(
        host=args.host,
        port=args.port,
        output_dir=args.out,
        mode=args.mode,
        stop_event=stop_event,
        event_callback=_print_event,
    )
    client.start()
    client.join()


if __name__ == "__main__":
    main()
