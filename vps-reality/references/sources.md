# 版本与官方资料

链接是重新核实的入口，不是永久行为保证。安装或变更当天查看当前页面、Release、发行版状态和账号控制台；不要把 Skill 维护日期当版本保证。

## 代理与控制面

- [3x-ui 官方项目](https://github.com/MHSanaei/3x-ui) 与 [Releases](https://github.com/MHSanaei/3x-ui/releases)：固定版本安装、架构、迁移和已知问题。
- [3x-ui 官方文档](https://docs.sanaei.dev/)：API/Swagger、订阅、客户端与设置。
- [3x-ui Hosts API](https://github.com/MHSanaei/3x-ui/blob/main/docs/content/docs/en/reference/api/hosts.mdx)：NAT/外部地址覆盖；当前 Hosts 机制取代旧 `externalProxy`，必须按安装版本验证。
- [3x-ui OpenAPI](https://github.com/MHSanaei/3x-ui/blob/main/docs/public/openapi.json)：按安装版本核对 `/panel/api/hosts/*`、设置与入站请求体，不能只参考 `main`。
- [XTLS REALITY](https://github.com/XTLS/REALITY/blob/main/README.en.md) 与 [Xray REALITY 配置](https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/reality.md)：target/SNI、客户端字段、鉴权失败回落和共享 CDN 风险。
- [Xray-core Releases](https://github.com/XTLS/Xray-core/releases)：core 版本、架构产物与变更。
- [Mihomo VLESS](https://wiki.metacubex.one/en/config/proxies/vless/) 与 [Releases](https://github.com/MetaCubeX/mihomo/releases)：客户端字段、架构和发布产物。
- [MetaCubeX 规则数据](https://github.com/MetaCubeX/meta-rules-dat)：可选分流模板上游。
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/) 与 [Access](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)：可选控制面。
- [Cloudflare IP 段](https://www.cloudflare.com/ips/)：共享 CDN 归属检查的一个信号，不是唯一证据。
- [Nginx stream ssl_preread](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)：仅在用户授权的 443/L4 前置专项方案中参考。

## 系统与云厂商

- [Debian Releases](https://www.debian.org/releases/) 与 [Ubuntu releases](https://ubuntu.com/about/release-cycle)：确认发行版仍受支持。
- [Red Hat 生命周期](https://access.redhat.com/support/policy/updates/errata) 与 [Oracle Linux 生命周期](https://www.oracle.com/a/ocom/docs/elsp-lifetime-069338.pdf)：DNF 系版本支持范围；Rocky/Alma 还需查看各自官方说明。
- [OCI Compute 最佳实践](https://docs.oracle.com/en-us/iaas/Content/Compute/References/bestpracticescompute.htm)、[Security Lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm) 与 [Public IP](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingpublicIPs.htm)：平台保留规则、云防火墙和地址生命周期。
- [AWS Security Groups](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html) 与 [Elastic IP](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-eips.html)：边缘规则和地址生命周期/费用。
- [Google Cloud VPC firewall](https://cloud.google.com/firewall/docs/firewalls) 与 [External IP addresses](https://cloud.google.com/compute/docs/ip-addresses/reserve-static-external-ip-address)：VPC 规则和静态地址。
- [Azure NSG](https://learn.microsoft.com/azure/virtual-network/network-security-groups-overview) 与 [Public IP](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses)：NSG 与公网地址。

## 已知版本边界

随附 `panel_api.py` 的写入路径源于历史 3x-ui API。新装必须读取目标版本 Swagger/源码；HTTP 200 还要检查业务 `success`。不得用旧 SQLite schema 硬改新数据库。

3x-ui 的 `shareAddrStrategy` 与 Hosts API 仍可能演进。NAT 模式生成 `hosts.pending.json`，不再自动写 legacy `externalProxy`；必须按安装版本核对 API，并读回 raw/JSON/Clash/二维码确认外部地址和端口。

Xray 的 X25519 公钥输出字段在版本间出现过 `Password (PublicKey)`、`PublicKey`、`Password`。生成脚本只接受已识别形式，否则停止私下检查。

`minClientVer` 没有跨版本、跨客户端通用的固定值。配置为空或显式值都必须按当前 core 和实际客户端验证；不得靠关闭验证、`allowInsecure` 或明文 VLESS 修复兼容问题。
