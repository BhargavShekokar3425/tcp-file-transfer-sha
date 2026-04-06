from __future__ import annotations

import queue
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from demo.simulator import TransferSimulator
from visualizer.chunk_animator import ChunkAnimator
from visualizer.metrics import ThroughputGraph
from visualizer.topology import TopologyPanel


MODE_LABELS = {
    "correct": "Correct Implementation",
    "no_chunking": "Broken: No Chunking",
    "no_hash_verification": "Broken: No Hash Verification",
    "packet_loss": "Broken: Packet Loss Simulation",
    "out_of_order": "Broken: Out-of-Order Application Chunks",
}


class FileTransferGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TCP File Transfer with SHA-256 Visualizer")
        self.root.geometry("1680x1020")
        self.root.minsize(1480, 920)
        self.root.configure(bg="#eef4f8")

        self.event_queue: "queue.Queue[dict]" = queue.Queue()
        self.simulator = TransferSimulator(self.event_queue)
        self.demo_file = self._ensure_demo_file()

        self.status_var = tk.StringVar(value="Ready")
        self.mode_var = tk.StringVar(value="correct")
        self.chunk_size_var = tk.IntVar(value=1024)
        self.speed_var = tk.IntVar(value=262144)
        self.hash_status_var = tk.StringVar(value="Status: Pending")
        self.expected_hash_var = tk.StringVar(value="Expected Hash: -")
        self.received_hash_var = tk.StringVar(value="Received Hash: -")
        self.reconstruction_var = tk.StringVar(value="Received chunks: [░░░░░░░░░░] 0%")
        self.bytes_var = tk.StringVar(value="Bytes received: 0 / 0")
        self.current_expected_size = 0
        self.hash_status_label: tk.Label | None = None

        self._build_layout()
        self.root.after(50, self.process_events)

    def _ensure_demo_file(self) -> Path:
        demo_dir = Path(tempfile.gettempdir()) / "tcp_sha_demo"
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_path = demo_dir / "sample_payload.bin"
        if not demo_path.exists():
            content = bytearray()
            for index in range(1024 * 32):
                content.extend(f"Chunk demo line {index:05d}\n".encode("utf-8"))
            demo_path.write_bytes(bytes(content[: 1024 * 1024]))
        return demo_path

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        outer.rowconfigure(2, weight=1)

        control = tk.LabelFrame(outer, text="Control Panel", padx=18, pady=16, bg="#f9fbfd", font=("Helvetica", 12, "bold"))
        control.grid(row=0, column=0, sticky="nsew", pady=(0, 18))
        for idx in range(9):
            control.columnconfigure(idx, weight=1)

        label_style = {"bg": "#f9fbfd", "font": ("Helvetica", 11, "bold")}
        tk.Label(control, text="Mode", **label_style).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Combobox(control, textvariable=self.mode_var, values=list(MODE_LABELS.keys()), state="readonly", width=28).grid(row=1, column=0, sticky="ew", padx=(0, 18), ipady=4)
        tk.Label(control, text="Chunk Size (bytes)", **label_style).grid(row=0, column=1, sticky="w", pady=(0, 6))
        tk.Spinbox(control, from_=256, to=65536, increment=256, textvariable=self.chunk_size_var, width=12, font=("Helvetica", 11)).grid(row=1, column=1, sticky="ew", padx=(0, 18), ipady=4)
        tk.Label(control, text="Speed Limit (B/s)", **label_style).grid(row=0, column=2, sticky="w", pady=(0, 6))
        tk.Spinbox(control, from_=0, to=10485760, increment=65536, textvariable=self.speed_var, width=14, font=("Helvetica", 11)).grid(row=1, column=2, sticky="ew", padx=(0, 18), ipady=4)

        ttk.Button(control, text="Run Demo", command=self.run_demo).grid(row=1, column=3, sticky="ew", padx=8, ipady=6)
        ttk.Button(control, text="Pause", command=self.simulator.pause).grid(row=1, column=4, sticky="ew", padx=8, ipady=6)
        ttk.Button(control, text="Resume", command=self.simulator.resume).grid(row=1, column=5, sticky="ew", padx=8, ipady=6)
        ttk.Button(control, text="Stop", command=self.simulator.stop).grid(row=1, column=6, sticky="ew", padx=8, ipady=6)
        ttk.Label(control, textvariable=self.status_var, font=("Helvetica", 11, "bold")).grid(row=1, column=7, columnspan=2, sticky="e")

        mid = ttk.Frame(outer)
        mid.grid(row=1, column=0, sticky="nsew", pady=(0, 18))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=4)
        mid.columnconfigure(2, weight=3)
        mid.rowconfigure(0, weight=1)

        self.topology_panel = TopologyPanel(mid)
        self.topology_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 18), ipadx=8, ipady=8)

        self.chunk_animator = ChunkAnimator(mid)
        self.chunk_animator.grid(row=0, column=1, sticky="nsew", padx=(0, 18), ipadx=8, ipady=8)

        reconstruction = tk.LabelFrame(mid, text="Chunk Monitor", padx=18, pady=16, font=("Helvetica", 12, "bold"))
        reconstruction.grid(row=0, column=2, sticky="nsew")
        tk.Label(reconstruction, textvariable=self.reconstruction_var, font=("Helvetica", 16, "bold"), justify="left").pack(anchor="w", pady=(8, 14))
        tk.Label(reconstruction, textvariable=self.bytes_var, fg="#334155", font=("Helvetica", 12)).pack(anchor="w", pady=(0, 14))
        ttk.Separator(reconstruction).pack(fill="x", pady=12)
        tk.Label(reconstruction, text="SHA-256 Verification", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(6, 12))
        tk.Label(reconstruction, textvariable=self.expected_hash_var, wraplength=420, justify="left", font=("Helvetica", 11)).pack(anchor="w", pady=4)
        tk.Label(reconstruction, textvariable=self.received_hash_var, wraplength=420, justify="left", font=("Helvetica", 11)).pack(anchor="w", pady=4)
        self.hash_status_label = tk.Label(reconstruction, textvariable=self.hash_status_var, font=("Helvetica", 14, "bold"), fg="#b45309")
        self.hash_status_label.pack(anchor="w", pady=16)

        lower = ttk.Frame(outer)
        lower.grid(row=2, column=0, sticky="nsew")
        lower.columnconfigure(0, weight=2)
        lower.columnconfigure(1, weight=3)
        lower.rowconfigure(0, weight=1)

        log_frame = tk.LabelFrame(lower, text="Event Logs", padx=14, pady=14, font=("Helvetica", 12, "bold"))
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.log_widget = tk.Text(log_frame, height=20, bg="#0f172a", fg="#e2e8f0", insertbackground="#e2e8f0", font=("Consolas", 11), padx=10, pady=10, spacing1=4, spacing3=4)
        self.log_widget.pack(fill="both", expand=True)

        self.metrics_panel = ThroughputGraph(lower)
        self.metrics_panel.grid(row=0, column=1, sticky="nsew")

    def log(self, message: str) -> None:
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")

    def reset_visuals(self) -> None:
        self.metrics_panel.reset()
        self.expected_hash_var.set("Expected Hash: -")
        self.received_hash_var.set("Received Hash: -")
        self.hash_status_var.set("Status: Pending")
        if self.hash_status_label:
            self.hash_status_label.configure(fg="#b45309")
        self.reconstruction_var.set("Received chunks: [░░░░░░░░░░] 0%")
        self.bytes_var.set("Bytes received: 0 / 0")
        self.chunk_animator.set_progress(0, 1, "Waiting for transfer")

    def run_demo(self) -> None:
        self.reset_visuals()
        mode = self.mode_var.get()
        self.status_var.set(f"Running {MODE_LABELS[mode]}")
        self.log(f"Demo started in mode: {MODE_LABELS[mode]}")
        self.topology_panel.update_status(server_status="Starting", client_status="Waiting", active_transfer=self.demo_file.name)
        self.simulator.start(
            host="127.0.0.1",
            port=5001,
            file_path=self.demo_file,
            output_dir=Path(tempfile.gettempdir()) / "tcp_sha_output",
            chunk_size=self.chunk_size_var.get(),
            mode=mode,
            speed_limit_bps=self.speed_var.get(),
        )

    def _progress_bar_text(self, received: int, total: int) -> str:
        width = 10
        filled = int((received / max(total, 1)) * width)
        return "[" + ("█" * filled) + ("░" * (width - filled)) + f"] {int((received / max(total, 1)) * 100)}%"

    def process_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self.handle_event(event)
        self.root.after(50, self.process_events)

    def handle_event(self, event: dict) -> None:
        event_type = event["type"]
        source = event.get("source", "system")
        if event_type == "status":
            self.topology_panel.update_status(server_status="Listening")
            self.log(f"Server: {event['message']}")
        elif event_type == "client_connected":
            self.topology_panel.update_status(server_status="Connected", client_status="Connected")
            self.log(f"Client connected from {event['address']}:{event['port']}")
        elif event_type == "connected":
            self.log(f"Client connected to {event['host']}:{event['port']}")
        elif event_type == "metadata_sent":
            metadata = event["metadata"]
            self.log(
                f"Metadata sent: {metadata.filename} | {metadata.filesize} bytes | {metadata.total_chunks} chunks"
            )
            self.expected_hash_var.set(f"Expected Hash: {metadata.sha256}")
            self.topology_panel.update_status(active_transfer=metadata.filename)
        elif event_type == "metadata_received":
            metadata = event["metadata"]
            self.log(
                f"Metadata received: mode={metadata.mode}, chunk_size={metadata.chunk_size}, total_chunks={metadata.total_chunks}"
            )
            self.current_expected_size = metadata.filesize
            self.chunk_animator.set_progress(0, metadata.total_chunks, "Client requested file; server streaming metadata")
            self.bytes_var.set(f"Bytes received: 0 / {metadata.filesize}")
        elif event_type == "chunk_sent":
            self.chunk_animator.add_chunk(event["seq_no"])
            self.chunk_animator.set_progress(
                self.chunk_animator.received_chunks,
                event["total_chunks"],
                f"Server -> Send Chunk {event['seq_no'] + 1}",
            )
            self.log(f"Server sent chunk {event['seq_no'] + 1} ({event['size']} bytes)")
        elif event_type == "chunk_dropped":
            self.log(f"Server dropped chunk {event['seq_no'] + 1} to simulate packet loss")
        elif event_type == "chunk_received":
            self.chunk_animator.set_progress(
                event["received_chunks"],
                event["total_chunks"],
                f"Client reconstructing after chunk {event['seq_no'] + 1}",
            )
            self.reconstruction_var.set(
                f"Received chunks: {self._progress_bar_text(event['received_chunks'], event['total_chunks'])}"
            )
            self.bytes_var.set(f"Bytes received: {event['bytes_received']} / {self.current_expected_size}")
            self.metrics_panel.update_samples(self.metrics_panel.samples + [(event["elapsed"], event["throughput"])])
            self.log(f"Chunk {event['seq_no'] + 1} received ({event['size']} bytes)")
        elif event_type == "eof_received":
            self.log("EOF received from server")
        elif event_type == "verification_complete":
            hash_match = event["hash_match"]
            color_text = "Status: Verification skipped" if hash_match is None else ("Status: MATCH" if hash_match else "Status: MISMATCH")
            self.received_hash_var.set(f"Received Hash: {event['actual_hash']}")
            self.hash_status_var.set(color_text)
            if self.hash_status_label:
                self.hash_status_label.configure(fg="#475569" if hash_match is None else ("#15803d" if hash_match else "#b91c1c"))
            self.reconstruction_var.set("Received chunks: [██████████] 100%")
            self.bytes_var.set(f"Bytes received: {event['bytes_received']} / {event['expected_size']}")
            self.metrics_panel.update_samples(event["samples"])
            self.metrics_panel.update_summary(
                bytes_received=event["bytes_received"],
                expected_size=event["expected_size"],
                hash_match=hash_match,
                duration=event["duration"],
                throughput=event["throughput"],
            )
            self.topology_panel.update_status(server_status="Complete", client_status="Verified")
            summary = (
                "--- Transfer Summary ---\n"
                f"Bytes received: {event['bytes_received']}\n"
                f"Expected size: {event['expected_size']}\n"
                f"Hash match: {hash_match}\n"
                f"Time taken: {event['duration']:.2f} seconds\n"
                f"Throughput: {event['throughput']:.0f} bytes/sec"
            )
            self.log(summary)
            self.status_var.set("Transfer finished")
        elif event_type == "error":
            self.log(f"Error: {event['message']}")
            self.status_var.set("Transfer error")
            if self.hash_status_label:
                self.hash_status_label.configure(fg="#b91c1c")
            self.hash_status_var.set("Status: ERROR")
        elif event_type == "paused":
            self.status_var.set("Transfer paused")
            self.log("Transfer paused")
        elif event_type == "resumed":
            self.status_var.set("Transfer resumed")
            self.log("Transfer resumed")
        elif event_type == "stopped":
            if source == "demo":
                self.log("Transfer stopped")
                self.status_var.set("Transfer stopped")


def launch_app() -> None:
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    FileTransferGUI(root)
    root.mainloop()
