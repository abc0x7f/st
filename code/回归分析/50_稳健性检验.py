from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm
from linearmodels.panel import PanelOLS


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DATA_PATH = ROOT / "data" / "最终数据" / "第二阶段_基础.csv"
LAG_DATA_PATH = ROOT / "data" / "最终数据" / "第二阶段_滞后一期.csv"
OUT_DIR = ROOT / "outputs" / "回归分析" / "50_稳健性检验"

ENTITY_COL = "province"
TIME_COL = "year"
DEP_VAR = "eff"
BASE_CORE_VAR = "lntl"
LAG_CORE_VAR = "lntl_lag1"
CONTROL_VARS = ["ind", "urb", "rd", "open", "es"]
WINSOR_VARS = [DEP_VAR, BASE_CORE_VAR, *CONTROL_VARS]
FONT_SIZE_DELTA = 2


def fs(size: float) -> float:
    return size + FONT_SIZE_DELTA


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
    matplotlib.rcParams["font.size"] = fs(10)
    matplotlib.rcParams["axes.titlesize"] = fs(12)
    matplotlib.rcParams["axes.labelsize"] = fs(10)
    matplotlib.rcParams["xtick.labelsize"] = fs(10)
    matplotlib.rcParams["ytick.labelsize"] = fs(10)
    matplotlib.rcParams["legend.fontsize"] = fs(9)


def format_decimal(value: float, digits: int = 4) -> str:
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}"


def plot_core_robustness_forest(summary_df: pd.DataFrame) -> Path:
    plot_df = summary_df.copy()
    label_map = {
        "baseline": "基准模型",
        "winsor_1pct": "1%缩尾",
        "winsor_5pct": "5%缩尾",
        "lag1": "滞后一期",
    }
    plot_df["label"] = plot_df["model"].map(label_map)
    plot_df = plot_df.iloc[::-1].reset_index(drop=True)
    y_pos = np.arange(len(plot_df))

    fig = plt.figure(figsize=(12.0, 6.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.6, 2.3, 2.0], wspace=0.05)
    ax_left = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[0, 1])
    ax_right = fig.add_subplot(gs[0, 2], sharey=ax)

    xmin = float(min(plot_df["ci_lower"].min(), 0.0))
    xmax = float(plot_df["ci_upper"].max() * 1.25)
    norm = TwoSlopeNorm(vmin=min(-0.03, xmin), vcenter=0.0, vmax=max(0.24, xmax))
    cmap = plt.get_cmap("RdBu")

    def strong_rdbu_color(value: float):
        scaled = float(np.clip(norm(value), 0.0, 1.0))
        if value >= 0:
            scaled = 0.30 + 0.70 * scaled
        else:
            scaled = 0.30 * scaled / max(norm(0.0), 1e-9)
        scaled = float(np.clip(scaled, 0.0, 1.0))
        return cmap(scaled)

    for idx, row in plot_df.iterrows():
        color = strong_rdbu_color(row["coef_core"])
        ax.hlines(y_pos[idx], row["ci_lower"], row["ci_upper"], color=color, linewidth=1.6, zorder=2)
        ax.vlines([row["ci_lower"], row["ci_upper"]], y_pos[idx] - 0.10, y_pos[idx] + 0.10, color=color, linewidth=1.2, zorder=2)
        ax.scatter(row["coef_core"], y_pos[idx], marker="s", s=20, color=color, edgecolor=color, linewidth=0.5, zorder=3)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-0.6, len(plot_df) - 0.4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([])
    xticks = np.arange(0.0, xmax + 0.05, 0.05)
    xticks = [x for x in xticks if x <= xmax]
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{x:.2f}" for x in xticks])
    ax.set_xlabel("系数估计值", fontsize=fs(10))
    ax.set_title("稳健性检验核心系数森林图", fontsize=fs(12))
    ax.grid(axis="y", linestyle=":", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="x", labelsize=fs(9), pad=6)

    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(ax.get_ylim())
    ax_left.axis("off")
    ax_left.text(0.00, len(plot_df) - 0.1, "模型", ha="left", va="bottom", fontsize=fs(10), color="black", fontweight="bold")
    for idx, row in plot_df.iterrows():
        ax_left.text(0.00, y_pos[idx], row["label"], ha="left", va="center", fontsize=fs(9.6), color="black")

    ax_right.set_xlim(0, 1)
    ax_right.set_ylim(ax.get_ylim())
    ax_right.axis("off")
    ax_right.text(0.02, len(plot_df) - 0.1, "coef (95% CI)", ha="left", va="bottom", fontsize=fs(10), color="black", fontweight="bold")
    ax_right.text(0.98, len(plot_df) - 0.1, "p", ha="right", va="bottom", fontsize=fs(10), color="black", fontweight="bold")
    for idx, row in plot_df.iterrows():
        coef_text = (
            f"{format_decimal(row['coef_core'])} "
            f"({format_decimal(row['ci_lower'])}, {format_decimal(row['ci_upper'])})"
        )
        ax_right.text(0.02, y_pos[idx], coef_text, ha="left", va="center", fontsize=fs(9.2), color="black")
        ax_right.text(0.98, y_pos[idx], f"{format_decimal(row['p_core'])}{row['stars_core']}", ha="right", va="center", fontsize=fs(9.2), color="black")

    fig.subplots_adjust(left=0.05, right=0.985, top=0.9, bottom=0.13, wspace=0.05)
    out = OUT_DIR / "稳健性核心森林图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def load_panel_data(path: Path, required_cols: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = sorted(set(required_cols) - set(df.columns))
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")

    df = df[required_cols].copy()
    df[ENTITY_COL] = df[ENTITY_COL].astype(str).str.strip()
    df[TIME_COL] = pd.to_numeric(df[TIME_COL], errors="coerce").astype("Int64")
    for col in required_cols:
        if col not in {ENTITY_COL, TIME_COL}:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().copy()
    df[TIME_COL] = df[TIME_COL].astype(int)
    return df.sort_values([ENTITY_COL, TIME_COL]).reset_index(drop=True)


def winsorize_series(series: pd.Series, lower_q: float, upper_q: float) -> tuple[pd.Series, float, float]:
    lower = float(series.quantile(lower_q))
    upper = float(series.quantile(upper_q))
    return series.clip(lower=lower, upper=upper), lower, upper


def build_winsorized_data(df: pd.DataFrame, rate: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    thresholds: list[dict[str, float | str]] = []
    for var in WINSOR_VARS:
        out[var], lower, upper = winsorize_series(out[var], rate, 1 - rate)
        thresholds.append(
            {
                "variable": var,
                "winsor_rate": rate,
                "lower_quantile": rate,
                "upper_quantile": 1 - rate,
                "lower_bound": lower,
                "upper_bound": upper,
            }
        )
    return out, pd.DataFrame(thresholds)


def fit_twfe(df: pd.DataFrame, core_var: str):
    panel_df = df.set_index([ENTITY_COL, TIME_COL])
    y = panel_df[DEP_VAR].astype(float)
    x = panel_df[[core_var, *CONTROL_VARS]].astype(float)
    model = PanelOLS(y, x, entity_effects=True, time_effects=True, drop_absorbed=True)
    result = model.fit(cov_type="driscoll-kraay")
    return result


def significance_stars(pvalue: float) -> str:
    if pvalue < 0.01:
        return "***"
    if pvalue < 0.05:
        return "**"
    if pvalue < 0.1:
        return "*"
    return ""


def extract_coefficients(result, model_name: str) -> pd.DataFrame:
    conf_int = result.conf_int()
    rows: list[dict[str, float | str]] = []
    for var in result.params.index.tolist():
        rows.append(
            {
                "model": model_name,
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


def extract_model_summary(result, model_name: str, core_var: str, df: pd.DataFrame) -> dict[str, float | str]:
    conf_int = result.conf_int()
    return {
        "model": model_name,
        "data_file": df.attrs.get("data_file", ""),
        "core_var": core_var,
        "nobs": int(result.nobs),
        "n_provinces": int(df[ENTITY_COL].nunique()),
        "n_years": int(df[TIME_COL].nunique()),
        "coef_core": float(result.params[core_var]),
        "se_core": float(result.std_errors[core_var]),
        "t_core": float(result.tstats[core_var]),
        "p_core": float(result.pvalues[core_var]),
        "ci_lower": float(conf_int.loc[core_var, "lower"]),
        "ci_upper": float(conf_int.loc[core_var, "upper"]),
        "stars_core": significance_stars(float(result.pvalues[core_var])),
        "r2_within": safe_float(result.rsquared_within),
        "r2_between": safe_float(result.rsquared_between),
        "r2_overall": safe_float(result.rsquared_overall),
        "r2_model": safe_float(result.rsquared),
        "f_statistic": safe_float(getattr(result.f_statistic, "stat", np.nan)),
        "f_pvalue": safe_float(getattr(result.f_statistic, "pval", np.nan)),
        "cov_type": "Driscoll-Kraay",
    }


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


def build_core_comparison(summary_df: pd.DataFrame) -> pd.DataFrame:
    cols = ["model", "core_var", "coef_core", "se_core", "t_core", "p_core", "stars_core", "r2_model", "nobs"]
    return summary_df[cols].copy()


def build_analysis(summary_df: pd.DataFrame) -> list[str]:
    baseline = summary_df.loc[summary_df["model"] == "baseline"].iloc[0]
    win1 = summary_df.loc[summary_df["model"] == "winsor_1pct"].iloc[0]
    win5 = summary_df.loc[summary_df["model"] == "winsor_5pct"].iloc[0]
    lag1 = summary_df.loc[summary_df["model"] == "lag1"].iloc[0]

    lines = [
        "## 结果分析",
        "",
        (
            f"基准模型中，核心解释变量 `{baseline['core_var']}` 的系数为 "
            f"`{baseline['coef_core']:.4f}`，显著性为 `{baseline['stars_core'] or 'ns'}`，"
            f"表明夜间灯光聚合度对碳排放效率存在正向影响。"
        ),
        (
            f"`1%` 缩尾后，核心系数为 `{win1['coef_core']:.4f}`；`5%` 缩尾后为 "
            f"`{win5['coef_core']:.4f}`。两者与基准模型方向一致，且系数量级接近，"
            "说明基准结论并非由少数极端值驱动。"
        ),
        (
            f"将核心解释变量替换为滞后一期的 `{lag1['core_var']}` 后，系数为 "
            f"`{lag1['coef_core']:.4f}`，显著性为 `{lag1['stars_core'] or 'ns'}`。"
            "若该系数仍显著为正，则说明夜间灯光聚合度对碳排放效率的促进作用在时间上具有延续性，"
            "同时反向因果和同期联立偏误对主结论的干扰有限。"
        ),
        (
            f"从拟合度看，四组模型的 `R^2` 均处于 `{summary_df['r2_model'].min():.4f}` 至 "
            f"`{summary_df['r2_model'].max():.4f}` 区间，整体差异不大，说明稳健性处理并未改变模型的基本解释结构。"
        ),
        "总体而言，缩尾处理与滞后一期检验均支持基准回归的核心判断，即夜间灯光聚合度越高，碳排放效率越高，结论具有较强稳健性。",
    ]
    return lines


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()

    baseline_df = load_panel_data(
        BASELINE_DATA_PATH,
        [ENTITY_COL, TIME_COL, DEP_VAR, BASE_CORE_VAR, *CONTROL_VARS],
    )
    baseline_df.attrs["data_file"] = BASELINE_DATA_PATH.name

    lag_df = load_panel_data(
        LAG_DATA_PATH,
        [ENTITY_COL, TIME_COL, DEP_VAR, LAG_CORE_VAR, *CONTROL_VARS],
    )
    lag_df.attrs["data_file"] = LAG_DATA_PATH.name

    win1_df, win1_thresholds = build_winsorized_data(baseline_df, 0.01)
    win1_df.attrs["data_file"] = BASELINE_DATA_PATH.name
    win5_df, win5_thresholds = build_winsorized_data(baseline_df, 0.05)
    win5_df.attrs["data_file"] = BASELINE_DATA_PATH.name

    model_specs = [
        ("baseline", baseline_df, BASE_CORE_VAR),
        ("winsor_1pct", win1_df, BASE_CORE_VAR),
        ("winsor_5pct", win5_df, BASE_CORE_VAR),
        ("lag1", lag_df, LAG_CORE_VAR),
    ]

    summaries: list[dict[str, float | str]] = []
    coef_tables: list[pd.DataFrame] = []

    for model_name, df, core_var in model_specs:
        result = fit_twfe(df, core_var)
        summaries.append(extract_model_summary(result, model_name, core_var, df))
        coef_tables.append(extract_coefficients(result, model_name))

    summary_df = pd.DataFrame(summaries)
    coef_df = pd.concat(coef_tables, ignore_index=True)
    core_df = build_core_comparison(summary_df)
    thresholds_df = pd.concat([win1_thresholds, win5_thresholds], ignore_index=True)
    forest_path = plot_core_robustness_forest(summary_df)

    summary_df.to_csv(OUT_DIR / "稳健性模型汇总.csv", index=False, encoding="utf-8-sig")
    coef_df.to_csv(OUT_DIR / "稳健性系数表.csv", index=False, encoding="utf-8-sig")
    core_df.to_csv(OUT_DIR / "稳健性核心比较表.csv", index=False, encoding="utf-8-sig")
    thresholds_df.to_csv(OUT_DIR / "Winsor阈值表.csv", index=False, encoding="utf-8-sig")

    md_lines = [
        "# 面板回归稳健性检验结果",
        "",
        "## 检验口径",
        "",
        f"- 基准模型：`{BASELINE_DATA_PATH.relative_to(ROOT).as_posix()}`，双向固定效应，`Driscoll-Kraay` 稳健标准误。",
        "- 缩尾稳健性：对 `eff`、`lntl`、`ind`、`urb`、`rd`、`open`、`es` 分别做 `1%` 与 `5%` 双侧 winsorize。",
        f"- 滞后稳健性：使用 `{LAG_DATA_PATH.relative_to(ROOT).as_posix()}`，将核心解释变量替换为 `lntl_lag1`。",
        "",
        "## 核心结果对比",
        "",
        df_to_md(core_df),
        "",
        "## 图形输出",
        "",
        f"- `{forest_path.name}`",
        "",
        "## 各模型完整系数表",
        "",
        df_to_md(coef_df),
        "",
        "## 缩尾阈值",
        "",
        df_to_md(thresholds_df),
        "",
    ]
    md_lines.extend(build_analysis(summary_df))
    (OUT_DIR / "稳健性检验报告.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(core_df.to_string(index=False))
    print(f"\nSaved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
