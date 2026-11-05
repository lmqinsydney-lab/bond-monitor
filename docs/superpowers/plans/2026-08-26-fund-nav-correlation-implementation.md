# 基金净值与债市指标同日对照实施计划

日期：2026-08-26  
依据：`docs/superpowers/specs/2026-08-26-fund-nav-correlation-design.md`

## 实施原则

- 保持 Python 标准库、SQLite、原生 HTML/CSS/JavaScript，不增加框架或常驻服务。
- 净值数据与市场指标分别保存来源、日期和质量；不以前值补齐缺口。
- 相关性只对基金日增长率和指标单日 BP 变化计算，最少 20 个同日样本。
- 先写确定性单元测试，再接真实数据和页面。
- 备用净值源必须显示为备用源，不伪装成基金管理人官方数据。

## 任务 1：净值数据契约与解析器

修改：

- `sources.py`
- `tests/test_sources.py`

步骤：

1. 新增 `FundNavObservation` 和 `FundNavSource`，输入基金代码、起止日期，输出单位净值、累计净值和来源发布的日增长率。
2. 适配历史净值分页响应，校验基金代码、日期、数值范围、日增长率和空页终止条件。
3. 为正常分页、空响应、无日增长率、异常字段和重复日期编写测试。
4. 来源初始标记为 `fallback`；只有稳定的基金管理人机器接口通过契约测试后才标记 `official`。

验收：

```bash
python3 -m unittest tests.test_sources -v
```

## 任务 2：SQLite 净值表、修订与幂等写入

修改：

- `storage.py`
- `tests/test_storage.py`

步骤：

1. 新增 `fund_nav_observations` 和 `fund_nav_revisions`。
2. 实现同值更新时间戳、异值记录修订、单基金失败不影响其他基金。
3. 增加按基金与日期读取、覆盖率统计和首尾日期查询。
4. 测试重复抓取、日增长率为空、净值修订和来源并存时的优先级。

验收：

```bash
python3 -m unittest tests.test_storage -v
```

## 任务 3：日期对齐与 Pearson 相关性

新增：

- `correlation.py`
- `tests/test_correlation.py`

步骤：

1. 实现仅按相同自然日内连接净值和市场指标，不填充缺失值。
2. 实现 Pearson 相关系数、样本数、正负方向和绝对值强弱等级。
3. 常数序列、少于 20 个样本、非有限数值返回不可计算。
4. 为完全正/负相关、阈值边界、错位日期、缺失样本和范围截取编写测试。

验收：

```bash
python3 -m unittest tests.test_correlation -v
```

## 任务 4：更新器与历史回填

修改：

- `updater.py`
- `app.py`
- `tests/test_updater.py`

步骤：

1. 每次 `update` 在市场数据之后独立更新三只基金，基金失败只降低整体状态为 `partial`。
2. 历史起点分别使用 2020-01-01、2020-01-01 和 2021-07-08。
3. 默认增量更新从数据库最新日期前回看少量交易日，以捕获来源修订。
4. `--force` 重新抓取全部净值分页。
5. 更新状态增加净值来源成功数、失败数和每只基金最新净值日。

验收：

```bash
python3 -m unittest tests.test_updater -v
python3 app.py update --from 2020
python3 app.py status
```

## 任务 5：导出同日对照数据

修改：

- `exporter.py`
- `tests/test_exporter.py`

步骤：

1. 为每只基金导出净值序列、相关指标键、同日记录和来源质量。
2. 预计算 20、60、120、近 1 年和全部范围的相关系数与样本量。
3. 同日记录保留基金日收益、单位净值、指标原值、指标单日 BP、双方日期与来源。
4. JSON 不重复复制整套市场历史；通过指标键和日期映射复用现有序列。
5. 浏览器根据当前筛选生成 UTF-8 BOM 同日对照 CSV。

验收：

```bash
python3 -m unittest tests.test_exporter -v
python3 app.py export
```

## 任务 6：同步小图与日期交互

修改：

- `web/index.html`
- `web/styles.css`
- `web/app.js`

布局：

```text
基金/范围/日期控件
当日净值 + 相关指标卡
基金日收益小图
相关指标单日 BP 小图（共享日期轴和游标）
相关系数摘要
```

步骤：

1. 新增基金、范围、日期和前后交易日控件，默认兴全、60 日和最新净值日。
2. 绘制共用日期轴的 SVG 小图；点击或键盘左右键切换选中交易日。
3. 同日卡同时展示数值、变化、常见压力方向、来源日期和缺失状态。
4. 相关摘要显示 `r`、强弱、方向、样本量和非因果提示。
5. 客户端导出当前基金和范围的 CSV。
6. 保持暖灰/青绿现有视觉系统，手机端卡片纵排，图表局部滚动而不撑宽整页。

验收：

- 基金、范围、日期、图表点击四种状态同步。
- 桌面和 390px 页面无横向整体溢出。
- 键盘焦点、按钮尺寸、颜色以外的文字状态完整。

## 任务 7：自动调度与最终验收

修改：

- `setup-schedule.sh`
- `launchd/com.local.bond-monitor.update.plist.template`
- `README.md`

步骤：

1. 在原有工作日 17:40、18:10 之外增加 21:30 净值补偿更新。
2. 重新安装用户级 LaunchAgent 并验证三个时点、`RunAtLoad` 和退出码。
3. 首次回填三只基金历史净值，检查起止日期、重复、空值、异常日涨跌和来源标记。
4. 运行全量测试和 `git diff --check`。
5. 启动本地页面，实际检查桌面、手机、日期切换、图表同步、CSV 和无控制台错误。

最终验收：

```bash
python3 -m unittest discover -s tests -v
python3 app.py update --from 2020
python3 app.py export
python3 app.py serve --port 8765
```

完成标准：三只基金都能选择历史净值日并与各自相关债市指标同日并排；预设区间相关性只使用有效共同样本，来源、缺口和样本不足均清晰可见。
