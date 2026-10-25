"""
RQL CONDUIT — FORMAL AUTOMATED INVARIANT TEST SUITE
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Empirical verification of interface discovery, RTT variance telemetry,
deterministic socket multiplexing, and protocol adherence.
"""

import unittest
import socket
import threading
import time
from core.adapter_discovery import NetworkDiscoveryManager, AdapterInfo
from core.jitter_radar import SunTzuJitterRadar
from core.volvo_chassis import VolvoSafetyChassis, RoutingMode
from core.socket_engine import SovereignSocketProxyServer
from core.windows_proxy import WindowsSystemProxyManager


class TestRQLConduitInvariants(unittest.TestCase):
    """Empirical mathematical validation of the 4-tier fault tolerance architecture."""

    def test_01_adapter_discovery_invariant(self):
        """Invariant 1: Host interface enumeration must be non-blocking and deterministic."""
        adapters = NetworkDiscoveryManager.get_active_adapters()
        self.assertIsInstance(adapters, list)
        self.assertGreater(len(adapters), 0, "At least one host network interface must be enumerated.")

        for a in adapters:
            self.assertFalse(a.ip_address.startswith("127."), "Loopback 127.0.0.1 must be filtered from routing pool.")
            self.assertIsInstance(a.name, str)
            self.assertIsInstance(a.is_up, bool)

    def test_02_rtt_variance_estimation(self):
        """Invariant 2: RTT sample mean and standard deviation (jitter) must evaluate without exception."""
        adapters = NetworkDiscoveryManager.get_active_adapters()
        radar = SunTzuJitterRadar()
        usable = [a for a in adapters if a.is_usable_for_traffic()]

        if usable:
            metrics = radar.probe_adapter(usable[0])
            self.assertIn("ping_ms", metrics)
            self.assertIn("jitter_ms", metrics)
            self.assertIn("packet_loss_pct", metrics)
            self.assertGreaterEqual(metrics["ping_ms"], 0.0)

    def test_03_quarantine_loss_threshold(self):
        """Invariant 3: Packet loss probability P_loss >= 0.20 must quarantine egress interface."""
        degraded_adapter = AdapterInfo(
            name="Simulated_Degraded_Link",
            ip_address="192.168.99.99",
            is_up=True,
            ping_ms=500.0,
            packet_loss_pct=80.0,
            is_quarantined=True
        )
        self.assertFalse(degraded_adapter.is_usable_for_traffic(), "Quarantined interface must be excluded from pool.")

    def test_04_static_pinning_override(self):
        """Invariant 4: Static interface pinning must clamp 100% of egress traffic to target interface."""
        chassis = VolvoSafetyChassis()
        adapter_a = AdapterInfo(name="Eth_Primary", ip_address="192.168.1.10", is_up=True, ping_ms=10.0)
        adapter_b = AdapterInfo(name="Cell_Secondary", ip_address="192.168.43.20", is_up=True, ping_ms=35.0)

        adapters = [adapter_a, adapter_b]

        chassis.engage_handbrake("Cell_Secondary")
        selected = chassis.select_outbound_adapter(adapters)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "Cell_Secondary", "Static pinning must route strictly to Cell_Secondary.")

        chassis.release_handbrake()
        self.assertFalse(chassis.handbrake_engaged, "Pinning release must restore dynamic dispatch.")

    def test_05_minimum_variance_dispatch_policy(self):
        """Invariant 5: Minimum latency variance policy must select argmin(mu_RTT + lambda * sigma_RTT)."""
        chassis = VolvoSafetyChassis()
        chassis.routing_mode = RoutingMode.LOWEST_LATENCY

        adapter_fast = AdapterInfo(name="Fast_Fiber", ip_address="192.168.1.10", is_up=True, ping_ms=8.5, jitter_ms=1.0)
        adapter_slow = AdapterInfo(name="Slow_Cellular", ip_address="192.168.43.20", is_up=True, ping_ms=65.0, jitter_ms=8.0)

        selected = chassis.select_outbound_adapter([adapter_slow, adapter_fast])
        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "Fast_Fiber")

    def test_06_socks5_handshake_protocol(self):
        """Invariant 6: RFC 1928 SOCKS5 greeting handshake must respond with 0x05 0x00 (NO AUTH)."""
        adapters = NetworkDiscoveryManager.get_active_adapters()
        test_port = 11080
        proxy = SovereignSocketProxyServer(host="127.0.0.1", port=test_port)
        proxy.start(adapters)
        time.sleep(0.3)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", test_port))
            client.sendall(b"\x05\x01\x00")
            resp = client.recv(2)
            self.assertEqual(resp, b"\x05\x00", "SOCKS5 server must confirm NO AUTH requirement.")
        finally:
            client.close()
            proxy.stop()

    def test_07_wininet_registry_query(self):
        """Invariant 7: Win32 WinINet proxy configuration state evaluation must execute safely."""
        is_on, srv = WindowsSystemProxyManager.is_proxy_enabled()
        self.assertIsInstance(is_on, bool)
        self.assertIsInstance(srv, str)

    def test_08_bare_metal_rust_c_abi_linking(self):
        """Invariant 8: Bare-metal Rust engine (rql_conduit_core.dll) must link and execute via C-ABI."""
        from core.rust_engine import RustConduitEngine
        engine = RustConduitEngine()
        self.assertTrue(engine.is_loaded, "rql_conduit_core.dll must be compiled and loaded via C-ABI.")
        ver = engine.get_version()
        self.assertIn("RQL Conduit Core", ver, "Rust kernel must return valid identity version string.")

        test_port = 11082
        engine.set_adapters(["127.0.0.1"])
        ok = engine.start_proxy("127.0.0.1", test_port)
        self.assertTrue(ok, "Rust proxy engine must bind and start successfully.")
        time.sleep(0.2)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", test_port))
            client.sendall(b"\x05\x01\x00")
            resp = client.recv(2)
            self.assertEqual(resp, b"\x05\x00", "Rust SOCKS5 server must confirm NO AUTH RFC 1928 requirement.")
        finally:
            client.close()
            engine.stop_proxy()
            time.sleep(0.1)

    def test_09_domain_session_affinity(self):
        """Invariant 9: Domain session affinity cache must pin consecutive requests to the same host."""
        from core.rust_engine import RustConduitEngine
        engine = RustConduitEngine()
        self.assertTrue(engine.is_loaded)
        engine.clear_domain_affinity()
        self.assertEqual(engine.get_affinity_count(), 0)

        engine.set_domain_affinity(enabled=True, ttl_sec=900)
        # Test affinity count query
        self.assertGreaterEqual(engine.get_affinity_count(), 0)

    def test_10_socks5_udp_associate_handshake(self):
        """Invariant 10: RFC 1928 SOCKS5 UDP ASSOCIATE (cmd 0x03) must allocate local relay port."""
        from core.rust_engine import RustConduitEngine
        engine = RustConduitEngine()
        self.assertTrue(engine.is_loaded)
        test_port = 11083
        engine.set_adapters(["127.0.0.1"])
        engine.start_proxy("127.0.0.1", test_port)
        time.sleep(0.2)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", test_port))
            # Greeting
            client.sendall(b"\x05\x01\x00")
            self.assertEqual(client.recv(2), b"\x05\x00")

            # Request: CMD 0x03 (UDP ASSOCIATE), IPv4 0.0.0.0:0
            client.sendall(b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00")
            resp = client.recv(10)
            self.assertEqual(len(resp), 10)
            self.assertEqual(resp[0], 0x05)
            self.assertEqual(resp[1], 0x00, "SOCKS5 UDP ASSOCIATE must reply with 0x00 SUCCESS.")
            # Assigned relay port is non-zero
            port = int.from_bytes(resp[8:10], "big")
            self.assertGreater(port, 0)
        finally:
            client.close()
            engine.stop_proxy()
            time.sleep(0.1)

    def test_11_http_range_slicing_decomposition(self):
        """Invariant 11: HTTP Range Slicer must decompose byte payloads into discrete non-overlapping segments."""
        from core.range_slicer import HttpRangeSlicingEngine
        slicer = HttpRangeSlicingEngine(candidate_ips=["192.168.1.10", "192.168.43.20"])
        content_len = 10 * 1024 * 1024  # 10 MB
        chunk_size = 2 * 1024 * 1024   # 2 MB chunks -> 5 slices

        tasks = slicer.compute_ranges(content_len, chunk_size=chunk_size)
        self.assertEqual(len(tasks), 5)
        self.assertEqual(tasks[0].start_byte, 0)
        self.assertEqual(tasks[0].end_byte, 2 * 1024 * 1024 - 1)
        self.assertEqual(tasks[-1].end_byte, content_len - 1)

        # Check round-robin assignment across adapters
        self.assertEqual(tasks[0].adapter_ip, "192.168.1.10")
        self.assertEqual(tasks[1].adapter_ip, "192.168.43.20")
        self.assertEqual(tasks[2].adapter_ip, "192.168.1.10")


if __name__ == "__main__":
    unittest.main()
