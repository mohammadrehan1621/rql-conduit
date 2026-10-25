"""
SOVEREIGN CONDUIT — NETWORK ADAPTER DISCOVERY ENGINE
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Invariant: Deterministic, non-invasive OS network interface enumeration.
Zero virtual driver dependencies. Zero administrative requirement.
"""

import socket
import psutil
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class AdapterInfo:
    name: str
    ip_address: str
    netmask: str = "255.255.255.0"
    mac_address: str = ""
    speed_mbps: int = 0
    is_up: bool = False
    is_valid_route: bool = True
    ping_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_pct: float = 0.0
    total_bytes_sent: int = 0
    total_bytes_recv: int = 0
    assigned_weight: int = 1
    is_quarantined: bool = False
    status_label: str = "Active"

    def is_usable_for_traffic(self) -> bool:
        """Determines if the adapter has a valid routable IP and is not quarantined."""
        if not self.is_up:
            return False
        if self.is_quarantined:
            return False
        if not self.ip_address or self.ip_address == "0.0.0.0":
            return False
        if self.ip_address.startswith("127.") or self.ip_address.startswith("169.254."):
            # Loopback or APIPA unassigned address
            return False
        return True


class NetworkDiscoveryManager:
    """Discovers and tracks physical and virtual network interfaces."""

    @staticmethod
    def get_active_adapters() -> List[AdapterInfo]:
        adapters: List[AdapterInfo] = []
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        for if_name, addrs in net_if_addrs.items():
            ipv4_addr: Optional[str] = None
            netmask: str = "255.255.255.0"
            mac_addr: str = ""

            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ipv4_addr = addr.address
                    if addr.netmask:
                        netmask = addr.netmask
                elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                    mac_addr = addr.address
                elif getattr(socket, "AF_LINK", -1) == addr.family:
                    mac_addr = addr.address

            if not ipv4_addr or ipv4_addr.startswith("127."):
                continue

            stats = net_if_stats.get(if_name)
            is_up = stats.isup if stats else False
            speed = stats.speed if stats else 0

            io = io_counters.get(if_name)
            bytes_sent = io.bytes_sent if io else 0
            bytes_recv = io.bytes_recv if io else 0

            # Filter out APIPA addresses from active usable pool
            is_apipa = ipv4_addr.startswith("169.254.")
            is_valid = is_up and not is_apipa

            status = "Ready" if is_valid else ("APIPA" if is_apipa else "Down")

            adapter = AdapterInfo(
                name=if_name,
                ip_address=ipv4_addr,
                netmask=netmask,
                mac_address=mac_addr,
                speed_mbps=speed,
                is_up=is_up,
                is_valid_route=is_valid,
                total_bytes_sent=bytes_sent,
                total_bytes_recv=bytes_recv,
                status_label=status,
            )
            adapters.append(adapter)

        # Sort so currently routable adapters appear first
        adapters.sort(key=lambda a: (a.is_usable_for_traffic(), a.speed_mbps), reverse=True)
        return adapters
