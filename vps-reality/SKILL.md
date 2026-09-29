---
name: vps-reality
description: 在主流 systemd Linux VPS 或云服务器上检查、部署、维护和排障个人及少量朋友自用的 3x-ui、Xray、VLESS REALITY Vision 节点。适用于从新 VPS 搭建、自建代理/VPN、节点连不上或断流、用户与配额管理，以及不同云厂商、APT/DNF、x86_64/ARM64、独立公网或明确 NAT TCP 映射；覆盖可选 Tunnel、SSH 或公网控制面、订阅、SNI/回落风险、验收和回滚，不用于机场运营、未授权服务器或不受支持的平台。
---

# 通用 VPS REALITY 自用节点

默认中文。把“完成”落实到真实客户端能够取得正确配置、通过 REALITY 握手并获得预期出口，而不是安装脚本返回 0。

本 Skill 源于真实 VPS 部署，但不得把任何历史供应商、IP、系统版本、target、额度、用户或密钥当作新机器默认值。每次先识别平台，再选择对应分支。

## 先识别任务，不要求用户先懂术语

把自然语言请求归入一个主模式；模式只是内部工作入口，不是假装已经存在的斜杠命令：

| 用户目标 | 主模式 | 默认行为 |
|---|---|---|
| “先看看现在怎么样”“健康检查” | `audit` | 只读盘点并给证据，不修复 |
| “从零搭建”“迁移到新 VPS” | `deploy` | 盘点后集中补齐必要输入和控制面选择，再实施 |
| “加一个人”“改额度/到期”“停用泄漏用户” | `user-change` | 只改目标用户，先备份，写后读回 |
| “连不上/断流/订阅打不开/面板进不去” | `diagnose` | 先按症状定位层级，不把诊断授权当修复授权 |
| “升级/换 target/恢复备份” | `maintenance` | 明确维护范围、中断和回退点后执行 |

常见请求的最短流程、询问方式和输出契约见 [任务模式与交互](references/task-modes.md)。故障请求同时读 [故障诊断](references/troubleshooting.md)。能从只读事实获取的信息不再问用户；确需补充时集中问，诊断场景通常一次不超过三个关键问题。

## 确定性工具与 AI 判断分工

- 平台识别、配置生成、面板有限写入、一致性备份、握手测试和受控回落取证使用本 Skill 随附脚本；不要在已有 helper 能覆盖时临时拼一套等价写操作。
- **先锁定资源边界。** 以当前实际加载的 `SKILL.md` 所在目录作为唯一 `SKILL_ROOT`，只从该目录按明确相对路径读取 `scripts/`、`assets/` 和 `references/`。不得通过当前工作目录、父目录、shell 历史、旧任务产物、备份目录或其他仓库搜索并自动执行同名脚本；Skill 外的历史脚本只能作为审查证据。若无法确定 `SKILL_ROOT`、资源路径不唯一或文件来源不明，在任何服务器写操作前停止。
- 上游安装器和发布产物不是 Skill helper。它们只能从执行当日核实的官方固定版本下载到本次新建的私密 staging 目录，记录 URL、版本和 digest，审查后再运行；不得因文件名相同而覆盖或替代 Skill 资源。
- 由 AI 判断支持状态、证据缺口、风险、变更范围和是否需要用户选择；脚本退出码只代表该脚本，不代表端到端完成。
- helper 与现场版本、schema 或拓扑不匹配时停止自动写入，先适配并离线测试。不要退回到未经审查的 `curl | bash`、直接改活跃 SQLite 或连续试错重启。
- 每次只实施已授权的最小修复，随后重跑受影响层和下游层的验收；不得因健康检查失败自动切换 target、轮换 IP、重装或放宽防火墙。

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
- 连不上、断流、订阅/面板异常或只在某个网络失败：读 [故障诊断](references/troubleshooting.md)，先把故障定位到客户端、控制面、REALITY、主机或云网络层。
- 新装选 target、切换 target、SNI/共享 CDN/异常流量：必须读 [SNI 与回落安全](references/sni-fallback-safety.md)。
- 安装或升级前读 [版本与官方资料](references/sources.md)，重新确认当日版本、安装器、API、发行版和云平台规则。
- 用户只要方案、文档或 Skill：只产出文件，不连接或修改服务器。

## 首次部署必须交互选择控制面

除非用户已经明确说明，完成只读盘点后、安装或开放端口前，集中询问一次访问方式，不得从示例文件、历史机器或已有 Cloudflare 账号推断答案：

1. **Cloudflare Tunnel（需要公网自动订阅时优先推荐）**：询问是否愿意安装 `cloudflared`，并确认 Cloudflare 管理权限。只需自动订阅时用一个订阅域名，面板继续 SSH-only；只有面板也要公网访问时才再使用不同的面板域名，并强制加 Access。
2. **SSH 隧道（最少依赖、攻击面最小）**：不要求域名或 Cloudflare；面板与订阅只监听回环，交付私密 VLESS 链接。没有公网 HTTPS 自动订阅。
3. **公网 IP 直连面板/订阅（高风险）**：先分别确认要暴露面板、订阅还是两者，再说明明文 HTTP 会泄露登录和订阅凭据、公开管理端口会遭扫描。继续前必须再次取得明确确认，并优先要求固定来源 CIDR 白名单和 TLS。不得把该选项描述为与前两项同等安全。

用户可以选择任一模式，也可以在部署后更改；选择权属于用户，但安全后果必须在变更前讲清。用户明确选择公网 IP，并在看到监听地址、端口、TLS 状态、来源范围和回滚方法后确认，就按所选范围实施；即使其确认使用明文 HTTP 或 `0.0.0.0/0`，也不得仅因不推荐而替用户改回 Tunnel/SSH。未得到回答时停在只读盘点，不自动安装 Cloudflare，也不自动把面板绑定到公网。公网 IP 分支属于逐机适配，不由安全默认的 renderer/helper 静默放宽回环限制。

## 固定执行顺序

1. **定位对象。** 核对实例、供应商、区域、系统、架构、SSH、已有业务、控制台/救援入口和授权范围；多台候选无法消歧时停止询问。
2. **只读盘点。** 运行 `preflight.sh` 并查看云控制台。主机监听、主机防火墙、云防火墙和公网可达是四项独立证据。
3. **判定支持状态。** 用 `platform_profile.py` 识别 OS 家族、架构与 init；不支持或信息不足时不得继续自动部署。
4. **选择入口与控制面。** 独立公网、NAT 映射、443 冲突、私网/IPv6-only 分别按网络文档处理，并让用户明确选择 Cloudflare Tunnel、SSH 隧道或公网 IP 直连。不得把 Cloudflare Tunnel 当作 REALITY 节点入口。
5. **给出变更摘要。** 说明会改什么、端口、可能中断、云端与主机规则、凭据位置和回滚点。已授权且没有新风险时继续，不逐条反复确认。
6. **固定版本、架构闭环、备份、应用。** 检查发布来源和官方 digest，用 `verify_elf_arch.py` 核对下载后及安装后的真实 ELF 架构，再备份现有 SQLite/配置并只做必要差异；接口、schema 或架构不匹配立即停止适配。
7. **逐层验收。** 本机服务、云端可达、外部 REALITY 握手、出口、订阅/直连配置、用户隔离、SNI 回落、重启恢复分别报告。

## 必须保持的边界

```text
客户端代理流量 ──> 供应商公网入口:PUBLIC_PORT ──> Xray REALITY:LISTEN_PORT
面板管理 ───────> 用户选择 Cloudflare Access + Tunnel / SSH 隧道 / 公网 IP 直连
订阅入口 ───────> 用户选择 Cloudflare Tunnel / 私密直连配置 / 公网 IP 直连
```

1. 节点流量直达 VPS/NAT TCP 入口，不走 Cloudflare 橙云、Workers 或 Tunnel。SNI/target 是伪装目标，不是出口。
2. 未选择前，面板与订阅源站仅绑定回环。Cloudflare 面板必须有 Access；公网 IP 直连则按用户确认的 TLS 和来源范围执行。订阅随机路径和每用户 Sub ID 都是凭据；未明确确认不得改为 `0.0.0.0`。
3. 443 空闲时优先使用；被网站或其他服务占用时不得抢占。选择独立高位 TCP 端口、独立 IP，或经单独设计和授权的 L4 前置方案。
4. NAT 模式必须同时记录外部地址/端口和内部监听端口；订阅及客户端必须实际显示外部端点。VLESS TCP REALITY 不需要额外 UDP 映射。
5. 云安全组/NSG/安全列表和主机防火墙分别验证。不得清空 iptables/nftables、覆盖现有规则体系或删除云厂商保留规则。
6. 不随意重装系统、删除 SSH 公钥、关闭 DHCP/cloud-init/云代理、禁用 SELinux/AppArmor。网络或 SSH 收紧前保留旧会话并验证第二会话和控制台恢复路径。
7. 每人独立 UUID、Sub ID、额度、到期与停用开关。面板额度不是供应商账单硬上限，也不能假定覆盖未认证回落流量。
8. Token、UUID、Sub ID、密钥、完整订阅地址和随机面板路径不写 Skill、公开文档、Git、日志或命令参数。
9. 重大修改前保存一致性 SQLite 快照与相关配置，目录 700、文件 600。复制活跃数据库文件不等于一致性备份。
10. 日常监控只告警，不自动切换 target、重启 Xray 或重装。`serverNames` 不等于回落防火墙；共享 CDN target 需单独风险评估。

## 最少输入

优先从只读配置获取，缺失时集中询问：目标实例/供应商、SSH 方式、系统与架构、云防火墙权限、公网或 NAT 入口、端口占用、面板与订阅各自的访问模式、用户与额度、实际客户端。控制面选择不得代替用户回答。不得要求用户把 Token 或私钥贴进聊天。

以默认 SSH-only 的 [deployment.example.json](assets/deployment.example.json) 为输入模板；只公开订阅的 Cloudflare 模式优先使用 [deployment.cloudflare-subscription.example.json](assets/deployment.cloudflare-subscription.example.json)，面板和订阅都要通过 Tunnel 时才使用 [deployment.cloudflare.example.json](assets/deployment.cloudflare.example.json)。示例地址与域名不可用于生产；只有 Cloudflare 控制面模式需要自有域名，REALITY 本身不要求域名。公网 IP 分支先按 [网络入口模式](references/network-topologies.md) 完成交互和风险确认，不直接改写安全模板。

## 随附工具

- `scripts/platform_profile.py`：离线识别发行版家族、架构和 init 支持状态。
- `scripts/verify_elf_arch.py`：离线读取 ELF 头，核对下载或安装后的 x86_64/ARM64 二进制；不执行被检查文件。
- `scripts/preflight.sh`：Linux 只读盘点，不安装、不重启、不改规则；云控制面仍需另查。
- `scripts/render_bundle.py`：校验 direct/NAT 和控制面参数，生成随机凭据、入站 payload 与私密客户端记录；不调用面板。
- `scripts/migrate_subscription_endpoint.py`：把已完成的 SSH-only 部署迁移为“仅订阅 Tunnel”，保留现有凭据与随机路径；不修改面板或 Cloudflare。
- `scripts/panel_api.py`：有限面板 API；读取私密 env，写请求须显式 `--apply`。
- `scripts/sqlite_snapshot.py`：SQLite 在线一致性备份，拒绝覆盖目标。
- `scripts/smoke_xray.py`：临时回环客户端验证配置、握手和出口，不修改系统代理。
- `scripts/probe_fallback.py`：默认只预览；授权后最多三次有界无凭据 HEAD 取证，不关闭证书校验。
- `scripts/reality_target_watch.py` 与 `assets/systemd/`：可选 systemd 告警；非 systemd 平台不安装。
- `assets/mihomo-routing.yaml`：可选分流模板，不是完整客户端配置。

这些工具不是盲跑的一键重装器。维护本 Skill 时运行 `python3 -B scripts/test_skill.py` 和 Skill validator。离线测试不等于任何供应商、系统或真实 VPS 的端到端验收。

## 交付

第一行先给 `完成 / 部分完成 / 阻塞 / 状态未知`，并用一句话说明用户现在能做什么。随后分别报告：支持判定、云端已核实、本机已应用、本机自检、外部客户端、订阅/直连配置、重启恢复、未验项目。报告系统/架构、供应商、入口模式、版本、监听、用户数量/额度、实际出口和回滚位置；不回显凭据。诊断未获修复授权时，交付根因层级、证据和一个优先修复建议，不执行修复。
