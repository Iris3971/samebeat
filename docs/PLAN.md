# SameBeat v0.1.0 — 发布设计基线

本文件是原始 PLAN 与 Phase0–3 实际实现的公开整理版，删除私人部署信息及已过期的阶段执行指令。

## 定位

AI-agnostic、read-only listening-presence layer。QQ Music 是播放器/事实源；SameBeat = 感官，OB = 记忆，AI = 判断。无音频下载、私有音乐 API、播放控制、歌词、情绪推断或自动记忆写入。OB 与具体 AI 都不是运行依赖。

## 已实现

1. Phase0：验证 macOS Now Playing / media-control；发现其他源可遮挡 QQ，暂停不带进度、旧缓存重放、切歌事件抖动和非稳定内容 ID。
2. Phase1：Python 3.11+ 标准库 Agent；QQ 来源过滤、0.8 秒 debounce、全状态 30 秒心跳、仅重发最新状态、分享开关、launchd。
3. Phase2：FastAPI、SQLite；Bearer ingest 和排错 state；独立部署；五种状态，120 秒 offline 阈值；时钟偏差超过 30 秒回退服务器时间；播放历史保守累计。
4. Phase3：MCPServer Streamable HTTP；四个只读工具；独立秘密路径；时区配置；估计进度与旧状态显式标记。

Phase3 Claude 验收有历史记录；2026-09-27 维护者确认 Mac 真实重启自启与 ChatGPT MCP 实时端到端复验通过。当前源码实现覆盖 Phase3，候选源码另通过隔离 Docker 构建、启动和健康检查；自动验收没有修改生产服务。

## 不变量

- occluded/offline 是未知，不是没在听；idle 只说明系统没有 Now Playing。
- 非 QQ 媒体内容只在本机解析时短暂存在，不上传、不持久保存。
- 只累计已确认可见播放区间，不填补离线或遮挡。
- 自然循环使用结尾附近进度回零的启发式；普通 seek 回头不新开播放段，但结尾处手动 seek 无法与循环绝对区分。
- MCP 只读，AI 决定事实意味着什么；任何记忆写入由独立的对话流程决定。

## 本次发布准备

公开材料脱敏、通用配置、README/Quick Start、MIT LICENSE、交接与发布检查、回归测试、离线可审阅源码包。实际发布前需确定托管仓库并完成剩余验证。Phase4 歌词与 Phase5 控制不在本次范围。
