from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.formula.api as smf
from matplotlib import font_manager
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "prcd" / "process2.csv"
OUT_DIR = ROOT / "prcd" / "baseline_panel_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEP_VAR = "eff"
CORE_VAR = "lntl"
CONTROL_VARS = ["ind", "urb", "rd", "open", "es"]
MODEL_FORMULA = "eff ~ lntl + ind + urb + rd + open + es + C(province) + C(year)"


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
    model = smf.ols(MODEL_FORMULA, data=df)
    result = model.fit()
    prediction = result.get_prediction(df).summary_frame(alpha=0.05)

    out = df.copy()
    out["fitted"] = result.fittedvalues
    out["resid"] = result.resid
    out["std_resid"] = (result.resid - result.resid.mean()) / result.resid.std(ddof=1)
    out["mean_ci_lower"] = prediction["mean_ci_lower"]
    out["mean_ci_upper"] = prediction["mean_ci_upper"]
    out["obs_ci_lower"] = prediction["obs_ci_lower"]
    out["obs_ci_upper"] = prediction["obs_ci_upper"]
    return result, out


def build_regression_table(result) -> pd.DataFrame:
    coef = result.params
    conf = result.conf_int()
    return pd.DataFrame(
        {
            "variable": coef.index,
            "coef": coef.values,
            "std_err": result.bse.values,
            "t_value": result.tvalues.values,
            "p_value": result.pvalues.values,
            "ci_lower": conf[0].values,
            "ci_upper": conf[1].values,
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
                "adj_r_squared",
                "f_statistic",
                "f_pvalue",
                "aic",
                "bic",
                "n_parameters",
            ],
            "value": [
                float(result.nobs),
                float(df["province"].nunique()),
                float(df["year"].nunique()),
                float(result.rsquared),
                float(result.rsquared_adj),
                float(result.fvalue) if result.fvalue is not None else np.nan,
                float(result.f_pvalue) if result.f_pvalue is not None else np.nan,
                float(result.aic),
                float(result.bic),
                float(len(result.params)),
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
    ax.fill_between(
        ordered["sample_index"],
        ordered["obs_ci_lower"],
        ordered["obs_ci_upper"],
        color="#B8C2CC",
        alpha=0.22,
        label="95% 预测置信区间",
        zorder=1,
    )

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


def save_outputs(result, fitted_df: pd.DataFrame) -> None:
    coef_table = build_regression_table(result)
    summary_table = build_summary_table(result, fitted_df)

    coef_table.to_csv(OUT_DIR / "baseline_regression_coefficients.csv", index=False, encoding="utf-8-sig")
    summary_table.to_csv(OUT_DIR / "baseline_regression_summary.csv", index=False, encoding="utf-8-sig")
    fitted_df.to_csv(OUT_DIR / "baseline_predictions_and_residuals.csv", index=False, encoding="utf-8-sig")

    plot_paths = [
        plot_lntl_eff_scatter(fitted_df),
        plot_true_vs_pred_sequence(fitted_df),
        plot_pred_vs_actual(fitted_df),
        plot_residual_vs_fitted(fitted_df),
        plot_residual_qq(fitted_df),
    ]

    report_lines = [
        "# 基准面板回归与诊断图",
        "",
        "## 模型",
        "",
        "```text",
        MODEL_FORMULA,
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

    (OUT_DIR / "baseline_panel_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    configure_matplotlib()
    df = load_data()
    result, fitted_df = fit_model(df)
    save_outputs(result, fitted_df)

    print("Baseline panel regression finished.")
    print(f"Output directory: {OUT_DIR}")
    print(f"Observations: {int(result.nobs)}")
    print(f"R-squared: {result.rsquared:.6f}")
    print(f"Adjusted R-squared: {result.rsquared_adj:.6f}")
    print("Core coefficients:")
    for var in [CORE_VAR, *CONTROL_VARS]:
        print(
            f"  {var}: coef={result.params[var]:.6f}, "
            f"std_err={result.bse[var]:.6f}, t={result.tvalues[var]:.4f}, p={result.pvalues[var]:.6f}"
        )


if __name__ == "__main__":
    main()
