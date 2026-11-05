# GitHub Pages 公开部署实施计划

日期：2026-11-05
依据：`docs/superpowers/specs/2026-11-05-github-pages-deployment-design.md`

## 任务 1：固定公开站与本地站的运行边界

- 为 GitHub Pages 增加明确的静态运行模式检测。
- 将 CSS、JavaScript、JSON 和 CSV 改为兼容 `/bond-monitor/` 的相对路径。
- 在线上隐藏不可用的手动刷新按钮；本地 `/refresh` 与 `/status` 行为保持原样。
- 为线上读取失败提供不依赖本地 Python 的提示。

## 任务 2：增加自动构建与发布工作流

- 新增 `.github/workflows/pages.yml`。
- 在 `main` 推送、手动触发和工作日 22:15（上海时区）运行。
- 依次执行测试、数据更新、导出、Pages artifact 上传和部署。
- 添加最小权限、并发锁和部署环境 URL。

## 任务 3：增加部署契约测试与文档

- 检查公开站资源路径、静态模式和工作流关键步骤。
- README 增加在线体验地址、数据更新说明和本地运行说明。
- 运行 Python 全量测试、JavaScript 语法检查和 Git diff 检查。

## 任务 4：发布与线上验收

- 提交本地修改并同步 GitHub `main`。
- 将仓库 Pages 发布源设置为 GitHub Actions。
- 等待 Actions 构建和部署完成。
- 访问公开网址，验证页面、数据、CSV、控制台和移动端基本布局。
