#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h}"
python_bin="$(command -v python3)"
agent_dir="${HOME}/Library/LaunchAgents"
update_agent_path="${agent_dir}/com.local.bond-monitor.update.plist"
serve_agent_path="${agent_dir}/com.local.bond-monitor.serve.plist"
update_template_path="${project_dir}/launchd/com.local.bond-monitor.update.plist.template"
serve_template_path="${project_dir}/launchd/com.local.bond-monitor.serve.plist.template"

mkdir -p "${agent_dir}" "${project_dir}/logs"

calendar_intervals=""
for weekday in 2 3 4 5 6; do
  calendar_intervals+="<dict><key>Weekday</key><integer>${weekday}</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>40</integer></dict>"
  calendar_intervals+="<dict><key>Weekday</key><integer>${weekday}</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>10</integer></dict>"
  calendar_intervals+="<dict><key>Weekday</key><integer>${weekday}</integer><key>Hour</key><integer>21</integer><key>Minute</key><integer>30</integer></dict>"
done

escaped_project="${project_dir//\//\\/}"
escaped_python="${python_bin//\//\\/}"
sed \
  -e "s/__PROJECT__/${escaped_project}/g" \
  -e "s/__PYTHON__/${escaped_python}/g" \
  -e "s|__CALENDAR_INTERVALS__|${calendar_intervals}|g" \
  "${update_template_path}" > "${update_agent_path}"

sed \
  -e "s/__PROJECT__/${escaped_project}/g" \
  -e "s/__PYTHON__/${escaped_python}/g" \
  "${serve_template_path}" > "${serve_agent_path}"

launchctl bootout "gui/${UID}" "${update_agent_path}" 2>/dev/null || true
launchctl bootout "gui/${UID}" "${serve_agent_path}" 2>/dev/null || true
launchctl bootstrap "gui/${UID}" "${update_agent_path}"
launchctl bootstrap "gui/${UID}" "${serve_agent_path}"
launchctl enable "gui/${UID}/com.local.bond-monitor.update"
launchctl enable "gui/${UID}/com.local.bond-monitor.serve"

echo "已安装每日更新：工作日 17:40，18:10 市场数据补偿，21:30 净值补偿。"
echo "登录或重新加载任务时也会检查并补齐缺口。"
echo "网页服务已设为登录后自动启动：http://127.0.0.1:8765/"
