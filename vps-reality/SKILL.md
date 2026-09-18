---
name: vps-reality
description: 在主流 systemd Linux VPS 或云服务器上部署、维护和审查个人及少量朋友自用的 3x-ui、Xray、VLESS REALITY Vision 节点。适用于不同云厂商、APT/DNF 系发行版、x86_64/ARM64、独立公网或明确的 NAT TCP 映射，并覆盖私有面板、订阅、SNI/回落风险、配额、验收和回滚；不用于机场运营、未授权服务器或不受支持的平台。
---

# 通用 VPS REALITY 自用节点

默认中文。把“完成”落实到真实客户端能够取得正确配置、通过 REALITY 握手并获得预期出口，而不是安装脚本返回 0。

本 Skill 源于真实 VPS 部署，但不得把任何历史供应商、IP、系统版本、target、额度、用户或密钥当作新机器默认值。每次先识别平台，再选择对应分支。

## 支持边界

公开支持的自动化基线：

- Linux + systemd；Debian/Ubuntu 的 APT 分支，RHEL/Oracle Linux/Rocky/AlmaLinux 的 DNF 分支。
- `x86_64` 与 `aarch64/arm64`；所有二进制必须与实际架构匹配。
- 独立公网 IPv4/双栈的直接入口，或供应商明确提供的 TCP NAT 端口映射。
- 3x-ui + Xray + VLESS + TCP RAW + REALITY + Vision；个人或少量朋友独立凭据。

以下环境不得按自动流程宣称支持：Windows/macOS、Alpine/OpenWrt/Arch、非 systemd、容器内充当宿主机、Kubernetes、IPv6-only、TLS 终止型负载均衡、未知透明代理、商业多租户。可以先审查并编写专门方案，但不能硬套命令。

## 按任务加载资料

- 首次接管、全新部署或迁移：先读 [平台与云厂商适配](references/platform-and-provider.md)、[网络入口模式](references/network-topologies.md)，再读 [完整部署流程](references/deploy.md)。
- 增加用户、修改额度、切换 target、升级或恢复：读 [运维与回滚](references/operations.md)，只执行请求范围内的部分。
- 检查“是否正常”：读 [分层验收](references/verification.md)，先只读，不因发现问题自动重装、重启或换目标。
- 新装选 target、切换 target、SNI/共享 CDN/异常流量：必须读 [SNI 与回落安全](references/sni-fallback-safety.md)。
- 安装或升级前读 [版本与官方资料](references/sources.md)，重新确认当日版本、安装器、API、发行版和云平台规则。
- 用户只要方案、文档或 Skill：只产出文件，不连接或修改服务器。

## 固定执行顺序

1. **定位对象。** 核对实例、供应商、区域、系统、架构、SSH、已有业务、控制台/救援入口和授权范围；多台候选无法消歧时停止询问。
2. **只读盘点。** 运行 `preflight.sh` 并查看云控制台。主机监听、主机防火墙、云防火墙和公网可达是四项独立证据。
3. **判定支持状态。** 用 `platform_profile.py` 识别 OS 家族、架构与 init；不支持或信息不足时不得继续自动部署。
4. **选择入口模式。** 独立公网、NAT 映射、443 冲突、私网/IPv6-only 分别按网络文档处理。不得把 Cloudflare Tunnel 当作 REALITY 节点入口。
5. **给出变更摘要。** 说明会改什么、端口、可能中断、云端与主机规则、凭据位置和回滚点。已授权且没有新风险时继续，不逐条反复确认。
6. **固定版本、备份、应用。** 检查发布来源与架构，备份现有 SQLite/配置，只做必要差异；接口或 schema 不匹配立即停止适配。
7. **逐层验收。** 本机服务、云端可达、外部 REALITY 握手、出口、订阅/直连配置、用户隔离、SNI 回落、重启恢复分别报告。

## 必须保持的边界

```text
客户端代理流量 ──> 供应商公网入口:PUBLIC_PORT ──> Xray REALITY:LISTEN_PORT
面板管理 ───────> Cloudflare Access + Tunnel 或 SSH 隧道 ──> 127.0.0.1:面板端口
订阅入口 ───────> 可选 Cloudflare Tunnel ────────────────> 127.0.0.1:订阅端口
```

1. 节点流量直达 VPS/NAT TCP 入口，不走 Cloudflare 橙云、Workers 或 Tunnel。SNI/target 是伪装目标，不是出口。
2. 面板与订阅源站仅绑定回环。面板公网访问必须有独立身份保护；订阅随机路径和每用户 Sub ID 都是凭据。没有域名时使用 SSH 隧道和私密直连配置，不临时暴露面板。
3. 443 空闲时优先使用；被网站或其他服务占用时不得抢占。选择独立高位 TCP 端口、独立 IP，或经单独设计和授权的 L4 前置方案。
4. NAT 模式必须同时记录外部地址/端口和内部监听端口；订阅及客户端必须实际显示外部端点。VLESS TCP REALITY 不需要额外 UDP 映射。
5. 云安全组/NSG/安全列表和主机防火墙分别验证。不得清空 iptables/nftables、覆盖现有规则体系或删除云厂商保留规则。
6. 不随意重装系统、删除 SSH 公钥、关闭 DHCP/cloud-init/云代理、禁用 SELinux/AppArmor。网络或 SSH 收紧前保留旧会话并验证第二会话和控制台恢复路径。
7. 每人独立 UUID、Sub ID、额度、到期与停用开关。面板额度不是供应商账单硬上限，也不能假定覆盖未认证回落流量。
8. Token、UUID、Sub ID、密钥、完整订阅地址和随机面板路径不写 Skill、公开文档、Git、日志或命令参数。
9. 重大修改前保存一致性 SQLite 快照与相关配置，目录 700、文件 600。复制活跃数据库文件不等于一致性备份。
10. 日常监控只告警，不自动切换 target、重启 Xray 或重装。`serverNames` 不等于回落防火墙；共享 CDN target 需单独风险评估。

## 最少输入

优先从只读配置获取，缺失时集中询问：目标实例/供应商、SSH 方式、系统与架构、云防火墙权限、公网或 NAT 入口、端口占用、面板/订阅访问模式、用户与额度、实际客户端。不得要求用户把 Token 或私钥贴进聊天。

以 [deployment.example.json](assets/deployment.example.json) 为输入模板。示例地址与域名不可用于生产；只有 Cloudflare 控制面模式需要自有域名，REALITY 本身不要求域名。

## 随附工具

- `scripts/platform_profile.py`：离线识别发行版家族、架构和 init 支持状态。
- `scripts/preflight.sh`：Linux 只读盘点，不安装、不重启、不改规则；云控制面仍需另查。
- `scripts/render_bundle.py`：校验 direct/NAT 和控制面参数，生成随机凭据、入站 payload 与私密客户端记录；不调用面板。
- `scripts/panel_api.py`：有限面板 API；读取私密 env，写请求须显式 `--apply`。
- `scripts/sqlite_snapshot.py`：SQLite 在线一致性备份，拒绝覆盖目标。
- `scripts/smoke_xray.py`：临时回环客户端验证配置、握手和出口，不修改系统代理。
- `scripts/probe_fallback.py`：默认只预览；授权后最多三次有界无凭据 HEAD 取证，不关闭证书校验。
- `scripts/reality_target_watch.py` 与 `assets/systemd/`：可选 systemd 告警；非 systemd 平台不安装。
- `assets/mihomo-routing.yaml`：可选分流模板，不是完整客户端配置。

这些工具不是盲跑的一键重装器。维护本 Skill 时运行 `python3 -B scripts/test_skill.py` 和 Skill validator。离线测试不等于任何供应商、系统或真实 VPS 的端到端验收。

## 交付

分别报告：支持判定、云端已核实、本机已应用、本机自检、外部客户端、订阅/直连配置、重启恢复、未验项目。报告系统/架构、供应商、入口模式、版本、监听、用户数量/额度、实际出口和回滚位置；不回显凭据。
