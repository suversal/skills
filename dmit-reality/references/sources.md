# 版本与资料

2026-09-03 整理时重新打开了以下官方入口。安装当天仍需复核，不能把整理日期当版本保证。

- [3x-ui 官方项目](https://github.com/MHSanaei/3x-ui)：固定版本安装、无人值守安装和 `/etc/x-ui/install-result.env` 的入口。
- [3x-ui Releases](https://github.com/MHSanaei/3x-ui/releases)：版本、迁移、已知问题；具体 tag 必须实际存在。
- [3x-ui 官方文档](https://docs.sanaei.dev/)：API/Swagger、订阅、用户字段和 Telegram 设置。
- [XTLS REALITY 官方示例](https://github.com/XTLS/REALITY/blob/main/README.en.md)：target/SNI、TLS 1.3/H2、客户端 REALITY 字段。
- [Xray REALITY 配置说明](https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/reality.md)：鉴权失败回落、共享 CDN 偷流量警告，以及回落限速的范围和可探测性代价。
- [Cloudflare 官方 IP 段](https://www.cloudflare.com/ips/)：对照当日实际 target 的 IPv4/IPv6；单一来源不证明非共享 CDN。
- [Nginx stream ssl_preread](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)：不终止 TLS 的 SNI 读取能力；例外防护先看代价，不原样照抄演示配置当白名单。
- [Xray-core Releases](https://github.com/XTLS/Xray-core/releases)：core 版本与变更。
- [Mihomo VLESS](https://wiki.metacubex.one/en/config/proxies/vless/) 与 [Releases](https://github.com/MetaCubeX/mihomo/releases)：实际客户端兼容性与可信发布产物。
- [MetaCubeX 规则数据](https://github.com/MetaCubeX/meta-rules-dat)：随附分流模板的上游，使用时检查资源可下载且内核解析成功。
- [Cloudflare Tunnel 本地管理流程](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/)：登录、创建、ingress、DNS 与服务配置。
- [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)：面板域名的 Access 应用与身份策略。
- [DMIT](https://www.dmit.io/)：以用户登录后台的实例信息、套餐账单和当期 ToS/AUP 为准，Skill 不固定价格、超额策略或重装收费。

## 已知版本边界

历史实机 3x-ui 3.6.0 使用 `/panel/api/clients/add`，请求为 `{"client": {...}, "inboundIds": [id]}`；不要套用旧 `/inbounds/addClient`。新装必须查看目标版本 Swagger/源码后再用随附 API helper，尤其 settings 字段和 `trafficResetDay`。

历史 Xray 26.7.28 输出的 X25519 公钥字段是 `Password (PublicKey)`；其他版本可能叫 `PublicKey` 或 `Password`。生成脚本只接受已识别形式，否则停止。

Xray 当前示例使用 `raw` 与客户端 `password`；历史面板 payload 是 `tcp` 与 `settings.publicKey`。随附 payload 沿用实机面板形状，smoke 客户端默认使用 `password`，也支持 `--key-field publicKey`。须按实际 core 执行 `run -test` 与真实握手，不能仅凭字段别名推断成功。

历史采用 `minClientVer=1.0.0` 是兼容实测选择，不是通用安全门槛；用户选择其他客户端时重测。不要靠关闭验证、`allowInsecure` 或改成明文 VLESS 修复兼容问题。
