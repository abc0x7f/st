from __future__ import annotations

import sys
from pathlib import Path

from step_types import InputRequirement, RunnerType, StepDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_EXE = Path(sys.executable)
LOGO_PATH = PROJECT_ROOT / "releases" / "比赛版" / "图" / "logo.png"


def root_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def py_command(script_relative_path: str) -> tuple[str, ...]:
    return ("python", script_relative_path)


def stata_command(script_relative_path: str) -> tuple[str, ...]:
    return ("stata-do", script_relative_path)


STEP_DEFINITIONS: tuple[StepDefinition, ...] = (
    StepDefinition(
        id="data_energy",
        name="构建省级能源总量与折标系数",
        stage="数据处理",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/数据处理/10_构建省级能源总量与折标系数.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="none",
        required_inputs=(
            InputRequirement(
                root_path("data", "原始数据", "全国能源产量与消费量_网络整理", "全国各地区能源产量和消费量", "【省年鉴版】能源消费总量2000-2022.xlsx"),
                kind="file",
            ),
            InputRequirement(
                root_path("data", "外部资料", "省级能源折标准煤系数_ceads.csv"),
                kind="csv",
                required_columns=("year",),
            ),
        ),
        expected_outputs=(
            "data/中间数据/省级能源energy和es.csv",
        ),
        primary_csv=root_path("data", "中间数据", "省级能源energy和es.csv"),
        description="从原始能源统计资料与折标系数构建省级能源总量与能源结构指标。",
    ),
    StepDefinition(
        id="data_ntl",
        name="夜间灯光指标检查",
        stage="数据处理",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/数据处理/20_夜间灯光指标检查.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="none",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "lntl")),
            InputRequirement(root_path("data", "外部资料", "中国省级地图.geojson"), kind="file"),
        ),
        expected_outputs=(
            "outputs/数据处理/20_夜间灯光指标检查/*.csv",
            "outputs/数据处理/20_夜间灯光指标检查/*.md",
            "outputs/数据处理/20_夜间灯光指标检查/*.png",
        ),
        primary_csv=root_path("outputs", "数据处理", "20_夜间灯光指标检查", "夜间灯光检查数据.csv"),
        image_globs=("outputs/数据处理/20_夜间灯光指标检查/*.png",),
        markdown_globs=("outputs/数据处理/20_夜间灯光指标检查/*.md",),
        description="检查夜间灯光指标的分布、趋势与空间分级效果。",
    ),
    StepDefinition(
        id="data_io",
        name="投入产出关系预检",
        stage="数据处理",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/数据处理/30_投入产出关系预检.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="none",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第一阶段_基础.csv"), kind="csv", required_columns=("province", "year")),
        ),
        expected_outputs=("outputs/数据处理/30_投入产出关系预检/*.png",),
        image_globs=("outputs/数据处理/30_投入产出关系预检/*.png",),
        description="在效率测算前检查投入产出变量关系是否异常。",
    ),
    StepDefinition(
        id="data_sample",
        name="样本构建流程与缺失检查",
        stage="数据处理",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/数据处理/50_样本构建流程缺失检查与变量箱线图.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="none",
        expected_outputs=("outputs/数据处理/50_样本构建流程缺失检查与变量箱线图/*",),
        image_globs=("outputs/数据处理/50_样本构建流程缺失检查与变量箱线图/*.png",),
        description="输出样本构建流程图、缺失热力图和核心变量箱线图。",
    ),
    StepDefinition(
        id="dearun_manual",
        name="Dearun 效率测算结果回填",
        stage="效率测算",
        runner_type=RunnerType.MANUAL,
        command=(),
        working_dir=PROJECT_ROOT,
        precheck_mode="manual_result",
        required_inputs=(
            InputRequirement(root_path("outputs", "效率测算", "模型输出"), kind="directory", label="Dearun 输出目录"),
        ),
        expected_outputs=(
            "outputs/效率测算/模型输出/**/*规模报酬可变VRS_0.xlsx",
            "outputs/效率测算/模型输出/**/*规模报酬不变CRS_0.xlsx",
        ),
        description="该步骤需人工运行 Dearun，并将结果文件放回 outputs/效率测算/模型输出。",
        notes=(
            "请先在 Dearun 中完成 SBM / GM 测算。",
            "结果文件需保留当前命名约定，后续提取脚本按此定位。",
            "人工完成后点击“检查”确认结果文件已回填。",
        ),
    ),
    StepDefinition(
        id="eff_extract",
        name="提取效率测算结果",
        stage="效率测算",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/效率测算/10_提取效率测算结果.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("outputs", "效率测算", "模型输出"), kind="directory"),
        ),
        expected_outputs=("data/中间数据/碳排放效率结果_2015_2022.csv",),
        primary_csv=root_path("data", "中间数据", "碳排放效率结果_2015_2022.csv"),
        description="从 Dearun 输出表中提取年度省级效率结果。",
    ),
    StepDefinition(
        id="eff_plot",
        name="碳排放效率绘图",
        stage="效率测算",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/效率测算/20_碳排放效率绘图.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "中间数据", "碳排放效率结果_2015_2022.csv"), kind="csv", required_columns=("year", "province", "eff")),
        ),
        expected_outputs=("outputs/效率测算/10_碳排放效率绘图/*",),
        image_globs=("outputs/效率测算/10_碳排放效率绘图/*.png",),
        description="输出效率均值、核密度、地图和区域差异图组。",
    ),
    StepDefinition(
        id="eff_ntl_plot",
        name="效率与灯光排序绘图",
        stage="效率测算",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/效率测算/30_效率与灯光排序绘图.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff", "lntl")),
        ),
        expected_outputs=("outputs/效率测算/10_碳排放效率绘图/*对比排序图.png",),
        image_globs=("outputs/效率测算/10_碳排放效率绘图/*对比排序图.png",),
        description="对比省均效率与夜间灯光强度排序。",
    ),
    StepDefinition(
        id="productivity_plot",
        name="生产率分解绘图",
        stage="效率测算",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/效率测算/40_生产率分解绘图.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("outputs", "效率测算", "模型输出"), kind="directory"),
        ),
        expected_outputs=("outputs/效率测算/20_GM分解绘图/*",),
        image_globs=("outputs/效率测算/20_GM分解绘图/*.png",),
        description="渲染 GM 及其分解项的趋势图和比较图。",
    ),
    StepDefinition(
        id="reg_corr",
        name="相关性与共线性分析",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/10_相关性与共线性分析.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("eff", "lntl", "ind", "urb", "rd", "open", "es")),
        ),
        expected_outputs=("outputs/回归分析/10_相关性与VIF分析/*",),
        primary_csv=root_path("outputs", "回归分析", "10_相关性与VIF分析", "皮尔逊相关系数矩阵.csv"),
        image_globs=("outputs/回归分析/10_相关性与VIF分析/*.png",),
        markdown_globs=("outputs/回归分析/10_相关性与VIF分析/*.md",),
        description="输出相关系数矩阵、VIF 和解释文本。",
    ),
    StepDefinition(
        id="reg_spec",
        name="模型设定检验",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/20_模型设定检验.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("eff", "lntl")),
        ),
        expected_outputs=("outputs/回归分析/20_模型设定检验/*",),
        primary_csv=root_path("outputs", "回归分析", "20_模型设定检验", "模型设定检验结果.csv"),
        markdown_globs=("outputs/回归分析/20_模型设定检验/*.md",),
        description="完成回归设定检验并输出说明。",
    ),
    StepDefinition(
        id="reg_unit_root",
        name="面板单位根检验",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/30_面板单位根检验.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff")),
        ),
        expected_outputs=("outputs/回归分析/30_面板单位根检验/*",),
        primary_csv=root_path("outputs", "回归分析", "30_面板单位根检验", "面板单位根汇总表.csv"),
        markdown_globs=("outputs/回归分析/30_面板单位根检验/*.md",),
        description="输出面板单位根检验表和说明。",
    ),
    StepDefinition(
        id="reg_baseline",
        name="基准面板回归诊断",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/40_基准面板回归诊断.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff", "lntl")),
        ),
        expected_outputs=("outputs/回归分析/40_基准面板回归诊断/*",),
        primary_csv=root_path("outputs", "回归分析", "40_基准面板回归诊断", "基准回归系数表.csv"),
        image_globs=("outputs/回归分析/40_基准面板回归诊断/*.png",),
        markdown_globs=("outputs/回归分析/40_基准面板回归诊断/*.md",),
        description="运行双固定效应模型并输出诊断图组。",
    ),
    StepDefinition(
        id="reg_robust",
        name="稳健性检验",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/50_稳健性检验.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff")),
        ),
        expected_outputs=("outputs/回归分析/50_稳健性检验/*",),
        primary_csv=root_path("outputs", "回归分析", "50_稳健性检验", "稳健性核心比较表.csv"),
        image_globs=("outputs/回归分析/50_稳健性检验/*.png",),
        markdown_globs=("outputs/回归分析/50_稳健性检验/*.md",),
        description="输出稳健性对比表、系数表和森林图。",
    ),
    StepDefinition(
        id="reg_heterogeneity",
        name="异质性检验",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/60_异质性检验.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff")),
        ),
        expected_outputs=("outputs/回归分析/60_异质性检验/*",),
        primary_csv=root_path("outputs", "回归分析", "60_异质性检验", "异质性核心结果表.csv"),
        markdown_globs=("outputs/回归分析/60_异质性检验/*.md",),
        description="生成异质性模型汇总和解释报告。",
    ),
    StepDefinition(
        id="spatial_adj_matrix",
        name="构建邻接矩阵",
        stage="空间分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/空间分析/10_构建邻接矩阵.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "中间数据", "碳排放效率结果_2015_2022.csv"), kind="csv", required_columns=("province",)),
        ),
        expected_outputs=("data/最终数据/省际01邻接矩阵.csv",),
        primary_csv=root_path("data", "最终数据", "省际01邻接矩阵.csv"),
        description="根据省份顺序生成 0-1 邻接矩阵。",
    ),
    StepDefinition(
        id="spatial_capitals",
        name="生成省会坐标与距离矩阵",
        stage="空间分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/空间分析/15_生成省会城市坐标与距离矩阵.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province",)),
        ),
        expected_outputs=(
            "data/中间数据/省会城市坐标表.csv",
            "data/最终数据/省际地理距离倒数矩阵_省会版.csv",
            "data/最终数据/省际经济地理嵌套矩阵_省会版.csv",
        ),
        primary_csv=root_path("data", "中间数据", "省会城市坐标表.csv"),
        description="生成省会坐标表与地理/嵌套空间矩阵。",
    ),
    StepDefinition(
        id="reg_spatial_weight_py",
        name="空间权重矩阵检验（Python）",
        stage="回归分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/回归分析/70_空间权重矩阵检验.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff")),
            InputRequirement(root_path("data", "最终数据", "省际01邻接矩阵.csv"), kind="csv"),
            InputRequirement(root_path("data", "最终数据", "省际经济距离矩阵.csv"), kind="csv"),
        ),
        expected_outputs=("outputs/回归分析/70_空间权重矩阵检验/*",),
        primary_csv=root_path("outputs", "回归分析", "70_空间权重矩阵检验", "LM与RobustLM检验结果.csv"),
        markdown_globs=("outputs/回归分析/70_空间权重矩阵检验/*.md",),
        description="基于 Python 空间计量包做 LM/LR/Wald 检验。",
    ),
    StepDefinition(
        id="reg_spatial_weight_stata",
        name="空间权重矩阵检验（Stata）",
        stage="回归分析",
        runner_type=RunnerType.HYBRID,
        command=stata_command("code/空间分析/stata/空间权重矩阵检验.do"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff")),
            InputRequirement(root_path("data", "最终数据", "省际地理距离倒数矩阵_省会版.csv"), kind="csv"),
        ),
        expected_outputs=("outputs/回归分析/70_空间权重矩阵检验/stata/*",),
        primary_csv=root_path("outputs", "回归分析", "70_空间权重矩阵检验", "LR检验结果.csv"),
        markdown_globs=("outputs/回归分析/70_空间权重矩阵检验/*.md",),
        description="优先尝试由 GUI 拉起 Stata；若不可用，则提示手动执行并回检。",
        notes=(
            "若 GUI 未找到 Stata，可手动运行 .do 文件。",
            "运行完成后点击“检查”刷新结果状态。",
        ),
    ),
    StepDefinition(
        id="spatial_moran",
        name="莫兰指数与局部聚类分析",
        stage="空间分析",
        runner_type=RunnerType.PYTHON,
        command=py_command("code/空间分析/20_莫兰指数与局部聚类分析.py"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "中间数据", "碳排放效率结果_2015_2022.csv"), kind="csv", required_columns=("year", "province", "eff")),
            InputRequirement(root_path("data", "最终数据", "省际经济距离矩阵.csv"), kind="csv"),
            InputRequirement(root_path("data", "外部资料", "中国省级地图.geojson"), kind="file"),
        ),
        expected_outputs=("outputs/空间分析/20_莫兰指数与LISA分析/*",),
        primary_csv=root_path("outputs", "空间分析", "20_莫兰指数与LISA分析", "全局莫兰指数_2015_2022.csv"),
        image_globs=("outputs/空间分析/20_莫兰指数与LISA分析/*.png",),
        markdown_globs=("outputs/空间分析/20_莫兰指数与LISA分析/*.md",),
        description="输出全局莫兰指数、LISA 聚类图和结果说明。",
    ),
    StepDefinition(
        id="reg_sdm_stata",
        name="空间 SDM 主模型（Stata）",
        stage="回归分析",
        runner_type=RunnerType.HYBRID,
        command=stata_command("code/空间分析/stata/空间SDM主模型.do"),
        working_dir=PROJECT_ROOT,
        precheck_mode="required_inputs",
        required_inputs=(
            InputRequirement(root_path("data", "最终数据", "第二阶段_基础.csv"), kind="csv", required_columns=("province", "year", "eff", "lntl", "ind", "urb", "rd", "open", "es")),
            InputRequirement(root_path("data", "最终数据", "省际经济地理嵌套矩阵_省会版.csv"), kind="csv"),
        ),
        expected_outputs=("outputs/回归分析/80_空间SDM主模型/*",),
        primary_csv=root_path("outputs", "回归分析", "80_空间SDM主模型", "主模型系数表.csv"),
        markdown_globs=("outputs/回归分析/80_空间SDM主模型/*.md",),
        description="优先尝试由 GUI 拉起 Stata 运行 SDM 主模型并回收结果。",
        notes=(
            "若 Stata 不可自动调用，可手动执行 .do 文件后回检。",
        ),
    ),
)


STEP_BY_ID = {step.id: step for step in STEP_DEFINITIONS}
