from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm
from linearmodels.panel import PanelOLS
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "prcd" / "process2.csv"
OUT_DIR = ROOT / "prcd" / "baseline_panel_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEP_VAR = "eff"
CORE_VAR = "lntl"
CONTROL_VARS = ["ind", "urb", "rd", "open", "es"]
MODEL_FORMULA = "eff ~ lntl + ind + urb + rd + open + es + C(province) + C(year)"


def resolve_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    try:
        with open(path, "a", encoding="utf-8"):
            return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_latest{path.suffix}")
        return fallback


def format_decimal(value: float, digits: int = 4) -> str:
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}"


def configure_matplotlib() -> None:
    sns.set_theme(style="whitegrid")
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif_candidates = ["Times New Roman", "Times New Roman PS MT", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC"]
    serif = next((name for name in serif_candidates if name in available), "DejaVu Serif")
    chinese = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = [serif, chinese]
    matplotlib.rcParams["font.serif"] = [serif]
    matplotlib.rcParams["font.sans-serif"] = [chinese]
    matplotlib.rcParams["axes.unicode_minus"] = False


def get_year_color_map(years: list[int]) -> dict[int, tuple[float, float, float, float]]:
    cmap = plt.get_cmap("gist_earth")
    values = np.linspace(0.85, 0.15, len(years))
    return {year: cmap(v) for year, v in zip(years, values)}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    cols = ["province", "year", DEP_VAR, CORE_VAR, *CONTROL_VARS]
    missing = sorted(set(cols) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df[cols].copy()
    df["province"] = df["province"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    for col in [DEP_VAR, CORE_VAR, *CONTROL_VARS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().copy()
    df["year"] = df["year"].astype(int)
    return df.sort_values(["year", "province"]).reset_index(drop=True)


def fit_model(df: pd.DataFrame):
    panel_df = df.set_index(["province", "year"])
    y = panel_df[DEP_VAR].astype(float)
    x = panel_df[[CORE_VAR, *CONTROL_VARS]].astype(float)
    model = PanelOLS(y, x, entity_effects=True, time_effects=True, drop_absorbed=True)
    result = model.fit(cov_type="driscoll-kraay")

    out = df.copy()
    out["fitted"] = df[DEP_VAR].to_numpy() - result.resids.to_numpy()
    out["resid"] = result.resids.to_numpy()
    out["std_resid"] = (out["resid"] - out["resid"].mean()) / out["resid"].std(ddof=1)
    return result, out


def fit_auxiliary_residuals(df: pd.DataFrame, target_var: str) -> pd.Series:
    panel_df = df.set_index(["province", "year"])
    y = panel_df[target_var].astype(float)
    x = panel_df[CONTROL_VARS].astype(float)
    aux_model = PanelOLS(y, x, entity_effects=True, time_effects=True, drop_absorbed=True)
    aux_result = aux_model.fit(cov_type="driscoll-kraay")
    return aux_result.resids


def build_regression_table(result) -> pd.DataFrame:
    coef = result.params
    conf = result.conf_int()
    return pd.DataFrame(
        {
            "variable": coef.index,
            "coef": coef.values,
            "std_err": result.std_errors.values,
            "t_value": result.tstats.values,
            "p_value": result.pvalues.values,
            "ci_lower": conf["lower"].values,
            "ci_upper": conf["upper"].values,
        }
    )


def build_summary_table(result, df: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "metric": [
                "nobs",
                "n_provinces",
                "n_years",
                "r_squared",
                "r_squared_within",
                "r_squared_between",
                "r_squared_overall",
                "f_statistic",
                "f_pvalue",
                "f_statistic_robust",
                "f_pvalue_robust",
                "poolability_f_statistic",
                "poolability_f_pvalue",
                "n_parameters",
                "cov_estimator",
            ],
            "value": [
                float(result.nobs),
                float(df["province"].nunique()),
                float(df["year"].nunique()),
                float(result.rsquared),
                float(result.rsquared_within),
                float(result.rsquared_between),
                float(result.rsquared_overall),
                float(result.f_statistic.stat) if result.f_statistic is not None else np.nan,
                float(result.f_statistic.pval) if result.f_statistic is not None else np.nan,
                float(result.f_statistic_robust.stat) if result.f_statistic_robust is not None else np.nan,
                float(result.f_statistic_robust.pval) if result.f_statistic_robust is not None else np.nan,
                float(result.f_pooled.stat) if result.f_pooled is not None else np.nan,
                float(result.f_pooled.pval) if result.f_pooled is not None else np.nan,
                float(len(result.params)),
                "Driscoll-Kraay",
            ],
        }
    )
    return summary


def prepare_ordered_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[int]]:
    first_year = int(df["year"].min())
    province_order = (
        df.loc[df["year"] == first_year, ["province", DEP_VAR]]
        .sort_values([DEP_VAR, "province"])["province"]
        .tolist()
    )
    province_rank = {province: idx for idx, province in enumerate(province_order)}
    years = sorted(df["year"].unique())
    year_rank = {year: idx for idx, year in enumerate(years)}

    ordered = (
        df.assign(
            province_rank=df["province"].map(province_rank),
            year_rank=df["year"].map(year_rank),
        )
        .sort_values(["year_rank", "province_rank", "province", "year"])
        .reset_index(drop=True)
    )
    ordered["sample_index"] = np.arange(1, len(ordered) + 1)
    return ordered, province_order, years


def plot_lntl_eff_scatter(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique())
    year_color_map = get_year_color_map(years)

    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    for year in years:
        part = df.loc[df["year"] == year]
        ax.scatter(
            part[CORE_VAR],
            part[DEP_VAR],
            s=40,
            color=year_color_map[year],
            alpha=0.8,
            edgecolor="white",
            linewidth=0.5,
            label=str(year),
        )

    x = df[CORE_VAR].to_numpy()
    y = df[DEP_VAR].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min(), min(3.0, x.max()), 200)
    y_line = intercept + slope * x_line
    ax.plot(x_line, y_line, color="#1F2933", linewidth=2.2, label="线性拟合")

    ax.set_title("lntl 与 eff 散点拟合图")
    ax.set_xlabel("lntl")
    ax.set_ylabel("eff")
    ax.set_xlim(right=3.0)
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()
    out = OUT_DIR / "01_lntl_eff_scatter_fit.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_true_vs_pred_sequence(df: pd.DataFrame) -> Path:
    ordered, _, years = prepare_ordered_frame(df)
    cmap = plt.get_cmap("RdYlGn", 450)

    fig, ax = plt.subplots(figsize=(14.5, 6.8))
    for year_idx, year in enumerate(years):
        part = ordered.loc[ordered["year"] == year].sort_values("sample_index")
        x = part["sample_index"].to_numpy()
        y = part[DEP_VAR].to_numpy()
        start = year_idx * 60
        point_colors = [cmap(start + offset) for offset in range(len(part))]
        ax.scatter(
            x,
            y,
            c=point_colors,
            s=24,
            edgecolor="white",
            linewidth=0.35,
            zorder=3,
            label="真实eff值" if year_idx == 0 else None,
        )

    ax.plot(
        ordered["sample_index"],
        ordered["fitted"],
        color="#4B5563",
        linewidth=1.1,
        marker="s",
        markersize=3.3,
        label="预测eff值",
        zorder=4,
    )

    ax.set_title("真实 eff 与预测 eff 序列图")
    ax.set_xlabel("样本序号")
    ax.set_ylabel("eff")
    ax.set_xlim(0, 240)
    major_ticks = np.arange(0, 241, 30)
    ax.set_xticks(major_ticks)
    ax.set_xticklabels([str(v) for v in major_ticks])
    for idx, year in enumerate(years):
        center = idx * 30 + 15.5
        ax.text(center, -0.11, str(year), ha="center", va="top", transform=ax.get_xaxis_transform(), fontsize=9)
    ax.legend(loc="upper left", fontsize=9, frameon=True)
    fig.text(
        0.5,
        0.012,
        "注：先按 2015 年 eff 从小到大确定省份顺序；其后各年份均保持该顺序，且同一年份样本相邻排列。",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = OUT_DIR / "02_true_vs_pred_sequence.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_pred_vs_actual(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique())
    year_color_map = get_year_color_map(years)

    fig, ax = plt.subplots(figsize=(7.2, 6.6))
    for year in years:
        part = df.loc[df["year"] == year]
        ax.scatter(
            part[DEP_VAR],
            part["fitted"],
            s=42,
            color=year_color_map[year],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.45,
            label=str(year),
        )

    lower = min(df[DEP_VAR].min(), df["fitted"].min())
    upper = max(df[DEP_VAR].max(), df["fitted"].max())
    ax.plot([lower, upper], [lower, upper], color="black", linewidth=1.8, label="45°线")

    ax.set_title("预测值-真实值散点图")
    ax.set_xlabel("真实值 eff")
    ax.set_ylabel("预测值 eff")
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()
    out = OUT_DIR / "03_pred_vs_actual_scatter.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_residual_vs_fitted(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique())
    year_color_map = get_year_color_map(years)

    fig, ax = plt.subplots(figsize=(7.4, 6.4))
    for year in years:
        part = df.loc[df["year"] == year]
        ax.scatter(
            part["fitted"],
            part["resid"],
            s=42,
            color=year_color_map[year],
            alpha=0.84,
            edgecolor="white",
            linewidth=0.45,
            label=str(year),
        )

    ax.axhline(0, color="#374151", linewidth=1.6, linestyle="--")
    ax.set_title("拟合值-残差图")
    ax.set_xlabel("拟合值")
    ax.set_ylabel("残差")
    ax.set_ylim(-0.3, 0.3)
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()
    out = OUT_DIR / "04_residual_vs_fitted.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_residual_qq(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique())
    year_color_map = get_year_color_map(years)

    qq_df = df[["year", "province", "std_resid"]].copy()
    qq_df = qq_df.sort_values(["std_resid", "year", "province"]).reset_index(drop=True)
    n = len(qq_df)
    probs = (np.arange(1, n + 1) - 0.5) / n
    qq_df["theoretical_q"] = stats.norm.ppf(probs)
    qq_df["ordered_std_resid"] = qq_df["std_resid"].to_numpy()

    slope, intercept, r = stats.probplot(qq_df["std_resid"].to_numpy(), dist="norm", fit=True)[1]

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    for year in years:
        part = qq_df.loc[qq_df["year"] == year]
        ax.scatter(
            part["theoretical_q"],
            part["ordered_std_resid"],
            color=year_color_map[year],
            s=28,
            alpha=0.85,
            edgecolor="none",
            label=str(year),
        )

    x_line = np.linspace(-3, 3, 200)
    ax.plot(x_line, slope * x_line + intercept, color="#1F2933", linewidth=1.9)
    ax.set_title("标准化残差正态 Q-Q 图")
    ax.set_xlabel("理论分位数")
    ax.set_ylabel("标准化残差分位数")
    ax.set_xlim(-3, 3)
    ax.set_ylim(bottom=-6)
#    ax.axhline(0, color="black", linewidth=1.0, linestyle="--", zorder=1)
#    ax.axvline(0, color="black", linewidth=1.0, linestyle="--", zorder=1)
    ax.legend(loc="upper left", ncol=2, fontsize=9, frameon=True)
    ax.text(0.03, 0.74, f"R = {r:.4f}", transform=ax.transAxes, ha="left", va="top", fontsize=10, color="#334E68")
    fig.tight_layout()
    out = OUT_DIR / "05_residual_qq.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_coefficient_forest(result) -> Path:
    coef_table = build_regression_table(result)
    coef_table = coef_table.loc[coef_table["variable"].isin([CORE_VAR, *CONTROL_VARS])].copy()
    label_map = {
        "lntl": "夜间灯光聚合度",
        "ind": "产业结构",
        "urb": "城镇化水平",
        "rd": "研发投入",
        "open": "对外开放",
        "es": "能源结构",
    }
    coef_table["label"] = coef_table["variable"].map(label_map)
    coef_table = coef_table.iloc[::-1].reset_index(drop=True)
    y_pos = np.arange(len(coef_table))

    fig = plt.figure(figsize=(11.8, 6.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.55, 2.35, 1.8], wspace=0.04)
    ax_left = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[0, 1])
    ax_right = fig.add_subplot(gs[0, 2], sharey=ax)

    xmin = float(min(coef_table["ci_lower"].min(), -3.5))
    xmax = float(max(coef_table["ci_upper"].max(), 14.5))
    norm = TwoSlopeNorm(vmin=xmin, vcenter=0.0, vmax=xmax)
    cmap = plt.get_cmap("RdBu_r")

    def strong_rdbu_color(value: float):
        raw = cmap(norm(value))
        if value >= 0:
            scaled = 0.30 + 0.70 * norm(value)
        else:
            scaled = 0.30 * norm(value) / max(norm(0.0), 1e-9)
        scaled = float(np.clip(scaled, 0.0, 1.0))
        return cmap(scaled)

    tick_values = [-10.0, -1.0, -0.1, 0.0, 0.1, 1.0, 10.0]
    tick_values = [v for v in tick_values if xmin <= v <= xmax]

    for idx, row in coef_table.iterrows():
        color = strong_rdbu_color(row["coef"])
        ax.hlines(y_pos[idx], row["ci_lower"], row["ci_upper"], color=color, linewidth=1.6, zorder=2)
        ax.vlines([row["ci_lower"], row["ci_upper"]], y_pos[idx] - 0.10, y_pos[idx] + 0.10, color=color, linewidth=1.2, zorder=2)
        ax.scatter(row["coef"], y_pos[idx], marker="s", s=20, color=color, edgecolor=color, linewidth=0.5, zorder=3)

    ax.axvline(0, color="#7F7F7F", linewidth=1.0, zorder=1)
    ax.set_xscale("symlog", linthresh=0.2)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-0.6, len(coef_table) - 0.4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([])
    ax.set_xticks(tick_values)
    ax.set_xticklabels([f"{v:.1f}" if abs(v) < 1 else f"{v:.0f}" for v in tick_values])
    ax.set_xlabel("系数估计值")
    ax.set_title("基准回归系数森林图")
    ax.grid(axis="y", linestyle=":", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(ax.get_ylim())
    ax_left.axis("off")
    ax_left.text(0.00, len(coef_table) - 0.1, "变量", ha="left", va="bottom", fontsize=10, color="black", fontweight="bold")
    for idx, row in coef_table.iterrows():
        ax_left.text(0.00, y_pos[idx], row["label"], ha="left", va="center", fontsize=9.6, color="black")

    ax_right.set_xlim(0, 1)
    ax_right.set_ylim(ax.get_ylim())
    ax_right.axis("off")
    ax_right.text(0.02, len(coef_table) - 0.1, "coef (95% CI)", ha="left", va="bottom", fontsize=10, color="black", fontweight="bold")
    ax_right.text(0.98, len(coef_table) - 0.1, "p", ha="right", va="bottom", fontsize=10, color="black", fontweight="bold")
    for idx, row in coef_table.iterrows():
        coef_text = (
            f"{format_decimal(row['coef'])} "
            f"({format_decimal(row['ci_lower'])}, {format_decimal(row['ci_upper'])})"
        )
        ax_right.text(0.02, y_pos[idx], coef_text, ha="left", va="center", fontsize=9.2, color="black")
        stars = ""
        if row["p_value"] < 0.01:
            stars = "***"
        elif row["p_value"] < 0.05:
            stars = "**"
        elif row["p_value"] < 0.1:
            stars = "*"
        ax_right.text(0.98, y_pos[idx], f"{format_decimal(row['p_value'])}{stars}", ha="right", va="center", fontsize=9.2, color="black")

    fig.tight_layout()

    out = OUT_DIR / "06_coefficient_forest.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_partial_relationship(df: pd.DataFrame, result) -> Path:
    eff_resid = fit_auxiliary_residuals(df, DEP_VAR)
    lntl_resid = fit_auxiliary_residuals(df, CORE_VAR)
    partial_df = pd.DataFrame(
        {
            "province": eff_resid.index.get_level_values(0),
            "year": eff_resid.index.get_level_values(1).astype(int),
            "eff_resid": eff_resid.to_numpy(),
            "lntl_resid": lntl_resid.to_numpy(),
        }
    )

    years = sorted(partial_df["year"].unique())
    year_color_map = get_year_color_map(years)

    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    for year in years:
        part = partial_df.loc[partial_df["year"] == year]
        ax.scatter(
            part["lntl_resid"],
            part["eff_resid"],
            s=36,
            color=year_color_map[year],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.4,
            label=str(year),
        )

    slope = float(result.params[CORE_VAR])
    x_line = np.linspace(partial_df["lntl_resid"].min(), partial_df["lntl_resid"].max(), 200)
    y_line = slope * x_line
    smooth = lowess(partial_df["eff_resid"], partial_df["lntl_resid"], frac=0.45, return_sorted=True)

    ax.plot(x_line, y_line, color="#1F2933", linewidth=2.0, label="线性净效应")
    ax.plot(smooth[:, 0], smooth[:, 1], color="#C26D00", linewidth=1.8, linestyle="--", label="LOWESS")
    ax.axhline(0, color="#9CA3AF", linewidth=1.0, linestyle=":")
    ax.axvline(0, color="#9CA3AF", linewidth=1.0, linestyle=":")
    ax.set_title("控制双固定效应后的 lntl 净关系图")
    ax.set_xlabel("lntl 残差")
    ax.set_ylabel("eff 残差")
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()

    out = OUT_DIR / "07_partial_relationship_lntl_eff.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_diagnostics_triptych(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique())
    year_color_map = get_year_color_map(years)
    fig, axes = plt.subplots(1, 3, figsize=(18.0, 5.8))

    ax = axes[0]
    for year in years:
        part = df.loc[df["year"] == year]
        ax.scatter(
            part[DEP_VAR],
            part["fitted"],
            s=28,
            color=year_color_map[year],
            alpha=0.8,
            edgecolor="white",
            linewidth=0.35,
        )
    lower = min(df[DEP_VAR].min(), df["fitted"].min())
    upper = max(df[DEP_VAR].max(), df["fitted"].max())
    ax.plot([lower, upper], [lower, upper], color="#111827", linewidth=1.5)
    ax.set_title("预测值-真实值")
    ax.set_xlabel("真实值 eff")
    ax.set_ylabel("预测值 eff")

    ax = axes[1]
    for year in years:
        part = df.loc[df["year"] == year]
        ax.scatter(
            part["fitted"],
            part["resid"],
            s=28,
            color=year_color_map[year],
            alpha=0.8,
            edgecolor="white",
            linewidth=0.35,
        )
    ax.axhline(0, color="#111827", linewidth=1.4, linestyle="--")
    ax.set_title("拟合值-残差")
    ax.set_xlabel("拟合值")
    ax.set_ylabel("残差")

    ax = axes[2]
    qq_df = df[["year", "province", "std_resid"]].copy()
    qq_df = qq_df.sort_values(["std_resid", "year", "province"]).reset_index(drop=True)
    n = len(qq_df)
    probs = (np.arange(1, n + 1) - 0.5) / n
    qq_df["theoretical_q"] = stats.norm.ppf(probs)
    qq_df["ordered_std_resid"] = qq_df["std_resid"].to_numpy()
    slope, intercept, r = stats.probplot(qq_df["std_resid"].to_numpy(), dist="norm", fit=True)[1]
    for year in years:
        part = qq_df.loc[qq_df["year"] == year]
        ax.scatter(
            part["theoretical_q"],
            part["ordered_std_resid"],
            color=year_color_map[year],
            s=18,
            alpha=0.82,
            edgecolor="none",
        )
    x_line = np.linspace(-3, 3, 200)
    ax.plot(x_line, slope * x_line + intercept, color="#111827", linewidth=1.5)
    ax.set_title("标准化残差 Q-Q")
    ax.set_xlabel("理论分位数")
    ax.set_ylabel("样本分位数")
    ax.text(0.04, 0.94, f"R = {r:.4f}", transform=ax.transAxes, ha="left", va="top", fontsize=9)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=year_color_map[year], markersize=6, label=str(year))
        for year in years
    ]
    fig.legend(handles=handles, loc="lower center", ncol=8, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("基准回归诊断图组", y=1.02, fontsize=14)
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))

    out = OUT_DIR / "08_diagnostics_triptych.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_outputs(result, fitted_df: pd.DataFrame) -> None:
    coef_table = build_regression_table(result)
    summary_table = build_summary_table(result, fitted_df)

    coef_path = resolve_output_path(OUT_DIR / "baseline_regression_coefficients.csv")
    summary_path = resolve_output_path(OUT_DIR / "baseline_regression_summary.csv")
    fitted_path = resolve_output_path(OUT_DIR / "baseline_predictions_and_residuals.csv")
    report_path = resolve_output_path(OUT_DIR / "baseline_panel_report.md")

    coef_table.to_csv(coef_path, index=False, encoding="utf-8-sig")
    summary_table.to_csv(summary_path, index=False, encoding="utf-8-sig")
    fitted_df.to_csv(fitted_path, index=False, encoding="utf-8-sig")

    obsolete_paths = [
        OUT_DIR / "03_pred_vs_actual_scatter.png",
        OUT_DIR / "04_residual_vs_fitted.png",
        OUT_DIR / "05_residual_qq.png",
    ]
    for obsolete in obsolete_paths:
        if obsolete.exists():
            try:
                obsolete.unlink()
            except PermissionError:
                pass

    plot_paths = [
        plot_lntl_eff_scatter(fitted_df),
        plot_true_vs_pred_sequence(fitted_df),
        plot_coefficient_forest(result),
        plot_partial_relationship(fitted_df, result),
        plot_diagnostics_triptych(fitted_df),
    ]

    report_lines = [
        "# 基准面板回归与诊断图",
        "",
        "## 模型",
        "",
        "```text",
        "PanelOLS: eff ~ lntl + ind + urb + rd + open + es",
        "Effects: Entity + Time",
        "Covariance: Driscoll-Kraay",
        "```",
        "",
        "## 拟合摘要",
        "",
        "```text",
        summary_table.to_string(index=False),
        "```",
        "",
        "## 核心系数",
        "",
        "```text",
        coef_table.loc[coef_table["variable"].isin([CORE_VAR, *CONTROL_VARS])].round(6).to_string(index=False),
        "```",
        "",
        "## 图形输出",
        "",
    ]
    for path in plot_paths:
        report_lines.append(f"- `{path.name}`")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    configure_matplotlib()
    df = load_data()
    result, fitted_df = fit_model(df)
    save_outputs(result, fitted_df)

    print("Baseline panel regression finished.")
    print(f"Output directory: {OUT_DIR}")
    print(f"Observations: {int(result.nobs)}")
    print(f"R-squared: {result.rsquared:.6f}")
    print(f"R-squared (within): {result.rsquared_within:.6f}")
    print("Covariance: Driscoll-Kraay")
    print("Core coefficients:")
    for var in [CORE_VAR, *CONTROL_VARS]:
        print(
            f"  {var}: coef={result.params[var]:.6f}, "
            f"std_err={result.std_errors[var]:.6f}, t={result.tstats[var]:.4f}, p={result.pvalues[var]:.6f}"
        )


if __name__ == "__main__":
    main()
