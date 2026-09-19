# Skills

个人整理的可复用 Agent Skills。每个 Skill 独立放在同名目录中，包含入口说明、条件化参考流程、模板与必要的辅助脚本。

## 当前 Skill

### [vps-reality](vps-reality/SKILL.md)

面向个人及少量朋友自用的通用 VPS REALITY 节点搭建、维护与审查流程：

- 3x-ui、Xray、VLESS + TCP RAW + REALITY + Vision。
- Debian/Ubuntu（APT）与 RHEL/Oracle Linux/Rocky/AlmaLinux（DNF）。
- x86_64 与 ARM64；独立公网或明确的 NAT TCP 映射。
- OCI、AWS、Google Cloud、Azure、DMIT 和普通 VPS 的云/主机防火墙分层检查。
- 控制面交互选择：优先推荐 Cloudflare Tunnel，也支持最小攻击面的 SSH 隧道，以及用户明确确认后的公网 IP 直连面板/订阅。
- 独立用户凭据/额度、SNI/共享 CDN/未认证回落检查、分层验收和回滚。

入口：[SKILL.md](vps-reality/SKILL.md)；平台适配：[平台与云厂商](vps-reality/references/platform-and-provider.md)；网络模式：[direct/NAT/端口冲突](vps-reality/references/network-topologies.md)；安全检查：[SNI 与回落](vps-reality/references/sni-fallback-safety.md)。

## 使用

将整个 `vps-reality/` 文件夹放入 Agent 工具支持的 Skills 目录，保持 `scripts/`、`references/`、`assets/`、`agents/` 的相对结构。调用 `$vps-reality` 后，Skill 会先识别供应商、发行版、架构、网络入口和现有服务，再决定对应分支。

这不是盲跑的一键重装脚本。公开支持范围是主流 systemd Linux、APT/DNF、x86_64/ARM64、独立公网 IPv4/双栈或明确的 TCP NAT 映射。Windows、Alpine/OpenWrt/Arch、非 systemd、容器宿主替代、IPv6-only、TLS 终止型负载均衡和商业多租户会安全停止并要求专门方案。

## 验证与边界

随附 32 项离线测试，需要 Python 3.9+ 和 PyYAML；覆盖 NAT Hosts、平台识别、配置生成、API 写保护、备份和 SNI 回落。完整 TLS 用例需 Python SSL 库支持 TLS 1.3/ALPN：

```bash
python3 -B vps-reality/scripts/test_skill.py
```

旧 SSL 运行环境会跳过两个依赖 TLS 1.3 的用例；回落检查脚本会在不支持 TLS 1.3 时拒绝联网，不降低证书要求。

离线测试不等于任何云厂商或 VPS 的实机部署、安全审计和真实客户端验收。所有供应商规则、发行版支持周期、上游版本、API 和 NAT/订阅行为都必须在执行当天重新核实。

辅助脚本不包含真实密码、私钥、UUID、Sub ID、订阅地址或 Cloudflare/Telegram Token；运行时产生的配置、备份和凭据不得提交到仓库。本项目只用于用户有权管理的服务器，不用于未授权扫描、公共代理或商业机场运营。
