# xnode — xray 一键管理工具

xray-core 的完整管理 CLI：从安装到日常使用，一个脚本搞定。

[English](README_EN.md)

## 功能

| 功能 | 说明 |
|------|------|
| 🔧 安装 xray | 自动检测架构、下载最新版、配置 systemd 服务 |
| 🔌 默认代理 | 安装后立即提供 SOCKS5 + HTTP 直通代理（无需订阅） |
| 📋 交互式菜单 | 纯数字操作，不用记字母快捷键 |
| ⚡ 快速切换 | `xnode 2` 一条命令切节点 |
| 🏓 延迟测试 | TCPing（快速）+ 真连接（curl 端到端），两种模式 |
| 🔢 持久化序号 | 节点序号从 1 开始，订阅更新后旧节点不变、新节点追加 |
| 📥 订阅管理 | 添加/修改/删除订阅 URL，一键拉取更新 |
| 📊 服务状态 | 版本、PID、内存、日志，全量展示 |

## 快速开始

### 1. 安装

```bash
# 下载
sudo curl -o /usr/local/bin/xnode https://raw.githubusercontent.com/buglyz/xnode/main/xnode
sudo chmod +x /usr/local/bin/xnode

# 运行，选择 1 安装 xray
xnode
```

安装完成后自动启动，SOCKS5 `127.0.0.1:20170` + HTTP `127.0.0.1:20171` 立即可用（直通模式，无代理）。

### 2. 添加订阅

```bash
xnode        # 交互菜单 → 选「订阅管理」序号 → 1 → 粘贴订阅 URL
# 或
xnode -u     # 直接更新（需先配置 /etc/xray-sub-sync.env）
```

### 3. 切换节点

```bash
xnode        # 交互菜单 → 输入节点序号
xnode 2      # 直接切到序号 2
```

## 交互式菜单

**全程纯数字操作**，不用记字母快捷键。节点序号从 1 开始，操作序号紧跟节点数偏移：

```
$ xnode

  ╔══════════════════════════════════════════╗
  ║            xnode — xray 管理工具         ║
  ╚══════════════════════════════════════════╝

  状态: 🟢 运行中    当前: 🇯🇵 VLESS-Tokyo

  ── 节点 ──
  1  🇬🇧 VLESS-London  (VLESS 1.2.3.4)
  2  🇭🇰 VLESS-HK  (VLESS 5.6.7.8)
  3  🇯🇵 VLESS-Tokyo  (VLESS 9.10.11.12) 👈
  4  🇯🇵 SS-Tokyo  (SS 9.10.11.12)
  5  🇺🇸 VLESS-US  (VLESS 13.14.15.16)

  ── 测试 ──
  6  TCPing 测试
  7  真连接测试
  ── 操作 ──
  8  更新订阅
  9  订阅管理（添加/修改/删除）
  10  服务状态
  11  重启 xray
  12  重装 xray
  0  退出

  > 6

  1  当前节点    2  所有节点
  > 2

  测试 5 个节点（TCPing）...

  1  🇬🇧 VLESS-London  0.229s
  2  🇭🇰 VLESS-HK  0.162s
  3  🇯🇵 VLESS-Tokyo  0.401s 👈
  4  🇯🇵 SS-Tokyo  0.207s
  5  🇺🇸 VLESS-US  0.153s

  🏆 最快: 🇺🇸 VLESS-US  0.153s
```

### 菜单操作速查

| 输入 | 作用 |
|------|------|
| `1~N` | 切换到第 N 个节点 |
| `N+1` | TCPing 测试 → 再选 1=当前 / 2=所有 |
| `N+2` | 真连接测试 → 再选 1=当前 / 2=所有 |
| `N+3` | 更新订阅 |
| `N+4` | 订阅管理（添加/修改/删除） |
| `N+5` | 服务状态 |
| `N+6` | 重启 xray |
| `N+7` | 重装 xray |
| `0` | 退出 |

## 命令行模式

```
xnode          交互式菜单（TTY）/ 列出节点（非 TTY）
xnode 2        切到序号 2 + 测延迟
xnode -t       测当前节点（TCPing + 真连接 curl）
xnode -T       TCPing 所有节点（快速，不切换 xray）
xnode -E       真连接测试所有节点（逐个切换+curl，慢但反映真实性能）
xnode -u       更新订阅
xnode -i       安装 xray
xnode -s       查看服务状态
```

## 延迟测试（两种模式）

### TCPing（快速，不切换 xray）

直接 TCP 握手测节点服务器延迟，5 节点 ~2 秒完成。

- 定位**网络层**问题：服务器是否可达、握手延迟多少
- 不需要重启 xray，不干扰当前代理

### 真连接（慢但反映真实代理性能）

逐个切换节点 + curl 端到端测延迟，5 节点 ~30 秒。

- 定位**代理性能**问题：完整链路（代理+TLS+目标站）延迟
- 测完自动切回原节点

### 两者互补

| 现象 | 诊断 |
|------|------|
| TCPing 快，真连接慢 | 代理/协议层有问题 |
| TCPing 也慢 | 网络层问题（服务器远或丢包） |

## 持久化节点序号

`/usr/local/etc/xray/nodes.json` 保存节点的 tag 顺序列表：

- **序号从 1 开始** — 输入更自然
- **序号稳定** — 不受切换、订阅更新影响
- **新节点追加到末尾** — 更新订阅时已有节点保持原位置，新节点按 tag 排序追加
- **消失的节点自动移除** — 订阅更新后不再存在的节点从顺序中剔除

## 默认直通代理

安装 xray 后即使没有添加订阅，`xnode` 也会自动生成一个最小配置：

- **SOCKS5**: `127.0.0.1:20170` — 无需认证，支持 UDP
- **HTTP**: `127.0.0.1:20171`
- 出站: **直通**（freedom）— 所有流量原样发出，不走代理
- 路由: CN 域名/IP 直连

好处：
1. 安装即用——其他工具可以立即连 SOCKS5 端口
2. 添加订阅后自动替换为代理配置，端口不变
3. 即使订阅失效，端口仍然监听，不会报连接拒绝

## 支持的协议

| 协议 | 解析 | 说明 |
|------|------|------|
| VLESS + Reality | ✅ | 含 flow/fp/pbk/sid |
| VLESS + TLS | ✅ | |
| VMess | ✅ | 含 WS/TLS 传输 |
| Shadowsocks (SIP002) | ✅ | |
| Trojan | ❌ | 未实现 |
| TUIC / Hysteria2 | ⏭️ 跳过 | xray 不支持 |

## 切换原理

xray 没有显式默认 outbound 配置项——默认出站 = `outbounds` 数组第一个代理节点。

`xnode` 把目标节点移到数组第一位，其余保持原序，原子写 config + restart xray + 端口就绪验证。

## 文件布局

| 文件 | 用途 |
|------|------|
| `/usr/local/bin/xray` | xray 二进制 |
| `/usr/local/bin/xnode` | xnode 管理脚本 |
| `/usr/local/etc/xray/config.json` | xray 配置（安装时自动生成直通配置） |
| `/usr/local/etc/xray/nodes.json` | 持久化节点序号 |
| `/usr/local/share/xray/geoip.dat` | GeoIP 数据库 |
| `/usr/local/share/xray/geosite.dat` | GeoSite 数据库 |
| `/etc/systemd/system/xray.service` | systemd 服务单元 |
| `/etc/xray-sub-sync.env` | 订阅 URL + 端口配置 |

## 环境变量

`/etc/xray-sub-sync.env` 支持以下变量：

```bash
XRAY_SUB_URL="https://your-subscription-url"
XRAY_CONFIG="/usr/local/etc/xray/config.json"
XRAY_SOCKS_PORT="20170"
XRAY_HTTP_PORT="20171"
```

## License

MIT
