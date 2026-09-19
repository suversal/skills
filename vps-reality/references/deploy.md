# 从新机器到可用配置

按顺序执行。所有示例变量必须来自本次平台档案，不直接运行示例 IP/域名。辅助脚本上传到独立 staging 目录，保留 `scripts/` 与 `assets/` 相对结构；不上传历史 `.env`、数据库或订阅。

## 1. 确认对象、授权和恢复入口

记录实例标识、供应商/区域、系统、架构、公网/NAT 模式、SSH、云防火墙、月度流量口径、已有业务及控制台/救援入口。域名、Tunnel、Access、保留 IP 若已存在，先确认归属。

只读信息齐全后，一次列出 Cloudflare Tunnel、SSH 隧道和公网 IP 直连，让用户选择。需要公网浏览器面板或自动订阅时优先推荐 Cloudflare Tunnel；只偶尔管理时说明 SSH 隧道攻击面更小。还要分别确认面板和订阅是否需要公网访问；不能因为用户拒绝 Cloudflare 就自动开放公网端口。选择公网 IP 时按 [网络入口模式](network-topologies.md) 做风险说明和二次确认；确认后必须按其选择实施，不能仅因风险较高而擅自换回 Tunnel/SSH。

重装会不可恢复地擦除系统盘。只有用户明确要求重装，并确认准确实例、目标镜像、架构、SSH 公钥指纹和数据清空后才能提交。云控制台显示 Running 不等于 SSH 验收；必须用本次密钥实际登录。主机指纹变化从可信控制台核对，不无条件删除 `known_hosts`。

```bash
ssh -p "$SSH_PORT" -i "$SSH_KEY_PATH" -o IdentitiesOnly=yes "$SSH_USER@$SERVER_ADDRESS"
```

## 2. 只读平台盘点

阅读 [平台与云厂商适配](platform-and-provider.md) 与 [网络入口模式](network-topologies.md)，在主机运行：

```bash
sudo bash scripts/preflight.sh
python3 scripts/platform_profile.py --require-supported
```

同时在控制台核对公网地址、地址生命周期、云边缘防火墙、路由/网关、NAT 映射、恢复入口和计费。确认：

- 发行版仍受供应商支持，systemd 正常，架构为 x86_64 或 arm64。
- cloud-init 已结束；磁盘、内存、时间同步和失败服务无阻塞问题。
- 实际 SSH 端口及密钥登录成功；有第二会话和控制台恢复路径。
- `LISTEN_PORT` 未被其他业务占用；443 被占用时不抢占。
- 云端与主机防火墙分别识别，IPv4/IPv6 分别检查。
- 已有 x-ui/Xray 时转运维流程，不覆盖安装。

任一支持证据不足，结论为 `manual_adaptation_required` 或 `blocked_missing_evidence`，停止自动变更。

## 3. 基础依赖和访问安全

先保存 SSH 配置、现有防火墙导出及云端规则摘要到服务器本机 700 目录；不删除旧公钥。

APT 分支在确认仓库和发行版后安装最小依赖：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl openssl python3 sqlite3 dnsutils
```

DNF 分支先查询包，再安装对应依赖：

```bash
sudo dnf makecache
sudo dnf install -y ca-certificates curl openssl python3 sqlite bind-utils
```

Fail2ban、`unattended-upgrades`、`dnf-automatic`、Swap 和 BBR 按现状决定，不作为安装成功前提。不得为了安装关闭 SELinux/AppArmor、替换内核或软件源。

SSH 收紧前运行实际 `sshd -t`、`sshd -T`，必要时用 `-C` 检查 Match；只 reload 实际服务名，并用第二会话验证。默认保留 SSH 端口和现有管理用户。

防火墙沿用当前管理器：

- 云端先仅增加本次 `PUBLIC_PORT/TCP`；NAT 供应商在控制台建立准确映射。面板/订阅规则只能按用户已确认的控制面模式另行增加。
- 主机先仅增加 `LISTEN_PORT/TCP`，不增加 UDP。SSH/Cloudflare 模式不开放面板/订阅端口；公网 IP 模式只开放已二次确认的服务，并按用户选择限制来源 CIDR 或开放到 `0.0.0.0/0`。
- OCI 保留 InstanceServices/iSCSI/链路本地规则，不 flush、不盲启 UFW。
- DNF 系沿用 firewalld/nftables 并保留 SELinux；APT 系也只有在确认无厂商关键规则和既有规则体系时才考虑 UFW。

先加允许路径，再收紧；从外部验证允许与拒绝结果。端口监听不能替代公网可达测试。

## 4. 固定版本安装 3x-ui

查看执行当日稳定 Release、迁移说明、安装器 tag/commit 和捆绑 Xray。优先官方原生安装 + SQLite；个人节点不默认 Docker/Postgres。不得安装 `master`、`dev-latest`，也不得把历史版本视为当前推荐。

下载到私密路径并审查：

```bash
umask 077
curl -fL --connect-timeout 15 --max-time 120 \
  "https://raw.githubusercontent.com/MHSanaei/3x-ui/${PANEL_VERSION}/install.sh" \
  -o "$INSTALLER_FILE"
sha256sum "$INSTALLER_FILE"
```

自算 hash 只能绑定本次审查内容，不等于官方签名。确认安装器支持本次发行版、架构、参数和安装方式后再执行；若不支持就停止。安装期间云/主机防火墙应已阻断管理端口公网访问。

安装后先把面板监听改为 `127.0.0.1`，检查所有面板/订阅监听、随机用户名/长密码/Web Base Path、面板/core 版本及架构。即使用户选择公网 IP，也先在回环状态完成备份和配置检查，再按已确认范围开放。安装日志和 `install-result.env` 权限 600，不输出到聊天，也不任意 `source`。

## 5. 选择 REALITY target

阅读 [SNI 与回落安全](sni-fallback-safety.md)，先完成目标预筛；交付前完成外部受控回落检查。共享 CDN 或证据不明的候选不得自动采用。

从本次服务器检查 DNS/TTL、所有 A/AAAA、CNAME、ASN/服务归属、TLS 1.3、ALPN H2、SAN、有效期、HTTPS 状态和延迟。固定 IP + SNI 按真实组合测试：

```bash
getent ahosts "$REALITY_SNI"
openssl s_client -connect "$REALITY_TARGET" -servername "$REALITY_SNI" \
  -tls1_3 -alpn h2 -verify_hostname "$REALITY_SNI" -verify_return_error < /dev/null
```

整体设置超时；不使用 `-k`。保留一份重新验证过的旧 target 作为回退，不自动轮换。

## 6. 生成私密配置包

SSH-only 使用 `assets/deployment.example.json`；Cloudflare 使用 `assets/deployment.cloudflare.example.json`。复制所选模板到本次私密工作目录，填写供应商、direct/NAT、控制面模式、内部/外部端口、实际出口、用户额度和当前客户端兼容要求。公网 IP 模式先用 SSH-only 模板生成节点与私密凭据，再走逐机适配分支；不得通过修改 helper 绕过二次确认。

```bash
python3 scripts/render_bundle.py --config deployment.json --check
sudo python3 scripts/render_bundle.py --config deployment.json \
  --xray "$XRAY_BINARY" --output /root/vps-reality-deploy-bundle
```

输出目录必须不存在。脚本生成随机密钥、UUID、Sub ID 和私密 VLESS 链接，只打印状态与路径。

- direct：`reality_listen_port == reality_public_port`。
- NAT：入站监听内部端口，客户端使用外部端口；额外生成的 `hosts.pending.json` 不含入站 ID，必须等入站创建并读回后填写。当前 3x-ui Hosts API 已取代旧 `externalProxy`；若安装版本没有对应 API，停止并做版本适配，不把旧字段硬塞进配置。
- Cloudflare 模式要求两个不同域名；SSH-only 模式允许域名留空，不得对外宣称已提供 HTTPS 自动订阅。
- 公网 IP 模式不是 renderer 的静默默认；它需要读取安装版本的真实设置 schema、单独备份、应用用户确认的监听和防火墙差异，再执行公网安全验收。

生成成功不代表 target、安全、面板 API 或网络已验证。

## 7. 备份并应用入站/订阅

查看当前 Swagger/源码，验证 settings、inbounds、clients 和 Hosts 的真实 API。随附 helper 的适配基线是历史版本；不匹配时先修改和测试 helper，不猜 endpoint 或直接改数据库。

```bash
sudo python3 scripts/sqlite_snapshot.py \
  --database /etc/x-ui/x-ui.db --output /root/vps-reality-before-inbound.sqlite
sudo python3 scripts/panel_api.py list --output /root/vps-reality-before-inbounds.json
sudo python3 scripts/panel_api.py settings --output /root/vps-reality-before-settings.json
```

确认没有现有入站或端口冲突。API 写操作需要一致性备份及显式 `--apply`。读取后合并 settings patch，不覆盖未知字段。NAT 模式创建入站后先 `list` 取得唯一入站 ID，把它填入 `hosts.pending.json`，再执行：

```bash
sudo python3 scripts/panel_api.py list-hosts --output /root/vps-reality-before-hosts.json
sudo python3 scripts/panel_api.py add-host --input /root/vps-reality-deploy-bundle/hosts.pending.json \
  --backup /root/vps-reality-before-inbound.sqlite --apply
```

helper 会拒绝空 ID、非 TCP REALITY 入站和已有 Hosts 条目。若 `/hosts/*` API 不存在或 schema 不同，操作失败并停下适配；不回退到旧 `externalProxy`。应用后读回 Hosts，并验证订阅使用外部端点。

如需 restart，使用唯一 systemd 临时任务并读取结果：

```bash
sudo systemd-run --unit="vps-reality-apply-$(date +%s)-$RANDOM" \
  --property=Type=oneshot /usr/bin/systemctl restart x-ui
```

不把命令提交成功当服务验收。检查 x-ui、Xray、LISTEN_PORT、回环监听、API 读回和实际生成配置。超时结果为未知，不自动重复写或恢复数据库。

在 Xray 路由中检查私网、保留、环回、链路本地地址阻止规则及用户约定的 P2P 边界。sniffing 不等于完成路由限制，P2P 识别也不是绝对保证。

## 8. 控制面

进入本节前复述用户选择。若此前没有明确答案，现在询问，不得从模板默认值推断。

### Cloudflare Tunnel 模式

从官方包源取得匹配架构的 cloudflared。Tunnel 凭据和 Token 私下写入 root-only 文件，不放聊天或命令行。ingress 形状：

```yaml
tunnel: TUNNEL_ID
credentials-file: /etc/cloudflared/TUNNEL_ID.json
ingress:
  - hostname: panel.example.com
    service: http://127.0.0.1:PANEL_PORT
  - hostname: sub.example.com
    service: http://127.0.0.1:SUB_PORT
  - service: http_status:404
```

先创建覆盖整个面板域名的 Access 应用，只允许指定身份，再开放面板路由。订阅域名不得被交互式 Access 覆盖。节点客户端仍使用 VPS/NAT 公网地址，不使用 Tunnel 域名。

验证：面板未授权被 Access 拦截；授权后仍需 3x-ui 登录；完整订阅 path 返回配置而非 HTML；根 404 可正常；公网 IP 的面板/订阅端口 IPv4/IPv6 均不可达。

### SSH-only 模式

保持面板/订阅回环监听，通过 `ssh -L` 在可信管理机访问面板。客户端导入私密 `clients.private.json` 中的 VLESS 链接。没有公网 HTTPS 订阅是预期限制，不安装临时 Web 服务补洞。

### 公网 IP 直连模式

读取当前版本设置/API 后，只对用户明确选择的面板或订阅改变监听。先展示并二次确认：公网地址、随机端口、HTTP/HTTPS、允许来源 CIDR 或 `0.0.0.0/0`、云与主机防火墙差异、凭据泄露影响和回滚点。优先推荐 TLS 与固定来源白名单；没有 TLS 时必须直说是明文 HTTP，不能称为安全或推荐方案。用户确认后即实施其选择，不得继续用相同风险反复劝退。

`panel_api.py` 故意只允许回环监听，公网模式不得给它增加隐式例外。逐机适配应使用安装版本明确支持的设置方式，并在写入前保存 SQLite 与防火墙；无法确认 schema 或回滚路径属于技术阻塞，应停止并说明，不能把“风险较高”本身当作阻塞。公网开放后验证所选服务确实可达、面板仍需自身认证、完整订阅仅返回对应用户配置；有限来源模式还要验证非允许来源不可达。选择 `0.0.0.0/0` 时单独确认并在最终报告中保留持续风险。

## 9. 最终验收

按 [分层验收](verification.md) 执行：

- 本机配置测试、服务和监听。
- 云防火墙、主机防火墙、NAT/LB 与外部 TCP 可达。
- 服务端临时客户端握手和出口。
- 用户真实外部设备/网络握手和出口。
- Cloudflare 完整订阅、SSH-only 私密直连配置，或经二次确认的公网 IP 访问边界。
- 每个用户的凭据、额度、到期、订阅隔离。
- NAT 对外地址/端口、SNI 回落与剩余风险。
- 获准重启后的服务、规则和登录恢复；未重启则明确未验。

最后交付脱敏说明、凭据私密位置和回滚路径。完整 URL/链接只进入 root-only 文件、密码管理器或用户明确批准的私密渠道。
