# xnode — xray 节点切换 CLI

xray-core 本地代理的交互式节点切换工具。

## 功能

- 📋 交互式菜单 — 输入序号切换节点
- ⚡ 快速切换 — `xnode 2` 直接切到序号 2
- 🏓 延迟测试 — 当前节点 / 所有节点
- 📥 订阅更新 — 一键拉取订阅并重启 xray

## 用法

### 交互式菜单

```
$ xnode

╔══════════════════════════════════════════╗
║          xnode — xray 节点切换           ║
╠══════════════════════════════════════════╣
║  0  🇯🇵 VLESS-Tokyo  👈                    ║
║  1  🇭🇰 VLESS-HK                          ║
║  2  🇯🇵 SS-Tokyo                        ║
║  3  🇺🇸 VLESS-US                     ║
║  4  🇬🇧 VLESS-London                  ║
╠══════════════════════════════════════════╣
║  t  测试当前节点延迟                     ║
║  T  测试所有节点延迟                     ║
║  u  更新订阅                             ║
║  q  退出                                 ║
╚══════════════════════════════════════════╝

  > _
```

### 命令行

```
xnode          交互式菜单（TTY）/ 列出节点（非 TTY）
xnode 2        切到序号 2 + 测延迟
xnode -t       测试当前节点延迟
xnode -T       测试所有节点延迟（逐个切换测3次取均值，最后切回）
xnode -u       一键更新订阅 + 重启 xray
```

## 切换原理

xray 没有显式默认 outbound 配置项——默认出站 = `outbounds` 数组第一个代理节点。

`xnode` 把目标节点移到数组第一位，其余保持原序，原子写 config + restart xray + 端口就绪验证。

## 依赖

- xray-core（systemd: `xray`）
- `curl`
- Python 3.9+
- 订阅更新可选：`xray-sub-sync` + `/etc/xray-sub-sync.env`

## 自定义

编辑脚本顶部的 `NODES` 列表匹配你的节点：

```python
NODES = [
    "🇯🇵 VLESS-Tokyo",
    "🇭🇰 VLESS-HK",
    "🇯🇵 SS-Tokyo",
    "🇺🇸 VLESS-US",
    "🇬🇧 VLESS-London",
]
```

修改 `CONFIG` 路径指向你的 xray 配置文件。

## License

MIT
