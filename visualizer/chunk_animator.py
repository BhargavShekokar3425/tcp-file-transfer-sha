from __future__ import annotations

import time
import tkinter as tk


class ChunkAnimator(tk.LabelFrame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Transfer View", padx=8, pady=8)
        self.canvas = tk.Canvas(self, bg="#fff8ef", height=170, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.active_blocks: list[dict] = []
        self.total_chunks = 1
        self.received_chunks = 0
        self.current_label = "Waiting for transfer"
        self.last_tick = time.perf_counter()
        self.after(30, self._animate)

    def set_progress(self, received_chunks: int, total_chunks: int, current_label: str) -> None:
        self.received_chunks = received_chunks
        self.total_chunks = max(total_chunks, 1)
        self.current_label = current_label
        self._draw_static()

    def add_chunk(self, seq_no: int) -> None:
        self.active_blocks.append({"seq_no": seq_no, "progress": 0.0})
        self._draw_static()

    def _draw_static(self) -> None:
        self.canvas.delete("background")
        width = max(self.canvas.winfo_width(), 520)
        height = max(self.canvas.winfo_height(), 170)
        self.canvas.create_text(74, 36, text="Server", fill="#2f6fed", font=("Helvetica", 12, "bold"), tags="background")
        self.canvas.create_text(width - 74, 36, text="Client", fill="#15803d", font=("Helvetica", 12, "bold"), tags="background")
        self.canvas.create_line(105, 85, width - 105, 85, fill="#cbd5e1", width=5, arrow=tk.LAST, tags="background")
        self.canvas.create_text(width // 2, 28, text=self.current_label, fill="#7c2d12", font=("Helvetica", 11, "bold"), tags="background")

        bar_x1, bar_y1, bar_x2, bar_y2 = 50, height - 45, width - 50, height - 18
        self.canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, outline="#cbd5e1", width=2, tags="background")
        filled = bar_x1 + ((bar_x2 - bar_x1) * (self.received_chunks / self.total_chunks))
        self.canvas.create_rectangle(bar_x1, bar_y1, filled, bar_y2, fill="#fb923c", outline="", tags="background")
        self.canvas.create_text(
            width // 2,
            height - 58,
            text=f"Chunk progress: {self.received_chunks}/{self.total_chunks}",
            fill="#475569",
            font=("Helvetica", 10),
            tags="background",
        )

    def _animate(self) -> None:
        now = time.perf_counter()
        delta = min(now - self.last_tick, 0.05)
        self.last_tick = now
        self._draw_static()
        width = max(self.canvas.winfo_width(), 520)
        left = 110
        right = width - 140
        updated_blocks = []
        for block in self.active_blocks:
            block["progress"] += delta * 1.8
            if block["progress"] < 1.0:
                updated_blocks.append(block)
            x = left + (right - left) * min(block["progress"], 1.0)
            y = 85
            self.canvas.create_rectangle(x, y - 18, x + 62, y + 18, fill="#fb923c", outline="#ea580c")
            self.canvas.create_text(x + 31, y, text=f"Chunk {block['seq_no'] + 1}", fill="white", font=("Helvetica", 9, "bold"))
        self.active_blocks = updated_blocks
        self.after(30, self._animate)
