# 更换 CEADs `es` 数据过程记录

## 任务目标

将原有 `energy_total`、煤炭消费总量、`es` 数据来源调整为：

- `data\各省能源清单CEADs`
- 标准煤折算系数来源于《中国统计年鉴 2023》上传图片

并完成以下工作：

1. 整理标准煤折算系数，使之与省级能源清单字段一一对应，输出 `csv`
2. 编写 `py` 脚本，输出标准的 `year-province-energy_total-es` 字段 `csv`
3. 如遇口径不确定处，先停下确认

---

## 已确认的数据结构

读取 `data\各省能源清单CEADs` 后确认：

- 年份覆盖 `2014-2022`
- 每年一个工作簿
- 每个工作簿包含 `NOTE` 页和各省份 sheet
- 各省份 sheet 的第 3 行 `Total Final Consumption` 为终端消费总量

CEADs 字段统一为：

- `Raw_Coal`
- `Cleaned_Coal`
- `Other_Washed_Coal`
- `Briquettes`
- `Coke`
- `Coke_Oven_Gas`
- `Other_Gas`
- `Other_Coking_Products`
- `Crude_Oil`
- `Gasoline`
- `Kerosene`
- `Diesel_Oil`
- `Fuel_Oil`
- `LPG`
- `Refinery_Gas`
- `Other_Petroleum_Products`
- `Natural_Gas`
- `Heat`
- `Electricity`
- `Other_Energy`

其中：

- `Other_Energy` 单位为 `10^4 tce`
- 说明该列已是标准煤单位，可直接并入 `energy_total`

---

## 初始处理思路

最初方案分两部分：

1. 年鉴图片中能直接找到标准煤折算系数的字段，直接采用年鉴值
2. 年鉴图片中没有与 CEADs 聚合字段一一对应的项，尝试参考 CEADs 论文 `Shan et al. (2018)` Table 1 的 `NCV` 反推折标准煤系数

据此实现了脚本：

- [build_ceads_energy_es.py](C:/Users/abc0x7f/Desktop/PRO/统计建模/build_ceads_energy_es.py)

并生成：

- [data/ceads_standard_coal_factors.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/data/ceads_standard_coal_factors.csv)
- [data/ceads_energy_total_es_2015_2022.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/data/ceads_energy_total_es_2015_2022.csv)

---

## 过程中发现的关键口径问题

在映射 CEADs 字段与年鉴标准煤折算系数时，发现以下字段无法由年鉴图片直接唯一对应：

- `Other_Washed_Coal`
- `Other_Gas`
- `Other_Coking_Products`
- `Other_Petroleum_Products`
- `Briquettes`

另外，以下字段在年鉴图片中是区间值而非单一值：

- `Natural_Gas`
- `Coke_Oven_Gas`

为此进一步核查了 CEADs 相关论文与说明页。

---

## 查阅 CEADs 论文后的结论

### 1. CEADs 论文是否说明分类口径

查阅链接：

- https://www.nature.com/articles/sdata2017201
- Table 1: https://www.nature.com/articles/sdata2017201/tables/2

结论：

- CEADs 论文对能源分类聚合口径有说明
- 文中指出中国能源统计原有 `26` 类燃料，研究中合并为 `17` 类燃料
- Table 1 给出了能源统计类别与研究分类的对应关系

可确认的典型关系包括：

- `Other_Gas = Blast furnace gas + Converter gas`
- `Other_Petroleum_Products = Naphtha + Lubricants + Paraffin + White spirit + Bitumen asphalt + Petroleum coke`
- `Other_Coking_Products = Other coking products`
- `Other_Washed_Coal = Other washed coal`

但同时也确认：

- 该论文主要给出的是排放核算所用的 `NCV`、`CC`、氧化率等参数
- 它**不是**一套专门用于标准煤折算的官方参考系数来源

### 2. 是否存在“学界公认的 CEADs 标准煤折算系数来源”

进一步检索后形成结论：

- 没有单独一套“CEADs 专属且学界另行公认”的标准煤折算系数
- 更稳妥的写法是：
  - CEADs 能源活动数据来源于《中国能源统计年鉴》
  - 折标准煤时依从《中国能源统计年鉴》附录“各种能源折标准煤参考系数”
  - 对于汇总项，应结合国家统计局对折标口径的公开说明

参考网页包括：

- CEADs 数据页  
  https://www.ceads.net/data/province/energy_inventory/Provincial/
- CEADs 中文镜像  
  https://www.ceads.net.cn/data/province/energy_inventory/Provincial/
- `Shan et al. (2018)`  
  https://www.nature.com/articles/sdata2017201
- `Shan et al. (2020)`  
  https://www.nature.com/articles/s41597-020-0393-y
- 国家统计局公开答复  
  https://www.stats.gov.cn/hd/lyzx/zxgk/202503/t20250317_1959087.html

---

## 用户提出的重要质疑

用户指出：

> 其他洗煤你确定算对了？比图片中两项任意一项都高

复核后确认：

- 原先根据 CEADs Table 1 `NCV` 反推得到的 `Other_Washed_Coal = 0.511813`
- 从数学计算本身看并未算错
- 但这个结果高于年鉴图片中可见相关子项 `Middlings = 0.2857` 和 `Slimes = 0.2857-0.4286`
- 因此虽然“能算”，但作为标准煤折算参考系数并不稳妥

随后用户明确要求：

> 按保守下限重做

---

## 最终采用的处理原则

最终不再使用 CEADs `NCV` 反推这些有争议聚合项，而改为：

### 总原则

- 年鉴图片中有直接值的，使用年鉴值
- 年鉴图片中为区间值的，按**保守下限**
- 年鉴图片中无一一对应聚合项的，按相关子项的**保守下限**近似
- `Other_Energy` 因原表单位为 `10^4 tce`，直接按 `1.0` 并入

### 最终保守下限系数

- `Raw_Coal = 0.7143`
- `Cleaned_Coal = 0.9000`
- `Other_Washed_Coal = 0.2857`
- `Briquettes = 0.5000`
- `Coke = 0.9714`
- `Coke_Oven_Gas = 0.5714`
- `Other_Gas = 0.1786`
- `Other_Coking_Products = 1.4286`
- `Crude_Oil = 1.4286`
- `Gasoline = 1.4714`
- `Kerosene = 1.4714`
- `Diesel_Oil = 1.4571`
- `Fuel_Oil = 1.4286`
- `LPG = 1.7143`
- `Refinery_Gas = 1.5714`
- `Other_Petroleum_Products = 1.4286`
- `Natural_Gas = 1.1000`
- `Heat = 0.03412`
- `Electricity = 0.1229`
- `Other_Energy = 1.0000`

---

## 输出结果

### 1. 折算系数表

输出文件：

- [data/ceads_standard_coal_factors.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/data/ceads_standard_coal_factors.csv)

说明：

- 共覆盖 `20` 个 CEADs 字段
- 包含字段名、中文名称、输入单位、折算系数、来源、备注等信息

### 2. 面板结果表

输出文件：

- [data/ceads_energy_total_es_2015_2022.csv](C:/Users/abc0x7f/Desktop/PRO/统计建模/data/ceads_energy_total_es_2015_2022.csv)

字段结构：

- `year`
- `province`
- `energy_total`
- `es`

口径说明：

- 时间范围：`2015-2022`
- 省份名称：中文省名
- `energy_total`：各能源按折标准煤系数折算后求和
- `es`：煤炭类能源折标合计 / `energy_total`

校验结果：

- 共 `240` 行
- `30` 个省份
- `8` 个年份
- `year-province` 无重复

---

## 与老师沟通的邮件草稿

为进一步确认 CEADs 团队对折标准煤参考系数的建议口径，整理了拟发送邮件内容，收件人为：

- 单钰理 `<shanyuli@outlook.com>`
- 关大博 `<guandabo@hotmail.com>`
- 刘竹 `<zhuliu@tsinghua.edu.cn>`

邮件主题：

> 关于省级能源清单折标准煤参考系数选取口径的请教

邮件要点包括：

- 说明正在使用 CEADs 省级能源清单进行实证研究
- 说明拟测算 `energy_total` 与 `es`
- 明确指出 CEADs 字段与《中国能源统计年鉴》折标系数并非完全一一对应
- 请教：
  1. 是否有推荐或默认的折标准煤参考系数来源
  2. 聚合项 `Other_Washed_Coal`、`Other_Gas`、`Other_Coking_Products`、`Other_Petroleum_Products` 如何处理
  3. `Natural_Gas`、`Coke_Oven_Gas` 等区间值应如何取值
  4. 是否已有 CEADs 团队的配套说明文档或参考表

---

## 当前结论

当前项目内已经完成：

1. CEADs 省级能源清单字段核对
2. 标准煤折算系数表整理
3. `2015-2022` 年省级 `energy_total-es` 面板表输出
4. 保守下限口径修正
5. 向 CEADs 老师请教的邮件措辞整理

后续待做事项：

1. 根据最终确认口径，更新 [数据来源.txt](C:/Users/abc0x7f/Desktop/PRO/统计建模/数据来源.txt)
2. 如收到 CEADs 团队回复，再决定是否需要更新系数表与结果表

