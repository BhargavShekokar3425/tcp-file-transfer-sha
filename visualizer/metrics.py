from __future__ import annotations

import tkinter as tk


class ThroughputGraph(tk.LabelFrame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Performance Metrics", padx=8, pady=8)
        self.canvas = tk.Canvas(self, bg="#f8fafc", height=220, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.samples: list[tuple[float, float]] = []
        self.summary_var = tk.StringVar(value="Bytes received: 0 | Expected: 0 | Hash: Pending | Time: 0.00s | Throughput: 0 B/s")
        tk.Label(self, textvariable=self.summary_var, anchor="w", fg="#0f172a").pack(fill="x", pady=(6, 0))
        self.redraw()

    def reset(self) -> None:
        self.samples.clear()
        self.summary_var.set("Bytes received: 0 | Expected: 0 | Hash: Pending | Time: 0.00s | Throughput: 0 B/s")
        self.redraw()

    def update_samples(self, samples: list[tuple[float, float]]) -> None:
        self.samples = samples[-80:]
        self.redraw()

    def update_summary(
        self,
        bytes_received: int,
        expected_size: int,
        hash_match: bool | None,
        duration: float,
        throughput: float,
    ) -> None:
        hash_label = "Skipped" if hash_match is None else ("Match" if hash_match else "Mismatch")
        self.summary_var.set(
            f"Bytes received: {bytes_received} | Expected: {expected_size} | Hash: {hash_label} | "
            f"Time: {duration:.2f}s | Throughput: {throughput:.0f} B/s"
        )

    def redraw(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 420)
        height = max(self.canvas.winfo_height(), 220)
        margin = 35
        self.canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#94a3b8", width=2)
        self.canvas.create_line(margin, margin, margin, height - margin, fill="#94a3b8", width=2)
        self.canvas.create_text(width // 2, 15, text="Throughput (bytes/sec) over time", fill="#1e293b", font=("Helvetica", 11, "bold"))
        if len(self.samples) < 2:
            self.canvas.create_text(width // 2, height // 2, text="Transfer samples will appear here", fill="#64748b", font=("Helvetica", 11))
            return

        max_time = max(sample[0] for sample in self.samples)
        max_value = max(sample[1] for sample in self.samples) or 1.0
        points = []
        for elapsed, throughput in self.samples:
            x = margin + (elapsed / max_time) * (width - margin * 2)
            y = height - margin - (throughput / max_value) * (height - margin * 2)
            points.extend([x, y])
        self.canvas.create_line(*points, fill="#0f766e", width=3, smooth=True)
        self.canvas.create_text(width - 55, height - 15, text=f"{max_time:.2f}s", fill="#475569", font=("Helvetica", 9))
        self.canvas.create_text(48, margin, text=f"{max_value:.0f}", fill="#475569", font=("Helvetica", 9))
