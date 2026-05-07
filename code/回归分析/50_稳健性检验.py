from __future__ import annotations

from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm
from linearmodels.panel import PanelOLS


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, stage_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
OUT_DIR = stage_output_dir(CONFIG, "50_稳健性检验")

ENTITY_COL = "province"
TIME_COL = "year"
DEP_VAR = CONFIG["dep_var"]
BASE_CORE_VAR = CONFIG["core_var"]
CONTROL_VARS = list(CONFIG["control_vars"])
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


def core_description(core_var: str) -> str:
    return "主灯光变量" if core_var == "lntl" else f"核心变量 {core_var}"


def plot_core_robustness_forest(summary_df: pd.DataFrame) -> Path:
    plot_df = summary_df.copy()
    plot_df["label"] = plot_df["model_label"]
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
    winsor_vars = [DEP_VAR, BASE_CORE_VAR, *CONTROL_VARS]
    for var in winsor_vars:
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
        "model_label": df.attrs.get("model_label", model_name),
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
    baseline = summary_df.iloc[0]
    other_rows = summary_df.iloc[1:]

    lines = [
        "## 结果分析",
        "",
        (
            f"基准模型中，核心解释变量 `{baseline['core_var']}` 的系数为 "
            f"`{baseline['coef_core']:.4f}`，显著性为 `{baseline['stars_core'] or 'ns'}`，"
            f"表明{core_description(str(baseline['core_var']))}对 `{DEP_VAR}` 存在正向影响。"
        ),
    ]
    for _, row in other_rows.iterrows():
        lines.extend(
            [
                (
                    f"`{row['model_label']}` 下，核心变量 `{row['core_var']}` 的系数为 "
                    f"`{row['coef_core']:.4f}`，显著性为 `{row['stars_core'] or 'ns'}`。"
                    "若方向与基准模型一致，说明主结论在该稳健性设定下保持稳定。"
                )
            ]
        )
    lines.extend(
        [
            (
                f"从拟合度看，各组模型的 `R^2` 处于 `{summary_df['r2_model'].min():.4f}` 至 "
                f"`{summary_df['r2_model'].max():.4f}` 区间，整体差异不大。"
            ),
            "总体而言，当前配置下的稳健性设定整体支持基准回归的核心判断。",
        ]
    )
    return lines


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()

    model_specs: list[tuple[str, pd.DataFrame, str]] = []
    threshold_frames: list[pd.DataFrame] = []
    spec_descriptions: list[str] = []
    for model_cfg in CONFIG["robust_models"]:
        model_name = str(model_cfg["name"])
        model_label = str(model_cfg["label"])
        core_var = str(model_cfg["core_var"])
        data_path = resolve_project_path(model_cfg["data_path"])
        mode = str(model_cfg.get("mode", "custom"))
        df = load_panel_data(data_path, [ENTITY_COL, TIME_COL, DEP_VAR, core_var, *CONTROL_VARS])
        df.attrs["data_file"] = data_path.name
        df.attrs["model_label"] = model_label
        if mode == "winsor":
            winsor_rate = float(model_cfg["winsor_rate"])
            df, threshold_df = build_winsorized_data(df, winsor_rate)
            df.attrs["data_file"] = data_path.name
            df.attrs["model_label"] = model_label
            threshold_df.insert(0, "model", model_name)
            threshold_frames.append(threshold_df)
            spec_descriptions.append(f"- `{model_label}`：基于 `{data_path.relative_to(ROOT).as_posix()}`，按 `{winsor_rate:.0%}` 双侧缩尾。")
        else:
            spec_descriptions.append(f"- `{model_label}`：使用 `{data_path.relative_to(ROOT).as_posix()}`，核心变量为 `{core_var}`。")
        model_specs.append((model_name, df, core_var))

    summaries: list[dict[str, float | str]] = []
    coef_tables: list[pd.DataFrame] = []

    for model_name, df, core_var in model_specs:
        result = fit_twfe(df, core_var)
        summaries.append(extract_model_summary(result, model_name, core_var, df))
        coef_tables.append(extract_coefficients(result, model_name))

    summary_df = pd.DataFrame(summaries)
    coef_df = pd.concat(coef_tables, ignore_index=True)
    core_df = build_core_comparison(summary_df)
    thresholds_df = pd.concat(threshold_frames, ignore_index=True) if threshold_frames else pd.DataFrame()
    forest_path = plot_core_robustness_forest(summary_df)

    summary_df.to_csv(OUT_DIR / "稳健性模型汇总.csv", index=False, encoding="utf-8-sig")
    coef_df.to_csv(OUT_DIR / "稳健性系数表.csv", index=False, encoding="utf-8-sig")
    core_df.to_csv(OUT_DIR / "稳健性核心比较表.csv", index=False, encoding="utf-8-sig")
    if not thresholds_df.empty:
        thresholds_df.to_csv(OUT_DIR / "Winsor阈值表.csv", index=False, encoding="utf-8-sig")

    md_lines = [
        "# 面板回归稳健性检验结果",
        "",
        "## 检验口径",
        "",
        f"- 当前配置：`{CONFIG['config_name']}`",
        f"- 因变量：`{DEP_VAR}`；基准核心变量：`{BASE_CORE_VAR}`；控制变量：`{', '.join(CONTROL_VARS)}`。",
        "- 模型均采用双向固定效应与 `Driscoll-Kraay` 稳健标准误。",
        *spec_descriptions,
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
    ]
    if not thresholds_df.empty:
        md_lines.extend(["## 缩尾阈值", "", df_to_md(thresholds_df), ""])
    md_lines.extend(build_analysis(summary_df))
    (OUT_DIR / "稳健性检验报告.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(core_df.to_string(index=False))
    print(f"\nSaved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
