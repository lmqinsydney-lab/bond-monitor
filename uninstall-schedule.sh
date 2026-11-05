#!/bin/zsh
set -euo pipefail

update_agent_path="${HOME}/Library/LaunchAgents/com.local.bond-monitor.update.plist"
serve_agent_path="${HOME}/Library/LaunchAgents/com.local.bond-monitor.serve.plist"

launchctl bootout "gui/${UID}" "${update_agent_path}" 2>/dev/null || true
launchctl bootout "gui/${UID}" "${serve_agent_path}" 2>/dev/null || true

for agent_path in "${update_agent_path}" "${serve_agent_path}"; do
  if [[ -f "${agent_path}" ]]; then
    rm "${agent_path}"
  fi
done

echo "已移除债市监测网页服务和定时更新；项目数据未删除。"
