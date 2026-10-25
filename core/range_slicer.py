"""
RQL CONDUIT — TRANSPARENT HTTP RANGE-SLICING AGGREGATION ENGINE
Principal Architect: Mohammad Rehan • Rehan Quant Lab

Bypasses the single-stream TCP bottleneck by decomposing large HTTP payloads
into K parallel byte-range requests distributed concurrently across multiple WAN links.
"""

import socket
import threading
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class RangeSliceTask:
    def __init__(self, index: int, start_byte: int, end_byte: int, adapter_ip: str):
        self.index = index
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.adapter_ip = adapter_ip
        self.data = bytearray()
        self.is_completed = False
        self.error: Optional[str] = None


class HttpRangeSlicingEngine:
    """
    Parallel multi-WAN byte-range multiplexer.
    Splits a single download stream into parallel chunks routed across independent NICs.
    """

    CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB default sub-slice

    def __init__(self, candidate_ips: List[str]):
        self.candidate_ips = [ip for ip in candidate_ips if ip and not ip.startswith("127.")]
        self.total_bytes_aggregated = 0

    def compute_ranges(self, content_length: int, chunk_size: int = CHUNK_SIZE) -> List[RangeSliceTask]:
        """Calculates discrete byte ranges and assigns them round-robin to network adapters."""
        if not self.candidate_ips:
            raise ValueError("No candidate egress network adapters available for range-slicing.")

        tasks = []
        num_adapters = len(self.candidate_ips)
        start = 0
        idx = 0

        while start < content_length:
            end = min(start + chunk_size - 1, content_length - 1)
            adapter_ip = self.candidate_ips[idx % num_adapters]
            tasks.append(RangeSliceTask(index=idx, start_byte=start, end_byte=end, adapter_ip=adapter_ip))
            start = end + 1
            idx += 1

        return tasks

    def fetch_slice_socket(
        self,
        host: str,
        port: int,
        path: str,
        task: RangeSliceTask,
        timeout_sec: float = 10.0,
    ) -> bool:
        """Fetches a specific byte slice by binding explicitly to the assigned adapter IP."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(timeout_sec)

        try:
            sock.bind((task.adapter_ip, 0))
            sock.connect((host, port))

            # Send HTTP Range GET
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Range: bytes={task.start_byte}-{task.end_byte}\r\n"
                f"User-Agent: RQL-Conduit-RangeEngine/2.0\r\n"
                f"Connection: close\r\n\r\n"
            )
            sock.sendall(req.encode("utf-8"))

            # Drain headers
            header_buf = b""
            while b"\r\n\r\n" not in header_buf:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                header_buf += chunk

            if b"\r\n\r\n" not in header_buf:
                task.error = "Malformed HTTP response (no header terminator)"
                return False

            parts = header_buf.split(b"\r\n\r\n", 1)
            body_start = parts[1]
            task.data.extend(body_start)

            # Receive payload
            expected_len = (task.end_byte - task.start_byte) + 1
            while len(task.data) < expected_len:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                task.data.extend(chunk)

            task.is_completed = (len(task.data) >= expected_len)
            return task.is_completed

        except Exception as e:
            task.error = str(e)
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass
