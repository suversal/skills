# 平台与云厂商适配

首次部署、迁移或接管新机器时必须阅读。本文件定义可公开承诺的支持矩阵；“命令能运行”不等于平台已支持。

## 1. 先形成平台档案

同时使用服务器只读结果和云控制台事实，记录：

```text
供应商/实例/区域：
发行版 ID/版本/是否仍受支持：
包管理器：APT / DNF / 其他
init：systemd / 其他
架构：x86_64 / arm64 / 其他
虚拟化：KVM / Xen / 容器 / 未知
公网：独立 IPv4 / 保留或临时 IP / NAT 映射 / IPv6-only / 私网
云防火墙：Security Group / NSG / Security List / VPC Firewall / 其他
主机防火墙：nftables / iptables / UFW / firewalld / 其他
恢复入口：串口/网页控制台/救援/快照/均无
已有业务及监听：
```

运行 `platform_profile.py --require-supported` 只能判定本 Skill 的 OS/架构/init 基线，不会判断发行版是否 EOL、云账号权限、端口公网可达或安装器是否支持当前版本。这些仍需当日官方资料和实际控制台确认。

## 2. 发行版分支

| 分支 | 支持对象 | 包与服务处理 | 不得照搬 |
|---|---|---|---|
| APT | Debian、Ubuntu 的受支持服务器版本 | `apt-get`；按实际选择 `unattended-upgrades`；SSH 服务通常为 `ssh` | 不假设 UFW 已启用；Debian/Ubuntu 安全源名称不同 |
| DNF | RHEL、Oracle Linux、Rocky、AlmaLinux 的受支持服务器版本 | `dnf`；DNS 工具通常为 `bind-utils`；SQLite 包通常为 `sqlite`；沿用 firewalld/SELinux | 不安装 UFW；不关闭 SELinux；Fail2ban 可能需要额外仓库，不能默认存在 |

安装最小依赖时先用包管理器查询真实包名和仓库，再安装 `ca-certificates`、`curl`、`openssl`、Python 3、SQLite CLI、DNS 工具。Fail2ban、自动更新、Swap、BBR 和 Docker 都不是部署 REALITY 的硬依赖；按现状和用户需求决定。

不支持的平台包括：Alpine/OpenWrt/Arch、非 systemd、Windows/macOS、容器内充当完整 VPS。遇到这些平台只做盘点并给出专用方案，不运行 APT/DNF/systemd 命令。

## 3. 架构分支

- 规范化 `x86_64/amd64` 为 `x86_64`，`aarch64/arm64` 为 `arm64`。
- 3x-ui 安装器、Xray、Mihomo、cloudflared 和任何下载的辅助二进制都逐一核对架构。某一组件没有匹配构建时停止，不用 QEMU 或未知第三方二进制掩盖。
- 压缩包能解压、二进制能执行、服务能启动、真实握手成功是不同层级。ARM64 必须跑与 x86_64 相同的配置测试和真实客户端验收。
- 不按文件名猜架构；使用 `file`、发布清单、官方 digest/签名和实际 `--version` 共同核对。

## 4. 云厂商适配器

所有厂商都要分别验证云边缘规则与主机规则。以下是检查入口，不是永久不变的控制台教程；执行当天重新打开官方文档。

### Oracle Cloud Infrastructure

- Security List/NSG、路由表、Internet Gateway、公网 IP 和主机规则分别确认。
- 保留平台镜像的 InstanceServices、iSCSI 和链路本地规则；不得 flush iptables/nftables，也不在 Ubuntu 镜像上盲目启用 UFW。
- A1/A2 为 ARM；公共 IP 区分 ephemeral 与 reserved。节点需长期稳定时优先评估 reserved IP，不把迁移后地址不变当保证。
- 免费额度、空闲回收、流量和区域能力按当前账号与官方规则核实；预算告警不是强制停机。

### AWS

- Security Group、NACL、路由表、Internet Gateway、Public/Elastic IP 与主机规则分别确认。
- Security Group 为允许规则模型，不要因主机端口监听就宣称公网可达。长期地址需求评估 Elastic IP 当前费用和配额。
- 不关闭 cloud-init、SSM、DHCP 或发行版网络服务来“精简”。Graviton 实例按 ARM64 分支。

### Google Cloud

- VPC firewall policy/rule、network tag 或 service account target、路由、外部 IP 与主机规则分别确认。
- 临时/静态外部 IP 的生命周期与费用按当前文档核实；已有代理/负载均衡不等于原始 TCP 已转发。
- 不把 HTTP(S) Load Balancer 当作 REALITY TCP 入口。

### Azure

- NSG、子网/NIC 规则、Public IP、路由和主机规则分别确认；NSG 生效不表示 guest firewall 已放行。
- Public IP 的 SKU、分配方式和生命周期按当前资源核实；不要沿用旧 Basic/动态行为记忆。
- Azure Load Balancer 只有明确配置 raw TCP probe/rule 且不终止 TLS 时才可能作为入口，需单独验收。

### DMIT、Hetzner、DigitalOcean、Vultr 等普通 VPS

- 核对控制台防火墙、救援/串口、重装与快照能力、流量计费方向、地址稳定性和 AUP。
- 没有云防火墙不代表可以重置主机规则。供应商自带 DDoS/防火墙产品也不能替代系统监听检查。

### NAT VPS

- 先取得服务商明确分配的公网 IPv4、外部 TCP 端口、内部端口和映射生命周期。
- 不把共享公网 IP 宣称为独享或必然“干净”；邻居行为可能影响信誉。
- 按 [网络入口模式](network-topologies.md) 生成和验证外部端点。

### 未识别供应商

走 `generic`：要求用户或控制台提供公网入口、边缘防火墙、恢复入口、地址生命周期和流量口径；信息不全时停在计划/盘点阶段，不猜控制台操作。

## 5. 防火墙决策

1. 列出现有管理器和规则；存在 nftables/iptables/firewalld/UFW 中任一实际规则时沿用它。
2. 先确认真实 SSH 来源、端口与第二会话，再添加 REALITY TCP 入口；面板/订阅端口不开放公网。
3. 云端只放行本次 public TCP port；SSH 按用户可维护的可信来源策略。不要为 VLESS TCP REALITY 增加 UDP 规则。
4. 检查 IPv4 和 IPv6。服务监听 `::` 可能同时暴露 IPv6；没有云 IPv6 规则也不能假定未来一直没有。
5. 修改后从外部验证允许和拒绝路径，并检查规则持久化。未经授权不重启；未重启就标记持久性未实测。

## 6. 支持结论

只允许以下结论：

- `supported_baseline`：OS/架构/init 落入支持矩阵；仍需部署前检查。
- `supported_with_provider_adaptation`：基础支持，云端/NAT/端口需按本机适配并验收。
- `manual_adaptation_required`：平台或拓扑超出自动范围；不得运行变更步骤。
- `blocked_missing_evidence`：无法确认实例、恢复入口、云规则或当前版本。

不要写“通用支持所有 Linux/所有云”。通用性的含义是先识别差异、选择已定义分支，并对未知环境安全停止。
