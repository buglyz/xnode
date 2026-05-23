# xnode — xray 一键管理工具

xray-core 的完整管理 CLI：从安装到日常使用，一个脚本搞定。

## 功能

| 功能 | 说明 |
|------|------|
| 🔧 安装 xray | 自动检测架构、下载最新版、配置 systemd 服务 |
| 🔌 默认代理 | 安装后立即提供 SOCKS5 + HTTP 直通代理（无需订阅） |
| 📋 交互式菜单 | 输入序号切换节点，一目了然 |
| ⚡ 快速切换 | `xnode 2` 一条命令切节点 |
| 🏓 延迟测试 | 当前节点 / 所有节点，3 次取均值 |
| 📥 订阅管理 | 添加/修改/删除订阅 URL，一键拉取更新 |
| 📊 服务状态 | 版本、PID、内存、日志，全量展示 |

## 快速开始

### 1. 安装

```bash
# 下载
sudo curl -o /usr/local/bin/xnode https://raw.githubusercontent.com/buglyz/xnode/main/xnode
sudo chmod +x /usr/local/bin/xnode

# 运行，选择 i 安装 xray
xnode
```

安装完成后自动启动，SOCKS5 `127.0.0.1:20170` + HTTP `127.0.0.1:20171` 立即可用（直通模式，无代理）。

### 2. 添加订阅

```bash
xnode        # 交互菜单 → s → 1 → 粘贴订阅 URL
# 或
xnode -u     # 直接更新（需先配置 /etc/xray-sub-sync.env）
```

### 3. 切换节点

```bash
xnode        # 交互菜单 → 输入序号
xnode 2      # 直接切到序号 2
```

## 用法详解

### 交互式菜单

```
$ xnode

  ╔══════════════════════════════════════════╗
  ║            xnode — xray 管理工具         ║
  ╚══════════════════════════════════════════╝

  状态: 🟢 运行中    当前: 🇯🇵 VLESS-Tokyo

  ── 节点 ──
  0  🇯🇵 VLESS-Tokyo  (VLESS 9.10.11.12) 👈
  1  🇭🇰 VLESS-HK  (VLESS 5.6.7.8)
  2  🇯🇵 SS-Tokyo  (SS 9.10.11.12)
  3  🇺🇸 VLESS-US  (VLESS 13.14.15.16)
  4  🇬🇧 VLESS-London  (VLESS 1.2.3.4)

  ── 操作 ──
  t  测试当前节点延迟
  T  测试所有节点延迟
  u  更新订阅
  s  订阅管理（添加/修改/删除）
  S  服务状态
  r  重启 xray
  i  重装 xray
  q  退出

  > _
```

### 命令行模式

```
xnode          交互式菜单（TTY）/ 列出节点（非 TTY）
xnode 2        切到序号 2 + 测延迟
xnode -t       测试当前节点延迟
xnode -T       测试所有节点延迟
xnode -u       更新订阅
xnode -i       安装 xray
xnode -s       查看服务状态
```

## 默认直通代理

安装 xray 后即使没有添加订阅，`xnode` 也会自动生成一个最小配置：

- **SOCKS5**: `127.0.0.1:20170` — 无需认证，支持 UDP
- **HTTP**: `127.0.0.1:20171`
- 出站: **直通**（freedom）— 所有流量原样发出，不走代理
- 路由: CN 域名/IP 直连

这个直通模式的好处：
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
| `/usr/local/etc/xray/config.json` | xray 配置（安装时自动生成直通配置） |
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
