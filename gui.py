"""
RQL CONDUIT — WORKSTATION USER INTERFACE
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Deterministic High-DPI Desktop Workstation for Multi-Interface Socket Multiplexing,
Continuous RTT Jitter Variance Telemetry, and Sub-3ms Deterministic Failover.
Executive Solarized Light Specification.
"""

import sys
import time
import threading
import customtkinter as ctk
from typing import List, Dict

from core.adapter_discovery import NetworkDiscoveryManager, AdapterInfo
from core.jitter_radar import SunTzuJitterRadar
from core.volvo_chassis import RoutingMode
from core.socket_engine import SovereignSocketProxyServer
from core.windows_proxy import WindowsSystemProxyManager


class RQLConduitGUI(ctk.CTk):
    """Institutional Workstation GUI for RQL Conduit (Solarized Light Specification)."""

    COLOR_BG = "#fdf6e3"              # Solarized Base 3 (Ivory Canvas)
    COLOR_CARD = "#ffffff"            # Pure White Container
    COLOR_BORDER = "#e2e8f0"          # 1px Structural Boundary
    COLOR_TEXT_PRIMARY = "#0f172a"    # Slate-900 (High-Contrast Primary)
    COLOR_TEXT_MUTED = "#64748b"      # Slate-500 (Technical Metadata)
    COLOR_ACCENT_BLUE = "#0284c7"     # Sky-600
    COLOR_ACCENT_GREEN = "#059669"    # Emerald-600
    COLOR_ACCENT_RED = "#dc2626"      # Red-600
    COLOR_TRIBUTE_BG = "#f0f9ff"      # Soft Sky Structural Banner
    COLOR_TRIBUTE_BORDER = "#38bdf8"  # Cyan Boundary

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")

        self.title("RQL CONDUIT v2.0-PROD — Deterministic Multi-Interface Network Gateway")
        self.geometry("1140x820")
        self.minsize(980, 720)
        self.configure(fg_color=self.COLOR_BG)

        # Core Engines
        self.proxy_engine = SovereignSocketProxyServer(host="127.0.0.1", port=1080, log_callback=self._on_proxy_log)
        self.adapters: List[AdapterInfo] = []
        self.radar = SunTzuJitterRadar(check_interval_sec=1.5, on_update_callback=self._on_radar_update)

        # UI state
        self.adapter_cards: Dict[str, dict] = {}
        self._closing = False

        self._build_ui()
        self._refresh_adapters()
        self.radar.start(self.adapters)

        self._poll_ui_telemetry()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.main_container = ctk.CTkScrollableFrame(self, fg_color=self.COLOR_BG, corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # 1. SPECIFICATION HEADER & PRIOR ART ACKNOWLEDGEMENT
        # -------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=self.COLOR_CARD,
            corner_radius=12,
            border_width=1,
            border_color=self.COLOR_BORDER
        )
        self.header_frame.pack(fill="x", padx=18, pady=(16, 10))

        title_row = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=20, pady=(14, 2))

        title_lbl = ctk.CTkLabel(
            title_row,
            text="RQL CONDUIT  •  v2.0-PROD",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=self.COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(side="left")

        is_rust = self.proxy_engine.rust_engine and self.proxy_engine.rust_engine.is_loaded
        core_badge = ctk.CTkLabel(
            title_row,
            text="  BARE-METAL RUST CORE (rql_conduit_core.dll)  " if is_rust else "  PYTHON C-SOCKET ENGINE  ",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=self.COLOR_ACCENT_GREEN if is_rust else "#0284c7",
            text_color="#ffffff",
            corner_radius=6
        )
        core_badge.pack(side="left", padx=12)

        sub_lbl = ctk.CTkLabel(
            self.header_frame,
            text="Deterministic Multi-Interface Socket Multiplexing  •  Native OS Socket Binding  •  Deterministic Failover (Δt ≤ 3ms)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.COLOR_TEXT_MUTED
        )
        sub_lbl.pack(anchor="w", padx=20, pady=(0, 10))

        # Formal Acknowledgement of Prior Art
        tribute_box = ctk.CTkFrame(
            self.header_frame,
            fg_color=self.COLOR_TRIBUTE_BG,
            corner_radius=8,
            border_width=1,
            border_color=self.COLOR_TRIBUTE_BORDER
        )
        tribute_box.pack(fill="x", padx=20, pady=(0, 16))

        tribute_title = ctk.CTkLabel(
            tribute_box,
            text="FORMAL ATTRIBUTION & ACKNOWLEDGEMENT OF PRIOR ART",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#0369a1"
        )
        tribute_title.pack(anchor="w", padx=14, pady=(10, 4))

        tribute_text = (
            "This software formally acknowledges the architectural contributions of foundational open-source implementations:\n"
            "1. Alex Kirszenberg (alexkirsz/dispatch-proxy, 2013): Proof of concept for client-side socket-level dispatching across multi-homed interfaces.\n"
            "2. Rohit (rohit267/net-merge, 2024): Demonstration of multi-interface aggregation in Go via virtual network drivers.\n"
            "RQL Conduit formalizes this lineage into a deterministic architecture: zero-driver local socket binding (SO_BINDTODEVICE / IP binding),\n"
            "continuous stochastic RTT jitter variance estimation, and deterministic sub-3ms connection failover. (Dual-Licensed under Apache-2.0 / MIT)."
        )
        tribute_desc = ctk.CTkLabel(
            tribute_box,
            text=tribute_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#334155",
            justify="left"
        )
        tribute_desc.pack(anchor="w", padx=14, pady=(0, 12))

        # -------------------------------------------------------------
        # 2. MASTER ENGINE CONTROL CONSOLE
        # -------------------------------------------------------------
        self.control_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=self.COLOR_CARD,
            corner_radius=12,
            border_width=1,
            border_color=self.COLOR_BORDER
        )
        self.control_frame.pack(fill="x", padx=18, pady=8)

        ctrl_grid = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ctrl_grid.pack(fill="x", padx=18, pady=16)

        # Column 1: Engine Start/Stop Toggle
        self.btn_toggle_engine = ctk.CTkButton(
            ctrl_grid,
            text="START RQL CONDUIT [127.0.0.1:1080]",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=self.COLOR_ACCENT_GREEN,
            hover_color="#047857",
            text_color="#ffffff",
            height=42,
            command=self._toggle_proxy_engine
        )
        self.btn_toggle_engine.grid(row=0, column=0, padx=(0, 12), sticky="w")

        # Column 2: Routing Policy Selector
        mode_lbl = ctk.CTkLabel(ctrl_grid, text="Dispatch Policy:", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.COLOR_TEXT_PRIMARY)
        mode_lbl.grid(row=0, column=1, padx=(6, 6), sticky="e")

        self.combo_mode = ctk.CTkComboBox(
            ctrl_grid,
            values=[
                "Weighted Round-Robin (Bandwidth Aggregation)",
                "Minimum RTT Variance (Latency Optimization)",
                "Deterministic Primary / Hot-Standby Failover",
            ],
            width=320,
            height=38,
            font=ctk.CTkFont(size=12),
            fg_color="#f8fafc",
            text_color=self.COLOR_TEXT_PRIMARY,
            command=self._on_mode_changed
        )
        self.combo_mode.set("Weighted Round-Robin (Bandwidth Aggregation)")
        self.combo_mode.grid(row=0, column=2, padx=(0, 12), sticky="w")

        # Column 3: Windows System Proxy Toggle
        self.btn_sys_proxy = ctk.CTkButton(
            ctrl_grid,
            text="Enable Windows WinINet Proxy",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            height=38,
            command=self._toggle_windows_system_proxy
        )
        self.btn_sys_proxy.grid(row=0, column=3, padx=(6, 0), sticky="e")

        # -------------------------------------------------------------
        # 3. LIVE INTERFACE TELEMETRY & JITTER VARIANCE METRICS
        # -------------------------------------------------------------
        adapter_header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        adapter_header_frame.pack(fill="x", padx=22, pady=(14, 6))

        sec_title = ctk.CTkLabel(
            adapter_header_frame,
            text="DISCOVERED NETWORK INTERFACES & CONTINUOUS RTT VARIANCE TELEMETRY",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self.COLOR_TEXT_PRIMARY
        )
        sec_title.pack(side="left")

        btn_rescan = ctk.CTkButton(
            adapter_header_frame,
            text="Enumerate Interfaces",
            font=ctk.CTkFont(size=11),
            fg_color="#e2e8f0",
            hover_color="#cbd5e1",
            text_color=self.COLOR_TEXT_PRIMARY,
            height=28,
            width=150,
            command=self._refresh_adapters
        )
        btn_rescan.pack(side="right")

        self.cards_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.cards_container.pack(fill="x", padx=18, pady=4)

        # -------------------------------------------------------------
        # 4. DETERMINISTIC METRICS & STATIC PINNING OVERRIDE
        # -------------------------------------------------------------
        telemetry_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=self.COLOR_CARD,
            corner_radius=12,
            border_width=1,
            border_color=self.COLOR_BORDER
        )
        telemetry_frame.pack(fill="x", padx=18, pady=10)

        dyno_grid = ctk.CTkFrame(telemetry_frame, fg_color="transparent")
        dyno_grid.pack(fill="x", padx=16, pady=14)

        # Stat 1: Active Sockets
        self.stat_active_sockets = self._create_stat_card(dyno_grid, "ACTIVE CLIENT SOCKS", "0", row=0, col=0)
        # Stat 2: Total Routed
        self.stat_total_routed = self._create_stat_card(dyno_grid, "TOTAL SESSIONS ROUTED", "0", row=0, col=1)
        # Stat 3: Deterministic Failovers Executed
        self.stat_airbags_caught = self._create_stat_card(dyno_grid, "FAILOVERS (Δt ≤ 3ms)", "0", row=0, col=2, accent_color=self.COLOR_ACCENT_GREEN)
        # Stat 4: Aggregate Throughput
        self.stat_bytes_pumped = self._create_stat_card(dyno_grid, "AGGREGATE THROUGHPUT", "0.0 MB", row=0, col=3)

        # Tier 3: Static Hardware Interface Pinning Override
        handbrake_frame = ctk.CTkFrame(
            telemetry_frame,
            fg_color="#fff1f2",
            corner_radius=8,
            border_width=1,
            border_color="#fecdd3"
        )
        handbrake_frame.pack(fill="x", padx=16, pady=(0, 14))

        hb_lbl = ctk.CTkLabel(
            handbrake_frame,
            text="TIER 3: STATIC HARDWARE PINNING OVERRIDE (POLICY LOCK)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.COLOR_ACCENT_RED
        )
        hb_lbl.pack(side="left", padx=16, pady=10)

        self.btn_handbrake = ctk.CTkButton(
            handbrake_frame,
            text="PIN TO PRIMARY INTERFACE",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=self.COLOR_ACCENT_RED,
            hover_color="#be123c",
            text_color="#ffffff",
            height=30,
            command=self._toggle_handbrake
        )
        self.btn_handbrake.pack(side="right", padx=16, pady=10)

        # -------------------------------------------------------------
        # 5. DETERMINISTIC SOCKET EVENT AUDIT STREAM
        # -------------------------------------------------------------
        log_header = ctk.CTkLabel(
            self.main_container,
            text="REAL-TIME SOCKET DISPATCH AUDIT STREAM",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=self.COLOR_TEXT_PRIMARY
        )
        log_header.pack(anchor="w", padx=22, pady=(10, 4))

        self.log_textbox = ctk.CTkTextbox(
            self.main_container,
            height=140,
            fg_color="#f8fafc",
            text_color="#0f172a",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            border_width=1,
            border_color=self.COLOR_BORDER
        )
        self.log_textbox.pack(fill="x", padx=18, pady=(0, 20))
        self.log_textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] RQL Conduit initialized. Deterministic socket binding engine active.\n")

    def _create_stat_card(self, parent, label_text: str, value_text: str, row: int, col: int, accent_color: str = "#0284c7"):
        f = ctk.CTkFrame(parent, fg_color="#f8fafc", corner_radius=8, border_width=1, border_color="#e2e8f0")
        f.grid(row=row, column=col, padx=8, pady=4, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        val_lbl = ctk.CTkLabel(f, text=value_text, font=ctk.CTkFont(family="Consolas", size=20, weight="bold"), text_color=accent_color)
        val_lbl.pack(anchor="center", pady=(10, 2))

        sub = ctk.CTkLabel(f, text=label_text, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=self.COLOR_TEXT_MUTED)
        sub.pack(anchor="center", pady=(0, 8))
        return val_lbl

    def _refresh_adapters(self):
        self.adapters = NetworkDiscoveryManager.get_active_adapters()
        self.proxy_engine.set_adapters(self.adapters)

        for widget in self.cards_container.winfo_children():
            widget.destroy()
        self.adapter_cards.clear()

        if not self.adapters:
            empty_lbl = ctk.CTkLabel(self.cards_container, text="No active routable network interfaces detected.", text_color="#dc2626")
            empty_lbl.pack(pady=20)
            return

        for idx, adapter in enumerate(self.adapters):
            card = ctk.CTkFrame(
                self.cards_container,
                fg_color=self.COLOR_CARD,
                corner_radius=10,
                border_width=1,
                border_color=self.COLOR_BORDER
            )
            card.pack(fill="x", pady=6)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=16, pady=(10, 4))

            name_lbl = ctk.CTkLabel(
                top_row,
                text=adapter.name,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color=self.COLOR_TEXT_PRIMARY
            )
            name_lbl.pack(side="left")

            status_badge = ctk.CTkLabel(
                top_row,
                text=f"  {adapter.status_label}  ",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#059669" if adapter.is_usable_for_traffic() else "#dc2626",
                text_color="#ffffff",
                corner_radius=6
            )
            status_badge.pack(side="right")

            mid_row = ctk.CTkFrame(card, fg_color="transparent")
            mid_row.pack(fill="x", padx=16, pady=(0, 10))

            ip_lbl = ctk.CTkLabel(mid_row, text=f"IPv4: {adapter.ip_address}", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=self.COLOR_ACCENT_BLUE)
            ip_lbl.pack(side="left", padx=(0, 16))

            speed_lbl = ctk.CTkLabel(mid_row, text=f"Capacity: {adapter.speed_mbps} Mbps" if adapter.speed_mbps else "Capacity: Dynamic", font=ctk.CTkFont(size=12), text_color=self.COLOR_TEXT_MUTED)
            speed_lbl.pack(side="left", padx=(0, 16))

            ping_lbl = ctk.CTkLabel(mid_row, text=f"RTT: {adapter.ping_ms} ms", font=ctk.CTkFont(size=12, weight="bold"), text_color="#059669")
            ping_lbl.pack(side="left", padx=(0, 16))

            jitter_lbl = ctk.CTkLabel(mid_row, text=f"Jitter (σ): {adapter.jitter_ms} ms", font=ctk.CTkFont(size=12), text_color=self.COLOR_TEXT_MUTED)
            jitter_lbl.pack(side="left", padx=(0, 16))

            loss_lbl = ctk.CTkLabel(mid_row, text=f"Loss Rate (P): {adapter.packet_loss_pct}%", font=ctk.CTkFont(size=12), text_color=self.COLOR_TEXT_MUTED)
            loss_lbl.pack(side="left")

            self.adapter_cards[adapter.ip_address] = {
                "badge": status_badge,
                "ping": ping_lbl,
                "jitter": jitter_lbl,
                "loss": loss_lbl,
            }

        self._check_initial_sys_proxy()

    def _on_radar_update(self):
        if self._closing:
            return
        self.after(0, self._sync_radar_ui)

    def _sync_radar_ui(self):
        for adapter in self.adapters:
            refs = self.adapter_cards.get(adapter.ip_address)
            if not refs:
                continue

            badge_color = "#059669"
            if adapter.is_quarantined:
                badge_color = "#dc2626"
            elif adapter.status_label == "Degraded":
                badge_color = "#d97706"
            elif adapter.status_label == "Good":
                badge_color = "#2563eb"

            refs["badge"].configure(text=f"  {adapter.status_label}  ", fg_color=badge_color)

            ping_color = "#059669" if adapter.ping_ms < 50 else ("#d97706" if adapter.ping_ms < 150 else "#dc2626")
            refs["ping"].configure(text=f"RTT: {adapter.ping_ms} ms", text_color=ping_color)
            refs["jitter"].configure(text=f"Jitter (σ): {adapter.jitter_ms} ms")
            refs["loss"].configure(text=f"Loss Rate (P): {adapter.packet_loss_pct}%")

    def _poll_ui_telemetry(self):
        if self._closing:
            return

        telemetry = self.proxy_engine.get_telemetry()
        self.stat_active_sockets.configure(text=str(telemetry["active_conns"]))
        self.stat_total_routed.configure(text=str(telemetry["total_routed"]))
        self.stat_airbags_caught.configure(text=str(telemetry["failovers"]))

        mb = telemetry["bytes_transferred"] / (1024 * 1024)
        if mb > 1024:
            self.stat_bytes_pumped.configure(text=f"{mb / 1024:.2f} GB")
        else:
            self.stat_bytes_pumped.configure(text=f"{mb:.1f} MB")

        self.after(500, self._poll_ui_telemetry)

    def _toggle_proxy_engine(self):
        if self.proxy_engine.is_running:
            self.proxy_engine.stop()
            self.btn_toggle_engine.configure(
                text="START RQL CONDUIT [127.0.0.1:1080]",
                fg_color=self.COLOR_ACCENT_GREEN,
                hover_color="#047857"
            )
        else:
            self.proxy_engine.start(self.adapters)
            self.btn_toggle_engine.configure(
                text="STOP RQL CONDUIT [ACTIVE: 1080]",
                fg_color=self.COLOR_ACCENT_RED,
                hover_color="#be123c"
            )

    def _on_mode_changed(self, choice: str):
        if "Latency" in choice:
            self.proxy_engine.chassis.routing_mode = RoutingMode.LOWEST_LATENCY
        elif "Failover" in choice:
            self.proxy_engine.chassis.routing_mode = RoutingMode.FAILOVER_STANDBY
        else:
            self.proxy_engine.chassis.routing_mode = RoutingMode.STRIP_MINING
        self._on_proxy_log(f"Routing policy updated: {choice}")

    def _toggle_windows_system_proxy(self):
        is_on, _ = WindowsSystemProxyManager.is_proxy_enabled()
        if is_on:
            WindowsSystemProxyManager.disable_system_proxy()
            self.btn_sys_proxy.configure(text="Enable Windows WinINet Proxy", fg_color="#2563eb")
            self._on_proxy_log("Windows WinINet system proxy disabled.")
        else:
            WindowsSystemProxyManager.set_system_proxy("127.0.0.1", 1080)
            self.btn_sys_proxy.configure(text="WinINet Proxy Active [1080]", fg_color=self.COLOR_ACCENT_GREEN)
            self._on_proxy_log("Windows WinINet system proxy enabled [127.0.0.1:1080].")

    def _check_initial_sys_proxy(self):
        is_on, _ = WindowsSystemProxyManager.is_proxy_enabled()
        if is_on:
            self.btn_sys_proxy.configure(text="WinINet Proxy Active [1080]", fg_color=self.COLOR_ACCENT_GREEN)
        else:
            self.btn_sys_proxy.configure(text="Enable Windows WinINet Proxy", fg_color="#2563eb")

    def _toggle_handbrake(self):
        chassis = self.proxy_engine.chassis
        if chassis.handbrake_engaged:
            chassis.release_handbrake()
            self.btn_handbrake.configure(text="PIN TO PRIMARY INTERFACE", fg_color=self.COLOR_ACCENT_RED)
            self._on_proxy_log("Static pinning released. Dynamic multi-interface dispatch restored.")
        else:
            usable = [a for a in self.adapters if a.is_usable_for_traffic()]
            if usable:
                pinned = usable[0].name
                chassis.engage_handbrake(pinned)
                self.btn_handbrake.configure(text=f"RELEASE PINNING [{pinned}]", fg_color="#9f1239")
                self._on_proxy_log(f"Static policy override: All outbound connections pinned to {pinned}.")

    def _on_proxy_log(self, msg: str):
        if self._closing:
            return
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {msg}\n"
        self.after(0, lambda: self._append_log(formatted))

    def _append_log(self, text: str):
        try:
            self.log_textbox.insert("end", text)
            self.log_textbox.see("end")
        except Exception:
            pass

    def _on_close(self):
        self._closing = True
        self.radar.stop()
        self.proxy_engine.stop()
        self.destroy()


def main():
    app = RQLConduitGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
