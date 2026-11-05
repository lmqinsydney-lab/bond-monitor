# 债市监测

本地、轻量的中国债市与债券基金压力监测工具。它保存 2020 年至今的公开收益率曲线，展示国债、国开债、银行二级资本债、AAA 中短期票据和 DR007，并用公开季报画像解释三只债券基金对利率、信用与融资变化的敏感方向。

“净值同日对照”可选择三只基金、历史净值日和 20/60/120 日、1 年或全部范围，把基金日收益与相关指标单日 BP 变化放在同一日期轴，并展示样本内 Pearson 相关系数。

它不是基金净值估算器，也不提供交易建议。

## 运行

要求：macOS 或其他带 Python 3.9+ 的系统。首版仅使用 Python 标准库。

```bash
cd /Users/didi/bond-monitor
python3 app.py update --from 2020
python3 app.py serve
```

然后打开 <http://127.0.0.1:8765>。

常用命令：

```bash
python3 app.py status          # 最近更新状态
python3 app.py export          # 重新生成页面 JSON 和 CSV
python3 app.py update          # 自动补缺并刷新本年度
python3 app.py update --force  # 强制重抓所有年份
```

## 自动更新

```bash
chmod +x setup-schedule.sh uninstall-schedule.sh
./setup-schedule.sh
```

脚本安装两个用户级 LaunchAgent：

- 网页服务在登录后自动启动，异常退出时自动恢复，地址仍为 <http://127.0.0.1:8765>。
- 数据任务在周一至周五 17:40 更新，18:10 市场数据补偿，21:30 净值补偿；登录时也会执行一次缺口检查。

卸载会停止并移除网页服务和定时更新，但不删除数据库：

```bash
./uninstall-schedule.sh
```

运行日志位于 `logs/serve.log`、`logs/serve-error.log`、`logs/update.log` 和 `logs/update-error.log`。

## 数据与口径

- 中债年度标准期限文件：国债、国开债、商业银行二级资本债 AAA-、中短期票据 AAA。
- 中国货币网：DR007 加权利率最新值和公开趋势 CSV。
- 长盛基金、广发基金季度报告 PDF；兴全恒裕种子画像来自 2026 年二季报公开信息，因精确 PDF 链接尚未稳定发现而降低可信度。
- 三只基金历史单位净值与发布的日增长率：东方财富历史净值接口，明确标记为备用源；分红日不使用单位净值简单相减代替日增长率。
- 所有收益率以百分比存储，例如 `1.68` 表示 `1.68%`；变化与信用利差以 BP 展示。

当前未完成的稳定数据入口会在页面明确显示：

- 上海清算所银行无固定期限资本债（行权）曲线自 2026-07-27 才开始发布，适配器待完成。
- 中国货币网公开页面已提供 DR007；R007 历史公开接口未稳定确认。工具不会用 FDR007 冒充 R007。

## 文件

- `data/bond-monitor.db`：本地历史数据库，不提交 Git。
- `web/data/dashboard.json`：页面数据，不提交 Git。
- `web/data/market-history.csv`：可下载历史数据，不提交 Git。
- `docs/superpowers/specs/`：已批准设计。
- `docs/superpowers/plans/`：实施计划。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

页面固定提示：数据可能延迟；基金压力为公开季报代理，不代表实时持仓、实时净值或投资建议。
