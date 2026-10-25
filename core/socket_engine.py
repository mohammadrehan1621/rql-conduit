"""
SOVEREIGN CONDUIT — MULTI-WAN JET SOCKET PROXY ENGINE
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Invariant: Zero kernel driver overhead. Pure deterministic socket multiplexing.
Acts as a dual-protocol SOCKS5 + HTTP CONNECT proxy listening on 127.0.0.1:1080.
Binds outbound connections to physical network adapters with Volvo Airbag failover.
"""

import socket
import select
import struct
import threading
import time
from typing import List, Callable, Optional
from core.adapter_discovery import AdapterInfo
from core.volvo_chassis import VolvoSafetyChassis, RoutingMode
from core.rust_engine import RustConduitEngine


class SovereignSocketProxyServer:
    """
    High-performance SOCKS5 and HTTP proxy server with multi-WAN socket dispatching.
    Supports bare-metal Rust acceleration (rql_conduit_core.dll) with pure Python fallback.
    """

    BUFFER_SIZE = 65536  # 64 KB high-throughput chunks

    def __init__(self, host: str = "127.0.0.1", port: int = 1080, log_callback: Optional[Callable] = None):
        self.host = host
        self.port = port
        self.log_callback = log_callback
        self.is_running = False
        self.server_socket: Optional[socket.socket] = None
        self.chassis = VolvoSafetyChassis()
        self.adapters: List[AdapterInfo] = []
        self._thread: Optional[threading.Thread] = None
        self.active_sockets_count = 0
        self._stats_lock = threading.Lock()
        self.rust_engine: Optional[RustConduitEngine] = None
        self._using_rust = False

        try:
            self.rust_engine = RustConduitEngine()
        except Exception:
            self.rust_engine = None

    def set_adapters(self, adapters: List[AdapterInfo]):
        self.adapters = adapters
        if self._using_rust and self.rust_engine and self.rust_engine.is_loaded:
            usable_ips = [a.ip_address for a in adapters if a.is_usable_for_traffic()]
            self.rust_engine.set_adapters(usable_ips)

    def start(self, adapters: List[AdapterInfo]):
        if self.is_running:
            return
        self.adapters = adapters
        self.is_running = True

        # Attempt Bare-Metal Rust Engine Execution
        if self.rust_engine and self.rust_engine.is_loaded:
            usable_ips = [a.ip_address for a in adapters if a.is_usable_for_traffic()]
            self.rust_engine.set_adapters(usable_ips)

            mode_map = {
                RoutingMode.STRIP_MINING: 0,
                RoutingMode.LOWEST_LATENCY: 1,
                RoutingMode.FAILOVER_STANDBY: 2,
            }
            mode_int = mode_map.get(self.chassis.routing_mode, 0)
            self.rust_engine.set_routing_mode(mode_int)

            if self.chassis.handbrake_engaged and self.chassis.handbrake_pinned_adapter:
                pinned_ip = next((a.ip_address for a in adapters if a.name == self.chassis.handbrake_pinned_adapter), None)
                if pinned_ip:
                    self.rust_engine.engage_handbrake(pinned_ip)

            ok = self.rust_engine.start_proxy(self.host, self.port)
            if ok:
                self._using_rust = True
                self._log(f"⚡ Bare-Metal Rust Kernel (rql_conduit_core.dll) listening on {self.host}:{self.port} [Sub-50µs Latency]")
                return

        # Fallback to pure Python asynchronous sockets
        self._using_rust = False
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self._log(f"⚡ RQL Conduit Python Socket Engine listening on {self.host}:{self.port}")

    def stop(self):
        self.is_running = False
        if self._using_rust and self.rust_engine:
            self.rust_engine.stop_proxy()
            self._using_rust = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        self._log("🛑 RQL Conduit Proxy Engine stopped.")

    def get_telemetry(self) -> dict:
        if self._using_rust and self.rust_engine:
            stats = self.rust_engine.get_stats()
            return {
                "is_rust": True,
                "engine_name": "Bare-Metal Rust (rql_conduit_core.dll)",
                "active_conns": stats["active_conns"],
                "total_routed": stats["routed"],
                "failovers": stats["failovers"],
                "bytes_transferred": stats["tx_bytes"] + stats["rx_bytes"],
            }
        else:
            return {
                "is_rust": False,
                "engine_name": "Python C-Runtime Sockets",
                "active_conns": self.active_sockets_count,
                "total_routed": self.chassis.total_connections_routed,
                "failovers": self.chassis.total_failovers_caught,
                "bytes_transferred": self.chassis.total_bytes_transferred,
            }

    def _log(self, msg: str):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def _accept_loop(self):
        while self.is_running and self.server_socket:
            try:
                client_sock, client_addr = self.server_socket.accept()
                with self._stats_lock:
                    self.active_sockets_count += 1
                t = threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple):
        client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client_sock.settimeout(15.0)

        outbound_sock: Optional[socket.socket] = None
        used_adapter: Optional[AdapterInfo] = None

        try:
            peek_data = client_sock.recv(4, socket.MSG_PEEK)
            if not peek_data:
                return

            if peek_data[0] == 0x05:
                # SOCKS5 Protocol Handshake
                outbound_sock, used_adapter = self._process_socks5(client_sock)
            elif peek_data.startswith(b"CONN") or peek_data.startswith(b"GET ") or peek_data.startswith(b"POST"):
                # HTTP / HTTPS Proxy Protocol
                outbound_sock, used_adapter = self._process_http(client_sock)
            else:
                return

            if not outbound_sock or not used_adapter:
                return

            # Pipe bi-directionally
            self._pipe_relay(client_sock, outbound_sock, used_adapter)

        except Exception:
            pass
        finally:
            with self._stats_lock:
                self.active_sockets_count = max(0, self.active_sockets_count - 1)
            try:
                client_sock.close()
            except Exception:
                pass
            if outbound_sock:
                try:
                    outbound_sock.close()
                except Exception:
                    pass

    def _process_socks5(self, client_sock: socket.socket) -> tuple:
        """Parses RFC 1928 SOCKS5 and establishes outbound connection."""
        # 1. Version identifier / method selection
        greet = client_sock.recv(2)
        if len(greet) < 2 or greet[0] != 0x05:
            return None, None
        nmethods = greet[1]
        methods = client_sock.recv(nmethods)

        # Reply: No authentication required (\x05\x00)
        client_sock.sendall(b"\x05\x00")

        # 2. Connection request
        req_hdr = client_sock.recv(4)
        if len(req_hdr) < 4 or req_hdr[1] != 0x01:  # Only CONNECT cmd supported
            return None, None

        addr_type = req_hdr[3]
        target_host: str = ""

        if addr_type == 0x01:  # IPv4
            raw_ip = client_sock.recv(4)
            target_host = socket.inet_ntoa(raw_ip)
        elif addr_type == 0x03:  # Domain Name
            domain_len = client_sock.recv(1)[0]
            target_host = client_sock.recv(domain_len).decode("utf-8", errors="ignore")
        elif addr_type == 0x04:  # IPv6
            raw_ip6 = client_sock.recv(16)
            target_host = socket.inet_ntop(socket.AF_INET6, raw_ip6)
        else:
            return None, None

        port_data = client_sock.recv(2)
        target_port = struct.unpack("!H", port_data)[0]

        # 3. Create outbound socket using Volvo Airbag
        outbound_sock, adapter = self.chassis.create_airbag_outbound_socket(
            target_host, target_port, self.adapters
        )

        if not outbound_sock or not adapter:
            # SOCKS5 General failure (\x05\x01)
            client_sock.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            return None, None

        # SOCKS5 Success (\x05\x00)
        client_sock.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        self._log(f"🔗 Routed SOCKS5 [{target_host}:{target_port}] via [{adapter.name} @ {adapter.ip_address}]")
        return outbound_sock, adapter

    def _process_http(self, client_sock: socket.socket) -> tuple:
        """Parses HTTP CONNECT and plain HTTP requests."""
        line = b""
        while b"\r\n" not in line:
            chunk = client_sock.recv(1)
            if not chunk:
                return None, None
            line += chunk

        first_line = line.decode("utf-8", errors="ignore").strip()
        parts = first_line.split(" ")
        if len(parts) < 2:
            return None, None

        method, target = parts[0], parts[1]

        # Drain headers until \r\n\r\n
        remaining_headers = b""
        while b"\r\n\r\n" not in remaining_headers:
            chunk = client_sock.recv(1024)
            if not chunk:
                break
            remaining_headers += chunk

        if method.upper() == "CONNECT":
            # CONNECT host:443 HTTP/1.1
            host_port = target.split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 443

            outbound_sock, adapter = self.chassis.create_airbag_outbound_socket(
                host, port, self.adapters
            )

            if not outbound_sock or not adapter:
                client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return None, None

            client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._log(f"🔗 Routed HTTPS CONNECT [{host}:{port}] via [{adapter.name} @ {adapter.ip_address}]")
            return outbound_sock, adapter

        else:
            # Plain HTTP GET/POST: e.g. http://example.com/path
            from urllib.parse import urlparse
            parsed = urlparse(target)
            host = parsed.hostname or target.split("/")[0]
            port = parsed.port or 80

            outbound_sock, adapter = self.chassis.create_airbag_outbound_socket(
                host, port, self.adapters
            )
            if not outbound_sock or not adapter:
                client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return None, None

            # Forward the original HTTP request line + headers
            raw_req = line + remaining_headers
            outbound_sock.sendall(raw_req)
            self._log(f"🔗 Routed HTTP [{host}:{port}] via [{adapter.name} @ {adapter.ip_address}]")
            return outbound_sock, adapter

    def _pipe_relay(self, client_sock: socket.socket, outbound_sock: socket.socket, adapter: AdapterInfo):
        """Bi-directional non-blocking socket data pump."""
        sockets = [client_sock, outbound_sock]
        client_sock.setblocking(False)
        outbound_sock.setblocking(False)

        while self.is_running:
            readable, _, exceptional = select.select(sockets, [], sockets, 10.0)
            if exceptional:
                break
            if not readable:
                continue

            for s in readable:
                other = outbound_sock if s is client_sock else client_sock
                try:
                    data = s.recv(self.BUFFER_SIZE)
                    if not data:
                        return
                    other.sendall(data)

                    # Track byte counters
                    byte_len = len(data)
                    self.chassis.total_bytes_transferred += byte_len
                    if s is outbound_sock:
                        adapter.total_bytes_recv += byte_len
                    else:
                        adapter.total_bytes_sent += byte_len

                except Exception:
                    return
