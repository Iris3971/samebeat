# Quick Start / 安装与连接

## 1. Requirements / 环境

Mac: Python 3.11+、官方 QQ Music 客户端、[media-control](https://github.com/ungive/media-control)。历史实测使用 `brew install media-control`；安装后以 `command -v media-control` 确认位置。Agent 只调用 `stream --no-artwork --micros`。

Server: Docker Engine with Compose; a domain and HTTPS reverse proxy. Obtain this source tree from the published repository or release archive. Run the following commands from its root. Python commands require 3.11 or newer.

## 2. Server / 服务端

```sh
cd server
umask 077
cp .env.example .env
python3 - <<'PYCODE'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text().replace('SAMEBEAT_TOKEN=\n', 'SAMEBEAT_TOKEN=' + secrets.token_hex(32) + '\n')
s = s.replace('SAMEBEAT_MCP_SECRET=\n', 'SAMEBEAT_MCP_SECRET=' + secrets.token_hex(32) + '\n')
p.write_text(s)
p.chmod(0o600)
PYCODE
```

首次配置使用以上命令；不要覆盖已有 `.env`。在私密编辑器里把 `SAMEBEAT_PUBLIC_HOSTS` 改成自己的域名（不带 `https://`、路径或通配符），检查时区。两个随机值不能相同，不要复制到聊天、截图或 shell 命令参数。

For first-time setup only: edit the private `.env` file, set your own public hostname and timezone, and keep both generated credentials private. Do not overwrite an existing deployment's configuration.

```sh
docker compose up -d --build
curl --fail http://127.0.0.1:8766/healthz
cd ..
```

Configure your HTTPS reverse proxy to forward to `http://127.0.0.1:8766` **on the server**, preserving the public Host header. This port is intentionally loopback-only. `/healthz` contains no listening data; unauthenticated `/state` should return 401. Public MCP Host values must match `SAMEBEAT_PUBLIC_HOSTS`.

反向代理必须保护访问日志，完整 MCP 请求路径含秘密。不要与其他服务共用凭据或数据库。Docker 构建仅发送白名单源码文件。

## 3. Mac Agent / 本机采集

```sh
mkdir -p ~/.config/samebeat
# First install only: do not overwrite an existing config.
cp agent/config.example.toml ~/.config/samebeat/config.toml
chmod 600 ~/.config/samebeat/config.toml
```

在私密编辑器中设置：

- `server_url`: 自己服务器的 HTTPS `/ingest` 地址。
- `token`: 与服务端 `SAMEBEAT_TOKEN` 相同的值；不是 MCP secret。
- `media_control`: `command -v media-control` 的结果；Intel Homebrew 路径可能不同。
- `sharing_enabled`: `true` 开启上报；`false` 停止。配置约 5 秒内重读。

Set the HTTPS ingest URL, matching ingest token and actual media-control executable path in the private config. Empty URL means local dry-run. Turn sharing off at any time; stored history remains.

```sh
python3 agent/samebeat_agent.py
# After checking playback updates, stop the foreground agent with Ctrl-C.
bash agent/install_launchd.sh
```

launchd 在当前用户登录后运行，并保存本机日志。安装脚本保留已有配置；移动源码目录后需要重新安装。不要同时运行前台和 launchd 两个实例。卸载自启：`bash agent/install_launchd.sh uninstall`（保留配置与服务器历史）。2026-09-27 维护者已确认真实重启后无需手动启动 Agent，ChatGPT MCP 可读取 QQ Music 实时状态；该环境的自启验收已通过。

## 4. MCP connection / AI 接入

Use a client supporting remote Streamable HTTP MCP. Privately compose your HTTPS endpoint from your domain plus `/mcp/` plus `SAMEBEAT_MCP_SECRET`. The URL is a read credential. This version has no OAuth flow and no separate MCP Bearer header. Client support, account availability and UI labels vary; use that client's current custom MCP connection settings.

添加后应列出 `now_playing`、`recent_history`、`track_context`、`listening_summary` 四个工具。调用 `now_playing`，核对 QQ 上显示的歌曲及状态。不要把 `occluded` / `offline` 当作停播；`position_estimated=true` 是推算进度。

历史 Claude 接入已验收；2026-09-27 维护者确认重启后 ChatGPT MCP 实时读取状态、歌曲和进度的端到端复验通过。其他客户端需自行验证；本说明不保证各平台所有账号均开放连接功能。

## 5. Verify / 验收

手动在 QQ 播放、暂停、切歌和拖进度，观察工具返回；用其他媒体源占用 Now Playing，应变成 occluded；关闭分享，超过 120 秒后应变成 offline。测试工具不会替你操控播放器。

Verify playback, pause, track changes and seek manually in QQ Music. Check occlusion and sharing-off behavior. The original acceptance target was an update within 10 seconds and position error within 2 seconds; these are test targets, not universal guarantees.

## Troubleshooting / 排错

- 401 from ingest/state: token mismatch or missing Bearer header.
- 404 from MCP: wrong secret path. Do not paste the full URL into a public report.
- 421 from MCP: configure the correct public hostname and preserve Host at the proxy.
- offline: Agent has not reported for more than 120 seconds; check sharing, network and Agent process.
- occluded: another source owns Now Playing; QQ may still be playing.
- Changing the media-control executable path requires restarting the Agent stream; restarting Agent is simplest.

Rotate the MCP secret privately in `.env`, run `docker compose up -d --force-recreate`, then update each client's private endpoint. Do not publish the old or new URL. Rotation does not require changing the independent ingest token.
