"""
SOVEREIGN CONDUIT — SUN TZU JITTER & LATENCY TERRAIN RADAR
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Invariant: "Every battle is won before it is fought."
Continuous microsecond probe of local adapters.
Detects congestion, jitter, and packet loss before routing critical sockets.
"""

import socket
import time
import threading
from typing import List, Dict, Callable, Optional
from core.adapter_discovery import AdapterInfo


class SunTzuJitterRadar:
    """
    Background terrain probe daemon.
    Binds test probes to each physical adapter IP and measures true network latency & jitter.
    """

    CANARY_TARGETS = [
        ("1.1.1.1", 53),   # Cloudflare Primary DNS
        ("8.8.8.8", 53),   # Google Primary DNS
        ("1.0.0.1", 53),   # Cloudflare Secondary DNS
    ]

    def __init__(self, check_interval_sec: float = 1.5, on_update_callback: Optional[Callable] = None):
        self.check_interval_sec = check_interval_sec
        self.on_update_callback = on_update_callback
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._latency_history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def start(self, adapters: List[AdapterInfo]):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._radar_loop, args=(adapters,), daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def probe_adapter(self, adapter: AdapterInfo) -> Dict[str, float]:
        """
        Binds a raw TCP connection to the specific adapter's local IP address
        and measures the round-trip latency to a reliable canary target.
        """
        if not adapter.is_usable_for_traffic():
            return {"ping_ms": 999.0, "jitter_ms": 0.0, "packet_loss_pct": 100.0}

        rtts: List[float] = []
        failures = 0
        attempts = 2

        for i in range(attempts):
            target_ip, target_port = self.CANARY_TARGETS[i % len(self.CANARY_TARGETS)]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.2)
            try:
                # Bind specifically to this adapter IP
                s.bind((adapter.ip_address, 0))
                t0 = time.perf_counter()
                s.connect((target_ip, target_port))
                t1 = time.perf_counter()
                rtt_ms = (t1 - t0) * 1000.0
                rtts.append(rtt_ms)
            except Exception:
                failures += 1
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        with self._lock:
            if adapter.ip_address not in self._latency_history:
                self._latency_history[adapter.ip_address] = []
            history = self._latency_history[adapter.ip_address]

            if rtts:
                avg_ping = sum(rtts) / len(rtts)
                history.append(avg_ping)
                if len(history) > 10:
                    history.pop(0)

                # Compute Jitter as average absolute delta between consecutive ping samples
                if len(history) >= 2:
                    deltas = [abs(history[j] - history[j - 1]) for j in range(1, len(history))]
                    jitter = sum(deltas) / len(deltas)
                else:
                    jitter = 1.0

                loss_pct = (failures / attempts) * 100.0
            else:
                avg_ping = 999.0
                jitter = 99.0
                loss_pct = 100.0

        # Layer 1: 3-Point Seatbelt Invariant
        # Quarantine adapter if packet loss > 20% or latency > 400ms
        is_quarantined = loss_pct >= 50.0 or avg_ping > 450.0

        adapter.ping_ms = round(avg_ping, 1)
        adapter.jitter_ms = round(jitter, 1)
        adapter.packet_loss_pct = round(loss_pct, 1)
        adapter.is_quarantined = is_quarantined

        if is_quarantined:
            adapter.status_label = "Quarantined"
        elif adapter.ping_ms < 35.0:
            adapter.status_label = "Optimal"
        elif adapter.ping_ms < 100.0:
            adapter.status_label = "Good"
        else:
            adapter.status_label = "Degraded"

        return {
            "ping_ms": adapter.ping_ms,
            "jitter_ms": adapter.jitter_ms,
            "packet_loss_pct": adapter.packet_loss_pct,
            "quarantined": adapter.is_quarantined,
        }

    def _radar_loop(self, adapters: List[AdapterInfo]):
        while self.is_running:
            for adapter in list(adapters):
                if not self.is_running:
                    break
                self.probe_adapter(adapter)

            if self.on_update_callback:
                try:
                    self.on_update_callback()
                except Exception:
                    pass

            time.sleep(self.check_interval_sec)
