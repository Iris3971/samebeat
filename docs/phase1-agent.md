# Phase1 — Agent 公开 checkpoint

Agent 只调用 media-control stream；处理完整与差分事件。QQ 元数据可上报，其他源只影响可见性。所有状态默认 30 秒心跳；失败退避后只补发最新快照。分享开关关闭后不发送新数据。

历史回放 11 项；历史实机记录覆盖播放、暂停、seek、切歌、分享开关、重试与进程恢复。2026-09-27 维护者完成真实整机重启：没有手动启动 Agent，QQ Music 播放后 ChatGPT MCP 成功读取实时状态、歌曲和进度。重启自启验收通过（维护者提供的实机证据）。

上报包含 status、title、artist、album、duration、position、playing、position_confirmed、observed_at、reason、sent_at，遮挡时可附带 stale 的 last_known。未知进度为 null。

发布准备收紧了 ingest URL 的初始与热加载校验，拒绝带凭据/查询/片段或非本机 HTTP 地址，并禁止携带凭据跟随重定向；启动日志不再输出服务器地址。

进度标记修正：心跳外推的进度和无进度暂停事件冻结出的值标记为估计，不伪装成播放器刚确认。
