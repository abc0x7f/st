from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parent
WEIGHT_PATH = ROOT / "prcd" / "matrix01.csv"
EFF_PATH = ROOT / "prcd" / "dearun_eff.csv"
OUT_DIR = ROOT / "prcd" / "spatial_plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_YEARS = [2018, 2019, 2020, 2021, 2022]
N_PERMUTATIONS = 9999
RANDOM_SEED = 42


def configure_matplotlib() -> None:
    sns.set_theme(style="whitegrid")
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((name for name in candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = [chosen]
    matplotlib.rcParams["axes.unicode_minus"] = False


def load_weight_matrix(path: Path) -> pd.DataFrame:
    w = pd.read_csv(path, index_col=0)
    w.index = w.index.astype(str).str.strip()
    w.columns = w.columns.astype(str).str.strip()
    w = w.loc[w.index, w.index]
    return w


def load_efficiency(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"year", "province", "eff"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"dearun_eff.csv 缺少字段: {sorted(missing)}")

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["province"] = df["province"].astype(str).str.strip()
    df["eff"] = pd.to_numeric(df["eff"], errors="coerce")
    df = df.dropna(subset=["year", "province", "eff"]).copy()
    df["year"] = df["year"].astype(int)
    return df


def row_standardize(matrix: np.ndarray) -> np.ndarray:
    row_sums = matrix.sum(axis=1, keepdims=True)
    return np.divide(matrix, row_sums, out=np.zeros_like(matrix, dtype=float), where=row_sums != 0)


def morans_i(values: np.ndarray, weights: np.ndarray) -> float:
    n = len(values)
    z = values - values.mean()
    s0 = weights.sum()
    return float((n / s0) * (z @ weights @ z) / (z @ z))


def permutation_test(
    values: np.ndarray,
    weights: np.ndarray,
    n_permutations: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, float, float]:
    observed = morans_i(values, weights)
    centered = values - values.mean()
    denom = float(centered @ centered)
    n = len(values)
    s0 = float(weights.sum())

    sims = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        permuted = rng.permutation(centered)
        sims[i] = (n / s0) * (permuted @ weights @ permuted) / denom

    p_one_sided = float((np.sum(sims >= observed) + 1) / (n_permutations + 1))
    sim_mean = float(sims.mean())
    sim_std = float(sims.std(ddof=1))
    z_value = float((observed - sim_mean) / sim_std) if sim_std > 0 else float("nan")
    return observed, z_value, p_one_sided, sim_mean, sim_std


def calculate_global_morans_i() -> pd.DataFrame:
    w_df = load_weight_matrix(WEIGHT_PATH)
    weights = row_standardize(w_df.to_numpy(dtype=float))
    provinces = w_df.index.tolist()
    eff_df = load_efficiency(EFF_PATH)
    rng = np.random.default_rng(RANDOM_SEED)

    rows: list[dict[str, float | int]] = []
    for year in TARGET_YEARS:
        year_df = eff_df.loc[eff_df["year"] == year].set_index("province")
        missing = [p for p in provinces if p not in year_df.index]
        if missing:
            raise ValueError(f"{year} 年缺少省份数据: {missing}")

        values = year_df.loc[provinces, "eff"].to_numpy(dtype=float)
        moran_i, z_value, p_value, sim_mean, sim_std = permutation_test(
            values=values,
            weights=weights,
            n_permutations=N_PERMUTATIONS,
            rng=rng,
        )
        rows.append(
            {
                "year": year,
                "moran_i": moran_i,
                "z_value": z_value,
                "p_value": p_value,
                "perm_mean": sim_mean,
                "perm_std": sim_std,
            }
        )

    result = pd.DataFrame(rows)
    result["significance"] = result["p_value"].apply(
        lambda p: "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    )
    return result


def save_result_table(result: pd.DataFrame) -> Path:
    out_path = OUT_DIR / "global_morans_i_2018_2022.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def save_plot(result: pd.DataFrame) -> Path:
    fig, ax_left = plt.subplots(figsize=(11.8, 7.2))
    ax_right = ax_left.twinx()
    ax_left.set_zorder(2)
    ax_right.set_zorder(1)
    ax_left.patch.set_visible(False)
    ax_left.grid(False)
    ax_right.grid(False)

    x = np.arange(len(result))
    width = 0.18
    p_color = "#D62728"
    z_color = "#1F77B4"
    i_color = "#2E8B57"
    p_sig = ("p值5%显著性（p=0.05）", 0.05, "#C44E52", "--")
    z_sig = ("z值10%显著性（z=1.645）", 1.645, "#8172B2", "-.")

    p_bars = ax_left.bar(x - width / 2, result["p_value"], width=width, color=p_color, label="p 值", zorder=3)
    (i_line,) = ax_left.plot(
        x,
        result["moran_i"],
        color=i_color,
        linewidth=2.2,
        marker="o",
        markersize=6.2,
        markerfacecolor="white",
        markeredgewidth=1.4,
        label="Moran's I",
        zorder=6,
    )
    z_bars = ax_right.bar(x + width / 2, result["z_value"], width=width, color=z_color, label="z 值", zorder=3)

    ax_left.axhline(p_sig[1], color=p_sig[2], linestyle=p_sig[3], linewidth=1.4, alpha=0.95, zorder=2)
    ax_right.axhline(z_sig[1], color=z_sig[2], linestyle=z_sig[3], linewidth=1.4, alpha=0.95, zorder=2)

    legend_handles: list[object] = [
        p_bars[0],
        z_bars[0],
        i_line,
        Line2D([0], [0], color=z_sig[2], linestyle=z_sig[3], linewidth=1.5),
        Line2D([0], [0], color=p_sig[2], linestyle=p_sig[3], linewidth=1.5),
    ]
    legend_labels = ["p 值", "z 值", "Moran's I", z_sig[0], p_sig[0]]

    ax_left.set_title("2018-2022 年 Global Moran's I、p 值与 z 值", fontsize=15, pad=14)
    ax_left.set_xlabel("年份")
    ax_left.set_ylabel("p 值 / Global Moran's I")
    ax_right.set_ylabel("z 值")
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(result["year"])

    left_step = 0.05
    left_upper = max(float(result["p_value"].max()), float(result["moran_i"].max()), p_sig[1])
    left_upper = float(np.ceil(left_upper / left_step) * left_step) + left_step
    right_upper = max(float(result["z_value"].max()), z_sig[1])
    n_intervals = max(int(round(left_upper / left_step)), int(np.ceil(right_upper)))
    left_upper = n_intervals * left_step
    right_upper = float(n_intervals)

    ax_left.set_ylim(0, left_upper)
    ax_right.set_ylim(0, right_upper)
    left_ticks = np.arange(0.0, left_upper + left_step / 2, left_step)
    right_ticks = np.arange(0.0, right_upper + 0.5, 1.0)
    ax_left.set_yticks(left_ticks)
    ax_right.set_yticks(right_ticks)
    ax_right.yaxis.set_major_locator(MultipleLocator(1.0))

    for bar, value, stars in zip(p_bars, result["p_value"], result["significance"]):
        ax_left.annotate(
            f"{value:.3f}{stars}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#1F2933",
        )

    for x_pos, value in zip(x, result["moran_i"]):
        ax_left.annotate(
            f"{value:.3f}",
            xy=(x_pos, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=i_color,
        )

    for bar, value in zip(z_bars, result["z_value"]):
        ax_right.annotate(
            f"{value:.3f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#1F2933",
        )

    ax_left.legend(legend_handles, legend_labels, loc="upper right", frameon=True, fontsize=9)

    note = "注：采用 0-1 邻接矩阵并进行行标准化；p 值为单侧置换检验结果（9999 次），z 值基于置换分布的均值与标准差计算。"
    fig.text(0.01, 0.01, note, ha="left", va="bottom", fontsize=9, color="#52606D")
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    out_path = OUT_DIR / "18_global_morans_i_2018_2022.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def build_markdown_table(result: pd.DataFrame) -> str:
    header = "| year | moran_i | z_value | p_value | significance |"
    sep = "|---:|---:|---:|---:|:---:|"
    rows = [
        f"| {int(row.year)} | {row.moran_i:.6f} | {row.z_value:.4f} | {row.p_value:.4f} | {row.significance} |"
        for row in result.itertuples(index=False)
    ]
    return "\n".join([header, sep, *rows])


def save_analysis(result: pd.DataFrame) -> Path:
    peak_row = result.loc[result["moran_i"].idxmax()]
    low_row = result.loc[result["moran_i"].idxmin()]
    strongest_z_row = result.loc[result["z_value"].idxmax()]
    significant_years = result.loc[result["p_value"] < 0.05, "year"].tolist()
    marginal_years = result.loc[(result["p_value"] >= 0.05) & (result["p_value"] < 0.10), "year"].tolist()

    lines = [
        "# 2018-2022 年全局 Moran's I 分析",
        "",
        "## 结果概览",
        "",
        build_markdown_table(result),
        "",
        "## 分析",
        "",
        (
            f"1. 2018-2022 年 Moran's I 均为正值，介于 {result['moran_i'].min():.3f} 到 "
            f"{result['moran_i'].max():.3f} 之间，说明省际碳排放效率整体存在正向空间自相关。"
        ),
        (
            f"2. 从变化趋势看，2018-2020 年 Moran's I 由 "
            f"{result.loc[result['year'] == 2018, 'moran_i'].iloc[0]:.3f} 小幅升至 "
            f"{result.loc[result['year'] == 2020, 'moran_i'].iloc[0]:.3f}，2021 年回落至 "
            f"{low_row['moran_i']:.3f}，2022 年升至 {peak_row['moran_i']:.3f}。"
        ),
        (
            f"3. 置换检验下，z 值最高的年份为 {int(strongest_z_row['year'])} 年，"
            f"对应 z={strongest_z_row['z_value']:.3f}；"
            f"{('、'.join(map(str, significant_years)) + ' 年') if significant_years else '无年份'}"
            f"在 5% 水平上显著，"
            f"{('、'.join(map(str, marginal_years)) + ' 年') if marginal_years else '无年份'}"
            "在 10% 水平上边际显著。"
        ),
        "4. 就论文表述而言，可以据此说明省际碳排放效率存在一定空间依赖性，继续使用空间计量模型具备经验依据。",
        "",
        "## 写作建议",
        "",
        (
            "可在正文中表述为：2018-2022 年我国省际碳排放效率的全局 Moran's I 均为正，"
            "且 2022 年的空间集聚信号最强，说明碳排放效率存在一定的正向空间集聚特征，"
            "邻近省份之间呈现相似效率水平，为后续空间计量分析提供了依据。"
        ),
    ]

    out_path = OUT_DIR / "global_morans_i_2018_2022_analysis.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    configure_matplotlib()
    result = calculate_global_morans_i()
    table_path = save_result_table(result)
    plot_path = save_plot(result)
    analysis_path = save_analysis(result)

    print(result.to_string(index=False))
    print(f"saved table: {table_path}")
    print(f"saved plot: {plot_path}")
    print(f"saved analysis: {analysis_path}")


if __name__ == "__main__":
    main()
