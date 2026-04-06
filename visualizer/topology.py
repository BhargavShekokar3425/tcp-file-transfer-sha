from __future__ import annotations

import tkinter as tk


class TopologyPanel(tk.LabelFrame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Network Topology", padx=8, pady=8)
        self.canvas = tk.Canvas(self, bg="#f7fbff", height=170, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.client_status = "Disconnected"
        self.server_status = "Idle"
        self.active_transfer = "No active transfer"
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 520)
        height = max(self.canvas.winfo_height(), 170)
        server_x, client_x, center_y = 120, width - 120, height // 2

        self.canvas.create_oval(server_x - 50, center_y - 45, server_x + 50, center_y + 45, fill="#2f6fed", outline="")
        self.canvas.create_text(server_x, center_y - 5, text="Server", fill="white", font=("Helvetica", 13, "bold"))
        self.canvas.create_text(server_x, center_y + 18, text="192.168.1.1", fill="white", font=("Helvetica", 10))

        self.canvas.create_oval(client_x - 50, center_y - 45, client_x + 50, center_y + 45, fill="#29a36a", outline="")
        self.canvas.create_text(client_x, center_y - 5, text="Client", fill="white", font=("Helvetica", 13, "bold"))
        self.canvas.create_text(client_x, center_y + 18, text="192.168.1.10", fill="white", font=("Helvetica", 10))

        self.canvas.create_line(server_x + 65, center_y, client_x - 65, center_y, width=4, fill="#8aa0b8", arrow=tk.BOTH)
        self.canvas.create_text(width // 2, center_y - 18, text=self.active_transfer, fill="#334155", font=("Helvetica", 11, "bold"))
        self.canvas.create_text(server_x, height - 24, text=f"Status: {self.server_status}", fill="#1d4ed8", font=("Helvetica", 10))
        self.canvas.create_text(client_x, height - 24, text=f"Status: {self.client_status}", fill="#15803d", font=("Helvetica", 10))

    def update_status(self, server_status: str | None = None, client_status: str | None = None, active_transfer: str | None = None) -> None:
        if server_status is not None:
            self.server_status = server_status
        if client_status is not None:
            self.client_status = client_status
        if active_transfer is not None:
            self.active_transfer = active_transfer
        self._draw()
