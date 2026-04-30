# 基准面板回归与诊断图

## 模型

```text
eff ~ lntl + ind + urb + rd + open + es + C(province) + C(year)
```

## 拟合摘要

```text
       metric         value
         nobs  2.400000e+02
  n_provinces  3.000000e+01
      n_years  8.000000e+00
    r_squared  9.573916e-01
adj_r_squared  9.483076e-01
  f_statistic  1.053929e+02
     f_pvalue 9.576176e-114
          aic -7.020719e+02
          bic -5.524045e+02
 n_parameters  4.300000e+01
```

## 核心系数

```text
variable      coef  std_err   t_value  p_value  ci_lower  ci_upper
    lntl  0.172489 0.063555  2.714022 0.007237  0.047154  0.297824
     ind  0.082859 0.131288  0.631121 0.528693 -0.176052  0.341769
     urb -1.928470 0.389614 -4.949689 0.000002 -2.696820 -1.160120
      rd  6.588261 2.817764  2.338117 0.020384  1.031408 12.145114
    open  0.452085 0.105900  4.268961 0.000031  0.243241  0.660929
      es -0.138637 0.145208 -0.954752 0.340873 -0.424998  0.147724
```

## 图形输出

- `01_lntl_eff_scatter_fit.png`
- `02_true_vs_pred_sequence.png`
- `03_pred_vs_actual_scatter.png`
- `04_residual_vs_fitted.png`
- `05_residual_qq.png`