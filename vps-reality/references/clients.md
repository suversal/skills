# 客户端导入与验收

最终验收必须由用户的真实设备和真实网络完成。本页帮助 Agent 用大白话指导用户导入配置，并把客户端现象映射到故障层。不要让用户把完整订阅地址或 VLESS 链接贴进聊天。

## 1. 选客户端

客户端必须同时支持 **VLESS**、**REALITY** 和 **`xtls-rprx-vision`**。以下是常见选择，不是版本保证；导入失败先让用户升级到当前正式版：

| 平台 | 常见客户端 | 建议订阅格式 |
|---|---|---|
| iOS / iPadOS | Shadowrocket、Stash、sing-box | Shadowrocket 用 Raw；Stash 用 Clash |
| Android | v2rayNG、FlClash、Clash Meta for Android、Hiddify | v2rayNG 用 Raw；Clash 系用 Clash |
| Windows | v2rayN、Clash Verge Rev、FlClash、Hiddify | v2rayN 用 Raw；Clash 系用 Clash |
| macOS | Clash Verge Rev、FlClash、sing-box、v2rayN | 按内核选 Raw 或 Clash |

“Clash 系”指 Mihomo（Clash Meta）内核。原版 Clash / Clash for Windows 等旧内核不支持 VLESS REALITY，不要推荐。

## 2. 三种导入方式

- **订阅链接**（Cloudflare 或公网订阅模式）：客户端里“添加订阅 / 从 URL 导入”，粘贴私密订阅地址，然后点更新。以后服务端改参数，用户只需再点更新。
- **VLESS 链接或二维码**（SSH-only 模式）：从 `clients.private.json` 取对应用户的链接，经用户认可的私密渠道交付；或在面板里显示二维码让用户扫。服务端改参数后要重新导入。
- **Raw / JSON / Clash 的区别**：Raw 是一组 `vless://` 链接，大部分 Xray/v2ray 系客户端能用；Clash 是 Mihomo 用的 YAML；JSON 是完整 Xray 配置，只给明确支持导入 Xray JSON 的客户端。用户不知道选哪个，按上表给一个即可。

## 3. 用户侧验收步骤

用下面这段话指导用户，逐条确认：

```text
1. 在客户端里添加订阅（或导入链接），点更新。列表里应该只有你自己的节点，而不是一堆网页代码或登录页。
2. 关掉 Wi-Fi，用手机流量，选中这个节点并连接。
3. 打开一个查 IP 的网站，显示的应该是服务器的 IP。
4. 再打开一两个平时常用的网站或 App，确认能正常加载。
5. 如果是订阅模式，再点一次更新，确认不开任何隧道也能更新成功。
```

用手机流量测，是为了排除家里网络和服务器同一路径时的误判。某一步失败时，记录客户端名称、版本、所用网络和报错原文，然后按下一节定位；不要先重装。

## 4. 客户端现象 → 故障层

| 客户端现象 | 最可能的层 | 先查 |
|---|---|---|
| 更新订阅失败，或导入后是 HTML、登录页 | 控制面 | 订阅域名是否被 Access 覆盖、完整路径/Sub ID、Tunnel 路由 |
| 导入成功但提示不支持 reality / flow，或节点缺字段 | 客户端 | 客户端或内核版本过旧、选错订阅格式 |
| 连接超时，所有网络都一样 | 云网络或主机入口 | 云防火墙、主机防火墙、端口监听、外部 TCP 可达 |
| 能建立连接但立刻断开、EOF、reset | REALITY 参数 | 客户端的 SNI、公钥、Short ID、flow 是否与服务端一致；是否用了旧订阅 |
| 显示已连接但打不开网页 | 出站、路由或 DNS | 服务端临时客户端的实际出口、Xray 路由、额度是否用完 |
| Wi-Fi 能用、流量不能用（或反过来） | 客户网络 | 两种网络分别实测；IPv4/IPv6；运营商对端口或地区的限制 |
| 只有某一个人不能用 | 用户凭据 | 该用户是否启用、额度/到期、订阅是否对应本人 |

定位后回到 [故障诊断](troubleshooting.md) 的修复门槛，一次只改一个变量，改完让用户在原设备、原网络上复测。
