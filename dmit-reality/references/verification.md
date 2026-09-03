# 分层验收：不能跳层

## A. 本机控制面

- SSH 新会话成功、NTP 正常、磁盘与内存健康。
- `x-ui`/Xray 正常；公网 443 确为目标 Xray 进程。
- 面板与订阅的**每一个**监听地址均为回环，不只检查第一条。检查 IPv4 与 IPv6。
- UFW/nftables 保留预期规则；Fail2ban sshd jail 正常；后台防火墙不冲突。
- 3x-ui API 读回 VLESS、REALITY、Vision、target、SNI、公钥、Short ID、用户数量、额度/到期/重置日，与本次输入一致。比较敏感字段只输出 match/mismatch，不回显值。
- 服务端 Xray 实际配置 `run -test` 通过；核实私网/保留地址和用户约定的 P2P 阻止规则，而不只验证入站 payload。

## B. REALITY 真连接

在配置包存在的主机上运行（用户名只用普通标签）：

```bash
sudo python3 scripts/smoke_xray.py \
  --record /root/dmit-deploy-bundle/clients.private.json \
  --client owner --xray "$XRAY_BINARY"
```

脚本生成临时 SOCKS 客户端，先 `run -test`，启动后通过它访问 HTTPS IP 检查服务，并比较 `expected_exit_ipv4`。只报告 config/handshake/exit 成功状态，结束时关临时进程，不碰系统代理。

若本次 Xray 使用旧别名，核对官方字段后再显式 `--key-field publicKey`；不要循环猜配置直到碰巧通过。凭据变更后必须从面板重新生成本次测试记录；旧 bundle 不是事实来源。

**服务器上连接自己只能证明内部路径**。必须在用户实际外部网络/设备上再用独立临时客户端或真实 App 验证。若没有外部设备权限，明确记为未验证；不能把服务器 self-test 当国内网络可达。

## C. 订阅控制面

私密 URL 通过读取受限文件进入网络库内存，避免命令行参数和异常栈泄漏。先本机回环 URL + 正确 Host，再外部 HTTPS full path，比较：

- HTTP 200；没有 Access 登录 HTML、重定向到登录页或空 body。
- 返回节点的服务端地址、SNI/公钥/Short ID、对应用户 UUID、Vision 均匹配。
- 不包含其他用户凭据。
- 所有启用用户均能获得其对应订阅。

随机路径、Sub ID、response body 和响应头的 subscription URL 都应脱敏。200 并不证明配置可解析，更不证明握手成功。

## D. Mihomo 与分流

取可信稳定 release 的正确平台/架构二进制；如发布 API 提供 SHA-256 digest，下载后校验，不把自算 hash 称为官方校验。缺可信校验时说明并选择已有可信安装，而不是跳过校验下载未知二进制。

将真实订阅存到 700 临时目录中的 600 文件。用 YAML 解析器设置测试端口/参数，不重复追加相同 YAML key。运行：

```bash
"$MIHOMO_BINARY" -d "$PRIVATE_RUNTIME_DIR" -f "$PRIVATE_CONFIG_FILE" -t
```

测试配置必须 `allow-lan: false`、绑定 127.0.0.1、禁止 TUN/系统代理、不公开 external-controller。启动临时内核，从该 HTTP/SOCKS 端口访问 HTTPS，验证期望出口；若默认组是自动选择或 DIRECT，先在本地私密配置里选定要测的 DMIT 节点，防止测到直连。

确认 providers 实际下载并加载，不只是 `-t` 语法通过。查看受控请求的规则命中：GitHub 在 Microsoft 之前并走代理；AI/媒体按约定；国内/局域网直连；广告可单独切 DIRECT 排障。不要保存敏感浏览历史或输出未脱敏内核日志。

## E. 外网安全入口和恢复

- 新装或 target/前置网络变更须完成 [SNI 与回落安全](sni-fallback-safety.md) 的目标归属和受控未认证测试，合法 REALITY 握手不能替代它。未知/未覆盖项单列，不因脚本退出码 0 判定安全。
- 外网 443 可达，但面板/订阅源站端口不可达（包括 IPv6）。
- 面板未授权身份被 Access 阻止，授权用户正常看到面板登录；账号密码/TOTP 状态实测。
- root 404 与 full path 200 的差异解释清楚。
- 用户同意中断时进行重启后恢复验收；否则标注“开机自启已配置，重启恢复未实测”。
- 回滚备份可读且 SQLite integrity check 为 ok；恢复操作未做就写“恢复预案已准备”，不能声称演练通过。

## 最终报告模板

```text
目标：本次实例/区域（避免私人标识过度披露）
版本：Debian / 3x-ui / Xray / 实测客户端
已完成：应用状态；监听边界；用户数和额度/重置日
验证：配置 / 服务端握手 / 外部客户端握手 / 完整订阅 / 分流 / Access
回落风险：目标归属证据 / 未认证测试范围与结果 / 计量边界 / 残余风险
未验证：具体项目、原因及下一步
凭据：服务器 root-only 文件位置；未展示内容
回滚：一致性快照与配置目录；是否实测恢复
```
