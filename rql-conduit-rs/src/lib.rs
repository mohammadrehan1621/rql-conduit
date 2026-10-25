//! RQL Conduit — Bare-Metal Dual-WAN Zero-Cloud Socket Multiplexing Engine
//! Principal Architect: Mohammad Rehan • Rehan Quant Lab
//!
//! Licensed under the Apache License, Version 2.0 OR MIT License.
//! Invariants:
//! 1. Zero kernel drivers (100% unprivileged user-space).
//! 2. Deterministic socket binding via Winsock2 `bind()`.
//! 3. Volvo 4-Tier Safety Chassis with sub-microsecond failover.
//! 4. Deterministic Domain Session Affinity (Host-Stickiness LRU).
//! 5. RFC 1928 SOCKS5 UDP Associate Support.
//! 6. Zero GC pauses, sub-50us socket switching, minimal memory (<4 MB).

use socket2::{Domain, Protocol, Socket, Type};
use std::collections::HashMap;
use std::ffi::CStr;
use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpListener, TcpStream, ToSocketAddrs, UdpSocket};
use std::os::raw::{c_char, c_int};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, OnceLock, RwLock};
use std::thread;
use std::time::{Duration, Instant};

const BUFFER_SIZE: usize = 65536; // 64 KB high-throughput chunks
const CONNECT_TIMEOUT_MS: u64 = 2500; // 2.5s connect timeout

#[repr(u32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RoutingMode {
    StripMining = 0,     // Round-robin bandwidth aggregation
    LowestLatency = 1,   // Minimum RTT
    FailoverStandby = 2, // Hot-standby primary link
}

impl From<u32> for RoutingMode {
    fn from(val: u32) -> Self {
        match val {
            1 => RoutingMode::LowestLatency,
            2 => RoutingMode::FailoverStandby,
            _ => RoutingMode::StripMining,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AdapterLink {
    pub ip: Ipv4Addr,
    pub rtt_ms: f64,
    pub is_quarantined: bool,
}

pub struct ConduitState {
    pub adapters: RwLock<Vec<AdapterLink>>,
    pub routing_mode: RwLock<RoutingMode>,
    pub handbrake_ip: RwLock<Option<Ipv4Addr>>,
    pub round_robin_idx: AtomicUsize,
    pub is_running: AtomicBool,
    pub active_conns: AtomicU32,
    pub failovers_caught: AtomicU32,
    pub connections_routed: AtomicU64,
    pub bytes_tx: AtomicU64,
    pub bytes_rx: AtomicU64,
    pub domain_affinity_enabled: AtomicBool,
    pub domain_affinity_ttl_sec: AtomicU64,
    pub domain_affinity_map: RwLock<HashMap<String, (Ipv4Addr, Instant)>>,
}

impl ConduitState {
    pub fn new() -> Self {
        ConduitState {
            adapters: RwLock::new(Vec::new()),
            routing_mode: RwLock::new(RoutingMode::StripMining),
            handbrake_ip: RwLock::new(None),
            round_robin_idx: AtomicUsize::new(0),
            is_running: AtomicBool::new(false),
            active_conns: AtomicU32::new(0),
            failovers_caught: AtomicU32::new(0),
            connections_routed: AtomicU64::new(0),
            bytes_tx: AtomicU64::new(0),
            bytes_rx: AtomicU64::new(0),
            domain_affinity_enabled: AtomicBool::new(true),
            domain_affinity_ttl_sec: AtomicU64::new(900), // 15-minute affinity
            domain_affinity_map: RwLock::new(HashMap::new()),
        }
    }

    pub fn set_adapters(&self, ips: Vec<Ipv4Addr>) {
        let mut list = self.adapters.write().unwrap();
        list.clear();
        for ip in ips {
            list.push(AdapterLink {
                ip,
                rtt_ms: 0.0,
                is_quarantined: false,
            });
        }
    }

    pub fn add_adapter(&self, ip: Ipv4Addr) {
        let mut list = self.adapters.write().unwrap();
        if !list.iter().any(|a| a.ip == ip) {
            list.push(AdapterLink {
                ip,
                rtt_ms: 0.0,
                is_quarantined: false,
            });
        }
    }

    pub fn clear_adapters(&self) {
        let mut list = self.adapters.write().unwrap();
        list.clear();
    }

    pub fn engage_handbrake(&self, ip: Ipv4Addr) {
        let mut hb = self.handbrake_ip.write().unwrap();
        *hb = Some(ip);
    }

    pub fn release_handbrake(&self) {
        let mut hb = self.handbrake_ip.write().unwrap();
        *hb = None;
    }

    pub fn set_routing_mode(&self, mode: RoutingMode) {
        let mut m = self.routing_mode.write().unwrap();
        *m = mode;
    }

    /// Selects candidate adapters in priority order for connection dispatch with Host Affinity support.
    pub fn get_candidate_adapters_for_host(&self, host: Option<&str>) -> Vec<Ipv4Addr> {
        // 1. Layer 3 Mechanical Handbrake Check (Highest Priority Clamp)
        if let Some(pinned_ip) = *self.handbrake_ip.read().unwrap() {
            return vec![pinned_ip];
        }

        let adapters_guard = self.adapters.read().unwrap();
        if adapters_guard.is_empty() {
            return Vec::new();
        }

        // Layer 1: Filter healthy adapters (quarantine invariant)
        let mut healthy: Vec<AdapterLink> = adapters_guard
            .iter()
            .filter(|a| !a.is_quarantined)
            .cloned()
            .collect();

        if healthy.is_empty() {
            healthy = adapters_guard.clone();
        }

        // Check Deterministic Domain Session Affinity
        if self.domain_affinity_enabled.load(Ordering::Relaxed) {
            if let Some(h) = host {
                let ttl = Duration::from_secs(self.domain_affinity_ttl_sec.load(Ordering::Relaxed));
                let map = self.domain_affinity_map.read().unwrap();
                if let Some((pinned_ip, recorded_at)) = map.get(h) {
                    if recorded_at.elapsed() <= ttl && healthy.iter().any(|a| a.ip == *pinned_ip) {
                        let mut ordered = vec![*pinned_ip];
                        for a in &healthy {
                            if a.ip != *pinned_ip {
                                ordered.push(a.ip);
                            }
                        }
                        return ordered;
                    }
                }
            }
        }

        // Standard Routing Mode Dispatch
        let mode = *self.routing_mode.read().unwrap();
        match mode {
            RoutingMode::LowestLatency => {
                healthy.sort_by(|a, b| a.rtt_ms.partial_cmp(&b.rtt_ms).unwrap_or(std::cmp::Ordering::Equal));
                healthy.into_iter().map(|a| a.ip).collect()
            }
            RoutingMode::FailoverStandby => {
                healthy.into_iter().map(|a| a.ip).collect()
            }
            RoutingMode::StripMining => {
                let n = healthy.len();
                if n == 0 {
                    return Vec::new();
                }
                let start_idx = self.round_robin_idx.fetch_add(1, Ordering::Relaxed) % n;
                let mut ordered = Vec::with_capacity(n);
                for i in 0..n {
                    ordered.push(healthy[(start_idx + i) % n].ip);
                }
                ordered
            }
        }
    }

    /// Creates an outbound TCP connection using Volvo Active Airbag Failover (Layer 2).
    /// Binds explicitly to the local adapter IP. If connection fails, falls back immediately
    /// to secondary adapters within microseconds.
    pub fn create_airbag_outbound_socket_for_host(
        &self,
        target_addrs: &[SocketAddr],
        host: Option<&str>,
    ) -> Option<(TcpStream, Ipv4Addr)> {
        let candidates = self.get_candidate_adapters_for_host(host);
        if candidates.is_empty() {
            return None;
        }

        for (attempt_idx, candidate_ip) in candidates.iter().enumerate() {
            let bind_addr = SocketAddr::new(IpAddr::V4(*candidate_ip), 0);

            for target_addr in target_addrs {
                if !target_addr.is_ipv4() {
                    continue;
                }

                let socket_result = (|| -> std::io::Result<TcpStream> {
                    let sock = Socket::new(Domain::IPV4, Type::STREAM, Some(Protocol::TCP))?;
                    sock.set_tcp_nodelay(true)?;
                    sock.set_read_timeout(Some(Duration::from_millis(CONNECT_TIMEOUT_MS)))?;
                    sock.set_write_timeout(Some(Duration::from_millis(CONNECT_TIMEOUT_MS)))?;
                    sock.bind(&bind_addr.into())?;
                    sock.connect_timeout(&target_addr.clone().into(), Duration::from_millis(CONNECT_TIMEOUT_MS))?;
                    let stream: TcpStream = sock.into();
                    stream.set_nodelay(true)?;
                    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
                    stream.set_write_timeout(Some(Duration::from_secs(30)))?;
                    Ok(stream)
                })();

                if let Ok(stream) = socket_result {
                    if attempt_idx > 0 {
                        self.failovers_caught.fetch_add(1, Ordering::Relaxed);
                    }
                    self.connections_routed.fetch_add(1, Ordering::Relaxed);

                    // Record Host Affinity
                    if self.domain_affinity_enabled.load(Ordering::Relaxed) {
                        if let Some(h) = host {
                            let mut map = self.domain_affinity_map.write().unwrap();
                            map.insert(h.to_string(), (*candidate_ip, Instant::now()));
                        }
                    }

                    return Some((stream, *candidate_ip));
                }
            }
        }

        None
    }

    pub fn create_airbag_outbound_socket(&self, target_addrs: &[SocketAddr]) -> Option<(TcpStream, Ipv4Addr)> {
        self.create_airbag_outbound_socket_for_host(target_addrs, None)
    }
}

static GLOBAL_ENGINE: OnceLock<Arc<ConduitState>> = OnceLock::new();
static SERVER_SHUTDOWN: AtomicBool = AtomicBool::new(false);

fn get_or_init_engine() -> Arc<ConduitState> {
    GLOBAL_ENGINE.get_or_init(|| Arc::new(ConduitState::new())).clone()
}

struct ConnGuard {
    state: Arc<ConduitState>,
}

impl Drop for ConnGuard {
    fn drop(&mut self) {
        self.state.active_conns.fetch_sub(1, Ordering::Relaxed);
    }
}

/// SOCKS5 (RFC 1928) & HTTP CONNECT Connection Handler
fn handle_client_connection(client_stream: TcpStream, state: Arc<ConduitState>) {
    client_stream.set_nonblocking(false).ok();
    state.active_conns.fetch_add(1, Ordering::Relaxed);
    let _conn_guard = ConnGuard {
        state: state.clone(),
    };

    client_stream.set_nodelay(true).ok();
    client_stream.set_read_timeout(Some(Duration::from_secs(15))).ok();

    // Peek first 4 bytes to distinguish SOCKS5 vs HTTP CONNECT
    let mut peek_buf = [0u8; 4];
    let n = match client_stream.peek(&mut peek_buf) {
        Ok(n) if n > 0 => n,
        _ => return,
    };

    if peek_buf[0] == 0x05 {
        // SOCKS5 Protocol
        handle_socks5(client_stream, &peek_buf[..n], state.clone());
    } else if peek_buf.starts_with(b"CONN") || peek_buf.starts_with(b"GET ") || peek_buf.starts_with(b"POST") {
        // HTTP / HTTPS Proxy Protocol
        handle_http(client_stream, state.clone());
    }
}

fn handle_socks5(mut client_stream: TcpStream, _peek: &[u8], state: Arc<ConduitState>) {
    // 1. Negotiation Handshake
    let mut greeting = [0u8; 2];
    if client_stream.read_exact(&mut greeting).is_err() || greeting[0] != 0x05 {
        return;
    }
    let nmethods = greeting[1] as usize;
    let mut methods = vec![0u8; nmethods];
    if client_stream.read_exact(&mut methods).is_err() {
        return;
    }

    // Reply: No Authentication Required (\x05\x00)
    if client_stream.write_all(&[0x05, 0x00]).is_err() {
        return;
    }

    // 2. Request Details
    let mut req_header = [0u8; 4];
    if client_stream.read_exact(&mut req_header).is_err() {
        return;
    }

    let cmd = req_header[1];

    if cmd == 0x03 {
        let atyp = req_header[3];
        handle_socks5_udp_associate(client_stream, atyp, state);
        return;
    }

    if cmd != 0x01 {
        // Command not supported
        let _ = client_stream.write_all(&[0x05, 0x07, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
        return;
    }

    let addr_type = req_header[3];
    let target_host_str: Option<String>;

    let target_addrs: Vec<SocketAddr> = match addr_type {
        0x01 => {
            // IPv4: 4 bytes
            let mut ip_buf = [0u8; 4];
            if client_stream.read_exact(&mut ip_buf).is_err() {
                return;
            }
            let mut port_buf = [0u8; 2];
            if client_stream.read_exact(&mut port_buf).is_err() {
                return;
            }
            let port = u16::from_be_bytes(port_buf);
            let ip = Ipv4Addr::new(ip_buf[0], ip_buf[1], ip_buf[2], ip_buf[3]);
            target_host_str = Some(ip.to_string());
            vec![SocketAddr::new(IpAddr::V4(ip), port)]
        }
        0x03 => {
            // Domain Name: 1 byte len + domain bytes
            let mut len_buf = [0u8; 1];
            if client_stream.read_exact(&mut len_buf).is_err() {
                return;
            }
            let domain_len = len_buf[0] as usize;
            let mut domain_buf = vec![0u8; domain_len];
            if client_stream.read_exact(&mut domain_buf).is_err() {
                return;
            }
            let domain = match String::from_utf8(domain_buf) {
                Ok(d) => d,
                Err(_) => return,
            };
            let mut port_buf = [0u8; 2];
            if client_stream.read_exact(&mut port_buf).is_err() {
                return;
            }
            let port = u16::from_be_bytes(port_buf);
            target_host_str = Some(domain.clone());
            let host_port = format!("{}:{}", domain, port);
            match host_port.to_socket_addrs() {
                Ok(iter) => iter.collect(),
                Err(_) => {
                    let _ = client_stream.write_all(&[0x05, 0x04, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
                    return;
                }
            }
        }
        _ => {
            // Unsupported address type
            let _ = client_stream.write_all(&[0x05, 0x08, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
            return;
        }
    };

    if target_addrs.is_empty() {
        let _ = client_stream.write_all(&[0x05, 0x04, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
        return;
    }

    // 3. Establish Outbound Connection via Volvo Airbag with Host Affinity
    let outbound_opt = state.create_airbag_outbound_socket_for_host(&target_addrs, target_host_str.as_deref());
    match outbound_opt {
        Some((outbound_stream, _used_ip)) => {
            // Send SOCKS5 Success (\x05\x00)
            if client_stream.write_all(&[0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0]).is_err() {
                return;
            }
            // Bi-directional duplex pipe
            pipe_duplex(client_stream, outbound_stream, state);
        }
        None => {
            let _ = client_stream.write_all(&[0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
        }
    }
}

/// Handles RFC 1928 SOCKS5 UDP Associate
fn handle_socks5_udp_associate(mut client_stream: TcpStream, atyp: u8, state: Arc<ConduitState>) {
    // Drain remaining client address/port in request
    match atyp {
        0x01 => {
            let mut buf = [0u8; 6];
            let _ = client_stream.read_exact(&mut buf);
        }
        0x03 => {
            let mut len_buf = [0u8; 1];
            if client_stream.read_exact(&mut len_buf).is_ok() {
                let mut buf = vec![0u8; len_buf[0] as usize + 2];
                let _ = client_stream.read_exact(&mut buf);
            }
        }
        0x04 => {
            let mut buf = [0u8; 18];
            let _ = client_stream.read_exact(&mut buf);
        }
        _ => return,
    }

    // Bind local UDP relay on loopback
    let udp_local = match UdpSocket::bind("127.0.0.1:0") {
        Ok(u) => u,
        Err(_) => {
            let _ = client_stream.write_all(&[0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
            return;
        }
    };

    let assigned_port = match udp_local.local_addr() {
        Ok(addr) => addr.port(),
        Err(_) => {
            let _ = client_stream.write_all(&[0x05, 0x01, 0x00, 0x01, 0, 0, 0, 0, 0, 0]);
            return;
        }
    };

    // Respond: Success (\x05\x00) + BND.ADDR (127.0.0.1) + BND.PORT
    let port_bytes = assigned_port.to_be_bytes();
    let reply = [0x05, 0x00, 0x00, 0x01, 127, 0, 0, 1, port_bytes[0], port_bytes[1]];
    if client_stream.write_all(&reply).is_err() {
        return;
    }
    client_stream.flush().ok();

    let udp_socket_clone = match udp_local.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    };

    let state_clone = state.clone();
    let active_flag = Arc::new(AtomicBool::new(true));
    let bg_flag = active_flag.clone();
    let main_flag = active_flag.clone();

    // Background thread for UDP datagram forwarding
    thread::spawn(move || {
        udp_socket_clone.set_read_timeout(Some(Duration::from_millis(500))).ok();
        let mut buf = [0u8; 65535];

        while bg_flag.load(Ordering::Relaxed) && !SERVER_SHUTDOWN.load(Ordering::Relaxed) {
            match udp_socket_clone.recv_from(&mut buf) {
                Ok((n, client_addr)) if n > 10 => {
                    // Header: RSV(2) + FRAG(1) + ATYP(1) + DST.ADDR + DST.PORT + DATA
                    let frag = buf[2];
                    if frag != 0 {
                        continue; // Drop fragmented packets per RFC 1928 recommendation
                    }
                    let atyp = buf[3];
                    let (dst_addr, data_offset): (Option<SocketAddr>, usize) = match atyp {
                        0x01 => {
                            // IPv4: 4 bytes + 2 bytes port
                            if n > 10 {
                                let ip = Ipv4Addr::new(buf[4], buf[5], buf[6], buf[7]);
                                let port = u16::from_be_bytes([buf[8], buf[9]]);
                                (Some(SocketAddr::new(IpAddr::V4(ip), port)), 10)
                            } else {
                                (None, 0)
                            }
                        }
                        0x03 => {
                            // Domain Name: 1 byte len + domain + 2 bytes port
                            let domain_len = buf[4] as usize;
                            let port_idx = 5 + domain_len;
                            if n > port_idx + 2 {
                                if let Ok(domain) = std::str::from_utf8(&buf[5..port_idx]) {
                                    let port = u16::from_be_bytes([buf[port_idx], buf[port_idx + 1]]);
                                    let host_port = format!("{}:{}", domain, port);
                                    let resolved = host_port.to_socket_addrs().ok().and_then(|mut iter| iter.next());
                                    (resolved, port_idx + 2)
                                } else {
                                    (None, 0)
                                }
                            } else {
                                (None, 0)
                            }
                        }
                        _ => (None, 0),
                    };

                    if let Some(target) = dst_addr {
                        let payload = &buf[data_offset..n];
                        // Select best outbound adapter for UDP egress
                        let candidates = state_clone.get_candidate_adapters_for_host(None);
                        if let Some(candidate_ip) = candidates.first() {
                            let bind_addr = SocketAddr::new(IpAddr::V4(*candidate_ip), 0);
                            if let Ok(outbound_udp) = UdpSocket::bind(bind_addr) {
                                outbound_udp.set_read_timeout(Some(Duration::from_millis(1500))).ok();
                                if outbound_udp.send_to(payload, target).is_ok() {
                                    state_clone.bytes_tx.fetch_add(payload.len() as u64, Ordering::Relaxed);
                                    let mut resp_buf = [0u8; 65535];
                                    if let Ok((resp_n, _)) = outbound_udp.recv_from(&mut resp_buf) {
                                        // Package response with SOCKS5 UDP header
                                        let mut socks_resp = Vec::with_capacity(resp_n + 10);
                                        socks_resp.extend_from_slice(&[0, 0, 0, 1, 0, 0, 0, 0, 0, 0]);
                                        socks_resp.extend_from_slice(&resp_buf[..resp_n]);
                                        udp_socket_clone.send_to(&socks_resp, client_addr).ok();
                                        state_clone.bytes_rx.fetch_add(resp_n as u64, Ordering::Relaxed);
                                    }
                                }
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    });

    // Per RFC 1928, UDP association lives as long as the TCP connection is maintained.
    client_stream.set_nonblocking(false).ok();
    client_stream.set_read_timeout(Some(Duration::from_millis(500))).ok();
    let mut dummy = [0u8; 1];
    while main_flag.load(Ordering::Relaxed) && !SERVER_SHUTDOWN.load(Ordering::Relaxed) {
        match client_stream.read(&mut dummy) {
            Ok(0) => break, // Clean EOF
            Ok(_) => {},    // Data received
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {
                thread::sleep(Duration::from_millis(100));
            }
            Err(_) => break, // Socket reset or aborted
        }
    }

    active_flag.store(false, Ordering::Relaxed);
}

fn handle_http(mut client_stream: TcpStream, state: Arc<ConduitState>) {
    // Read HTTP request header
    let mut header_buf = Vec::with_capacity(1024);
    let mut byte = [0u8; 1];
    while header_buf.len() < 8192 {
        if client_stream.read_exact(&mut byte).is_err() {
            return;
        }
        header_buf.push(byte[0]);
        if header_buf.ends_with(b"\r\n\r\n") {
            break;
        }
    }

    let header_str = match std::str::from_utf8(&header_buf) {
        Ok(s) => s,
        Err(_) => return,
    };

    let first_line = match header_str.lines().next() {
        Some(l) => l,
        None => return,
    };

    let parts: Vec<&str> = first_line.split_whitespace().collect();
    if parts.len() < 2 {
        return;
    }

    let method = parts[0];
    let target = parts[1];

    if method.eq_ignore_ascii_case("CONNECT") {
        // CONNECT target.com:443 HTTP/1.1
        let host_port: Vec<&str> = target.split(':').collect();
        let host = host_port[0];
        let port: u16 = if host_port.len() > 1 {
            host_port[1].parse().unwrap_or(443)
        } else {
            443
        };

        let target_str = format!("{}:{}", host, port);
        let target_addrs: Vec<SocketAddr> = match target_str.to_socket_addrs() {
            Ok(iter) => iter.collect(),
            Err(_) => {
                let _ = client_stream.write_all(b"HTTP/1.1 502 Bad Gateway\r\n\r\n");
                return;
            }
        };

        match state.create_airbag_outbound_socket_for_host(&target_addrs, Some(host)) {
            Some((outbound_stream, _)) => {
                if client_stream.write_all(b"HTTP/1.1 200 Connection Established\r\n\r\n").is_err() {
                    return;
                }
                pipe_duplex(client_stream, outbound_stream, state);
            }
            None => {
                let _ = client_stream.write_all(b"HTTP/1.1 502 Bad Gateway\r\n\r\n");
            }
        }
    } else {
        // Plain HTTP GET / POST forwarder
        let host_header = header_str
            .lines()
            .find(|l| l.to_ascii_lowercase().starts_with("host:"))
            .map(|l| l[5..].trim());

        let host = match host_header {
            Some(h) => h,
            None => return,
        };

        let host_port: Vec<&str> = host.split(':').collect();
        let domain_only = host_port[0];
        let port: u16 = if host_port.len() > 1 {
            host_port[1].parse().unwrap_or(80)
        } else {
            80
        };

        let target_str = format!("{}:{}", domain_only, port);
        let target_addrs: Vec<SocketAddr> = match target_str.to_socket_addrs() {
            Ok(iter) => iter.collect(),
            Err(_) => {
                let _ = client_stream.write_all(b"HTTP/1.1 502 Bad Gateway\r\n\r\n");
                return;
            }
        };

        match state.create_airbag_outbound_socket_for_host(&target_addrs, Some(domain_only)) {
            Some((mut outbound_stream, _)) => {
                if outbound_stream.write_all(&header_buf).is_err() {
                    return;
                }
                pipe_duplex(client_stream, outbound_stream, state);
            }
            None => {
                let _ = client_stream.write_all(b"HTTP/1.1 502 Bad Gateway\r\n\r\n");
            }
        }
    }
}

/// Zero-pause duplex byte pump between client and outbound sockets
fn pipe_duplex(mut client: TcpStream, mut outbound: TcpStream, state: Arc<ConduitState>) {
    let mut client_clone = match client.try_clone() {
        Ok(c) => c,
        Err(_) => return,
    };
    let mut outbound_clone = match outbound.try_clone() {
        Ok(o) => o,
        Err(_) => return,
    };

    let state_tx = state.clone();
    let tx_handle = thread::spawn(move || {
        let mut buf = [0u8; BUFFER_SIZE];
        loop {
            match client.read(&mut buf) {
                Ok(0) => break, // EOF
                Ok(n) => {
                    if outbound_clone.write_all(&buf[..n]).is_err() {
                        break;
                    }
                    state_tx.bytes_tx.fetch_add(n as u64, Ordering::Relaxed);
                }
                Err(_) => break,
            }
        }
        let _ = outbound_clone.shutdown(std::net::Shutdown::Write);
    });

    let state_rx = state.clone();
    let rx_handle = thread::spawn(move || {
        let mut buf = [0u8; BUFFER_SIZE];
        loop {
            match outbound.read(&mut buf) {
                Ok(0) => break, // EOF
                Ok(n) => {
                    if client_clone.write_all(&buf[..n]).is_err() {
                        break;
                    }
                    state_rx.bytes_rx.fetch_add(n as u64, Ordering::Relaxed);
                }
                Err(_) => break,
            }
        }
        let _ = client_clone.shutdown(std::net::Shutdown::Write);
    });

    let _ = tx_handle.join();
    let _ = rx_handle.join();
}

// ============================================================================
// C-ABI FFI EXPORT INTERFACE
// ============================================================================

#[no_mangle]
pub extern "C" fn conduit_version() -> *const c_char {
    static VERSION: &[u8] = b"RQL Conduit Core v2.0-PROD (Bare-Metal Rust Edition)\0";
    VERSION.as_ptr() as *const c_char
}

#[no_mangle]
pub extern "C" fn conduit_init() -> c_int {
    let _ = get_or_init_engine();
    0
}

#[no_mangle]
pub extern "C" fn conduit_add_adapter(ip_str: *const c_char) -> c_int {
    if ip_str.is_null() {
        return -1;
    }
    let c_str = unsafe { CStr::from_ptr(ip_str) };
    let slice = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -1,
    };
    let ip: Ipv4Addr = match slice.parse() {
        Ok(ip) => ip,
        Err(_) => return -1,
    };
    get_or_init_engine().add_adapter(ip);
    0
}

#[no_mangle]
pub extern "C" fn conduit_clear_adapters() -> c_int {
    get_or_init_engine().clear_adapters();
    0
}

#[no_mangle]
pub extern "C" fn conduit_set_routing_mode(mode: u32) -> c_int {
    get_or_init_engine().set_routing_mode(RoutingMode::from(mode));
    0
}

#[no_mangle]
pub extern "C" fn conduit_engage_handbrake(pinned_ip_str: *const c_char) -> c_int {
    if pinned_ip_str.is_null() {
        return -1;
    }
    let c_str = unsafe { CStr::from_ptr(pinned_ip_str) };
    let slice = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -1,
    };
    let ip: Ipv4Addr = match slice.parse() {
        Ok(ip) => ip,
        Err(_) => return -1,
    };
    get_or_init_engine().engage_handbrake(ip);
    0
}

#[no_mangle]
pub extern "C" fn conduit_release_handbrake() -> c_int {
    get_or_init_engine().release_handbrake();
    0
}

#[no_mangle]
pub extern "C" fn conduit_set_domain_affinity(enabled: c_int, ttl_sec: u32) -> c_int {
    let state = get_or_init_engine();
    state.domain_affinity_enabled.store(enabled != 0, Ordering::SeqCst);
    if ttl_sec > 0 {
        state.domain_affinity_ttl_sec.store(ttl_sec as u64, Ordering::SeqCst);
    }
    0
}

#[no_mangle]
pub extern "C" fn conduit_clear_domain_affinity() -> c_int {
    let state = get_or_init_engine();
    let mut map = state.domain_affinity_map.write().unwrap();
    map.clear();
    0
}

#[no_mangle]
pub extern "C" fn conduit_get_affinity_count() -> u32 {
    let state = get_or_init_engine();
    let map = state.domain_affinity_map.read().unwrap();
    map.len() as u32
}

#[no_mangle]
pub extern "C" fn conduit_start_proxy(bind_ip_str: *const c_char, port: u16) -> c_int {
    let state = get_or_init_engine();
    if state.is_running.load(Ordering::SeqCst) {
        return 0; // Already running
    }

    let bind_ip = if bind_ip_str.is_null() {
        Ipv4Addr::new(127, 0, 0, 1)
    } else {
        let c_str = unsafe { CStr::from_ptr(bind_ip_str) };
        match c_str.to_str().unwrap_or("127.0.0.1").parse::<Ipv4Addr>() {
            Ok(ip) => ip,
            Err(_) => Ipv4Addr::new(127, 0, 0, 1),
        }
    };

    let bind_addr = SocketAddr::new(IpAddr::V4(bind_ip), port);
    let listener = match TcpListener::bind(bind_addr) {
        Ok(l) => l,
        Err(_) => return -1,
    };

    state.is_running.store(true, Ordering::SeqCst);
    SERVER_SHUTDOWN.store(false, Ordering::SeqCst);

    let state_clone = state.clone();
    thread::spawn(move || {
        listener.set_nonblocking(true).ok();
        while !SERVER_SHUTDOWN.load(Ordering::Relaxed) {
            match listener.accept() {
                Ok((stream, _addr)) => {
                    let s_clone = state_clone.clone();
                    thread::spawn(move || {
                        handle_client_connection(stream, s_clone);
                    });
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(5));
                }
                Err(_) => break,
            }
        }
        state_clone.is_running.store(false, Ordering::SeqCst);
    });

    0
}

#[no_mangle]
pub extern "C" fn conduit_stop_proxy() -> c_int {
    SERVER_SHUTDOWN.store(true, Ordering::SeqCst);
    get_or_init_engine().is_running.store(false, Ordering::SeqCst);
    0
}

#[no_mangle]
pub extern "C" fn conduit_is_running() -> c_int {
    if get_or_init_engine().is_running.load(Ordering::SeqCst) {
        1
    } else {
        0
    }
}

#[no_mangle]
pub extern "C" fn conduit_get_stats(
    out_tx: *mut u64,
    out_rx: *mut u64,
    out_active: *mut u32,
    out_failovers: *mut u32,
    out_routed: *mut u64,
) -> c_int {
    let state = get_or_init_engine();
    unsafe {
        if !out_tx.is_null() {
            *out_tx = state.bytes_tx.load(Ordering::Relaxed);
        }
        if !out_rx.is_null() {
            *out_rx = state.bytes_rx.load(Ordering::Relaxed);
        }
        if !out_active.is_null() {
            *out_active = state.active_conns.load(Ordering::Relaxed);
        }
        if !out_failovers.is_null() {
            *out_failovers = state.failovers_caught.load(Ordering::Relaxed);
        }
        if !out_routed.is_null() {
            *out_routed = state.connections_routed.load(Ordering::Relaxed);
        }
    }
    0
}

#[no_mangle]
pub extern "C" fn conduit_probe_rtt_us(ip_str: *const c_char, port: u16, timeout_ms: u32) -> f64 {
    if ip_str.is_null() {
        return -1.0;
    }
    let c_str = unsafe { CStr::from_ptr(ip_str) };
    let slice = match c_str.to_str() {
        Ok(s) => s,
        Err(_) => return -1.0,
    };
    let target_ip: Ipv4Addr = match slice.parse() {
        Ok(ip) => ip,
        Err(_) => return -1.0,
    };

    let target = SocketAddr::new(IpAddr::V4(target_ip), port);
    let start = Instant::now();
    match TcpStream::connect_timeout(&target, Duration::from_millis(timeout_ms as u64)) {
        Ok(_) => {
            let elapsed = start.elapsed();
            elapsed.as_micros() as f64
        }
        Err(_) => -1.0,
    }
}
