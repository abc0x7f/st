from __future__ import annotations

import sys
from pathlib import Path

from stage_config import derived_dearun_result_dir, load_stage_config, resolve_project_path
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


def open_path_command(target_path: str) -> tuple[str, ...]:
    return ("open-path", target_path)


def _step_output(stage_output_root: Path, folder_name: str) -> Path:
    return stage_output_root / folder_name


def build_step_definitions() -> tuple[StepDefinition, ...]:
    data_cfg = load_stage_config("数据处理")
    eff_cfg = load_stage_config("效率测算")
    reg_cfg = load_stage_config("回归分析")
    spatial_cfg = load_stage_config("空间分析")

    data_output_root = resolve_project_path(data_cfg["output_root"])
    eff_output_root = resolve_project_path(eff_cfg["output_root"])
    reg_output_root = resolve_project_path(reg_cfg["output_root"])
    spatial_output_root = resolve_project_path(spatial_cfg["output_root"])

    first_stage_panel = resolve_project_path(data_cfg["first_stage_panel"])
    second_stage_panel = resolve_project_path(data_cfg["second_stage_panel"])
    efficiency_output = resolve_project_path(eff_cfg["efficiency_extract_output"])
    dearun_result_dir = derived_dearun_result_dir(eff_cfg)

    reg_panel_path = resolve_project_path(reg_cfg["panel_data"])
    spatial_efficiency_path = resolve_project_path(spatial_cfg["efficiency_data"])
    spatial_second_panel = resolve_project_path(spatial_cfg["second_stage_panel"])

    return (
        StepDefinition(
            id="data_sample",
            name="样本构建流程与缺失检查",
            stage="数据处理",
            runner_type=RunnerType.PYTHON,
            command=py_command("code/数据处理/50_样本构建流程缺失检查与变量箱线图.py"),
            working_dir=PROJECT_ROOT,
            precheck_mode="none",
            expected_outputs=(
                str((_step_output(data_output_root, "50_样本构建流程缺失检查与变量箱线图") / "图5_变量缺失热力图.png").relative_to(PROJECT_ROOT)),
            ),
            image_globs=(
                str((_step_output(data_output_root, "50_样本构建流程缺失检查与变量箱线图") / "图5_变量缺失热力图.png").relative_to(PROJECT_ROOT)),
            ),
            description="输出样本缺失热力图。",
        ),
        StepDefinition(
            id="data_energy",
            name="构建省级能源总量与折标系数",
            stage="数据处理",
            runner_type=RunnerType.PYTHON,
            command=py_command("code/数据处理/10_构建省级能源总量与折标系数.py"),
            working_dir=PROJECT_ROOT,
            precheck_mode="none",
            required_inputs=(
                InputRequirement(resolve_project_path(data_cfg["energy_ceads_dir"]), kind="directory"),
            ),
            expected_outputs=(
                str(resolve_project_path(data_cfg["energy_panel_output"]).relative_to(PROJECT_ROOT)),
            ),
            primary_csv=resolve_project_path(data_cfg["energy_panel_output"]),
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
                InputRequirement(second_stage_panel, kind="csv", required_columns=("province", "year", "lntl")),
                InputRequirement(resolve_project_path(data_cfg["map_geojson_paths"][0]), kind="file"),
            ),
            expected_outputs=(str((_step_output(data_output_root, "20_夜间灯光指标检查") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(data_output_root, "20_夜间灯光指标检查") / "夜间灯光检查数据.csv",
            image_globs=(str((_step_output(data_output_root, "20_夜间灯光指标检查") / "*.png").relative_to(PROJECT_ROOT)),),
            markdown_globs=(str((_step_output(data_output_root, "20_夜间灯光指标检查") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(first_stage_panel, kind="csv", required_columns=("province", "year")),),
            expected_outputs=(str((_step_output(data_output_root, "30_投入产出关系预检") / "*.png").relative_to(PROJECT_ROOT)),),
            image_globs=(str((_step_output(data_output_root, "30_投入产出关系预检") / "*.png").relative_to(PROJECT_ROOT)),),
            description="在效率测算前检查投入产出变量关系是否异常。",
        ),
        StepDefinition(
            id="dearun_manual",
            name="Dearun 效率测算结果回填",
            stage="效率测算",
            runner_type=RunnerType.MANUAL,
            command=open_path_command(r"C:\Program Files (x86)\Dearun"),
            working_dir=PROJECT_ROOT,
            precheck_mode="manual_result",
            required_inputs=(
                InputRequirement(dearun_result_dir, kind="directory", label="Dearun 输出目录"),
            ),
            expected_outputs=(
                str((dearun_result_dir.relative_to(PROJECT_ROOT) / "**/*规模报酬可变VRS_0.xlsx").as_posix()),
                str((dearun_result_dir.relative_to(PROJECT_ROOT) / "**/*规模报酬不变CRS_0.xlsx").as_posix()),
            ),
            description=f"该步骤需人工运行 Dearun，并将结果文件放回 {dearun_result_dir.relative_to(PROJECT_ROOT)}。",
            notes=(
                "请先在 Dearun 中完成 SBM / GM 测算。",
                "结果目录按当前输入文件自动推导为 结果_<文件名>。",
                "点击“执行”可自动打开 Dearun 安装目录。",
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
            required_inputs=(InputRequirement(dearun_result_dir, kind="directory"),),
            expected_outputs=(str(efficiency_output.relative_to(PROJECT_ROOT)),),
            primary_csv=efficiency_output,
            description=f"从 {dearun_result_dir.relative_to(PROJECT_ROOT)} 提取年度省级效率结果。",
        ),
        StepDefinition(
            id="eff_plot",
            name="碳排放效率绘图",
            stage="效率测算",
            runner_type=RunnerType.PYTHON,
            command=py_command("code/效率测算/20_碳排放效率绘图.py"),
            working_dir=PROJECT_ROOT,
            precheck_mode="required_inputs",
            required_inputs=(InputRequirement(efficiency_output, kind="csv", required_columns=("year", "province", "eff")),),
            expected_outputs=(str((_step_output(eff_output_root, "10_碳排放效率绘图") / "*").relative_to(PROJECT_ROOT)),),
            image_globs=(str((_step_output(eff_output_root, "10_碳排放效率绘图") / "*.png").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(resolve_project_path(eff_cfg["second_stage_panel"]), kind="csv", required_columns=("province", "year", "eff", "lntl")),),
            expected_outputs=(str((_step_output(eff_output_root, "10_碳排放效率绘图") / "*对比排序图.png").relative_to(PROJECT_ROOT)),),
            image_globs=(str((_step_output(eff_output_root, "10_碳排放效率绘图") / "*对比排序图.png").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(dearun_result_dir, kind="directory"),),
            expected_outputs=(str((_step_output(eff_output_root, "20_GM分解绘图") / "*").relative_to(PROJECT_ROOT)),),
            image_globs=(str((_step_output(eff_output_root, "20_GM分解绘图") / "*.png").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("eff", "lntl", "ind", "urb", "rd", "open", "es")),),
            expected_outputs=(str((_step_output(reg_output_root, "10_相关性与VIF分析") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "10_相关性与VIF分析") / "皮尔逊相关系数矩阵.csv",
            image_globs=(str((_step_output(reg_output_root, "10_相关性与VIF分析") / "*.png").relative_to(PROJECT_ROOT)),),
            markdown_globs=(str((_step_output(reg_output_root, "10_相关性与VIF分析") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("eff", "lntl")),),
            expected_outputs=(str((_step_output(reg_output_root, "20_模型设定检验") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "20_模型设定检验") / "模型设定检验结果.csv",
            markdown_globs=(str((_step_output(reg_output_root, "20_模型设定检验") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("province", "year", "eff")),),
            expected_outputs=(str((_step_output(reg_output_root, "30_面板单位根检验") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "30_面板单位根检验") / "面板单位根汇总表.csv",
            markdown_globs=(str((_step_output(reg_output_root, "30_面板单位根检验") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("province", "year", "eff", "lntl")),),
            expected_outputs=(str((_step_output(reg_output_root, "40_基准面板回归诊断") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "40_基准面板回归诊断") / "基准回归系数表.csv",
            image_globs=(str((_step_output(reg_output_root, "40_基准面板回归诊断") / "*.png").relative_to(PROJECT_ROOT)),),
            markdown_globs=(str((_step_output(reg_output_root, "40_基准面板回归诊断") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("province", "year", "eff")),),
            expected_outputs=(str((_step_output(reg_output_root, "50_稳健性检验") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "50_稳健性检验") / "稳健性核心比较表.csv",
            image_globs=(str((_step_output(reg_output_root, "50_稳健性检验") / "*.png").relative_to(PROJECT_ROOT)),),
            markdown_globs=(str((_step_output(reg_output_root, "50_稳健性检验") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(reg_panel_path, kind="csv", required_columns=("province", "year", "eff")),),
            expected_outputs=(str((_step_output(reg_output_root, "60_异质性检验") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(reg_output_root, "60_异质性检验") / "异质性核心结果表.csv",
            markdown_globs=(str((_step_output(reg_output_root, "60_异质性检验") / "*.md").relative_to(PROJECT_ROOT)),),
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
            required_inputs=(InputRequirement(spatial_efficiency_path, kind="csv", required_columns=("province",)),),
            expected_outputs=(str(resolve_project_path(spatial_cfg["adjacency_matrix"]).relative_to(PROJECT_ROOT)),),
            primary_csv=resolve_project_path(spatial_cfg["adjacency_matrix"]),
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
            required_inputs=(InputRequirement(spatial_second_panel, kind="csv", required_columns=("province",)),),
            expected_outputs=(
                str(resolve_project_path(spatial_cfg["capital_output"]).relative_to(PROJECT_ROOT)),
                str(resolve_project_path(spatial_cfg["geo_inverse_output"]).relative_to(PROJECT_ROOT)),
                str(resolve_project_path(spatial_cfg["economic_geo_nested_output"]).relative_to(PROJECT_ROOT)),
            ),
            primary_csv=resolve_project_path(spatial_cfg["capital_output"]),
            description="生成省会坐标表与地理/嵌套空间矩阵。",
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
                InputRequirement(spatial_efficiency_path, kind="csv", required_columns=("year", "province", "eff")),
                InputRequirement(resolve_project_path(spatial_cfg["economic_matrix"]), kind="csv"),
                InputRequirement(resolve_project_path(spatial_cfg["province_geojson"]), kind="file"),
            ),
            expected_outputs=(str((_step_output(spatial_output_root, "20_莫兰指数与LISA分析") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(spatial_output_root, "20_莫兰指数与LISA分析") / "全局莫兰指数_2015_2022.csv",
            image_globs=(str((_step_output(spatial_output_root, "20_莫兰指数与LISA分析") / "*.png").relative_to(PROJECT_ROOT)),),
            markdown_globs=(str((_step_output(spatial_output_root, "20_莫兰指数与LISA分析") / "*.md").relative_to(PROJECT_ROOT)),),
            description="输出全局莫兰指数、LISA 聚类图和结果说明。",
        ),
        StepDefinition(
            id="reg_spatial_weight_stata",
            name="空间权重矩阵检验（Stata）",
            stage="空间分析",
            runner_type=RunnerType.HYBRID,
            command=stata_command("code/空间分析/30_空间权重矩阵检验.do"),
            working_dir=PROJECT_ROOT,
            precheck_mode="required_inputs",
            required_inputs=(
                InputRequirement(spatial_second_panel, kind="csv", required_columns=("province", "year", "eff")),
                InputRequirement(resolve_project_path(spatial_cfg["geo_inverse_matrix"]), kind="csv"),
            ),
            expected_outputs=(str((_step_output(spatial_output_root, "30_空间权重矩阵检验") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(spatial_output_root, "30_空间权重矩阵检验") / "LR检验结果.csv",
            markdown_globs=(str((_step_output(spatial_output_root, "30_空间权重矩阵检验") / "*.md").relative_to(PROJECT_ROOT)),),
            description="优先尝试由 GUI 拉起 Stata；若不可用，则提示手动执行并回检。",
            notes=(
                "若 GUI 未找到 Stata，可手动运行 .do 文件。",
                "运行完成后点击“检查”刷新结果状态。",
            ),
        ),
        StepDefinition(
            id="reg_sdm_stata",
            name="空间 SDM 主模型（Stata）",
            stage="空间分析",
            runner_type=RunnerType.HYBRID,
            command=stata_command("code/空间分析/40_空间SDM主模型.do"),
            working_dir=PROJECT_ROOT,
            precheck_mode="required_inputs",
            required_inputs=(
                InputRequirement(spatial_second_panel, kind="csv", required_columns=("province", "year", "eff", "lntl", "ind", "urb", "rd", "open", "es")),
                InputRequirement(resolve_project_path(spatial_cfg["economic_geo_nested_matrix"]), kind="csv"),
            ),
            expected_outputs=(str((_step_output(spatial_output_root, "40_空间SDM主模型") / "*").relative_to(PROJECT_ROOT)),),
            primary_csv=_step_output(spatial_output_root, "40_空间SDM主模型") / "主模型系数表.csv",
            markdown_globs=(str((_step_output(spatial_output_root, "40_空间SDM主模型") / "*.md").relative_to(PROJECT_ROOT)),),
            description="优先尝试由 GUI 拉起 Stata 运行 SDM 主模型并回收结果。",
            notes=("若 Stata 不可自动调用，可手动执行 .do 文件后回检。",),
        ),
    )


def build_step_map() -> dict[str, StepDefinition]:
    steps = build_step_definitions()
    return {step.id: step for step in steps}
