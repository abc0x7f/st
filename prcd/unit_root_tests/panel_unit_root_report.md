# 面板单位根检验结果

数据文件：`prcd/process2.csv`

- 面板：30 个省份 × 8 年（2015-2022），平衡面板
- 水平值检验设定：常数项 `c`
- `LLC`、`IPS` 使用 `panelbox`
- `ADF-Fisher` 使用 `statsmodels.adfuller` 的 Fisher 合并实现
- `PP-Fisher` 使用 `arch.unitroot.PhillipsPerron` 的 Fisher 合并实现

## 水平值结果汇总

| variable | reject_count_5pct | llc | ips | adf_fisher | pp_fisher |
| --- | --- | --- | --- | --- | --- |
| eff | 3 | Reject H0 | Fail to reject H0 | Reject H0 | Reject H0 |
| es | 4 | Reject H0 | Reject H0 | Reject H0 | Reject H0 |
| ind | 4 | Reject H0 | Reject H0 | Reject H0 | Reject H0 |
| lntl | 4 | Reject H0 | Reject H0 | Reject H0 | Reject H0 |
| open | 4 | Reject H0 | Reject H0 | Reject H0 | Reject H0 |
| rd | 1 | Fail to reject H0 | Fail to reject H0 | Reject H0 | Fail to reject H0 |
| urb | 4 | Reject H0 | Reject H0 | Reject H0 | Reject H0 |

## 水平值详细结果

| variable | test | statistic | pvalue | decision_5pct | note |
| --- | --- | --- | --- | --- | --- |
| eff | LLC | -1.71021 | 0.0436135 | Reject H0 | lags=0 |
| eff | IPS | 0.517695 | 0.697664 | Fail to reject H0 | mean_lag=0.17 |
| eff | ADF-Fisher | 165.009 | 9.63818e-12 | Reject H0 | statsmodels.adfuller + Fisher combine |
| eff | PP-Fisher | 1675.87 | 0 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| lntl | LLC | -6.39968 | 7.78492e-11 | Reject H0 | lags=0 |
| lntl | IPS | -8.62282 | 3.26614e-18 | Reject H0 | mean_lag=0.43 |
| lntl | ADF-Fisher | 150.69 | 9.36999e-10 | Reject H0 | statsmodels.adfuller + Fisher combine |
| lntl | PP-Fisher | 92.5122 | 0.00446919 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| ind | LLC | -8.62861 | 3.10507e-18 | Reject H0 | lags=0 |
| ind | IPS | -70.0024 | 0 | Reject H0 | mean_lag=0.13 |
| ind | ADF-Fisher | 205.107 | 0 | Reject H0 | statsmodels.adfuller + Fisher combine |
| ind | PP-Fisher | 329.083 | 0 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| urb | LLC | -17.7931 | 3.99501e-71 | Reject H0 | lags=0 |
| urb | IPS | -19.8717 | 3.57917e-88 | Reject H0 | mean_lag=0.17 |
| urb | ADF-Fisher | 384.519 | 0 | Reject H0 | statsmodels.adfuller + Fisher combine |
| urb | PP-Fisher | 1585.73 | 0 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| rd | LLC | -1.43162 | 0.0761268 | Fail to reject H0 | lags=0 |
| rd | IPS | -0.170741 | 0.432214 | Fail to reject H0 | mean_lag=0.07 |
| rd | ADF-Fisher | 84.514 | 0.0202337 | Reject H0 | statsmodels.adfuller + Fisher combine |
| rd | PP-Fisher | 72.6136 | 0.127284 | Fail to reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| open | LLC | -5.12871 | 1.45868e-07 | Reject H0 | lags=0 |
| open | IPS | -4.46661 | 3.97339e-06 | Reject H0 | mean_lag=0.60 |
| open | ADF-Fisher | 242.354 | 0 | Reject H0 | statsmodels.adfuller + Fisher combine |
| open | PP-Fisher | 338.597 | 0 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |
| es | LLC | -5.02846 | 2.47215e-07 | Reject H0 | lags=0 |
| es | IPS | -71.5719 | 0 | Reject H0 | mean_lag=0.37 |
| es | ADF-Fisher | 281.509 | 0 | Reject H0 | statsmodels.adfuller + Fisher combine |
| es | PP-Fisher | 245.521 | 0 | Reject H0 | arch.unitroot.PhillipsPerron + Fisher combine |

## 一阶差分复检（边界变量）

| variable | test | statistic | pvalue | decision_5pct | note |
| --- | --- | --- | --- | --- | --- |
| D.eff | LLC | -15.6775 | 1.07769e-55 | Reject H0 | lags=0 |
| D.eff | IPS | -12.9335 | 1.45619e-38 | Reject H0 | mean_lag=0.13 |
| D.eff | ADF-Fisher | 317.893 | 0 | Reject H0 | first difference check |
| D.eff | PP-Fisher | 367.486 | 0 | Reject H0 | first difference check; PP lags=1 |
| D.rd | LLC | -14.8919 | 1.85936e-50 | Reject H0 | lags=0 |
| D.rd | IPS | -8.66235 | 2.31065e-18 | Reject H0 | mean_lag=0.03 |
| D.rd | ADF-Fisher | 252.666 | 0 | Reject H0 | first difference check |
| D.rd | PP-Fisher | 217.667 | 0 | Reject H0 | first difference check; PP lags=1 |

## 结果解读口径

1. 若大多数单位根检验在 5% 水平拒绝原假设，可将该变量视为总体平稳。
2. 若结果出现分歧，优先结合短面板 `T=8` 的低检验功效来解释，不机械按单一检验下结论。
3. 对于水平值存在争议但一阶差分稳定拒绝单位根的变量，可表述为“可能处于边界平稳或弱平稳状态，回归时需结合双固定效应与稳健标准误谨慎解释”。