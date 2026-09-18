# 日常维护、告警与回滚

## 新增用户、配额及订阅命名

不要重跑安装或 render 后覆盖既有凭据。先 API 只读获取入站、客户清单和当前统计，备份数据库，确认同名/重复 ID 不存在。

历史 3.6.0 的独立客户端接口：`POST /panel/api/clients/add`，payload 为 `{"client": {...}, "inboundIds": [实际入站ID]}`。字段包括随机 UUID、随机 Sub ID、`email` 标签、`flow=xtls-rprx-vision`、`totalGB`（单位是字节）、`expiryTime`（毫秒，0 为不设）、`enable`、`limitIp`。新版本按 Swagger。不得将 HTTP 200 当 success=true，也不得失败后直接重复创建。

`panel_api.py add-client --input 私密payload文件 --backup 一致性备份 --apply` 会拒绝同 UUID/Sub ID/名称；写后重新读回并验证每用户订阅/握手。额度之和不等于套餐增加；尤其总入站保险额度不随加朋友自动上涨。用户月度 reset 与入站 reset 是不同字段，设置后必须验证实际调度，不把 `reset=0` 当作“每月自动重置”。

泄漏时仅停用/轮换受影响用户的 UUID + Sub ID，保留其他人；停用、轮换都是写操作，须在用户授权范围内。不能只改 URL 外观而保留已泄漏 UUID。

全局命名入口：面板设置 → 订阅 → 信息 → Remark Template。只改一个节点/用户则改入站 remark 或 client email，不改全局。emoji 是普通文本；实际支持变量按安装版本检查。

可用模板：

```text
{{INBOUND}}-{{EMAIL}}|📊{{TRAFFIC_LEFT}}|⏳{{DAYS_LEFT}}D
{{INBOUND}}|{{EMAIL}}|{{TRAFFIC_USED}}/{{TRAFFIC_TOTAL}}
{{INBOUND}}|{{STATUS_EMOJI}}|到期 {{EXPIRE_DATE}}
```

`DAYS_LEFT/TIME_LEFT/EXPIRE_DATE/EXPIRE_UNIX` 为不同显示方式；无限额或未设置到期可能隐藏相应段。不要在显示名称放 UUID、Short ID、Sub ID、Telegram ID。

## target 切换：备份—同步—验证—必要时回退

只改实际目标入站。读取当前 target/SNI、客户端集、额度/重置日，保存完整 before payload；按 [SNI 与回落安全](sni-fallback-safety.md) 准备新 target 的归属/协议证据，切换后重做受控回落检查，不能仅以合法客户端可用作为验收。

1. 用 SQLite backup 保存一致性快照，并备份测试凭据记录、订阅设置和活动 target 记录。服务端 backup 700/600。
2. 新目标连接预检通过，确认本次中断范围及用户授权。
3. 在唯一名称的 systemd transient unit 内执行完整事务，不只 detach 一个 restart；加单任务锁。不要复用尚未清理的 unit 名，否则可能根本没运行。
4. 只更新 target/serverNames 及确需变更的客户端对应 SNI，**先同步测试记录**再调用 smoke。默认保留 UUID、私钥/公钥、Short ID、客户端集、额度/重置日。
5. 重启/重载，检查 core 配置、实际 `LISTEN_PORT/PUBLIC_PORT`、API 读回、所有订阅的新 SNI 和实际外网握手。用 before/after 比较不应变化的字段，不能写死用户数、额度或重置日。
6. 失败时先辨别是 SSH 经代理中断、测试 SNI 仍旧，还是实际目标失败。超时后读回事实；未确认任务结束不得并发重试或回滚。
7. 确认失败且回退在本次授权内时恢复 before payload/记录，必要时按下节恢复数据库，再做**旧目标握手验收**。打印“已复制备份”不等于恢复成功。
8. 成功后要求客户端更新订阅。旧配置缓存/旧连接可能继续走旧参数，需要刷新/重启客户端内核。

随附 Skill 不打包旧的固定 Sony/其他目标切换脚本：旧脚本写死了客户数量和计费周期，不能在另一台机器上安全执行。已有服务器安装的 `reality-target-switch` 必须先审查其实际版本与档位再使用，不能假定其存在或适用于当前主机。

## 数据库恢复

`sqlite_snapshot.py` 用 SQLite backup API 创建可验证的一致性快照，包含凭据，别上传公开渠道。

恢复须处于已授权故障回退或维护窗口，阻止并发面板写入：

1. 保存当前失败现场到另一个私密目录，记录服务状态；停止 x-ui 并确认数据库没有写进程。
2. 将现有 `x-ui.db` 及同名 `-wal`、`-shm` 移入失败现场目录，不把旧 WAL 残留到恢复后的数据库旁边。禁止对通配根目录执行删除。
3. 将指定、已核验 `integrity_check=ok` 的快照恢复为 `/etc/x-ui/x-ui.db`，保持实际服务所需 owner/group，权限不宽于原来；同步恢复相关 env/target/Tunnel 配置。
4. 启动 x-ui，执行 verification.md 的对应验收。如启动失败，停止继续写入，保留两份现场，报告状态。

如果期间发生其他人的面板修改，整库回退会覆盖那些修改；先协调维护窗口，优先按 before payload 做局部回退。数据库迁移后的备份不能盲还原到旧版本 core/panel 组合。

## 可选：本地 target 健康监控

用户选择启用时才安装。随附 `reality_target_watch.py` 只检查固定候选 target 的 DNS/TLS/证书/HTTPS，以及本机 x-ui/配置的监听端口；**不是完整外网 REALITY、订阅、整机宕机或回落偷流量监控**。它不检查带宽计量、云/NAT 公网入口或跨域回落；`healthy` 不等于无滥用。同机服务无法在 VPS 完全失联时自告警。无自动切换、重启、流量重置。

把脚本安装到 `/usr/local/sbin/reality-target-watch`，权限 755；服务/timer 来自 `assets/systemd/`。创建 `/var/lib/reality-target-watch`（700）。配置 `/etc/x-ui/reality-watch.env`（600，root），经交互隐藏输入写 Token/Chat ID，不把它们放入 argv、heredoc 工具消息或聊天：

```text
WATCH_DOMAIN=实际目标域名
WATCH_IP=实际目标IPv4
TARGET_PORT=443
LISTEN_PORT=实际Xray监听端口
FAILURE_THRESHOLD=3
RECOVERY_THRESHOLD=2
CERT_WARN_DAYS=14
CONNECT_TIMEOUT_SECONDS=8
TELEGRAM_BOT_TOKEN=由用户私下填入
TELEGRAM_CHAT_ID=由用户私下填入
```

复制模板后先填真实值；脚本拒绝不合法 Token/IP。`WATCH_IP` 应出现在域名解析中，这一策略用于发现目标漂移；只固定 IP 但与 DNS 不一致的目标需要解释并调整策略，不能关告警掩盖。

先 `reality-target-watch --no-alert`（不发送、不改变通知计数），再在已授权接入 Telegram 的前提下 `--test-alert`，验证对方真实收到、API `ok=true`。最后 `systemctl daemon-reload`、`systemctl enable --now reality-target-watch.timer`，手动启动一次 service，确认 unit Result、下次调度和状态文件。

服务沙箱必须保留 `RuntimeDirectory=reality-target-watch`、锁 `/run/reality-target-watch/lock`、`ReadWritePaths=/var/lib/reality-target-watch /run/reality-target-watch`；直接把锁放 `/run/reality-target-watch.lock` 会遇到只读文件系统。oneshot 完成后 runtime 目录消失可以正常。

3 次连续失败告警、2 次连续恢复通知；发送失败不标记通知已送达，下次重试。`--no-alert` 不消耗阈值状态。正常且无变化时不发消息。

Telegram 409 通常说明同一个 Bot Token 被多个 3x-ui 实例长轮询。选一台或不同 Bot；不能由此断言另一台的 SIGHUP 是该冲突造成。若内置机器人也使用同一 Token，该 Token 有面板管理能力，不应称为“仅告警 Token”。默认不开启数据库 Telegram 备份或自助管理。

## 常见故障最短路径

| 现象 | 先查 | 不要做 |
|---|---|---|
| SSH publickey 拒绝 | 实例、端口、所选密钥指纹、控制台 | 开密码登录/删全部公钥 |
| 安装/改配置后入口没起来 | 实际 core 配置测试、LISTEN/PUBLIC 端口、云/NAT 规则、服务日志 | 连续整机重启 |
| 面板/订阅根 404 | 完整随机路径，订阅专属 Sub ID | 重装面板 |
| 订阅 200 但客户端失败 | 内容是否 HTML、API 参数、内核兼容性 | 禁用 TLS 验证 |
| 切换后 connection reset | 新 SNI 是否同步、任务是否结束 | 拿旧 SNI 测新服务 |
| GitHub 仍直连 | 规则顺序、providers、旧连接缓存 | 修改 Microsoft 全部业务策略 |
| 供应商用量上涨而面板用户流量较低 | 同窗整机/用户/隧道统计、回落路径，见安全检查流程 | 把差值直接判成偷流量或靠用户配额保底 |
| OOM/服务中断 | 内核历史 journal、时间线、资源和重启证据 | 仅凭当前内存正常排除历史 OOM |

## 升级

只在用户要求或已授权维护范围执行。查看固定 release 与迁移说明；先一致性备份、记录准确面板/core 版本和回退二进制，单测试客户端灰度，验证订阅与外网握手再完成。别同时换系统、面板、core 和 target，避免无法定位原因。
