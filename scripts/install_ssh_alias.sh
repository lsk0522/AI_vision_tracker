#!/usr/bin/env bash
# ~/.ssh/config 에 'pi' 별칭을 등록합니다.
# 이후로는 IP가 바뀌어도 `ssh pi` (VS Code Remote-SSH 도 'pi') 로 접속됩니다.
# 접속할 때마다 find_pi.py 가 현재 IP를 찾아 연결합니다.
# 사용법: ./scripts/install_ssh_alias.sh [사용자명]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIND="$SCRIPT_DIR/find_pi.py"
PI_USER="${1:-pi30306}"
CONF="$HOME/.ssh/config"
BEGIN="# >>> ai_vision_tracker pi >>>"
END="# <<< ai_vision_tracker pi <<<"

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
touch "$CONF" && chmod 600 "$CONF"

# 예전에 등록한 블록이 있으면 지우고 새로 씀
if grep -qF "$BEGIN" "$CONF"; then
    cp "$CONF" "$CONF.bak.$(date +%Y%m%d%H%M%S)"
    awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$CONF" > "$CONF.tmp"
    mv "$CONF.tmp" "$CONF" && chmod 600 "$CONF"
fi

cat >> "$CONF" <<EOF

$BEGIN
Host pi
    User $PI_USER
    ProxyCommand sh -c 'exec nc "\$(python3 "$FIND")" 22'
    HostKeyAlias ai-vision-pi
    StrictHostKeyChecking accept-new
    ServerAliveInterval 30
$END
EOF

echo "✅ ~/.ssh/config 에 'pi' 별칭을 등록했습니다."
echo "   이제 IP가 바뀌어도:  ssh pi"
