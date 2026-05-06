# 空间 SDM 主模型报告

本报告基于 `code/空间分析/stata/空间SDM主模型.do` 的最新实际输出整理，采用双固定效应空间杜宾模型（SDM）估计四类矩阵下的结果，并对空间直接效应、间接效应与总效应进行分解。

结果文件口径说明：本报告仅以 `主模型系数表.csv`、`空间效应分解表.csv` 及对应 Stata 日志为最终引用口径。

## 一、模型设定

- 主模型：`经济倒数权重矩阵 + 双固定效应 SDM`
- 对照矩阵：
  - `0-1 邻接矩阵`
  - `地理距离倒数矩阵（省会版）`
  - `经济地理嵌套矩阵（省会版）`
- 被解释变量：`eff`
- 解释变量：`lntl`、`ind`、`urb`、`rd`、`open`、`es`

之所以继续将 `经济倒数权重矩阵 + 双固定效应 SDM` 作为主模型，主要基于三点：

1. `LM Error` 与 `Robust LM Error` 在 `5%` 水平显著；
2. `LR` 检验明确支持 `双固定效应` 优于单一固定效应；
3. `Wald` 检验拒绝将 `SDM` 简化为 `SAR` 或 `SEM`。

## 二、四类矩阵的核心系数结果

### 1. Main 系数

| weight_type | lntl | ind | urb | rd | open | es | rho |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adjacency_01 | 0.3301*** | 0.0862 | -1.7434*** | 4.7408* | 0.5004*** | 0.0215 | 0.1610* |
| economic_inv | 0.0350 | 0.0313 | -2.0312*** | 5.1145** | 0.4252*** | -0.0641 | -0.1565 |
| geographic_inv | 0.1253* | 0.0949 | -1.2064*** | 6.2544** | 0.4370*** | -0.0247 | -0.3063 |
| economic_geo_nested | 0.0562 | 0.1029 | -1.1563*** | 5.9918** | 0.4540*** | -0.0363 | -0.2093 |

注：`*`、`**`、`***` 分别表示在 `10%`、`5%`、`1%` 水平显著。

### 2. Wx 系数中较关键的显著项

| weight_type | variable | coef | pvalue | 结论 |
| --- | --- | ---: | ---: | --- |
| adjacency_01 | Wx:lntl | -0.3654 | 0.0007 | 显著为负 |
| adjacency_01 | Wx:open | 0.5298 | 0.0018 | 显著为正 |
| economic_inv | Wx:lntl | 0.7706 | 0.0000 | 显著为正 |
| economic_inv | Wx:es | -1.2090 | 0.0001 | 显著为负 |
| geographic_inv | Wx:open | 1.2348 | 0.0475 | 显著为正 |
| geographic_inv | Wx:urb | -4.4511 | 0.0488 | 显著为负 |
| economic_geo_nested | Wx:open | 1.2951 | 0.0384 | 显著为正 |
| economic_geo_nested | Wx:lntl | 0.6804 | 0.0597 | 10%边际显著为正 |
| economic_geo_nested | Wx:urb | -4.1665 | 0.0573 | 10%边际显著为负 |

## 三、空间效应分解

空间模型解释应优先以 `LR_Direct`、`LR_Indirect`、`LR_Total` 为准，而不宜只看 `Main` 与 `Wx` 系数。

### 1. 经济倒数权重矩阵主模型

| effect_type | variable | coef | pvalue | 5%结论 |
| --- | --- | ---: | ---: | --- |
| LR_Direct | urb | -2.0083 | 0.0000 | 显著为负 |
| LR_Direct | rd | 5.1231 | 0.0331 | 显著为正 |
| LR_Direct | open | 0.4291 | 0.0000 | 显著为正 |
| LR_Indirect | lntl | 0.6830 | 0.0000 | 显著为正 |
| LR_Indirect | es | -1.0566 | 0.0001 | 显著为负 |
| LR_Total | lntl | 0.6990 | 0.0000 | 显著为正 |
| LR_Total | urb | -1.5906 | 0.0387 | 显著为负 |
| LR_Total | es | -1.0787 | 0.0001 | 显著为负 |

### 2. 三类对照矩阵的主要空间效应

| weight_type | effect_type | variable | coef | pvalue | 结论 |
| --- | --- | --- | ---: | ---: | --- |
| adjacency_01 | LR_Direct | lntl | 0.3207 | 0.0000 | 显著为正 |
| adjacency_01 | LR_Direct | urb | -1.7315 | 0.0000 | 显著为负 |
| adjacency_01 | LR_Direct | rd | 4.8698 | 0.0471 | 显著为正 |
| adjacency_01 | LR_Direct | open | 0.5221 | 0.0000 | 显著为正 |
| adjacency_01 | LR_Indirect | lntl | -0.3652 | 0.0020 | 显著为负 |
| adjacency_01 | LR_Indirect | open | 0.7039 | 0.0005 | 显著为正 |
| adjacency_01 | LR_Total | open | 1.2260 | 0.0000 | 显著为正 |
| adjacency_01 | LR_Total | urb | -2.6200 | 0.0008 | 显著为负 |
| geographic_inv | LR_Direct | rd | 6.1278 | 0.0146 | 显著为正 |
| geographic_inv | LR_Direct | open | 0.4207 | 0.0000 | 显著为正 |
| geographic_inv | LR_Direct | urb | -1.1029 | 0.0163 | 显著为负 |
| geographic_inv | LR_Total | open | 1.3080 | 0.0222 | 显著为正 |
| geographic_inv | LR_Total | urb | -4.2890 | 0.0055 | 显著为负 |
| economic_geo_nested | LR_Direct | rd | 5.7279 | 0.0235 | 显著为正 |
| economic_geo_nested | LR_Direct | open | 0.4404 | 0.0000 | 显著为正 |
| economic_geo_nested | LR_Direct | urb | -1.0677 | 0.0150 | 显著为负 |
| economic_geo_nested | LR_Total | lntl | 0.6164 | 0.0399 | 显著为正 |
| economic_geo_nested | LR_Total | open | 1.4810 | 0.0206 | 显著为正 |
| economic_geo_nested | LR_Total | urb | -4.3886 | 0.0090 | 显著为负 |

## 四、结果解释

### 1. 相对稳健的本地效应

1. 四类矩阵下，`open` 的直接作用均为显著正向，说明开放水平提升对本地 `eff` 的促进作用较稳健。
2. 四类矩阵下，`urb` 的直接作用均为显著负向，说明城镇化变量与本地 `eff` 呈稳定负相关。
3. `rd` 在四类矩阵下都表现为正向，且除邻接矩阵为 `10%` 边际显著外，其余三类矩阵均在 `5%` 水平显著。

### 2. 空间溢出方向存在矩阵依赖

1. 主模型 `economic_inv` 下，`lntl` 的间接效应和总效应显著为正，`es` 的间接效应和总效应显著为负，说明其空间传导特征最清晰。
2. `adjacency_01` 下，`lntl` 的间接效应显著转为负值，而 `open` 的间接效应和总效应显著为正，说明邻接矩阵更容易识别出开放变量的扩散效应。
3. `geographic_inv` 与 `economic_geo_nested` 下，`open` 和 `urb` 的总效应更突出，而间接效应单独显著性相对弱一些。

### 3. 主模型与对照矩阵的比较

1. `economic_inv` 是四类矩阵中识别链条最完整的一类，既有前期检验支持，也有较清晰的溢出效应结构。
2. `economic_geo_nested` 的结果方向与主模型较接近，尤其是 `open` 正向、`urb` 负向、`lntl` 总效应为正，可作为较有价值的补充对照。
3. `geographic_inv` 的结果可读性尚可，但前期矩阵检验证据偏弱，适合作为附加稳健性矩阵而非主结论载体。
4. `adjacency_01` 保留了传统空间邻接视角，适合用于和经济权重矩阵做对比。

## 五、结论与建议

1. 后续正文中的主回归仍建议使用 `经济倒数权重矩阵 + 双固定效应 SDM`。
2. `经济地理嵌套矩阵（省会版）` 可以作为优先级较高的对照矩阵写入稳健性分析。
3. `0-1 邻接矩阵` 与 `地理距离倒数矩阵（省会版）` 可作为补充对照，但不建议替代主模型。
4. 论文正文解释时，应优先使用 `直接效应 / 间接效应 / 总效应`，不要只解释 `Main` 和 `Wx` 系数。

## 六、输出文件

- `outputs/回归分析/80_空间SDM主模型/主模型系数表.csv`
- `outputs/回归分析/80_空间SDM主模型/空间效应分解表.csv`
- `outputs/回归分析/80_空间SDM主模型/stata/SDM主模型_adjacency_01.log`
- `outputs/回归分析/80_空间SDM主模型/stata/SDM主模型_economic_inv.log`
- `outputs/回归分析/80_空间SDM主模型/stata/SDM主模型_geographic_inv.log`
- `outputs/回归分析/80_空间SDM主模型/stata/SDM主模型_economic_geo_nested.log`
