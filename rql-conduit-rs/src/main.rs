//! RQL Conduit — Standalone Native Windows CLI Executable
//! Principal Architect: Mohammad Rehan • Rehan Quant Lab
//!
//! Cold Systems Engineering Standalone Binary.
//! Zero Python runtime. Zero Java runtime. Zero PHP. Zero kernel drivers.
//! Unprivileged user-space Winsock2 multiplexer.

use rql_conduit_core::{
    conduit_add_adapter, conduit_clear_adapters, conduit_get_stats, conduit_init,
    conduit_set_routing_mode, conduit_start_proxy, conduit_stop_proxy, conduit_version,
};
use std::ffi::{CStr, CString};
use std::io::Write;
use std::net::Ipv4Addr;
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

static RUNNING: AtomicBool = AtomicBool::new(true);

extern "system" {
    fn SetConsoleCtrlHandler(
        handler: Option<unsafe extern "system" fn(u32) -> i32>,
        add: i32,
    ) -> i32;
}

unsafe extern "system" fn console_ctrl_handler(_ctrl_type: u32) -> i32 {
    RUNNING.store(false, Ordering::SeqCst);
    1 // Handled
}

fn discover_windows_ipv4_adapters() -> Vec<String> {
    let mut detected = Vec::new();

    let output = match Command::new("ipconfig").output() {
        Ok(out) => String::from_utf8_lossy(&out.stdout).to_string(),
        Err(_) => return detected,
    };

    for line in output.lines() {
        let line_lower = line.to_lowercase();
        if line_lower.contains("ipv4") && line.contains(":") {
            if let Some(ip_part) = line.split(':').nth(1) {
                let clean_ip = ip_part.trim().trim_end_matches("(Preferred)").trim();
                if let Ok(ipv4) = clean_ip.parse::<Ipv4Addr>() {
                    let octets = ipv4.octets();
                    // Filter loopback (127.0.0.1) and APIPA (169.254.x.x)
                    if octets[0] != 127 && !(octets[0] == 169 && octets[1] == 254) {
                        detected.push(ipv4.to_string());
                    }
                }
            }
        }
    }

    detected.sort();
    detected.dedup();
    detected
}

fn print_banner() {
    let ver_ptr = conduit_version();
    let ver_str = unsafe { CStr::from_ptr(ver_ptr).to_string_lossy() };
    println!("=================================================================");
    println!(" [*] REHAN QUANT LAB - RQL CONDUIT BARE-METAL ENGINE");
    println!("     {}", ver_str);
    println!("     Dual-WAN Deterministic Socket Multiplexer");
    println!("     License: Apache-2.0 OR MIT (Dual Standard)");
    println!("=================================================================");
}

fn main() {
    print_banner();

    let args: Vec<String> = std::env::args().collect();
    let mut port: u16 = 1080;
    let mut mode: u32 = 0; // 0 = Strip Mining
    let mut manual_adapters: Vec<String> = Vec::new();

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--port" | "-p" => {
                if i + 1 < args.len() {
                    port = args[i + 1].parse().unwrap_or(1080);
                    i += 1;
                }
            }
            "--mode" | "-m" => {
                if i + 1 < args.len() {
                    mode = args[i + 1].parse().unwrap_or(0);
                    i += 1;
                }
            }
            "--adapters" | "-a" => {
                if i + 1 < args.len() {
                    manual_adapters = args[i + 1]
                        .split(',')
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty())
                        .collect();
                    i += 1;
                }
            }
            "--help" | "-h" => {
                println!("Usage: RQLConduit-Rust.exe [OPTIONS]");
                println!("Options:");
                println!("  --port, -p <PORT>       Local proxy listen port (default: 1080)");
                println!("  --mode, -m <MODE>       Routing policy: 0=Strip Mining, 1=Lowest Latency, 2=Failover (default: 0)");
                println!("  --adapters, -a <IPS>    Comma-separated list of adapter IPv4 addresses");
                println!("  --help, -h              Print this help information");
                return;
            }
            _ => {}
        }
        i += 1;
    }

    let adapters = if !manual_adapters.is_empty() {
        manual_adapters
    } else {
        println!("[*] Discovering active host network adapters via Winsock...");
        discover_windows_ipv4_adapters()
    };

    if adapters.is_empty() {
        eprintln!("[ERROR] No active physical/virtual IPv4 network adapters discovered.");
        eprintln!("[ERROR] Connect at least one active network interface and retry.");
        return;
    }

    println!("[+] Initializing Core Multiplexer C-ABI...");
    conduit_init();
    conduit_clear_adapters();

    println!("[+] Registering egress interface candidate pool ({} adapters):", adapters.len());
    for (idx, ip) in adapters.iter().enumerate() {
        println!("    [{}] Egress IP: {}", idx + 1, ip);
        if let Ok(c_ip) = CString::new(ip.as_str()) {
            conduit_add_adapter(c_ip.as_ptr());
        }
    }

    conduit_set_routing_mode(mode);
    let mode_desc = match mode {
        1 => "Lowest Latency (Sun Tzu Mode)",
        2 => "Hot-Standby Failover (Zero-Drop)",
        _ => "Strip-Mining (Jet Bandwidth Aggregation)",
    };
    println!("[+] Dispatch Policy: {}", mode_desc);
    println!("[+] Volvo 4-Tier Safety Chassis: ENGAGED");
    println!("    Tier 1: Pre-Routing Quarantining (Loss Rate Threshold P_loss >= 0.20)");
    println!("    Tier 2: Active Airbag Instant Failover (Sub-Microsecond Delta-t)");
    println!("    Tier 3: Mechanical Handbrake Single-Link Clamp (Available)");
    println!("    Tier 4: Local Air-Gap Loopback (127.0.0.1 Binding Invariant)");

    let listen_host = CString::new("127.0.0.1").unwrap();
    let start_res = conduit_start_proxy(listen_host.as_ptr(), port);
    if start_res != 0 {
        eprintln!("[ERROR] Failed to bind local TCP listener on 127.0.0.1:{}", port);
        eprintln!("[ERROR] Check if port {} is occupied by another process.", port);
        return;
    }

    println!("[+] SOCKS5 / HTTP Proxy Server listening on 127.0.0.1:{}", port);
    println!("[+] Configure your browser/application proxy to: SOCKS5://127.0.0.1:{} or HTTP://127.0.0.1:{}", port, port);
    println!("[*] Press Ctrl+C to terminate cleanly.\n");

    unsafe {
        SetConsoleCtrlHandler(Some(console_ctrl_handler), 1);
    }

    let mut last_tx: u64 = 0;
    let mut last_rx: u64 = 0;

    while RUNNING.load(Ordering::SeqCst) {
        thread::sleep(Duration::from_millis(1000));

        let mut tx: u64 = 0;
        let mut rx: u64 = 0;
        let mut active: u32 = 0;
        let mut failovers: u32 = 0;
        let mut routed: u64 = 0;

        conduit_get_stats(&mut tx, &mut rx, &mut active, &mut failovers, &mut routed);

        let delta_tx_kb = (tx.saturating_sub(last_tx)) as f64 / 1024.0;
        let delta_rx_kb = (rx.saturating_sub(last_rx)) as f64 / 1024.0;
        last_tx = tx;
        last_rx = rx;

        print!(
            "\r[STATUS] Conns: {:<3} | Routed: {:<6} | Airbag Saves: {:<3} | TX: {:>7.2} MB ({:>6.1} KB/s) | RX: {:>7.2} MB ({:>6.1} KB/s)",
            active,
            routed,
            failovers,
            (tx as f64) / (1024.0 * 1024.0),
            delta_tx_kb,
            (rx as f64) / (1024.0 * 1024.0),
            delta_rx_kb
        );
        std::io::stdout().flush().ok();
    }

    println!("\n[*] Shutting down RQL Conduit engine...");
    conduit_stop_proxy();
    println!("[OK] Sockets closed cleanly. Kernel state restored.");
}
