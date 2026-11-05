# GitHub Pages 公开部署设计

日期：2026-11-05

## 目标

把现有 `bond-monitor` 从仅能通过 `127.0.0.1:8765` 访问的本地工具，发布为任何人都能直接打开的公开网站：

`https://lmqinsydney-lab.github.io/bond-monitor/`

保持项目轻量、无常驻服务器费用，并让公开页面的数据在工作日自动更新。现有本地服务、手动更新按钮和 LaunchAgent 继续保留，不因线上部署而失效。

## 方案比较

### 方案一：GitHub Pages + GitHub Actions（采用）

- GitHub Actions 运行现有 Python 更新与导出流程。
- `web/` 作为 Pages 构建产物发布，生成的数据文件只存在于部署产物中，不提交数据库。
- 优点：公开链接稳定、无需服务器、维护成本最低。
- 限制：线上页面是静态站，不能直接执行 `/refresh`；数据按计划任务刷新。

### 方案二：托管 Python 服务

- 在 Render、Railway 或同类平台运行 `server.py`。
- 优点：可以保留线上“立即更新”。
- 缺点：需要持久化磁盘、后台任务和费用控制，远超当前轻量需求。

### 方案三：手动导出静态文件

- 在本机生成数据后手工发布。
- 优点：实现最少。
- 缺点：数据容易过期，不符合日常监测目标。

## 架构与数据流

1. 推送到 `main`、手动触发或周一至周五 22:15（`Asia/Shanghai`）定时触发 GitHub Actions。
2. Actions 检出代码，配置 Python，运行全量测试。
3. Actions 运行 `python3 app.py update --from 2020`，在临时 SQLite 中补齐数据。
4. Actions 运行 `python3 app.py export`，生成 `web/data/dashboard.json` 和 `web/data/market-history.csv`。
5. Actions 将 `web/` 上传为 GitHub Pages artifact，并部署到 `github-pages` 环境。
6. 浏览器通过相对路径读取同一部署目录中的 JSON、CSV、CSS 和 JavaScript。

## 前端行为

- 所有站内资源和数据地址改为相对路径，兼容 `/bond-monitor/` 子路径。
- 本地模式继续显示“立即更新”，调用现有 `/refresh` 和 `/status`。
- GitHub Pages 模式隐藏手动更新按钮，改为只展示“最新数据至 YYYY-MM-DD”。
- CSV 下载使用相对路径 `data/market-history.csv`。
- 线上读取失败时提示“公开数据暂时不可用，请稍后刷新”，不再要求访问者运行本地 Python。

## 自动更新

- `push` 到 `main` 时发布。
- 支持 `workflow_dispatch` 手动发布。
- 周一至周五在 `Asia/Shanghai` 时区 22:15 执行一次自动更新，避开主要数据源尚未完成发布的时段。
- 使用并发锁，新的部署会取消同分支尚未完成的旧部署，避免多个发布互相覆盖。

## 失败处理

- 测试失败：停止部署，保留上一次可用网站。
- 数据更新完全失败：停止部署，保留上一次可用网站。
- 数据更新部分成功：由现有质量字段在页面标记缺失或备用来源，并允许部署。
- Pages 发布失败：在 Actions 中显示失败，不覆盖上一版。

## 验收标准

- 公开网址无需登录即可打开。
- 首页样式、趋势图、净值同日对照、基金持仓组成与交互正常。
- 浏览器控制台没有由错误绝对路径导致的 404。
- JSON 与 CSV 能从 `/bond-monitor/data/` 正常读取。
- 线上不出现不可用的“立即更新”操作。
- 本地 `python3 app.py serve` 的更新与下载能力保持不变。
- 全量 Python 测试通过，`web/app.js` 语法检查通过。

## 不在本次范围

- 自定义域名。
- 用户登录、权限控制或私人数据。
- 常驻 Python 服务器与在线数据库。
- 分钟级实时行情或盘中刷新。
