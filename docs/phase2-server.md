# Phase2 — Server 公开 checkpoint

历史部署与人工验收在 2026-09-26 完成。本公开版省略主机、域名、远程目录与隧道信息。

FastAPI 提供 POST /ingest、受相同 Bearer token 保护的 GET /state 和无数据的 GET /healthz。SQLite 记录当前状态与播放段。Docker 使用非 root 用户、独立卷和 loopback 端口。

五种状态：playing、paused、occluded、idle、offline。120 秒未收到上报后为 offline。客户端 observed_at 与服务器时间偏差超过 30 秒则回退 received_at。暂停不会新建播放段；普通 seek 回开头不计新播放，结尾循环以启发式识别。

历史测试 18 项；包含端到端事件回放与真实循环回放。历史人工验收覆盖 HTTPS、鉴权、延迟、进度、遮挡期间不累计、分享关闭后的 offline。Phase3 已在此基础上实现 MCP；“不含 MCP”仅描述当时阶段边界。
