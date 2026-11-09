#!/usr/bin/env bash
# 在 macOS 上安装一个每日定时抓取 MagicRule 规则的 launchd 任务。
#
#   ./install_launchd.sh            # 安装并启用
#   ./install_launchd.sh --uninstall # 卸载
#
# 说明: 若只是想让 GitHub 仓库自动保持最新, 更推荐仓库里的
# .github/workflows/magicrule.yml —— 云端跑, 不占本机资源, 也不受
# 登录钥匙串锁定的影响。
set -euo pipefail

LABEL="com.surge.magicrule"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/surge"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "已卸载 $LABEL"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>
            cd "$REPO" || exit 1
            /usr/bin/git pull --ff-only || true
            /usr/bin/python3 magicrule/tools/fetch_magicrule.py Surge || exit 2
            if [ -n "\$(/usr/bin/git status --porcelain -- magicrule/surge)" ]; then
                /usr/bin/git config user.name "magicrule-bot"
                /usr/bin/git config user.email "magicrule-bot@users.noreply.github.com"
                /usr/bin/git add magicrule/surge
                /usr/bin/git commit -m "chore(magicrule): 自动更新规则集"
                /usr/bin/git push
            fi
        </string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>5</integer>
        <key>Minute</key>
        <integer>23</integer>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/magicrule.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/magicrule.err.log</string>
</dict>
</plist>
PLIST_EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"

echo "已安装并启用: $LABEL"
echo "  仓库:    $REPO"
echo "  运行时间: 每天 05:23 (本机时间)"
echo "  日志:    $LOG_DIR/magicrule.log"
echo "  立即试跑: launchctl kickstart -p gui/$(id -u)/$LABEL"
echo "  卸载:    $0 --uninstall"
