# SameBeat

**让你一直在聊的 AI，知道你正在听什么。**

SameBeat 是 **AI-agnostic、read-only 的 listening-presence layer**。继续用 QQ Music 官方 Mac 客户端听歌，通过 MCP 把歌曲、播放状态、进度和已确认的播放历史提供给支持该协议的 AI。AI 不会听见音频；v0.1.0 不含歌词、情绪推断或播放控制。

QQ Music 是播放器与事实源；**SameBeat = 感官，OB = 记忆，AI = 判断**。OB 是可选的独立记忆系统，SameBeat 不连接它、不写记忆，也不要求使用特定 AI。

```text
QQ Music → macOS Now Playing → media-control → Mac Agent
                                             ↓ HTTPS
                                       Server + SQLite
                                             ↓ read-only MCP
                                       Claude / ChatGPT / compatible AI
```

## 状态与边界

| 状态 | 含义 |
|---|---|
| playing | QQ 可见且播放中 |
| paused | QQ 可见且暂停 |
| occluded | Agent 在线，但其他媒体源占用 Now Playing；QQ 状态未知 |
| idle | Agent 在线，系统没有 Now Playing 信息 |
| offline | 超过 120 秒未收到上报；当前状态未知 |

**occluded / offline 不等于没在听。** `last_known` 是明确标记 `stale` 的旧状态。进度允许外推，但必须标记估计；历史统计不填补遮挡或离线区间。循环次数是依据结尾附近进度回零的启发式判断，不能用来推断用户情绪或意图。

## Quick Start

完整步骤见 [安装与连接](docs/QUICKSTART.md)。

1. Mac 安装 Python 3.11+、QQ Music 官方客户端及 `media-control`；服务器使用 Docker Compose。
2. 在 `server/` 把 `.env.example` 复制为 `.env`，在本地生成两个独立凭据，设置自己的公开域名。启动服务器，把 HTTPS 反向代理指向服务器的 `127.0.0.1:8766`。
3. 把 `agent/config.example.toml` 复制到 `~/.config/samebeat/config.toml`，填入自己的 `/ingest` HTTPS 地址及 ingest token。
4. 先在前台运行 Agent；验证后执行 `bash agent/install_launchd.sh` 安装当前用户登录后自启。
5. 在兼容的 MCP 客户端私下填写自己的 `/mcp/<secret>` HTTPS 地址。列出工具，再调用 `now_playing`。

不要把完整 MCP URL、配置截图或真实凭据放进公开 issue。模板默认 `server_url` 为空：仅 dry-run，不联网，但会在本机输出 QQ 歌曲状态。

## 四个只读工具

| 工具 | 参数 | 内容 |
|---|---|---|
| `now_playing` | 无 | 五种状态、歌曲、带估计标记的进度、连续播放遍数 |
| `recent_history` | `hours=24, limit=20` | 最近播放段与已确认时长 |
| `track_context` | `title?, artist?` | 当前、最近或指定歌曲的历史 |
| `listening_summary` | `date?` | 用户时区内某日的播放统计 |

返回中文事实摘要和结构化字段。日期统计按播放段开始时间归属日期；近期历史按开始时间筛选。单首连续遍数最多回看 200 个历史段。v0.1 是个人自托管、单用户服务，无 OAuth 或多租户隔离。

## 隐私与运行限制

Agent 在本机解析系统当前 Now Playing 事件以识别来源；**非 QQ 媒体信息不上传或持久保存**。服务器保存 QQ 状态和历史，MCP 客户端及其 AI 服务会收到你查询的内容。关闭 `sharing_enabled` 停止新上报，约两分钟后变为 offline；这不会删除已有历史。

原始采集日志与真实配置不随源码发布。公开回放样本去除了非 QQ 媒体内容、系统标识等非必要字段。密钥应独立生成；秘密路径本身就是只读凭据，代理和平台日志也需要保护。详见 [安全说明](SECURITY.md)。

Mac Agent 只支持 macOS。历史实机验证环境为 macOS 26.5.2、QQ Music 11.8.1、media-control 0.7.7；这不是对所有版本的兼容性保证。2026-09-27 维护者确认已完成真实重启验收：未手动启动 Agent，QQ Music 播放后，ChatGPT 通过 SameBeat MCP 成功读取实时播放状态、歌曲和进度。Mac reboot autostart 与 ChatGPT 端到端复验已通过；Claude 接入保留 Phase3 历史验收记录。当前候选 Dockerfile 已在目标 VPS 完成隔离构建、容器启动和内置健康检查（healthy），并通过容器内 API/MCP 合成数据检查。维护者另确认当前 Mac release candidate 在独立临时 volume 上的容器验收达到 `running / healthy`，测试资源已清理，生产 SameBeat 与 OB 正常。详见发布检查清单中的证据与范围。

## 开发与验证

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r server/requirements.txt -r requirements-dev.txt -c requirements-lock.txt
python scripts/check_release.py
python -m unittest discover -s agent -p 'test_*.py'
python -m unittest discover -s server -p 'test_*.py'
```

测试使用临时数据库和假凭据，不需要实际 QQ、生产服务器或真实 token。参见 [交接记录](HANDOFF.md)、[发布检查](docs/RELEASE_CHECKLIST.md) 和 [设计基线](docs/PLAN.md)。MIT License；第三方软件保留各自许可证。

## Credits / Acknowledgements

- [media-control](https://github.com/ungive/media-control) by **Jonas van den Berg (ungive)** — [BSD-3-Clause](https://github.com/ungive/media-control#license). The Mac Agent invokes its separately installed CLI to read macOS Now Playing events; its source and binaries are not bundled with SameBeat. Thanks also to its upstream [mediaremote-adapter](https://github.com/ungive/mediaremote-adapter) (BSD-3-Clause).
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — MIT. SameBeat uses the **Model Context Protocol** for interoperability and imports the official SDK at runtime to expose its tools; it does not vendor or modify SDK source.
- [FastAPI](https://github.com/fastapi/fastapi) and [Pydantic](https://github.com/pydantic/pydantic) — MIT; [Uvicorn](https://github.com/Kludex/uvicorn) — BSD-3-Clause; [tzdata](https://github.com/python/tzdata) — Apache-2.0 (IANA time-zone data is public domain). [HTTPX](https://github.com/encode/httpx) — BSD-3-Clause, for tests.
- Built with [Python](https://docs.python.org/3/license.html) (PSF license and included third-party notices) and [SQLite](https://www.sqlite.org/copyright.html) (public domain). QQ Music and macOS remain separately installed products under their own terms.

SameBeat's MIT license covers its own code, not these independent projects. See the [dependency/license review](HANDOFF.md#third-party-dependency-and-license-review) for all locked Python dependencies and redistribution requirements.

## English

SameBeat is an **AI-agnostic, read-only listening-presence layer** for the official QQ Music Mac client. It shares playback facts through MCP with your existing AI conversation. QQ Music remains the player and source of truth. SameBeat provides senses; an optional independent memory system such as OB provides memory; the AI makes judgments.

The AI receives metadata, not audio. v0.1.0 includes four read-only tools, no lyrics, no playback controls, no emotion inference and no automatic memory writes. `occluded` and `offline` mean **unknown**, never “not listening.” Estimated positions and stale snapshots are explicitly marked. History does not invent listening time during occlusion or disconnection.

See the bilingual [Quick Start](docs/QUICKSTART.md) for a personal self-hosted deployment. Keep the ingest token and secret MCP URL private and separate. The service is single-user and does not implement OAuth. Claude connectivity is recorded in the original Phase3 acceptance notes. On 2026-09-27 the maintainer confirmed a real Mac reboot with no manual Agent launch, followed by successful live state, track and progress retrieval through ChatGPT MCP. Reboot autostart and ChatGPT end-to-end revalidation passed. The candidate also passed isolated Docker build, startup, built-in healthcheck and internal API/MCP checks on the target VPS; production services were not modified. The maintainer also confirmed a clean candidate build and a separate disposable-volume container reaching running/healthy, followed by complete test-resource cleanup.
