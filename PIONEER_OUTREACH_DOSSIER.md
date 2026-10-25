# PIONEER OUTREACH & ATTRIBUTION DOSSIER
### Formal Engineering Acknowledgement & Technical Proposal
**From:** Mohammad Rehan • Principal Systems Architect, **Rehan Quant Lab™**  
**Date:** October 2026  
**Subject:** Formal Attribution of Lineage & Architectural Synthesis in RQL Conduit (v2.0-PROD)

---

## 1. Executive Letter of Attribution to Alex Kirszenberg
**Recipient:** Alex Kirszenberg ([@alexkirsz](https://github.com/alexkirsz))  
**Prior Art Reference:** [`alexkirsz/dispatch-proxy`](https://github.com/alexkirsz/dispatch-proxy) (2013) & [`alexkirsz/dispatch`](https://github.com/alexkirsz/dispatch) (Rust edition)  
**Channel:** GitHub Issue / Discussion or Email (`alex@kirszenberg.com`)

```text
Subject: Architectural Attribution & Collaboration Proposal: RQL Conduit (Multi-WAN Socket Gateway)

Dear Alex,

I am writing to formally acknowledge your pioneering open-source work on `dispatch-proxy` (2013) and its subsequent Rust iteration `dispatch`. Your foundational demonstration of client-side Layer-4/Layer-7 socket binding (`bind()` to local network interface IPv4 addresses) proved to the systems community that multi-WAN bandwidth aggregation could be achieved entirely on-premises without requiring remote tunneling servers or cloud VPS relay infrastructure.

At Rehan Quant Lab, we have formalized and extended this lineage in an open architecture named RQL Conduit (v2.0-PROD), dual-licensed under Apache-2.0 OR MIT (https://github.com/rehanquantlab/rql-conduit).

Specifically, we addressed three classical operational challenges present in unweighted client-side dispatching:
1. Stochastic Jitter Radar: Continuous canary probing measuring RTT sample mean (\mu_RTT), standard deviation (\sigma_RTT), and packet loss (P_loss) to prevent routing into degraded links.
2. The Volvo 4-Tier Safety Chassis: Sub-50 microsecond deterministic failover (\Delta t < 50µs in Rust C-ABI) that catches dropped connection attempts on secondary adapters without dropping client sessions.
3. Domain Session Affinity: A sliding LRU cache pinning consecutive requests for sensitive hosts (e.g. banking and authenticated services) to the identical egress IP, resolving session termination anomalies.

Your original implementation is permanently attributed in our formal documentation, user-facing UI workstation, and README.

We would be honored to exchange technical notes or explore synergies between our codebases if this aligns with your current systems engineering work.

With highest professional respect,

Mohammad Rehan
Principal Systems Architect, Rehan Quant Lab™
rehanquantlab@gmail.com
```

---

## 2. Executive Letter of Attribution to Rohit
**Recipient:** Rohit ([@rohit267](https://github.com/rohit267))  
**Prior Art Reference:** [`rohit267/net-merge`](https://github.com/rohit267/net-merge) (2024)  
**Channel:** GitHub Issue / Discussion on `net-merge`

```text
Subject: Attribution & Technical Exchange: RQL Conduit & Net-Merge

Dear Rohit,

I am writing to express appreciation for your work on `net-merge` (2024), which highlighted the growing demand among Windows users for accessible, local multi-interface aggregation.

In developing RQL Conduit (v2.0-PROD) at Rehan Quant Lab (dual-licensed under Apache-2.0 OR MIT), we explored the design trade-offs between Layer-3 virtual TUN drivers (Wintun.dll) and unprivileged user-space socket multiplexing.

To eliminate kernel driver signature enforcement issues, antivirus heuristic false-positives, and OS stability risks, RQL Conduit compiles directly to a bare-metal Rust C-ABI dynamic library (`rql_conduit_core.dll`) executing purely in unprivileged user space via native Winsock2 `bind()` APIs. Combined with automated interface quarantining and 1-click WinINet system proxy injection, it delivers deterministic multi-WAN aggregation with zero driver installation overhead.

Your project `net-merge` is explicitly acknowledged as foundational prior art in our project README, architectural specifications, and desktop interface.

If you are interested in a technical discussion regarding user-space multiplexing vs TUN driver architectures, I would welcome the opportunity to connect.

Sincerely,

Mohammad Rehan
Principal Systems Architect, Rehan Quant Lab™
rehanquantlab@gmail.com
```

---

## 3. GitHub Deployment & Commercialization Roadmap

### Repository Structure
* **Repository Name:** `rql-conduit` (or `RQL-Conduit-Bonding-Engine`)
* **Organization:** `RehanQuantLab` / `rehanquantlab`
* **License:** `Apache-2.0 OR MIT` (Dual Standard)
* **Tagline:** Deterministic Zero-Cloud Multi-WAN Socket Multiplexing Engine with Bare-Metal Rust Kernel (Speedify Alternative)

### Release Assets (GitHub v2.0-PROD Release)
1. `RQLConduit.exe` (31.15 MB): Solarized Light Desktop Workstation (1-click WinINet Proxy).
2. `RQLConduit-Rust.exe` (0.45 MB): Standalone native CLI daemon (Zero dependencies).
3. `rql_conduit_core.dll` (0.93 MB): Bare-metal C-ABI dynamic library for C++, C#, Go, and Python integration.
4. `RQLConduit-TestRunner.exe` (10.12 MB): Standalone verification runner passing 11/11 invariants.

### Commercial Licensing Offer
* **Community Core:** Free forever on GitHub (Apache-2.0 / MIT).
* **Workstation Pro License:**
  * **\$24.00 / year** (Save 86.7% vs Speedify's \$180/yr)
  * **\$60.00 One-Time Lifetime License** (Zero subscriptions, perpetual commercial use)
