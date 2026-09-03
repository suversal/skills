# 从新机器到可用订阅

按顺序执行。以下命令中的变量必须由本次核实的信息填写，不直接执行示例域名/IP。辅助脚本从 Skill 的 `scripts/` 上传至服务器独立 staging 目录，保留 `assets/` 相对布局；不要上传历史 `.env`、数据库或私人订阅。

## 1. 确认范围和机器

记录实例标识、套餐、区域、公网 IPv4/IPv6、OS/架构、SSH 用户/端口/私钥路径、月流量计费口径、重置日、剩余流量。域名、Tunnel 和 Access 应用若已存在，先辨认归属，不能把旧节点路由改给新机器。

如用户要求重装：展示准确实例、目标 Debian 版本、所选 SSH 公钥指纹以及不可恢复的数据清空影响；得到明确确认后，才通过 DMIT 后台提交。`Running`/运行时长归零只是后台完成，还要用所选私钥实际 SSH 登录。失败先查密钥匹配/后台控制台，禁止为省事开放密码登录。

```bash
ssh -p "$SSH_PORT" -i "$SSH_KEY_PATH" -o IdentitiesOnly=yes "$SSH_USER@$SERVER_ADDRESS"
```

不要关闭主机指纹检查。重装后指纹变更须通过可信控制台核对，不能无条件删除 known_hosts。

## 2. 只读基线

在目标 Debian 主机执行 `sudo bash scripts/preflight.sh`。确认：

- Debian/systemd、架构、内存/Swap/磁盘、NTP；没有尚未完成的 cloud-init。
- SSH 实际端口和公钥认证成功；443 没有被其他业务占用。
- 当前 UFW/nftables、IPv6、公网监听和服务；已有 x-ui 时走维护流程，不重新覆盖安装。
- 有第二个独立管理会话及 DMIT 控制台恢复方式。

只输出必要基线，不读取/打印 `authorized_keys` 全文、环境变量或服务 Token。公网 IP 是数据中心出口，不保证任何 AI/视频账号资格或“住宅 IP”标签。

## 3. 基础加固（逐项、可回退）

先保存 SSH 配置及防火墙导出到服务器本机 700 目录；不自动清理任何旧公钥。安装必要包：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl openssl python3 sqlite3 dnsutils ufw fail2ban unattended-upgrades
```

依据实际情况启用 NTP/安全更新。保留现有 SSH 端口，drop-in 可采用 `PasswordAuthentication no`、`KbdInteractiveAuthentication no`、`PubkeyAuthentication yes`、`PermitRootLogin prohibit-password`、`MaxAuthTries 3`。若用户已有 sudo 管理员，沿用其方案，不强制增加/删除用户。

先运行 `sudo sshd -t`，检查 `sudo sshd -T` 的实际值，随后 reload 而非盲重启。用第二个会话验证成功；原会话保持。Fail2ban sshd jail 使用实际 SSH 端口、systemd backend，确认不会封禁当前管理入口。

仅在确认新机没有其他业务/规则体系时设置 UFW：先放行实际 SSH TCP 端口和 443/TCP，再启用默认入站拒绝/出站允许。确认 UFW IPv6 开关与主机 IPv6 一致。**禁止 `ufw reset`、flush nftables 或照抄 22 导致非标准 SSH 断联。** 如已有复杂规则，保留原体系，仅做最小变更。

不为“性能优化”无条件加 sysctl、Swap 或改 MTU。小内存无 Swap 时可提议有上限的 Swap；BBR 已启用则不动。重启需要用户接受中断，且完成二次登录/启动恢复验收，不能把计划重启写成已验证。

## 4. 固定版本安装 3x-ui

查看执行当日稳定 Release 与对应 tag 的安装器，记录其 commit/tag、捆绑 Xray、迁移风险。优先官方原生安装 + SQLite，个人节点无需 Docker/Postgres。不得默认为历史 3.6.0，也不得无审查安装 `master`、`dev-latest`。

下面是已审查版本安装的命令形状，不是在 Skill 中固定版本：

```bash
umask 077
curl -fL --connect-timeout 15 --max-time 120 \
  "https://raw.githubusercontent.com/MHSanaei/3x-ui/${PANEL_VERSION}/install.sh" \
  -o "$INSTALLER_FILE"
sha256sum "$INSTALLER_FILE"
# 在执行前审查该文件，并将 hash 与已审查内容绑定；本地算 hash 不等于官方签名。
XUI_NONINTERACTIVE=1 XUI_DB_TYPE=sqlite XUI_SSL_MODE=none \
  bash "$INSTALLER_FILE" "$PANEL_VERSION" > "$PRIVATE_INSTALL_LOG" 2>&1
chmod 600 "$PRIVATE_INSTALL_LOG" /etc/x-ui/install-result.env
/usr/local/x-ui/x-ui setting -listenIP 127.0.0.1
systemctl restart x-ui
```

先核对所选安装器仍支持这些参数及随机凭据输出；如不支持，使用其真实文档，不盲跑。此阶段入站防火墙必须已阻断所有管理端口，避免安装器初始全接口监听窗口。不要把安装日志打到聊天。不要 `source` 不明 `.env`，随附 API helper 会以数据方式读取它。

验收：面板版本/core 版本、`x-ui active`、所有面板监听都为回环、root-only 安装记录、随机用户名/长密码/Web Base Path。记录准确端口，不能假定旧机随机端口。TOTP 在面板支持且用户能保存恢复方式时由用户私下绑定，不能未经验证声称已启用。

## 5. 选择并检查 REALITY target

本阶段先读 [SNI 与回落安全](sni-fallback-safety.md)，完成其目标预筛；交付前完成对应外部回落检查。共享 CDN 或证据不明的候选不得自动采用。该流程不要求默认增加 Nginx/限速器。

旧方案先用公开站点，后来切换到另一个目标；任何旧站点/IP 都只能作为待重测候选。优先 TLS 1.3、H2、证书匹配、不重定向的稳定站点，网络路径较近更好。

从本次 DMIT 检查 DNS/TTL、解析 IP/ASN、TLS 1.3、ALPN H2、SAN、有效期、HTTPS 状态和延迟。例如：

```bash
getent ahostsv4 "$REALITY_SNI"
openssl s_client -connect "$REALITY_TARGET" -servername "$REALITY_SNI" \
  -tls1_3 -alpn h2 -verify_hostname "$REALITY_SNI" -verify_return_error < /dev/null
```

命令整体加超时执行；不使用 `-k` 掩盖证书错误。核查共享 CDN 与未认证 fallback 风险，单次 `/cdn-cgi/trace` 没出现特征不构成安全证明。只做少量必要目标探测；端口/未认证行为测试仅针对自己的 VPS。保留一份经过验证的旧 target/SNI 作为回退，不实现自动轮换。生成脚本仅检查参数/生成配置，不做目标归属或回落安全判定，不能跳过本阶段。

## 6. 生成参数和私密配置包

把 `assets/deployment.example.json` 复制到本次工作目录，填入已确认参数。`quota_gib` 按 GiB 转字节；核对供应商 GB/TB 与上下行口径，入站留足系统与隧道流量余量。未认证回落不应假定受用户/入站额度完整保护，整机计量边界见安全检查流程。`expiry_ms` 是毫秒时间戳，0 表示不设到期；`limit_ip=0` 表示不要求限制，面板填写非零不等于 Fail2ban 强制限制已验证。

```bash
python3 scripts/render_bundle.py --config deployment.json --check
# 下行在目标主机执行；准确找出安装的 Xray 二进制，不能假定 amd64。
sudo python3 scripts/render_bundle.py --config deployment.json \
  --xray "$XRAY_BINARY" --output /root/dmit-deploy-bundle
```

输出目录必须不存在。脚本生成真实随机密钥/UUID/Sub ID，仅打印状态与路径，不在终端展示内容。它不安装、不访问面板、不修改 VPS 现有服务。配置包也不能上传 GitHub。

## 7. 保存回滚点并应用入站/订阅

先查看本版本 Swagger：验证 `settings all/update`、`inbounds list/add` 的路径和 payload 字段。下面 helper 的适配基线来自历史 3.6.0；新版本不匹配就适配，不反复猜 API。

```bash
sudo python3 scripts/sqlite_snapshot.py \
  --database /etc/x-ui/x-ui.db --output /root/dmit-before-inbound.sqlite
sudo python3 scripts/panel_api.py list --output /root/dmit-before-inbounds.json
sudo python3 scripts/panel_api.py settings --output /root/dmit-before-settings.json
```

快照目标拒绝覆盖。先确认没有已有入站/443 业务；已有节点转运维流程。用 API **读取后合并** settings patch，不覆盖未知设置。helper 的写操作需要传入现存的一致性 SQLite 备份及显式 `--apply`；这只是防误执行，不代替用户授权。

```bash
sudo python3 scripts/panel_api.py merge-settings \
  --input /root/dmit-deploy-bundle/settings.patch.json \
  --backup /root/dmit-before-inbound.sqlite --apply
sudo python3 scripts/panel_api.py add-inbound \
  --input /root/dmit-deploy-bundle/inbound.json \
  --backup /root/dmit-before-inbound.sqlite --apply
```

helper 拒绝在已有入站的面板执行全新入站创建；`clients` 随初始入站一并创建。订阅设置生效如需 restart，放入服务器端唯一命名临时任务，避免 SSH 走代理时截断执行：

```bash
sudo systemd-run --unit="dmit-apply-$(date +%s)-$RANDOM" \
  --property=Type=oneshot /usr/bin/systemctl restart x-ui
```

不要用上述命令退出码当验收；读取该 unit 结果，检查 API 回读、x-ui、Xray、443、两个回环监听及订阅。helper 遇到超时只报告未知结果，**不自动重复写、不自动恢复数据库**，按运维说明先读回事实。

在面板 Xray 路由模板中检查并补充本次需要的安全边界：保留/私有/环回/链路本地地址不得被代理用户访问，按约定限制 BitTorrent/P2P。检查是否已有对应 block outbound/rules，仅最小补充，生成实际 Xray 配置后 `run -test`。随附入站 payload 的 sniffing 不等于完成了这些路由限制；P2P 识别也不是完美保证。

## 8. Cloudflare Tunnel 与面板 Access

若用户没有 Cloudflare 权限/域名，停在这一阶段明确缺项；不声称部署全链路完成。不能用用户订阅 URL 去公共转换网站。

从官方包源安装 cloudflared，校验包源签名。本地管理或远程管理任选一种，避免混用控制面：

- **本地管理**：在可信管理机登录 Cloudflare，创建专用 Tunnel；服务器只保留该 Tunnel 的专用 JSON 凭据，不拷贝账号级 `cert.pem`。编辑下面 ingress，对应用 CLI 验证与添加 DNS 路由，然后安装服务。
- **远程管理**：在后台创建 Tunnel 和两个 Published application routes；由用户在受控终端/安全文件注入 connector Token。检查当前版本是否支持 Token 文件；不可把 Token 放进聊天、复制到 Skill 或 `ps` 可见参数。若官方安装步骤不可避免暴露参数，让用户自行私下执行，助手只验证结果。

本地管理配置形状（实际值均要替换）：

```yaml
tunnel: TUNNEL_ID
credentials-file: /etc/cloudflared/TUNNEL_ID.json
ingress:
  - hostname: panel.example.com
    service: http://127.0.0.1:PANEL_PORT
  - hostname: sub.example.com
    service: http://127.0.0.1:2096
  - service: http_status:404
```

配置/凭据 root-only；`cloudflared tunnel ingress validate` 通过后启用服务。域名对应该 Tunnel 的 DNS 路由，不是代理节点地址；不要让 Xray 客户端使用橙云域名替代 VPS IP。

**先**创建面板 Access Self-hosted 应用，覆盖整个面板主机名，仅允许指定身份；确认未登录和未授权身份无法进入，再开放面板的 Tunnel 路由。合法用户仍须登录 3x-ui。订阅主机名不得被此应用或通配 Access 策略覆盖；无法交互登录的客户端会拿到 HTML 而不是订阅。

外部验证：面板先到 Access；完整订阅路径 HTTP 200 且内容是配置；根路径 404 可正常；直接公网 IP:面板端口/IP:订阅端口均不可达；IPv6 同样检查。只验证 full path，绝不能把订阅根 404 当故障。

## 9. 客户端导入与最终验收

按 [分层验收](verification.md) 执行。私下从生成包 `clients.private.json` 或面板取得每个人自己的地址。Clash Verge Rev/Mihomo 导入 Clash URL，更新并激活配置，规则模式，选中 DMIT 节点，按用户需求开启系统代理/TUN。

分流模板保留我们原来的 AI、GitHub、Telegram、YouTube、Netflix、境外媒体走代理，Apple/Microsoft/国内默认直连和可关闭广告组。GitHub 规则排在 Microsoft 之前；规则数据拉取失败必须报告，不能只凭 YAML 有相应文字宣布分流成功。QX rewrite/脚本/MITM 不能直接搬到 Mihomo。

为每个人测试独立订阅、UUID/额度/到期和实际握手。未经同意不故意耗尽流量或停用活跃用户做测试。只在新建测试用户或确认的维护窗口验证停用效果。

最后交付脱敏使用说明和回滚路径；完整 URL 仅进入密码管理器或明确批准的私密交付文件。告警/监控按 [运维文档](operations.md) 可选追加，不自动启用。
