from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import font_manager
from linearmodels.panel import PanelOLS


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "最终数据" / "第二阶段_基础.csv"
OUT_DIR = ROOT / "outputs" / "回归分析" / "60_异质性检验"

ENTITY_COL = "province"
TIME_COL = "year"
DEP_VAR = "eff"
CORE_VAR = "lntl"
CONTROL_VARS = ["ind", "urb", "rd", "open", "es"]

REGION_MAP = {
    "东部": ["北京", "天津", "河北", "上海", "江苏", "浙江", "福建", "山东", "广东", "海南"],
    "中部": ["山西", "安徽", "江西", "河南", "湖北", "湖南"],
    "西部": ["内蒙古", "广西", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"],
    "东北": ["辽宁", "吉林", "黑龙江"],
}


def configure_matplotlib() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif_candidates = ["Times New Roman", "Times New Roman PS MT", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC"]
    serif = next((name for name in serif_candidates if name in available), "DejaVu Serif")
    chinese = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = [serif, chinese]
    matplotlib.rcParams["font.serif"] = [serif]
    matplotlib.rcParams["font.sans-serif"] = [chinese]
    matplotlib.rcParams["axes.unicode_minus"] = False


def significance_stars(pvalue: float) -> str:
    if pvalue < 0.01:
        return "***"
    if pvalue < 0.05:
        return "**"
    if pvalue < 0.1:
        return "*"
    return ""


def format_decimal(value: float, digits: int = 4) -> str:
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}"


def format_numeric(value) -> str:
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return ""
        return f"{value:.4f}"
    return str(value)


def df_to_md(df: pd.DataFrame) -> str:
    headers = [str(col) for col in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(format_numeric(row[col]) for col in df.columns) + " |")
    return "\n".join(lines)


def load_panel_data() -> pd.DataFrame:
    required_cols = [ENTITY_COL, TIME_COL, DEP_VAR, CORE_VAR, *CONTROL_VARS]
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    missing = sorted(set(required_cols) - set(df.columns))
    if missing:
        raise ValueError(f"{DATA_PATH.name} missing columns: {missing}")

    df = df[required_cols].copy()
    df[ENTITY_COL] = df[ENTITY_COL].astype(str).str.strip()
    df[TIME_COL] = pd.to_numeric(df[TIME_COL], errors="coerce").astype("Int64")
    for col in [DEP_VAR, CORE_VAR, *CONTROL_VARS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().copy()
    df[TIME_COL] = df[TIME_COL].astype(int)

    province_to_region = {
        province: region
        for region, provinces in REGION_MAP.items()
        for province in provinces
    }
    df["region"] = df[ENTITY_COL].map(province_to_region)

    missing_region = sorted(df.loc[df["region"].isna(), ENTITY_COL].unique().tolist())
    if missing_region:
        raise ValueError(f"Unmapped provinces: {missing_region}")

    return df.sort_values(["region", ENTITY_COL, TIME_COL]).reset_index(drop=True)


def fit_twfe(df: pd.DataFrame):
    panel_df = df.set_index([ENTITY_COL, TIME_COL])
    y = panel_df[DEP_VAR].astype(float)
    x = panel_df[[CORE_VAR, *CONTROL_VARS]].astype(float)
    model = PanelOLS(y, x, entity_effects=True, time_effects=True, drop_absorbed=True)
    return model.fit(cov_type="driscoll-kraay")


def extract_coefficients(result, region: str) -> pd.DataFrame:
    conf_int = result.conf_int()
    rows: list[dict[str, float | str]] = []
    for var in result.params.index.tolist():
        rows.append(
            {
                "region": region,
                "variable": var,
                "coef": float(result.params[var]),
                "std_err": float(result.std_errors[var]),
                "t_stat": float(result.tstats[var]),
                "p_value": float(result.pvalues[var]),
                "ci_lower": float(conf_int.loc[var, "lower"]),
                "ci_upper": float(conf_int.loc[var, "upper"]),
                "stars": significance_stars(float(result.pvalues[var])),
            }
        )
    return pd.DataFrame(rows)


def safe_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def extract_summary(result, region: str, df: pd.DataFrame) -> dict[str, float | str]:
    conf_int = result.conf_int()
    return {
        "region": region,
        "nobs": int(result.nobs),
        "n_provinces": int(df[ENTITY_COL].nunique()),
        "n_years": int(df[TIME_COL].nunique()),
        "coef_core": float(result.params[CORE_VAR]),
        "se_core": float(result.std_errors[CORE_VAR]),
        "t_core": float(result.tstats[CORE_VAR]),
        "p_core": float(result.pvalues[CORE_VAR]),
        "ci_lower": float(conf_int.loc[CORE_VAR, "lower"]),
        "ci_upper": float(conf_int.loc[CORE_VAR, "upper"]),
        "stars_core": significance_stars(float(result.pvalues[CORE_VAR])),
        "r2_within": safe_float(result.rsquared_within),
        "r2_between": safe_float(result.rsquared_between),
        "r2_overall": safe_float(result.rsquared_overall),
        "r2_model": safe_float(result.rsquared),
        "f_statistic": safe_float(getattr(result.f_statistic, "stat", np.nan)),
        "f_pvalue": safe_float(getattr(result.f_statistic, "pval", np.nan)),
        "cov_type": "Driscoll-Kraay",
    }


def build_core_table(summary_df: pd.DataFrame) -> pd.DataFrame:
    out = summary_df[
        [
            "region",
            "coef_core",
            "se_core",
            "t_core",
            "p_core",
            "ci_lower",
            "ci_upper",
            "stars_core",
            "nobs",
            "n_provinces",
            "n_years",
            "r2_model",
            "cov_type",
        ]
    ].copy()
    out = out.rename(
        columns={
            "coef_core": "lntl_coef",
            "se_core": "lntl_se",
            "t_core": "lntl_t",
            "p_core": "lntl_p",
            "ci_lower": "lntl_ci_lower",
            "ci_upper": "lntl_ci_upper",
            "stars_core": "lntl_stars",
        }
    )
    return out


def build_field_explanations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["region", "地区分组", "东部、中部、西部、东北"],
            ["variable", "回归变量名", "核心解释变量与控制变量名称"],
            ["coef", "系数估计值", "变量每增加1单位对eff的边际影响方向和大小"],
            ["std_err", "标准误", "Driscoll-Kraay稳健标准误"],
            ["t_stat", "t统计量", "用于检验系数是否显著偏离0"],
            ["p_value", "P值", "常用阈值为0.01、0.05、0.10"],
            ["ci_lower", "95%置信区间下限", "系数可能取值范围下界"],
            ["ci_upper", "95%置信区间上限", "系数可能取值范围上界"],
            ["stars", "显著性星号", "*** p<0.01, ** p<0.05, * p<0.10"],
            ["nobs", "样本量", "地区组内省份数乘以年份数后的有效观测值"],
            ["n_provinces", "省份数", "该地区参与回归的省份数量"],
            ["n_years", "年份数", "该地区参与回归的年份数量"],
            ["r2_model", "模型R²", "模型整体拟合度"],
            ["cov_type", "协方差估计方法", "这里固定为Driscoll-Kraay"],
        ],
        columns=["field", "meaning", "interpretation"],
    )


def build_analysis(summary_df: pd.DataFrame) -> list[str]:
    ordered = summary_df.sort_values("coef_core", ascending=False).reset_index(drop=True)
    sig_df = summary_df.loc[summary_df["p_core"] < 0.1].copy()
    strongest = ordered.iloc[0]
    weakest = ordered.iloc[-1]

    lines = [
        "## 结果分析",
        "",
        (
            f"四大区域中，`lntl` 系数绝对值和方向存在明显差异。按系数大小排序，依次为"
            f" `{ordered.iloc[0]['region']}`（{ordered.iloc[0]['coef_core']:.4f}）、"
            f"`{ordered.iloc[1]['region']}`（{ordered.iloc[1]['coef_core']:.4f}）、"
            f"`{ordered.iloc[2]['region']}`（{ordered.iloc[2]['coef_core']:.4f}）、"
            f"`{ordered.iloc[3]['region']}`（{ordered.iloc[3]['coef_core']:.4f}）。"
        ),
        (
            f"其中，影响最强的是 `{strongest['region']}`，最弱的是 `{weakest['region']}`。"
            "如果同为正值，说明夜间灯光集聚度对绿色经济效率的促进作用主要体现为强弱差异；"
            "如果存在负值，则说明部分区域可能存在扩张型增长对绿色效率的挤出。"
        ),
    ]

    if sig_df.empty:
        lines.append(
            "四个地区中，`lntl` 在 10% 水平下均未达到显著，这说明分组后样本缩小明显，"
            "异质性更多体现为系数方向和量级差异，而不是统计显著差异。"
        )
    else:
        sig_items = "、".join(
            f"`{row.region}`（coef={row.coef_core:.4f}, p={row.p_core:.4f}{row.stars_core}）"
            for row in sig_df.itertuples()
        )
        nonsig = summary_df.loc[summary_df["p_core"] >= 0.1, "region"].tolist()
        lines.append(f"在显著性上，达到 10% 水平的地区为：{sig_items}。")
        if nonsig:
            lines.append(
                "其余地区未通过常用显著性阈值，分别为："
                + "、".join(f"`{name}`" for name in nonsig)
                + "。这通常与组内样本量下降、区域内部差异较大有关。"
            )

    northeast = summary_df.loc[summary_df["region"] == "东北"].iloc[0]
    if int(northeast["n_provinces"]) <= 3:
        lines.append(
            "需要单独说明的是，东北地区仅含 3 个省份，组内有效样本量最小。即便系数方向具有解释意义，"
            "其显著性也更容易受到标准误偏大的影响，因此应避免仅凭显著与否作过度结论。"
        )

    lines.append(
        "从论文写作角度，正文应优先比较 `lntl` 的系数方向、大小和显著性，再结合东中西东北在"
        "经济基础、产业结构、创新投入、能源结构和开放水平上的差异解释区域异质性。"
    )
    return lines


def save_report(
    core_df: pd.DataFrame,
    coef_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    field_df: pd.DataFrame,
) -> None:
    report_lines = [
        "# 四大区域异质性回归结果",
        "",
        "## 模型设定",
        "",
        "```text",
        "PanelOLS: eff ~ lntl + ind + urb + rd + open + es",
        "Effects: Entity + Time",
        "Covariance: Driscoll-Kraay",
        "Sample split: 东部 / 中部 / 西部 / 东北",
        "```",
        "",
        "## 核心结果表",
        "",
        df_to_md(core_df),
        "",
        "## 输出字段解释",
        "",
        df_to_md(field_df),
        "",
        "## 分地区完整系数表",
        "",
        df_to_md(coef_df),
        "",
        "## 分地区模型摘要",
        "",
        df_to_md(summary_df),
        "",
    ]
    report_lines.extend(build_analysis(summary_df))
    (OUT_DIR / "异质性检验报告.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()
    df = load_panel_data()

    summary_rows: list[dict[str, float | str]] = []
    coef_tables: list[pd.DataFrame] = []

    for region in ["东部", "中部", "西部", "东北"]:
        region_df = df.loc[df["region"] == region].copy()
        result = fit_twfe(region_df)
        summary_rows.append(extract_summary(result, region, region_df))
        coef_tables.append(extract_coefficients(result, region))

    summary_df = pd.DataFrame(summary_rows)
    coef_df = pd.concat(coef_tables, ignore_index=True)
    core_df = build_core_table(summary_df)
    field_df = build_field_explanations()

    core_df.to_csv(OUT_DIR / "异质性核心结果表.csv", index=False, encoding="utf-8-sig")
    coef_df.to_csv(OUT_DIR / "异质性系数表.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(OUT_DIR / "异质性模型汇总.csv", index=False, encoding="utf-8-sig")
    field_df.to_csv(OUT_DIR / "异质性字段解释.csv", index=False, encoding="utf-8-sig")
    save_report(core_df, coef_df, summary_df, field_df)

    print(core_df.to_string(index=False))
    print(f"\nSaved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
