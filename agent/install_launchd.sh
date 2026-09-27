#!/bin/bash
# 安装 / 卸载 SameBeat Agent 的 launchd 开机自启。
#   ./install_launchd.sh            安装（或更新）并立即启动
#   ./install_launchd.sh uninstall  停止并移除自启（保留配置文件）
set -euo pipefail

LABEL="com.samebeat.agent"
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
CONFIG_DIR="$HOME/.config/samebeat"
LOG_DIR="$HOME/Library/Logs/samebeat"
DOMAIN="gui/$(id -u)"

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "已卸载。配置保留在 $CONFIG_DIR"
  exit 0
fi

# 找一个 Python 3.11+（Agent 用到 tomllib）
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  for c in python3 /opt/homebrew/bin/python3 /opt/anaconda3/bin/python3 /usr/local/bin/python3; do
    if p="$(command -v "$c" 2>/dev/null)" && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
      PY="$p"; break
    fi
  done
fi
if [[ -z "$PY" ]]; then
  echo "找不到 Python 3.11+，请安装后重试，或用 PYTHON=/path/to/python3 指定" >&2
  exit 1
fi

MC="$(command -v media-control || echo /opt/homebrew/bin/media-control)"
if [[ ! -x "$MC" ]]; then
  echo "找不到 media-control，请先 brew install media-control" >&2
  exit 1
fi

mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$(dirname "$PLIST")"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
  cp "$AGENT_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
  chmod 600 "$CONFIG_DIR/config.toml"
  echo "已创建配置 $CONFIG_DIR/config.toml（默认 dry-run，只写日志不联网）"
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>-u</string>
    <string>$AGENT_DIR/samebeat_agent.py</string>
    <string>--config</string>
    <string>$CONFIG_DIR/config.toml</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG_DIR/agent.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/agent.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$(dirname "$MC"):/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "已安装并启动 $LABEL"
echo "  Python: $PY"
echo "  日志:   $LOG_DIR/agent.log"
echo "  配置:   $CONFIG_DIR/config.toml"
