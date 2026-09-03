---
name: dmit-reality
description: 在 DMIT Debian VPS 上搭建或维护个人及少量朋友自用的 3x-ui、Xray、VLESS REALITY Vision 节点，配置 Cloudflare Tunnel 私有面板与订阅、Mihomo 分流、独立用户配额，并完成验收、目标切换和回滚。适用于 DMIT 搭梯子、重建节点、增加订阅用户及相关排障；不用于机场运营或无关 VPS 服务部署。
---

# DMIT REALITY 自用节点

默认中文。把“完成”落实到真实客户端能够更新订阅、通过 REALITY 连接并获得预期出口，而不是安装脚本返回 0。

本 Skill 来自 2026-08-27～28 的两次 DMIT 实践及后续运维记录。历史验证组合是 Debian 13、3x-ui 3.6.0、Xray 26.7.28、Mihomo 1.19.30；**这是历史兼容证据，不是今天的最新版或永久安全推荐**。不得把历史 IP、目标站点、额度、用户、SSH 公钥当作新机器默认值。

## 先识别本次任务

- 全新搭建：读 [完整部署流程](references/deploy.md)，按阶段执行。
- 增加用户、修改额度/备注、切换 target、升级、故障恢复：读 [运维与回滚](references/operations.md)，只执行请求范围内的部分，禁止重跑全新安装。
- 检查“是否正常”：读 [分层验收](references/verification.md)，先只读，不因发现问题自动重装、重启或换目标。
- 新装选目标、切换 target、SNI/共享 CDN/CF 偷流量问题：必须读 [SNI 与回落安全](references/sni-fallback-safety.md)。目标预筛在部署前完成，受控回落验收在交付前完成；证据不明不得当作安全通过。
- 用户只要方案、文档或 Skill：只产出文件，不连接或修改 VPS。

执行前重新查阅 [版本与官方资料](references/sources.md) 中本次需要的来源，尤其安装器、API 和客户端字段。新版本接口不匹配就停止该步骤，先适配，不能用旧 SQLite 写法硬改新数据库。

## 必须保持的边界

```text
客户端代理流量 ──> DMIT 公网 IP:443 ──> Xray REALITY + Vision
面板 HTTPS ─────> Cloudflare Access + Tunnel ──> 127.0.0.1:面板端口
订阅 HTTPS ─────> Cloudflare Tunnel ───────────> 127.0.0.1:订阅端口
```

1. 节点直连 DMIT，不走 Cloudflare 橙云/Tunnel。SNI/target 是伪装目标，不是出口；多个用户/端口不能变出多个国家的出口。
2. 面板与订阅仅绑定回环；面板加 Access 身份白名单，订阅不加交互式 Access 登录。随机订阅路径与每用户 Sub ID 都属于凭据。
3. 不随意重装系统、清空防火墙、删 SSH 公钥或关闭现有登录方式。重装需核对实例后获得明确的数据清空确认；加固时保留旧会话，并验证第二会话和控制台恢复路径。
4. 默认只需现有 SSH TCP 端口及 REALITY TCP 443。发现其他业务/监听时先调查，不能套用“只留两个端口”删掉业务规则。
5. 每人独立 UUID、Sub ID、额度、到期与停用开关。用户额度总和可以超卖，但入站额度应按 DMIT 当期实际计费口径留余量；不能把面板额度当作整机账单上限，尤其不得假定它覆盖未认证回落流量。
6. 密钥、Token、UUID、Sub ID、完整订阅/面板随机路径不写 Skill、公开文档、Git、日志或命令参数。仅在服务器 root-only 文件或用户批准的私密交付渠道保存。读取 `.env` 不能任意 `source` 不受信文件。
7. 重大修改前保存本机一致性 SQLite 快照与配置，目录 700、文件 600。不要复制活跃 SQLite 主文件当完整备份；数据库备份包含用户凭据。
8. 不默认安装 Komari、离机备份代理、额外协议、WARP、公共订阅转换器或公网订阅监控。保留本机回滚。Telegram/定时监控在用户本次选择时才启用；同一 Bot 不允许两台面板同时长轮询。
9. 日常监控只告警，不自动切换 target、重启 Xray 或重装。重启/切换影响代理时，用唯一命名的服务器端 systemd 临时任务；执行后单独验收，不能拿 SSH 断开当失败结论。
10. `serverNames` 不等于回落防火墙。默认不选可跨站复用的共享 CDN target；SNI 过滤/回落限速是需要评估与授权的例外措施，不自动堆叠。健康监控正常、trace 403/404、固定 IP 或未泄漏 UUID，均不能证明没有回落偷流量。

## 最少输入

先从当前任务和只读配置获取，缺失时集中询问：目标实例/IP、SSH 用户/端口/密钥、面板与订阅域名及 Cloudflare 可用权限、用户清单/额度/重置日、实际客户端。不得要求用户把 Token/私钥贴进聊天。

以 [deployment.example.json](assets/deployment.example.json) 为输入模板；示例地址与域名不是可用生产值。只有面板/订阅入口需要自有域名，REALITY 协议本身不要求购买域名；用户没有域名时解释 SSH 转发管理和私密本地配置的受限替代，不擅自购买。

先给一段精简执行摘要：目标机器、当前/目标状态、会改什么、会不会中断、回滚点。已获得授权且没有新风险时继续，不逐条反复确认。

## 随附资源

- `scripts/preflight.sh`：Linux 只读体检，无安装/重启/规则变更。
- `scripts/render_bundle.py`：校验参数并用本机 Xray 生成随机凭据、3x-ui 入站 payload、订阅设置 patch、私密用户记录。只写新目录，不调用面板、不覆盖已有文件。
- `scripts/panel_api.py`：回环地址上的有限 API 操作；读取私密 env，不把 Bearer Token 放进进程参数；写请求须显式 `--apply`，默认不写。
- `scripts/sqlite_snapshot.py`：SQLite 在线一致性备份，拒绝覆盖目标；不恢复、不改源库。
- `scripts/smoke_xray.py`：启动临时回环 SOCKS 客户端、验证 Xray 配置与预期出口，然后清理；不会修改系统代理。需在真实客户端侧再测一次。
- `scripts/probe_fallback.py`：默认只预览；明确指定自己的节点并启用后，最多 3 次无 REALITY 凭据的 TLS/HTTP HEAD 取证，不关闭证书校验、不自动判安全。
- `scripts/reality_target_watch.py` 与 `assets/systemd/`：可选服务器本地健康告警；须先按运维文档配置，默认不安装/启用。
- `assets/mihomo-routing.yaml`：原方案的 AI/GitHub/媒体分流模板；GitHub 优先于 Microsoft。不是完整客户端配置，交给订阅生成器与节点合并。

这些脚本不是盲跑的一键重装器。完整的账号授权、版本核对、SSH 加固、Cloudflare 配置与真实外网验收由部署流程串起来。

维护本 Skill 时运行 `python3 -B scripts/test_skill.py`（测试额外需要 PyYAML，运行脚本本身仅需标准库）。离线用例覆盖参数/凭据生成、重复执行拒绝、SQLite WAL 一致性、API 写入门槛、schema 漂移、分流顺序和告警状态；它们不等同真实 VPS 部署测试。

## 交付

区分：本地已生成／服务端已应用／本地自检通过／外部订阅与真实客户端已验证。报告版本、监听、用户数量/额度、实际出口、回滚位置、未验项目及原因；不回显凭据。若只在本机做过静态测试，不得宣称新 Skill 已在 VPS 上端到端验证。
