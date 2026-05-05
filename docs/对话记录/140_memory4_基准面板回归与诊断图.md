# 记忆 4

## 本轮任务概述

本轮围绕第二阶段基准面板回归与回归诊断图展开，主要完成了以下工作：

1. 基于 `prcd/process2.csv` 运行不含平方项的基准双固定效应回归。
2. 输出回归结果、预测值、残差、拟合优度汇总表。
3. 绘制并多轮修改以下图形：
   - `lntl` 与 `eff` 散点拟合图
   - 真实值与预测值序列图
   - 预测值-真实值散点图
   - 拟合值-残差图
   - 标准化残差正态 Q-Q 图
4. 逐步修正图形的字体、颜色、排序逻辑、图例位置、坐标范围和注释。

---

## 脚本与输出文件

### 核心脚本

- [baseline_panel_diagnostics.py](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_diagnostics.py)

### 输出目录

- [baseline_panel_outputs](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_outputs)

### 主要输出文件

- [baseline_regression_coefficients.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_outputs/baseline_regression_coefficients.csv)
- [baseline_regression_summary.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_outputs/baseline_regression_summary.csv)
- [baseline_predictions_and_residuals.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_outputs/baseline_predictions_and_residuals.csv)
- [baseline_panel_report.md](C:/Users/abc0x7f/Desktop/PRO/统计建模/prcd/baseline_panel_outputs/baseline_panel_report.md)

---

## 基准回归设定

使用的模型为：

$$
eff_{it}=\alpha+\beta_1 lntl_{it}+\gamma'X_{it}+\mu_i+\delta_t+\varepsilon_{it}
$$

其中：

- 被解释变量：`eff`
- 核心解释变量：`lntl`
- 控制变量：`ind`、`urb`、`rd`、`open`、`es`
- 固定效应：省份固定效应 `C(province)`、年份固定效应 `C(year)`

脚本中对应公式为：

```text
eff ~ lntl + ind + urb + rd + open + es + C(province) + C(year)
```

---

## 基准回归结果

### 样本与拟合优度

- 样本量：`240`
- 省份数：`30`
- 年份数：`8`
- `R^2 = 0.957392`
- 调整 `R^2 = 0.948308`

### 核心结果

- `lntl` 系数为 `0.172489`，`p = 0.007237`，显著为正。
- `urb` 系数为 `-1.928470`，显著为负。
- `rd` 系数为 `6.588261`，显著为正。
- `open` 系数为 `0.452085`，显著为正。
- `ind`、`es` 在该设定下不显著。

---

## 图形修改过程

### 图 1：`lntl` 与 `eff` 散点拟合图

最终要求：

- 字体统一为 `Times New Roman, SimSun`
- 配色改为与图 5 一致的按年份 `gist_earth` 配色
- `x` 轴最大值设为 `3.0`

### 图 2：真实值与预测值序列图

最终要求：

- 样本排序规则改为：
  1. 先按 2015 年 `eff` 从小到大确定省份顺序
  2. 后续年份均保持这一顺序
  3. 同一年份样本相邻排列
- 横轴范围设为 `0-240`
- 每 `30` 个样本为一组，对应一个年份
- 横轴主刻度为 `0, 30, ..., 240`
- 刻度之间标记 `2015` 至 `2022`
- 真实值颜色使用 `RdYlGn` 的分段渐变
- 预测线更细，颜色统一为深灰，点型为方块
- 图例放左上角，仅保留必要说明
- 图底部增加排序规则注释

### 图 3：预测值-真实值散点图

最终要求：

- 配色改为 `gist_earth`
- 颜色顺序前后翻转
- 45 度线使用黑色直线

### 图 4：拟合值-残差图

最终要求：

- 配色改为 `gist_earth`
- 颜色顺序前后翻转
- `y` 轴上下限固定为 `-0.3` 和 `0.3`

### 图 5：标准化残差正态 Q-Q 图

本图经历了关键逻辑修正。

#### 初始问题

最初版本错误地把 `stats.probplot()` 排序后的样本分位数，与原始 `year, province` 顺序直接对应，导致：

- 点的横纵坐标是“排序后的残差样本”
- 颜色却使用“原始数据年份顺序”
- 因而年份颜色映射不成立

#### 修正后的处理逻辑

现已改为：

1. 先计算标准化残差 `std_resid`
2. 再按 `std_resid` 从小到大排序
3. Q-Q 图中的每个点就是该排序后的样本
4. 每个点的年份颜色来自该样本自身所属年份

因此，当前图 5 中：

- 点与年份是一一对应的
- 颜色映射是有效的，不是后贴标签

#### 图 5 的最终要求

- 使用标准化残差而不是原始残差
- 配色改为 `gist_earth`
- 颜色顺序前后翻转
- 按年份区分颜色
- 散点不加白色边框
- `x` 轴范围设为 `-3` 到 `3`
- `y` 轴下限设为 `-6`
- 从原点向两坐标轴添加灰色虚线辅助线
- 图例放左上角
- 将 `R^2` 改为 `R`

---

## 关于 Q-Q 图中 `R` 与 `R^2` 的说明

本轮明确提出：

- Q-Q 图中的文字说明应使用 `R`，不使用 `R^2`

原因是：

- `R` 表示 Q-Q 点与理论正态参考线之间的线性相关程度
- `R^2` 只是其平方，更多用于回归拟合优度场景
- 在 Q-Q 图语境下，直接报告 `R` 更自然，也更常见

---

## 当前可直接使用的解释方向

### 回归结果

- `lntl` 显著为正，可解释为夜间灯光聚合度提高会显著提升碳排放效率。
- `urb` 显著为负，说明当前样本下城镇化水平提升可能伴随能源消耗与排放压力上升。
- `rd`、`open` 显著为正，说明技术投入和对外开放有助于效率改善。

### Q-Q 图

- 若多数点贴近参考线，说明标准化残差总体接近正态分布。
- 若尾部偏离较明显，说明极端残差存在一定厚尾或偏态，但不必然否定模型结论。
- 图中按年份着色，可观察异常偏离是否集中在某些年份。

---

## 需要注意的工程状态

- 当前 `baseline_panel_diagnostics.py` 已是重新整理后的干净版本。
- 历史文件中曾出现部分中文乱码，因此后续若继续微调图形，优先在当前版本基础上改，不要回退到旧缓存文本。
- `memory3.md` 已存在编码异常内容，本轮新记忆单独写入 `memory4.md`，避免污染旧文件。
- 当前已过模型设定检验（需要FE）、误差结构检验（使用Driscoll-Kraay 标准误）；下一步还需：稳健性检验、内生性检验或处理、异质性分析