# 模型设定与误差结构检验结果

数据文件：`prcd/process2.csv`

- 基准回归变量：`eff ~ lntl + ind + urb + rd + open + es`
- `Pooled F` 基于双固定效应模型的 poolability 检验
- `Hausman` 比较对象为“省份固定效应 + 年份虚拟变量”和“随机效应 + 年份虚拟变量”，仅对核心解释变量与控制变量系数作比较
- `Pesaran CD`、`Modified Wald`、`Wooldridge` 基于双固定效应模型残差

## 检验结果

| test | statistic | pvalue | df | decision_5pct | null_hypothesis | interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| Pooled F | 60.6519 | 0 | F(36,197) | Reject H0 | All entity/time effects are jointly zero | Effects needed |
| Time Effects Wald | 25.1665 | 0.000708907 | chi2(7) | Reject H0 | Year effects jointly zero | Keep time effects |
| Hausman | 13.9716 | 0.0299546 | 6 | Reject H0 | RE consistent and efficient | Prefer FE |
| Pesaran CD | 1.81311 | 0.0698156 |  | Fail to reject H0 | No cross-sectional dependence | avg_abs_corr=0.450 |
| Modified Wald | 265.816 | 0 | 30 | Reject H0 | Homoskedasticity across entities | variance_ratio=190.407 |
| Wooldridge AR(1) | 15.4935 | 0.000475637 | F(1,29) | Reject H0 | No first-order serial correlation | beta=-0.232, se=0.068 |
