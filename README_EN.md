# xnode — xray One-Stop Management CLI

A complete CLI for xray-core: from installation to daily use, one script does it all.

[中文文档](README.md)

## Features

| Feature | Description |
|---------|-------------|
| 🔧 Install xray | Auto-detect arch, download latest, configure systemd |
| 🔌 Default proxy | SOCKS5 + HTTP passthrough proxy available immediately after install |
| 📋 Interactive menu | All-digit operation, no letter shortcuts to memorize |
| ⚡ Quick switch | `xnode 2` to switch node in one command |
| 🏓 Latency test | TCPing (fast) + Real connection (curl end-to-end), dual modes |
| 🔢 Persistent numbering | Node numbers start from 1, stable across sub updates, new nodes appended |
| 📥 Subscription management | Add/edit/delete subscription URL, one-click fetch & update |
| 📊 Service status | Version, PID, memory, logs — all at a glance |

## Quick Start

### 1. Install

```bash
# Download
sudo curl -o /usr/local/bin/xnode https://raw.githubusercontent.com/buglyz/xnode/main/xnode
sudo chmod +x /usr/local/bin/xnode

# Run, select 1 to install xray
xnode
```

After installation, xray starts automatically. SOCKS5 `127.0.0.1:20170` + HTTP `127.0.0.1:20171` are ready immediately (passthrough mode, no proxy).

### 2. Add Subscription

```bash
xnode        # Menu → select "Subscription Management" number → 1 → paste URL
# or
xnode -u     # Direct update (requires /etc/xray-sub-sync.env configured first)
```

### 3. Switch Node

```bash
xnode        # Menu → enter node number
xnode 2      # Switch directly to node 2
```

## Interactive Menu

**All-digit operation** — no letter shortcuts needed. Node numbers start from 1, action numbers follow after the node count:

```
$ xnode

  ╔══════════════════════════════════════════╗
  ║            xnode — xray Manager          ║
  ╚══════════════════════════════════════════╝

  Status: 🟢 Running    Current: 🇯🇵 VLESS-Tokyo

  ── Nodes ──
  1  🇬🇧 VLESS-London  (VLESS 1.2.3.4)
  2  🇭🇰 VLESS-HK  (VLESS 5.6.7.8)
  3  🇯🇵 VLESS-Tokyo  (VLESS 9.10.11.12) 👈
  4  🇯🇵 SS-Tokyo  (SS 9.10.11.12)
  5  🇺🇸 VLESS-US  (VLESS 13.14.15.16)

  ── Tests ──
  6  TCPing test
  7  Real connection test
  ── Actions ──
  8  Update subscription
  9  Subscription management
  10  Service status
  11  Restart xray
  12  Reinstall xray
  0  Exit

  > 6

  1  Current node    2  All nodes
  > 2

  Testing 5 nodes (TCPing)...

  1  🇬🇧 VLESS-London  0.229s
  2  🇭🇰 VLESS-HK  0.162s
  3  🇯🇵 VLESS-Tokyo  0.401s 👈
  4  🇯🇵 SS-Tokyo  0.207s
  5  🇺🇸 VLESS-US  0.153s

  🏆 Fastest: 🇺🇸 VLESS-US  0.153s
```

### Menu Quick Reference

| Input | Action |
|-------|--------|
| `1~N` | Switch to node N |
| `N+1` | TCPing test → then 1=current / 2=all |
| `N+2` | Real connection test → then 1=current / 2=all |
| `N+3` | Update subscription |
| `N+4` | Subscription management (add/edit/delete) |
| `N+5` | Service status |
| `N+6` | Restart xray |
| `N+7` | Reinstall xray |
| `0` | Exit |

## Command Line

```
xnode          Interactive menu (TTY) / list nodes (non-TTY)
xnode 2        Switch to node 2 + test latency
xnode -t       Test current node (TCPing + real connection curl)
xnode -T       TCPing all nodes (fast, no xray restart)
xnode -E       Real connection test all nodes (switch one by one, slow but accurate)
xnode -u       Update subscription
xnode -i       Install xray
xnode -s       Show service status
```

## Latency Testing (Dual Modes)

### TCPing (fast, no xray restart)

Direct TCP handshake to measure node server latency. ~2 seconds for 5 nodes.

- Diagnoses **network layer** issues: is the server reachable, how long is the handshake
- Does not restart xray, does not disturb current proxy

### Real Connection (slow but reflects actual proxy performance)

Switch to each node one by one + curl end-to-end latency test. ~30 seconds for 5 nodes.

- Diagnoses **proxy performance**: full chain latency (proxy + TLS + target site)
- Automatically switches back to original node after testing

### Combined Diagnosis

| Observation | Diagnosis |
|-------------|-----------|
| TCPing fast, real connection slow | Proxy/protocol layer issue |
| TCPing also slow | Network layer issue (server far or packet loss) |

## Persistent Node Numbering

`/usr/local/etc/xray/nodes.json` stores the ordered list of node tags:

- **Numbering starts from 1** — more natural input
- **Numbers are stable** — not affected by switching or subscription updates
- **New nodes appended to end** — existing nodes keep their positions, new ones added sorted by tag
- **Removed nodes auto-cleaned** — nodes no longer in subscription are removed from the order

## Default Passthrough Proxy

Even without a subscription, `xnode` generates a minimal config after installing xray:

- **SOCKS5**: `127.0.0.1:20170` — no auth, UDP supported
- **HTTP**: `127.0.0.1:20171`
- Outbound: **passthrough** (freedom) — all traffic sent directly, no proxy
- Routing: CN domains/IPs go direct

Benefits:
1. Ready to use — other tools can connect to SOCKS5 immediately
2. Adding a subscription replaces passthrough with proxy config, ports unchanged
3. Even if subscription expires, ports still listen — no connection refused errors

## Supported Protocols

| Protocol | Parse | Notes |
|----------|-------|-------|
| VLESS + Reality | ✅ | Including flow/fp/pbk/sid |
| VLESS + TLS | ✅ | |
| VMess | ✅ | Including WS/TLS transport |
| Shadowsocks (SIP002) | ✅ | |
| Trojan | ❌ | Not implemented |
| TUIC / Hysteria2 | ⏭️ Skipped | xray does not support |

## Switching Mechanism

xray has no explicit default outbound config — the default is the first proxy node in the `outbounds` array.

`xnode` moves the target node to array position 1, keeps the rest in original order, atomically writes config + restarts xray + verifies port readiness.

## File Layout

| File | Purpose |
|------|---------|
| `/usr/local/bin/xray` | xray binary |
| `/usr/local/bin/xnode` | xnode management script |
| `/usr/local/etc/xray/config.json` | xray config (auto-generated passthrough config on install) |
| `/usr/local/etc/xray/nodes.json` | Persistent node numbering |
| `/usr/local/share/xray/geoip.dat` | GeoIP database |
| `/usr/local/share/xray/geosite.dat` | GeoSite database |
| `/etc/systemd/system/xray.service` | systemd service unit |
| `/etc/xray-sub-sync.env` | Subscription URL + port config |

## Environment Variables

`/etc/xray-sub-sync.env` supports:

```bash
XRAY_SUB_URL="https://your-subscription-url"
XRAY_CONFIG="/usr/local/etc/xray/config.json"
XRAY_SOCKS_PORT="20170"
XRAY_HTTP_PORT="20171"
```

## License

MIT
