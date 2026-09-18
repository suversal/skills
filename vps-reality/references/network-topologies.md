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

### Cloudflare Tunnel

仅承载面板/订阅：

```text
panel.example.com -> Access -> Tunnel -> 127.0.0.1:PANEL_PORT
sub.example.com -> Tunnel -> 127.0.0.1:SUB_PORT
```

节点地址仍是 VPS/NAT 公网入口。面板主机名加 Access；订阅主机名不能被交互式登录覆盖。直接公网访问面板/订阅端口必须失败。

### SSH 隧道

没有域名或 Cloudflare 权限时，面板只绑定回环，通过本地端口转发访问；使用生成的私密 VLESS 链接导入客户端。不要为了“方便”把面板临时监听到 `0.0.0.0`。外部自动订阅缺失必须如实报告。

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
