"""
RQL CONDUIT — BARE-METAL RUST C-ABI ENGINE CONNECTOR
Principal Architect: Mohammad Rehan • Rehan Quant Lab

High-Performance C-ABI Dynamic Linker for rql_conduit_core.dll.
Provides sub-microsecond socket switching, zero GC pauses,
and deterministic multi-WAN socket dispatching directly from Rust.
"""

import os
import sys
import ctypes
from typing import List, Optional, Tuple, Dict, Any


class RustConduitEngine:
    """
    Python ctypes wrapper around the bare-metal Rust rql_conduit_core.dll.
    """

    _instance = None
    _dll: Optional[ctypes.CDLL] = None

    def __init__(self, dll_path: Optional[str] = None):
        self.dll_path = self._resolve_dll_path(dll_path)
        self.is_loaded = False
        self._init_dll()

    @staticmethod
    def _resolve_dll_path(explicit_path: Optional[str] = None) -> Optional[str]:
        if explicit_path and os.path.exists(explicit_path):
            return explicit_path

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(base_dir, "rql_conduit_core.dll"),
            os.path.join(base_dir, "rql-conduit-rs", "target", "release", "rql_conduit_core.dll"),
            os.path.join(os.getcwd(), "rql_conduit_core.dll"),
            os.path.join(os.getcwd(), "rql-conduit-rs", "target", "release", "rql_conduit_core.dll"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _init_dll(self):
        if not self.dll_path or not os.path.exists(self.dll_path):
            return

        try:
            self._dll = ctypes.CDLL(self.dll_path)

            # conduit_version() -> *const c_char
            self._dll.conduit_version.argtypes = []
            self._dll.conduit_version.restype = ctypes.c_char_p

            # conduit_init() -> c_int
            self._dll.conduit_init.argtypes = []
            self._dll.conduit_init.restype = ctypes.c_int

            # conduit_add_adapter(ip_str: *const c_char) -> c_int
            self._dll.conduit_add_adapter.argtypes = [ctypes.c_char_p]
            self._dll.conduit_add_adapter.restype = ctypes.c_int

            # conduit_clear_adapters() -> c_int
            self._dll.conduit_clear_adapters.argtypes = []
            self._dll.conduit_clear_adapters.restype = ctypes.c_int

            # conduit_set_routing_mode(mode: u32) -> c_int
            self._dll.conduit_set_routing_mode.argtypes = [ctypes.c_uint32]
            self._dll.conduit_set_routing_mode.restype = ctypes.c_int

            # conduit_engage_handbrake(pinned_ip: *const c_char) -> c_int
            self._dll.conduit_engage_handbrake.argtypes = [ctypes.c_char_p]
            self._dll.conduit_engage_handbrake.restype = ctypes.c_int

            # conduit_release_handbrake() -> c_int
            self._dll.conduit_release_handbrake.argtypes = []
            self._dll.conduit_release_handbrake.restype = ctypes.c_int

            # conduit_set_domain_affinity(enabled: c_int, ttl_sec: u32) -> c_int
            self._dll.conduit_set_domain_affinity.argtypes = [ctypes.c_int, ctypes.c_uint32]
            self._dll.conduit_set_domain_affinity.restype = ctypes.c_int

            # conduit_clear_domain_affinity() -> c_int
            self._dll.conduit_clear_domain_affinity.argtypes = []
            self._dll.conduit_clear_domain_affinity.restype = ctypes.c_int

            # conduit_get_affinity_count() -> u32
            self._dll.conduit_get_affinity_count.argtypes = []
            self._dll.conduit_get_affinity_count.restype = ctypes.c_uint32

            # conduit_start_proxy(bind_ip: *const c_char, port: u16) -> c_int
            self._dll.conduit_start_proxy.argtypes = [ctypes.c_char_p, ctypes.c_uint16]
            self._dll.conduit_start_proxy.restype = ctypes.c_int

            # conduit_stop_proxy() -> c_int
            self._dll.conduit_stop_proxy.argtypes = []
            self._dll.conduit_stop_proxy.restype = ctypes.c_int

            # conduit_is_running() -> c_int
            self._dll.conduit_is_running.argtypes = []
            self._dll.conduit_is_running.restype = ctypes.c_int

            # conduit_get_stats(out_tx, out_rx, out_active, out_failovers, out_routed) -> c_int
            self._dll.conduit_get_stats.argtypes = [
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_uint64),
            ]
            self._dll.conduit_get_stats.restype = ctypes.c_int

            # conduit_probe_rtt_us(ip_str: *const c_char, port: u16, timeout_ms: u32) -> f64
            self._dll.conduit_probe_rtt_us.argtypes = [ctypes.c_char_p, ctypes.c_uint16, ctypes.c_uint32]
            self._dll.conduit_probe_rtt_us.restype = ctypes.c_double

            self._dll.conduit_init()
            self.is_loaded = True
        except Exception:
            self.is_loaded = False
            self._dll = None

    def get_version(self) -> str:
        if not self.is_loaded or not self._dll:
            return "Rust Engine Not Loaded"
        try:
            val = self._dll.conduit_version()
            return val.decode("utf-8") if val else ""
        except Exception:
            return "Unknown"

    def set_adapters(self, ip_addresses: List[str]):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_clear_adapters()
        for ip in ip_addresses:
            self._dll.conduit_add_adapter(ip.encode("utf-8"))

    def set_routing_mode(self, mode: int):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_set_routing_mode(mode)

    def engage_handbrake(self, pinned_ip: str):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_engage_handbrake(pinned_ip.encode("utf-8"))

    def release_handbrake(self):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_release_handbrake()

    def start_proxy(self, host: str = "127.0.0.1", port: int = 1080) -> bool:
        if not self.is_loaded or not self._dll:
            return False
        res = self._dll.conduit_start_proxy(host.encode("utf-8"), port)
        return res == 0

    def stop_proxy(self):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_stop_proxy()

    def is_running(self) -> bool:
        if not self.is_loaded or not self._dll:
            return False
        return self._dll.conduit_is_running() == 1

    def get_stats(self) -> Dict[str, Any]:
        if not self.is_loaded or not self._dll:
            return {"tx_bytes": 0, "rx_bytes": 0, "active_conns": 0, "failovers": 0, "routed": 0}

        tx = ctypes.c_uint64(0)
        rx = ctypes.c_uint64(0)
        active = ctypes.c_uint32(0)
        failovers = ctypes.c_uint32(0)
        routed = ctypes.c_uint64(0)

        self._dll.conduit_get_stats(
            ctypes.byref(tx),
            ctypes.byref(rx),
            ctypes.byref(active),
            ctypes.byref(failovers),
            ctypes.byref(routed),
        )

        return {
            "tx_bytes": tx.value,
            "rx_bytes": rx.value,
            "active_conns": active.value,
            "failovers": failovers.value,
            "routed": routed.value,
        }

    def probe_rtt_microseconds(self, ip: str, port: int = 80, timeout_ms: int = 2000) -> float:
        if not self.is_loaded or not self._dll:
            return -1.0
        return float(self._dll.conduit_probe_rtt_us(ip.encode("utf-8"), port, timeout_ms))

    def set_domain_affinity(self, enabled: bool = True, ttl_sec: int = 900):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_set_domain_affinity(1 if enabled else 0, ttl_sec)

    def clear_domain_affinity(self):
        if not self.is_loaded or not self._dll:
            return
        self._dll.conduit_clear_domain_affinity()

    def get_affinity_count(self) -> int:
        if not self.is_loaded or not self._dll:
            return 0
        return int(self._dll.conduit_get_affinity_count())
