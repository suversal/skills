# SNI、共享 CDN 与回落偷流量

用于新装选 target、切换 target、修改 REALITY 前置网络、或用户询问异常带宽。只检查订阅命名/增加普通用户时无需重复全部测试；本次只改 Skill 时不接触 VPS。

## 1. 分清三条路径

| 路径 | 认证与行为 | 主要检查 |
|---|---|---|
| 合法 REALITY 客户端 → VPS → 业务站点 | 有效 REALITY 参数和 VLESS 用户凭据 | 实际握手、每用户配额、订阅泄漏 |
| 普通 TLS/非合法 REALITY → VPS → target | 鉴权失败流量可能回落转发，访问者不需要合法用户凭据 | target 是否是共享 CDN、跨域回落能力、整机流量 |
| 面板/订阅域名 → Cloudflare Tunnel → 回环服务 | 面板 Access + 自身认证；订阅为每用户私密 URL | 控制面暴露与凭据保护 |

回落用于伪装，所以“无 UUID 能看到 target 站点”本身不等于 VLESS 认证被绕过。问题在于 target 的共享服务能力是否让自己的 VPS 成为他人的 CDN 转发入口。此机制及风险见 [Xray 官方警告](https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/reality.md)。使用 Cloudflare 管理 DNS/面板/订阅，本身不说明 REALITY target 存在这类风险。

`serverName` 是客户端 SNI，`serverNames` 是服务端允许的 REALITY 名称，`target` 是实际回落地址；三者不是同一字段。白名单参与 REALITY 认证，不能仅凭“填了一个 serverNames”断言未认证连接被阻断。固定 target IP 也不能改变该 IP 原本的共享 CDN 属性。SNI 不应被当作秘密口令。

## 2. 选目标：先做风险判断，再部署

1. 从本次 VPS 读取候选 target 的 A/AAAA、CNAME、实际连接 IP、ASN/服务归属和检查时间；域名解析有多个地址时全部纳入范围，不能只挑一条非 CF 地址。
2. 用当日 [Cloudflare 官方 IP 段](https://www.cloudflare.com/ips/) 检查相关 IPv4/IPv6，结合 CNAME/ASN/服务信息判断。非 CF 不等于非共享 CDN；同 ASN、低延迟或供应商网络也不自动等于安全。
3. 验证候选的证书/SAN、TLS 1.3、H2、HTTPS 和稳定性。对固定 IP + 不同 SNI，按配置的真实组合测试，不用域名普通解析代替。
4. 默认优先选择有证据支持的非共享 CDN 目标。确认是 CF/其他可跨站复用的共享 CDN，或归属证据不明时，不自动推进上线/切换；报告风险，选择已验证替代目标，或请求用户决定是否走例外方案。
5. 换 IP、变更 DNS/target/SNI、修改前置代理或升级涉及回落行为的 core 后，重新评估受影响项目。历史“未见异常”不能作为当前白名单。

“不是共享 CDN”不能只靠一次 403/404、一个 `Server: nginx`、无 `CF-Ray` 或 `/cdn-cgi/trace` 不可用来判定。响应头可以隐藏/伪装；反过来，出现 CF 字段是调查信号，也不是既已发生滥用的证明。

未部署时只能预筛 target；外部回落验收需要节点存在。新机可在授权的测试阶段创建入站，尽可能把测试窗口限制在受控来源；测试完成前不向普通用户交付。不要因“待检查”自动停用已有节点。

## 3. 小流量受控回落检查

前提：准确核对自己的 VPS IP/端口；测试域名为用户控制或明确获准测试的端点，使用公开、无副作用的小资源。不得扫描别人的节点、枚举 CDN 站点、下载大文件、测速或制造持续偷跑。只读核验也会产生少量网络流量。

随附 `scripts/probe_fallback.py` 不读取任何 REALITY 密钥/UUID/Sub ID，以普通 TLS 请求模拟未认证连接；TCP 连接始终直达指定 VPS IP，不受系统 HTTP 代理变量或测试域名 DNS 影响。

运行环境需要 Python 3.9+ 且其 SSL 库支持 TLS 1.3/ALPN（某些 macOS 系统 Python/旧 LibreSSL 不满足）。先用 `python3 -c 'import ssl; print(ssl.OPENSSL_VERSION, ssl.HAS_TLSv1_3, ssl.HAS_ALPN)'` 检查；不支持时脚本在建立连接前拒绝，换已有可信 OpenSSL Python 或合适的外部测试主机，不降低 TLS 版本/证书要求。预览模式不需要 TLS 能力。若改在 VPS 自身运行，只能标为内部路径证据。

```bash
# 默认只校验参数/显示测试范围，不联网。
python3 scripts/probe_fallback.py --server-ip "$PUBLIC_IP" --port "$PUBLIC_PORT" --allowed-sni "$REALITY_SNI"

# 已获得针对该节点的测试授权后才执行：一次基础 HEAD 请求。
python3 scripts/probe_fallback.py --server-ip "$PUBLIC_IP" --port "$PUBLIC_PORT" --allowed-sni "$REALITY_SNI" \
  --run --confirm-server "$PUBLIC_IP"

# 有获准测试的另一域名时，最多三次 HEAD 请求；可选明确的公开测试资源路径。
python3 scripts/probe_fallback.py --server-ip "$PUBLIC_IP" --port "$PUBLIC_PORT" --allowed-sni "$REALITY_SNI" \
  --test-domain "$CONTROLLED_DOMAIN" --path /probe.txt \
  --run --confirm-server "$PUBLIC_IP" --confirm-test-domain "$CONTROLLED_DOMAIN"
```

三个场景分别为：允许 SNI + 同名 Host；另一域名 SNI + 同名 Host；允许 SNI + 另一域名 Host。最后一个用于检查只限制 SNI 后仍可能存在的跨 Host 能力，不预设 CDN 必然允许 domain fronting。

脚本默认每次最多 8 秒、读取最多 8 KiB HTTP 响应头，无重试、并发、重定向跟随、大响应体下载或证书验证绕过。上限不是整机网卡字节精确上限，TLS/内核缓冲仍有开销。每次只跑一轮，有证据或失败即停下分析，不能循环到“成功”。

若已获准的测试端点预先配置了公开且唯一的响应头标记，可加 `--marker-header X-Reality-Probe --marker-value 公开标记`。脚本只输出是否匹配，不回显原始响应头/body。不要自动为测试创建外部站点或在第三方服务写数据。

### 结果如何解释

- 基础场景普通 TLS 能看到预期 target：说明回落路径可达，不等于拿到了代理授权。
- 跨域场景收到 HTTP/CF 头：存在回落响应信号，需与目标实际归属/日志核对；403/404 既不能自动判安全，也不能证明能访问任意内容。
- 跨域场景拿到约定测试资源的唯一标记，且目标端记录/流量时间线一致：可报告“已在受控范围复现跨域回落转发能力”，不要扩展成“所有 CF 站点均可访问”或“已经发生真实偷流量”。
- 证书错误、超时、reset、无标记、只有服务端本机测试：均为有限结果/未完成，不视为通过。脚本的 `security_assessment=requires_review` 与退出码 0 都不是安全认证。
- 脚本只覆盖 TLS 1.3 + HTTP/1.1 HEAD 和配置端点。空 SNI、其他协议、不同 TLS 行为不在自动覆盖范围；用户选择了 SNI 前置防护时，应在受控窗口追加空/不允许 SNI 拒绝测试和实际合法客户端回归，不能宣布全协议覆盖。

## 4. 处置顺序与例外

**首选：更换为经过检查的非共享 CDN target。** 沿用现有 target/SNI 变更与回滚流程，保留用户凭据/额度，重新做真实客户端与回落检查；这是降低共享转发面，不是消除所有匿名探测流量。

必须保留共享 CDN 时，先解释以下两种措施的代价并取得相应变更授权，不自动都装上：

- **SNI 前置过滤**：例如 Nginx stream `ssl_preread`，只把明确允许的 SNI 转发到回环 Xray，其他/空 SNI 按明确策略拒绝。它读取 ClientHello 而不终止 TLS，见 [Nginx 官方说明](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)。不能套用“默认也转到后端”的官方演示配置；它不是拒绝策略。增加前置层会改变 443 所有者、Xray 监听端口和来源 IP 统计/限 IP 行为，必须更新相应验收，不得开放后端公网端口；PROXY protocol 两端支持与配置要核验，不能为省事丢失来源限制。SNI 过滤看不到加密的 HTTP Host，不能承诺彻底消除同 SNI 下的滥用；需重跑跨 Host 检查。
- **回落限速**：核对安装版本的 `limitFallbackUpload` / `limitFallbackDownload`，只把它当带宽缓解，不当封堵。它按回落连接生效，不能推断为 VPS 全局流量上限。官方同时提醒限速可能形成可探测特征，故默认不启用；没有通用“安全固定数值”，也不把所有实例写成相同参数。若授权采用，按目标资源/预算评估并在极小、明确测试预算下验证；本 Skill 的 HEAD 检查不验证限速阈值。[Xray 参数与警告](https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/reality.md)

不要把“443 只允许 Cloudflare IP”作为修复：此架构合法客户端直连 VPS，套用面板源站防护规则会切断用户连接。也不能把 Cloudflare Access 登录页加到 REALITY 流量入口。

未知风险的现有节点：先采集、报告与请求处置方向；已授权止损时可限定受控来源或停用相关入口，但说明会断开用户，保留 SSH/控制台恢复路径。确认真实用户凭据泄漏时另行轮换该用户，别把所有流量异常都当成 CF 回落。

## 5. 计量与监控边界

不要假定未认证回落会计入某个合法用户、受 3x-ui 的用户/入站额度完整约束，或会经过用户路由/P2P 阻止规则；需以实际 core 版本、统计路径和受控对照验证。面板额度不是整机或供应商账单的硬上限。

疑似异常时先对齐同一时间窗：供应商上下行计费口径/更新延迟、物理网卡 RX/TX 增量、3x-ui/Xray 用户统计增量、实际监听连接与 target 出站、cloudflared/系统更新/其他业务。连接来源在前置代理/NAT 后可能不同；单一来源也不构成无滥用证明。差值只能提示继续定位，不能直接归因偷流量。短时日志只保留必要元数据，不长期抓取用户明文内容。

现有 `reality_target_watch.py` 检查 DNS/TLS/HTTPS、x-ui 和配置的本机监听端口，**既不做回落安全测试，也不检查带宽偷跑或云/NAT 公网入口**；`healthy` 不代表无滥用。DNS 漂移应触发重新评估，但不能自动换 target。整机流量告警/外部可达监控/探针需要另行授权，不因更新本 Skill 自动装服务。

## 6. 验收与结论

新装交付/target 切换完成之前，报告以下项；证据缺失记为待确认，不写“安全检查全部通过”：

```text
检查时间/实例：本次核实的对象
target/SNI/实际连接IP：匹配；覆盖哪些 IPv4/IPv6
目标归属：共享 / 非共享证据支持 / 不确定（附来源）
合法客户端：外部握手与预期出口
未认证测试：各场景状态、标记是否匹配、未覆盖项目
流量证据：窗口/统计口径/有无异常线索，或未检查
结论：风险未消除 / 证据不足 / 本次范围内未复现
处置：替代目标或获准的例外措施；剩余风险；回滚点
```

“本次范围内未复现”不是零风险保证；选择非共享目标也不能保证不被人重复请求其自身资源。历史快照不能证明当前没有偷流量。
