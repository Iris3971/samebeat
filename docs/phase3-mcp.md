# Phase3 — MCP 公开 checkpoint

2026-09-26 的记录确认 Claude MCP 接入成功；2026-09-27 维护者确认真实重启后、无需手动启动 Agent，ChatGPT MCP 成功读取 QQ Music 实时播放状态、歌曲和进度，端到端复验通过。Phase3 已完成；Claude 使用历史验收证据，ChatGPT 使用本次维护者提供的实机复验证据。自动验收另在隔离容器内验证四个 MCP 工具，不连接或修改生产服务。

四个工具：now_playing、recent_history、track_context、listening_summary。官方 MCP SDK 的 MCPServer，Streamable HTTP，stateless JSON。全部标注 readOnlyHint。

返回中文事实摘要与结构化字段。occluded/offline 表示未知；last_known 明确 stale；外推进度标估计；历史只用已确认时间。日统计按配置时区、播放段开始时间归属。

MCP secret 与 ingest token 独立；错误路径 404，非允许 Host 421。应用访问日志对 MCP secret 脱敏。反向代理、隧道、平台统计可能另存路径，需单独保护。

历史测试 19 项；另有官方 MCP 客户端初始化、列工具和调用成功记录。公开发行不提供共享服务、真实端点或凭据。
