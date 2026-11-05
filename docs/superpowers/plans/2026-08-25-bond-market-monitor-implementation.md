# 债市监测工具实施计划

日期：2026-08-25
依据：`docs/superpowers/specs/2026-08-25-bond-market-monitor-design.md`

## 实施原则

- 保持单机、轻量：Python 标准库优先，SQLite、原生 HTML/CSS/JavaScript，不引入 React、Node 或云服务。
- 先固定真实数据响应，再写解析器；每个外部源保存原始样例和契约测试。
- 市场数据、基金画像、压力公式、展示 JSON 分层，官网改版不影响其余模块。
- 历史记录不静默覆盖；来源、抓取时间、质量和修订都可追溯。
- 每个阶段先写失败测试，再实现到通过；完成后运行全量测试。

## 页面实施基线

### 布局

```text
┌─────────────────────────────────────────────────────────────────────┐
│ 债市监测        完整数据日 / 更新时间 / 来源状态     更新  导出 CSV │
├─────────────────────────────────────────────────────────────────────┤
│ 国债10Y │ 国开5Y │ 二级资本债5Y │ 信用利差 │ R007               │
├──────────────────────────────────────────┬──────────────────────────┤
│ 趋势图（指标切换；1月/3月/1年/全部）     │ 今日压力拆解             │
│                                          │ 利率 / 信用 / 融资 / 质量 │
├──────────────────────────────────────────┴──────────────────────────┤
│ 兴全恒裕 A        长盛安逸纯债 A        广发添财 180 天 A          │
│ 综合压力与可信度；展开后显示权重、指标变化、画像版本和公式          │
├─────────────────────────────────────────────────────────────────────┤
│ 数据来源、缺失项、备用源与免责声明                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 主题与动效

- 暖灰白背景、墨黑正文、低饱和青绿色主色；黄/红仅表达压力，不采用行情终端式高饱和配色。
- 使用系统字体栈以保证离线可用；数字使用等宽数字特性。
- 4px 间距基线，12–18px 圆角，细边框和单层轻阴影。
- 卡片悬停 160ms 轻微抬升；展开区域 220ms 淡入；尊重 `prefers-reduced-motion`。
- 所有状态同时使用文字、符号和颜色；交互控件最小 44px，提供清晰焦点环。

## 任务 1：建立项目骨架与运行契约

新增：

- `app.py`
- `sources.py`
- `fund_profiles.py`
- `pressure.py`
- `storage.py`
- `exporter.py`
- `requirements.txt`
- `.gitignore`
- `README.md`
- `tests/`

步骤：

1. 用 `unittest` 建立 CLI 测试，约束 `python3 app.py update`、`serve`、`status` 和 `export`。
2. `app.py` 只负责命令分派；业务逻辑放到独立模块。
3. 建立运行目录和可覆盖配置：数据库路径、Web 输出路径、监听端口、离线样例模式。
4. README 写明支持的 Python 版本、安装、首次回填和启动方式。

验收：

```bash
python3 -m unittest discover -s tests -v
python3 app.py --help
```

## 任务 2：固定官方数据契约与源适配器

新增：

- `tests/fixtures/sources/`
- `tests/test_sources.py`

步骤：

1. 对中债国债、国开债、银行二级资本债/永续债曲线和中国货币网 R007/DR007 分别抓取一份近期真实响应。
2. 记录请求 URL、方法、参数、编码、发布日期与官网说明页；原始样例去除无关大字段后保存为 fixture。
3. 定义统一 `Observation`：`metric/date/tenor/rating/value/unit/source/source_tier/fetched_at/quality`。
4. 为每个适配器测试正常、空响应、字段变更、超时和数值越界。
5. 备用源必须单独标记，禁止在解析器内部伪装成官方值。

验收：

```bash
python3 -m unittest tests.test_sources -v
```

## 任务 3：SQLite、幂等写入与修订记录

新增：

- `tests/test_storage.py`

步骤：

1. 创建 `market_observations`、`source_fetches`、`fund_reports`、`fund_profiles`、`fund_pressure`、`revisions` 表。
2. 对指标、日期、期限、评级和来源建立唯一约束与查询索引。
3. 同值重复抓取不写重复行；值发生变化时保留旧值到 `revisions`。
4. 所有批次使用事务，部分失败不提交半成品。

验收：

```bash
python3 -m unittest tests.test_storage -v
```

## 任务 4：2020 至今历史回填与每日更新

新增：

- `updater.py`
- `calendar_cn.py`
- `tests/test_updater.py`

步骤：

1. 历史抓取按官网允许的最大区间分块，支持断点续跑和请求间隔。
2. 日历先以工作日为候选，再以官方是否发布数据确认交易日；周末不报缺失，节假日不靠前值填补。
3. 每次更新计算最近完整数据日，自动补齐数据库缺口。
4. 官方失败时尝试备用源；两者失败记录抓取错误并保留空值。
5. 实现确定性的单日、5 日 BP、信用利差和 R-DR 计算。

验收：

```bash
python3 -m unittest tests.test_updater -v
python3 app.py update --from 2020-01-01
python3 app.py status
```

## 任务 5：基金报告、版本化画像与压力计算

新增：

- `tests/fixtures/funds/`
- `tests/test_fund_profiles.py`
- `tests/test_pressure.py`

步骤：

1. 为 006985、007744、012591 建立基金元数据和管理人报告索引适配器。
2. 保存三只基金各一份公开报告 fixture，解析报告截止日、发布日期、资产/净资产、债券仓位和前五大债券。
3. 分类银行二级资本债、永续债、政策性金融债和普通信用债；无法确定时进入 `unknown`，不强行分类。
4. 画像从实际发布日期开始生效，失败时沿用上一版并标记过期。
5. 按规格实现标准压力、缺失权重阈值、可信度降级和计算明细。

验收：

```bash
python3 -m unittest tests.test_fund_profiles tests.test_pressure -v
```

## 任务 6：生成前端数据与 CSV

新增：

- `web/data/dashboard.json`
- `tests/test_exporter.py`

步骤：

1. 从 SQLite 生成只包含页面所需字段的 JSON，不让浏览器直接查询数据库。
2. 输出概览、全部趋势序列、数据质量、三只基金最新状态及完整计算明细。
3. 实现按指标和日期范围导出 UTF-8 BOM CSV，确保 Excel 可直接打开中文。
4. 为缺失值、备用源、来源切换和历史画像缺失提供明确字段。

验收：

```bash
python3 -m unittest tests.test_exporter -v
python3 app.py export
```

## 任务 7：本地服务和单页界面

新增：

- `server.py`
- `web/index.html`
- `web/styles.css`
- `web/app.js`
- `tests/test_server.py`

步骤：

1. 使用标准库 HTTP 服务，只监听 `127.0.0.1`；提供静态文件、`GET /status`、`POST /refresh` 和 CSV 下载。
2. 完成语义化页面、概览卡、Canvas/SVG 趋势图、压力拆解和基金展开明细。
3. 范围筛选、指标切换、工具提示和 CSV 导出均用原生 JavaScript。
4. 刷新按钮展示等待、成功、部分失败和失败状态，防止并发重复更新。
5. 在桌面和手机宽度检查层级、键盘、焦点、对比度与减少动效设置。

验收：

```bash
python3 -m unittest tests.test_server -v
python3 app.py serve
```

然后在实际浏览器检查首页、展开态、错误态和手机窄屏。

## 任务 8：macOS 调度、安装与最终验收

新增：

- `setup-schedule.sh`
- `uninstall-schedule.sh`
- `launchd/com.local.bond-monitor.update.plist.template`
- `tests/test_schedule.py`

步骤：

1. 安装两个交易日触发时点：17:40 主更新、18:10 补偿更新。
2. 使用绝对 Python 和项目路径，日志写入项目 `logs/`；重复安装保持幂等。
3. 页面启动时先做快速缺口检查，缺失才触发补齐。
4. 对真实数据库执行覆盖率、来源占比、异常跳点和三个基金画像时效检查。
5. 运行全量测试，完成首次 2020 至今回填和真实页面视觉检查。

最终验收：

```bash
python3 -m unittest discover -s tests -v
python3 app.py update --from 2020-01-01
python3 app.py export
python3 app.py serve
```

完成标准：页面能展示最近数据与 2020 至今趋势；任一数值都能追溯来源；缺失和备用源不会被误报成完整官方数据；三只基金的压力详情能解释使用了哪份公开报告与哪些指标。
