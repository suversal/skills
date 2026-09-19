# 网络入口模式

部署前必须确定一种模式。`PUBLIC_PORT` 是客户端连接端口，`LISTEN_PORT` 是 Xray 在实例内监听的端口。

## A. 独立公网地址

```text
客户端 -> 公网 IPv4:PUBLIC_PORT -> Xray:LISTEN_PORT
```

通常 `PUBLIC_PORT == LISTEN_PORT`。443 空闲时优先使用 443；其他 TCP 端口也能承载 REALITY，但客户端网络可达性和伪装观感需实际验证。

检查：公网地址是否绑定目标实例、临时/保留生命周期、云防火墙、主机规则、IPv6 暴露、端口占用、外部 TCP 可达。公网地址与实际出口可以不同，必须分别记录。

## B. NAT 端口映射

```text
客户端 -> 共享公网 IPv4:PUBLIC_PORT -> NAT -> 私网实例:LISTEN_PORT
```

要求供应商明确提供 TCP 映射。配置包使用 `network_mode=nat`；入站监听 `LISTEN_PORT`，私密客户端记录使用 `PUBLIC_PORT`。生成器会另外生成 `hosts.pending.json`，但不会写入已经被当前官方 Hosts API 取代的旧 `externalProxy` 字段。创建入站并读回 ID 后，才可填写模板的 `inboundIds`，按安装版本的 Swagger 复核，再通过 helper 显式应用。最后验证 raw、JSON、Clash 和二维码均输出外部地址与端口。

只为 VLESS TCP REALITY 配置 TCP 映射。服务商同时给出的同端口 UDP 映射不是本协议需求，不应据此开放主机 UDP。

NAT 共享 IP 不等于独享固定 IP。记录端口映射是否会在重装、续费、迁移后变化；变化时订阅必须同步更新。

## C. 443 已被占用

先定位所有者和业务，禁止停止未知网站或抢占端口。按优先级选择：

1. 使用单独的公网高位 TCP 端口。
2. 使用另一公网 IP/实例。
3. 用户确需共用 443 时，单独设计 L4 SNI 前置，并评估合法 REALITY、来源地址、PROXY protocol、网站 TLS、回落和限 IP行为。

本 Skill 不自动安装 Nginx/HAProxy 复用 443，也不把 HTTP 反向代理当成 raw TCP REALITY 前置。未完成专项设计就标记 `manual_adaptation_required`。

## D. 私网实例、负载均衡或端口转发器

只有入口能够原样转发 TCP、保留 REALITY TLS ClientHello、健康检查不会篡改协议，并且公网端点稳定时才继续。HTTP(S) 负载均衡、TLS termination、Cloudflare 橙云/Workers/Tunnel 不能作为 REALITY 节点入口。

使用 raw TCP Load Balancer/NAT Gateway 时，记录是否保留来源 IP、是否产生额外费用、idle timeout、健康检查和端口限制；用外部真实客户端验收。证据不全时停止。

## E. IPv6

双栈主机默认仍按已验证的 IPv4 节点生成配置，同时检查 IPv6 没有意外暴露面板或订阅源站。IPv6-only 自动生成尚不在本 Skill 的公开支持范围，因为客户端网络可达性、URI 格式、出口验证和供应商防火墙都需单独覆盖；先做专项适配。

## F. 控制面模式

只读盘点后必须把以下选择交给用户；未选择时不安装 Cloudflare，也不开放管理端口：

| 选择 | 面板 | 订阅 | 主要取舍 |
| --- | --- | --- | --- |
| Cloudflare Tunnel（公网访问优先推荐） | Access + Tunnel | 独立订阅域名，不套交互式 Access | 浏览器和自动订阅方便，需要域名、Cloudflare 权限和额外服务 |
| SSH 隧道（最小攻击面） | `ssh -L` 访问回环面板 | 私密 VLESS 链接；本机订阅仅在隧道内可达 | 最少依赖，但没有公网自动订阅 |
| 公网 IP 直连（高风险） | 公网管理端口 | 可选公网 HTTP 订阅 | 无第三方依赖，但会增加扫描、爆破和明文凭据泄露风险 |

一次把三种模式都告诉用户并让其选择；需要随时随地用浏览器访问面板或自动更新订阅时，优先推荐 Cloudflare Tunnel；只偶尔管理且能使用 SSH 时，说明 SSH 隧道攻击面更小。不要把“不装 Cloudflare”等同于“必须公网暴露”。

### Cloudflare Tunnel

仅承载面板/订阅：

```text
panel.example.com -> Access -> Tunnel -> 127.0.0.1:PANEL_PORT
sub.example.com -> Tunnel -> 127.0.0.1:SUB_PORT
```

节点地址仍是 VPS/NAT 公网入口。面板主机名加 Access；订阅主机名不能被交互式登录覆盖。直接公网访问面板/订阅端口必须失败。

### SSH 隧道

没有域名或 Cloudflare 权限时，面板只绑定回环，通过本地端口转发访问；使用生成的私密 VLESS 链接导入客户端。不要为了“方便”把面板临时监听到 `0.0.0.0`。外部自动订阅缺失必须如实报告。

### 公网 IP 直连

该模式不是安全默认，也不由 `render_bundle.py` 或 `panel_api.py` 自动放宽回环限制。用户选择后依次确认：

1. 暴露范围：仅面板、仅订阅或两者；二者端口必须与 REALITY/SSH 分开。
2. 传输保护：是否已有可验证的 TLS 方案。只有公网 IP + HTTP 时，明确说明账号密码、随机路径、Sub ID 和返回配置可能被中间网络观察。
3. 来源范围：优先建议一个或多个固定管理 CIDR，在云防火墙和主机防火墙同时白名单；用户也可以明确选择 `0.0.0.0/0`，但必须把它作为另一项高风险决定单独确认。
4. 二次确认：展示将监听的地址/端口、云端规则、主机规则、泄露后果和回滚方法，等待明确同意后才变更。

不得把随机高位端口、随机路径或强密码宣传成 TLS/访问控制的替代品。用户拒绝风险时回到 SSH 隧道或 Cloudflare Tunnel；用户理解风险并明确选择公网后，就继续实施，不得仅因没有 TLS、没有稳定白名单或选择 `0.0.0.0/0` 而替他撤销决定。实施时先备份设置与防火墙；一次只开放用户选中的服务；有限来源模式从允许和不允许的外部来源分别验收，全网开放模式则记录持续风险。完整凭据仍不得写入聊天。

## G. 验收清单

```text
模式：direct / nat / raw-tcp-lb / manual
公网地址与生命周期：
PUBLIC_PORT -> LISTEN_PORT：
云防火墙：
主机防火墙：
443 所有者：
外部 TCP 可达：
订阅/直连配置中的地址端口：
实际出口 IPv4：
IPv6 暴露：
剩余风险：
```
