# Skills

个人整理的可复用 Agent Skills。每个 Skill 独立放在同名目录中，包含使用说明、参考流程、模板与必要的辅助脚本。

## 当前 Skill

### [dmit-reality](dmit-reality/SKILL.md)

面向个人及少量朋友自用的 DMIT Debian VPS 节点搭建与维护流程：

- 3x-ui、Xray、VLESS REALITY + Vision。
- Cloudflare Tunnel 私有面板与订阅入口。
- Mihomo 分流、独立用户凭据与配额。
- SNI、共享 CDN、未认证回落流量的检查和处置。
- 分层验收、目标切换、监控边界及回滚。

入口：[SKILL.md](dmit-reality/SKILL.md)；安全检查：[SNI 与回落安全](dmit-reality/references/sni-fallback-safety.md)。

## 使用

将整个 `dmit-reality/` 文件夹放入所用 Agent 工具支持的 Skills 目录，保持 `scripts/`、`references/`、`assets/`、`agents/` 的相对结构。先阅读 `SKILL.md`，再根据任务进入对应流程。

这不是盲跑的一键重装脚本。部署前需要确认目标机器、版本、权限、域名、用户额度和回滚方案；重装、网络变更与外部写入仍须得到相应授权。所有示例参数都需要按实际情况检查。

## 验证与边界

随附 29 项离线测试，需要 Python 3.9+ 和 PyYAML；完整测试需 SSL 库支持 TLS 1.3/ALPN：

```bash
python3 -B dmit-reality/scripts/test_skill.py
```

旧 SSL 运行环境会跳过两个依赖 TLS 1.3 的测试；回落检查脚本在不支持 TLS 1.3 时拒绝联网执行，不降低证书校验要求。

离线测试不等于 VPS 实机部署或安全审计。辅助脚本不包含真实密码、私钥、用户 UUID、Sub ID、订阅地址或 Cloudflare/Telegram Token；运行时产生的配置、备份和凭据不得提交到仓库。

本项目用于有权管理的个人设备和服务器，不用于未授权扫描或滥用第三方服务。上游软件、API、供应商规则和客户端行为可能变化，实际使用时需要重新核验。
