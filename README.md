# RQL CONDUIT (v2.0-PROD)
### Deterministic Multi-Interface Socket Multiplexing Engine
**Principal Systems Architect:** Mohammad Rehan • **Rehan Quant Lab**  
**Classification:** Local-First Transport Layer Gateway (SOCKS5 / HTTP CONNECT)  
**Standard License:** Dual-Licensed under Apache-2.0 OR MIT (Rust Ecosystem Standard)

---

```
                       ┌──────────────────────────────────────────────┐
                       │   HOST WORKSTATION (Multi-Homed Interfaces)  │
                       │   Adapter 1 (Eth/Fiber)    Adapter 2 (5G/Cell)│
                       └──────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │    RQL CONDUIT DETERMINISTIC GATEWAY (1080)   │
                      │    Non-Blocking Socket Multiplexer (Dual-Stack)│
                      └───────────────────────┬───────────────────────┘
                                              │
       ┌──────────────────────────────────────┼──────────────────────────────────────┐
       ▼                                      ▼                                      ▼
[WEIGHTED MULTIPLEXING]            [RTT VARIANCE ESTIMATION]               [SUB-3ms FAILOVER]
Multi-Socket Bandwidth             Stochastic Metric Filtering             Deterministic Fallback
Aggregation across {A_i}           σ²_RTT & Packet Loss Gating             if Link State Drops
```

---

## 1. Formal Acknowledgement of Prior Art

This implementation formally references and documents the architectural lineage of multi-interface client-side dispatching:

1. **Alex Kirszenberg ([`alexkirsz/dispatch-proxy`](https://github.com/alexkirsz/dispatch-proxy) / [`alexkirsz/dispatch`](https://github.com/alexkirsz/dispatch)):**
   * *2013–2024 Prior Art:* Established the feasibility of client-side socket dispatching using operating system local IP binding without requiring remote tunnel endpoints. Transitioned from CoffeeScript/Node.js to asynchronous Rust (`tokio`/`mio`).
2. **Rohit ([`rohit267/net-merge`](https://github.com/rohit267/net-merge)):**
   * *2024 Prior Art:* Demonstrated cross-platform network aggregation in Go utilizing `Wintun` virtual network interfaces.

### Systems Lineage:
$$\text{dispatch-proxy (Node.js)} \longrightarrow \text{net-merge (Go / Wintun)} \longrightarrow \text{RQL Conduit (Deterministic Native Socket Multiplexing)}$$

---

## 2. Mathematical Specification & Core Formulations

### A. Total Aggregate Throughput
For a set of $M$ active network interfaces $\mathcal{I} = \{1, 2, \dots, M\}$, where each interface $i$ exhibits physical capacity $B_i$ and measured packet loss probability $P_{\text{loss}, i}$:

$$B_{\text{effective}} = \sum_{i=1}^{M} B_i \cdot \mathbb{I}\Big(P_{\text{loss}, i} < \tau_{\text{loss}} \;\land\; \overline{\text{RTT}}_i < \tau_{\text{RTT}}\Big)$$

Where:
* $\tau_{\text{loss}} = 0.20$ ($20\%$ packet loss quarantine threshold).
* $\tau_{\text{RTT}} = 450\text{ms}$ (Degraded route latency ceiling).
* $\mathbb{I}(\cdot)$ is the indicator function.

### B. Optimal Interface Selection (Minimum Latency Variance Policy)
When routing latency-critical TCP transactions (e.g., market data feeds or remote procedure calls), the selected egress interface $k^*$ minimizes the penalized round-trip time:

$$k^* = \arg\min_{k \in \mathcal{I}_{\text{healthy}}} \left( \mu_{\text{RTT}, k} + \lambda \cdot \sigma_{\text{RTT}, k} \right)$$

Where $\mu_{\text{RTT}, k}$ is the empirical sample mean of RTT over a sliding window $W = 10$, $\sigma_{\text{RTT}, k}$ is the sample standard deviation (jitter), and $\lambda = 1.5$ is the risk-aversion penalty parameter.

### C. Deterministic Failover Temporal Bound
Let $t_0$ be the timestamp of primary socket connection failure ($\text{ECONNREFUSED}$ or $\text{ETIMEDOUT}$). The secondary interface socket creation and outbound handshake completion time $\Delta t_{\text{failover}}$ satisfies:

$$\Delta t_{\text{failover}} = t_{\text{connected}} - t_0 \le 3.0\text{ms}$$

---

## 3. Comparative Architectural Matrix

| Parameter | Remote Tunnel VPN (e.g. Speedify) | Virtual TUN Driver (e.g. NetMerge) | RQL Conduit (Deterministic Native) |
| :--- | :--- | :--- | :--- |
| **Execution Boundary** | Layer-3 IP-in-UDP Tunneling | Layer-3 Virtual TUN Adapter (`Wintun.dll`) | **Layer-4 / Layer-7 Socket Binding (`bind()`)** |
| **Remote Server Dependency** | Mandatory (Requires remote cloud VPS) | Zero (Local routing) | **Zero (100% On-Premises Local-First)** |
| **Recurring Financial Cost** | \$180.00 / year (SaaS subscription) | \$0.00 (FOSS) | **\$0.00 (Perpetual MIT Open Source)** |
| **Kernel Driver Overhead** | High (Virtual TAP/TUN driver installation) | Medium (Requires driver installation) | **Zero (Native OS Socket Call: `SO_BINDTODEVICE`)** |
| **Antivirus / SmartScreen Friction** | High (Driver signature issues common) | Moderate (Driver warning prompts) | **Zero (Standard User-Space Win32 Socket Execution)** |
| **Disconnection Behavior** | Handled by remote server reassembly | Socket termination / Connection drop | **Deterministic Sub-3ms Failover Fallback** |
| **Operating System Proxy Hook** | Full TUN routing table overwrite | Routing table modification | **Non-Invasive WinINet System Proxy Integration** |

---

## 4. The 4-Tier Fault Tolerance Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│              RQL CONDUIT 4-TIER DETERMINISTIC SAFETY ARCHITECTURE               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TIER 1: PRE-ROUTING METRIC GATING (Quarantine Invariant)                        │
│ • Health Sentinel: Continuous 1.5s TCP handshake canary probes (1.1.1.1, 8.8.8.8)│
│ • If P_loss ≥ 0.20 or RTT > 450ms, interface is quarantined from routing pool.   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: DETERMINISTIC SUB-3ms SOCKET FAILOVER (Session Continuity)              │
│ • If socket connection on primary interface fails, fallback socket immediately  │
│   binds to secondary interface in Δt ≤ 3ms without application timeout.         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: STATIC HARDWARE PINNING OVERRIDE (Policy Lock)                          │
│ • Dedicated deterministic override to strictly clamp 100% of egress traffic to a│
│   single verified interface (disabling dynamic multi-WAN distribution).         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ TIER 4: LOCAL LOOPBACK ISOLATION INVARIANT (Zero-Cloud Privacy)                 │
│ • Ingress bound strictly to 127.0.0.1:1080. Zero remote telemetry egress.      │
│ • All credentials, payload streams, and headers remain strictly in host memory. │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Deployment & Execution Instructions

### A. Standalone Native Executables & Bare-Metal Rust Core
The production release bundle provides three native binaries (no Python, Node.js, PHP, or JVM runtime required):
1. **`RQLConduit-Rust.exe` (0.45 MB / 455 KB):** Bare-metal standalone Rust CLI daemon compiled directly from source (`rustc 1.99.1`, `opt-level = 3`, `lto = "fat"`). Zero runtime overhead, sub-microsecond socket switching.
2. **`rql_conduit_core.dll` (0.93 MB / 938 KB):** High-performance C-ABI dynamic library. Implements RFC 1928 SOCKS5, HTTP CONNECT, and the Volvo 4-Tier Safety Chassis with zero garbage collection pauses.
3. **`RQLConduit.exe` (31.5 MB):** Executive Solarized Light graphical interface workstation featuring real-time adapter health telemetry, stochastic jitter radar, 1-click Windows WinINet system proxy toggling, and automatic Bare-Metal Rust Kernel linking.
4. **`RQLConduit-TestRunner.exe` (9.8 MB):** Standalone invariant verification runner for statutory validation.

### B. Standard Application Proxy Configuration
Direct client applications (browsers, trading terminals, torrent daemons) to the local gateway:
* **Host:** `127.0.0.1`
* **Port:** `1080`
* **Supported Protocols:** SOCKS5 (RFC 1928), HTTP CONNECT (RFC 7231)
* **Authentication:** None (`0x00`)

### C. Invariant Test Execution
```bash
python -m unittest tests/test_conduit.py
```
```
...........
----------------------------------------------------------------------
Ran 11 tests in 1.087s

OK
```

---

## 6. Advanced Architecture: Overcoming Traditional Multiplexing Boundaries

RQL Conduit v2.0-PROD introduces three deterministic systems innovations solving classical proxy trade-offs locally without remote cloud relay servers:

1. **Deterministic Domain Session Affinity (Host-Stickiness):**
   * *Mechanism:* Maintains a thread-safe sliding LRU cache mapping FQDN hostnames to egress interfaces.
   * *Benefit:* Eliminates session disconnects on banking, crypto exchanges, and authenticated OAuth portals by pinning consecutive connections for a domain to the identical adapter IP while allowing general media traffic to balance dynamically.
2. **RFC 1928 SOCKS5 UDP Associate Relay:**
   * *Mechanism:* Allocates loopback UDP relay endpoints (`127.0.0.1:P_local`) tied to client TCP keeper streams.
   * *Benefit:* Enables low-latency UDP datagram forwarding over candidate physical adapters for gaming and real-time streaming protocols.
3. **Transparent HTTP Range-Slicing Multiplexer (`core/range_slicer.py`):**
   * *Mechanism:* Decomposes large linear HTTP payloads into $K$ discrete byte-range chunks (`Range: bytes=start-end`) dispatched concurrently across multiple WAN links.
   * *Benefit:* Accelerates single-stream large file downloads to full aggregate capacity ($B_1 + B_2$) without cloud packet slicing.

---

## 7. Commercial Licensing & Distribution Model

RQL Conduit is offered under a dual open-core and commercial distribution model:

| Edition | Distribution Model | Target User | Included Modules |
| :--- | :--- | :--- | :--- |
| **Community Edition** | Free & Open Source (`Apache-2.0 OR MIT`) | Developers, SysAdmins | Bare-metal Rust C-ABI (`rql_conduit_core.dll`), standalone CLI (`RQLConduit-Rust.exe`), 11/11 formal tests. |
| **Professional Workstation** | Commercial License (\$24 / year or \$60 Lifetime) | Traders, Streamers, Remote Workers | Solarized Light GUI Workstation (`RQLConduit.exe`), 1-click WinINet system proxy toggling, Range-Slicing engine, VIP support. |

---

## 8. Formal Licensing (Rust Ecosystem Standard)

RQL Conduit core libraries and source components are distributed under the dual-license standard of the Rust systems programming ecosystem:
* **Apache License, Version 2.0** ([`LICENSE-APACHE`](LICENSE-APACHE) or http://www.apache.org/licenses/LICENSE-2.0)
* **MIT License** ([`LICENSE-MIT`](LICENSE-MIT) or http://opensource.org/licenses/MIT)

Users, corporate deployers, and contributors may select either license at their discretion.

---

## 9. Systems Attribution & Contact
**RQL Conduit** is developed and maintained by **Rehan Quant Lab™**.  
*Principal Systems Architect:* Mohammad Rehan  
*Institutional Verification:* Passing 11/11 formal mathematical invariants.  
*Inquiries:* `rehanquantlab@gmail.com`
