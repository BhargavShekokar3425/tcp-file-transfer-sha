from __future__ import annotations

import queue
import threading
from pathlib import Path
import sys
import argparse
import time

# Ensure repository root is on sys.path when run as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from client.file_client import TCPFileClient
    from server.file_server import TCPFileServer
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from client.file_client import TCPFileClient
    from server.file_server import TCPFileServer


class TransferSimulator:
    def __init__(self, event_queue: "queue.Queue[dict]") -> None:
        self.event_queue = event_queue
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.server: TCPFileServer | None = None
        self.client: TCPFileClient | None = None

    def emit(self, event: dict) -> None:
        self.event_queue.put(event)

    def start(
        self,
        host: str,
        port: int,
        file_path: str | Path,
        output_dir: str | Path,
        chunk_size: int,
        mode: str,
        speed_limit_bps: int,
    ) -> None:
        self.stop()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.server = TCPFileServer(
            host=host,
            port=port,
            file_path=file_path,
            chunk_size=chunk_size,
            mode=mode,
            speed_limit_bps=speed_limit_bps,
            pause_event=self.pause_event,
            stop_event=self.stop_event,
            event_callback=self.emit,
        )
        self.client = TCPFileClient(
            host=host,
            port=port,
            output_dir=output_dir,
            mode=mode,
            stop_event=self.stop_event,
            event_callback=self.emit,
        )
        self.server.start()
        self.client.start()

    def pause(self) -> None:
        self.pause_event.set()
        self.emit({"source": "demo", "type": "paused"})

    def resume(self) -> None:
        self.pause_event.clear()
        self.emit({"source": "demo", "type": "resumed"})

    def stop(self) -> None:
        if self.server:
            self.server.stop()
        if self.stop_event:
            self.stop_event.set()
        self.emit({"source": "demo", "type": "stopped"})


def _print_event(ev: dict) -> None:
    kind = ev.get("type", "event")
    src = ev.get("source", "demo")
    msg = ev.get("message") or ev
    print(f"[{src}:{kind}] {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless simulator: spins server+client once.")
    parser.add_argument("--mode", choices=["correct", "no_chunking", "no_hash_verification", "packet_loss", "out_of_order"], default="correct")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--speed-limit-bps", type=int, default=0)
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()

    # Create demo file
    demo_dir = Path("/tmp/tcp_sha_demo")
    demo_dir.mkdir(parents=True, exist_ok=True)
    file_path = demo_dir / "sim_demo.bin"
    file_path.write_bytes(b"Simulator demo\n" * 8000)

    event_queue: "queue.Queue[dict]" = queue.Queue()
    sim = TransferSimulator(event_queue)
    sim.start(
        host="127.0.0.1",
        port=args.port,
        file_path=file_path,
        output_dir=Path("/tmp/tcp_sha_output"),
        chunk_size=args.chunk_size,
        mode=args.mode,
        speed_limit_bps=args.speed_limit_bps,
    )

    done = False
    while not done:
        try:
            ev = event_queue.get(timeout=0.2)
            _print_event(ev)
            if ev.get("type") == "verification_complete":
                done = True
                sim.stop()
        except queue.Empty:
            continue


if __name__ == "__main__":
    main()
