from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager, patches
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "最终数据" / "第二阶段_基础.csv"
OUT_DIR = ROOT / "outputs" / "回归分析" / "10_相关性与VIF分析"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORR_VARS = ["eff", "lntl", "ind", "urb", "rd", "open", "es"]
VIF_VARS = ["lntl", "ind", "urb", "rd", "open", "es"]
LABELS = {
    "eff": "碳排放效率\neff",
    "lntl": "夜间灯光\nlntl",
    "ind": "产业结构\nind",
    "urb": "城镇化率\nurb",
    "rd": "研发投入\nrd",
    "open": "对外开放度\nopen",
    "es": "能源结构\nes",
}


def configure_matplotlib() -> None:
    sns.set_theme(style="white")
    serif_candidates = ["Times New Roman", "Times New Roman PS MT", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif = next((name for name in serif_candidates if name in available), "DejaVu Serif")
    chinese = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = [serif, chinese]
    matplotlib.rcParams["font.serif"] = [serif]
    matplotlib.rcParams["font.sans-serif"] = [chinese]
    matplotlib.rcParams["axes.unicode_minus"] = False


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [col for col in CORR_VARS if col not in df.columns]
    if missing:
        raise ValueError(f"数据缺少字段: {missing}")

    for col in CORR_VARS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=CORR_VARS).copy()
    return df


def text_color_for_value(value: float, cmap: colors.Colormap, norm: colors.Normalize) -> tuple[float, float, float, float]:
    display_value = value
    center_gap = 0.25
    if 0 <= display_value < center_gap:
        display_value = center_gap
    elif -center_gap < display_value < 0:
        display_value = -center_gap
    return cmap(norm(display_value))


def build_corr_and_pvalues(
    df: pd.DataFrame, vars_to_use: list[str], method: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    renamed = df[vars_to_use].rename(columns=LABELS)
    cols = renamed.columns.tolist()
    corr = pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols, dtype=float)
    pvals = pd.DataFrame(np.zeros((len(cols), len(cols))), index=cols, columns=cols, dtype=float)

    corr_func = pearsonr if method == "pearson" else spearmanr
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            coef, pvalue = corr_func(renamed.iloc[:, i], renamed.iloc[:, j])
            corr.iloc[i, j] = corr.iloc[j, i] = float(coef)
            pvals.iloc[i, j] = pvals.iloc[j, i] = float(pvalue)
    return corr, pvals


def draw_ellipse_cell(
    ax: plt.Axes,
    x: int,
    y: int,
    value: float,
    cmap: colors.Colormap,
    norm: colors.Normalize,
) -> None:
    abs_value = abs(value)
    scale = 0.9
    width = scale * np.sqrt(1 + abs_value) / np.sqrt(2)
    height = scale * np.sqrt(1 - abs_value) / np.sqrt(2)
    angle = 45 if value >= 0 else -45
    ellipse = patches.Ellipse(
        (x + 0.5, y + 0.5),
        width=width,
        height=height,
        angle=angle,
        facecolor=cmap(norm(value)),
        edgecolor="none",
        linewidth=0,
        alpha=0.95,
    )
    ax.add_patch(ellipse)


def draw_corr_ellipse_matrix_on_ax(
    ax: plt.Axes,
    corr: pd.DataFrame,
    title: str,
) -> None:
    n = len(corr)
    cmap = plt.get_cmap("RdBu_r")
    norm = colors.Normalize(vmin=-1, vmax=1)
    ax.set_xlim(0, n)
    ax.set_ylim(n, 0)
    ax.set_aspect("equal")

    for i in range(n):
        for j in range(n):
            rect = patches.Rectangle((j, i), 1, 1, facecolor="white", edgecolor="#D1D5DB", linewidth=0.8)
            ax.add_patch(rect)

            value = float(corr.iloc[i, j])

            if i > j:
                draw_ellipse_cell(ax, j, i, value, cmap, norm)
            elif i < j:
                text = f"{value:.2f}"
                ax.text(
                    j + 0.5,
                    i + 0.5,
                    text,
                    ha="center",
                    va="center",
                    fontsize=10,
                    color=text_color_for_value(value, cmap, norm),
                    fontweight="normal",
                )
            else:
                ax.text(
                    j + 0.5,
                    i + 0.5,
                    corr.index[i],
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="#111827",
                    fontweight="bold",
                )

    ax.set_xticks(np.arange(n) + 0.5)
    ax.set_yticks(np.arange(n) + 0.5)
    ax.set_xticklabels(corr.columns, fontsize=10)
    ax.set_yticklabels(corr.index, fontsize=10)
    ax.xaxis.tick_top()
    plt.setp(ax.get_xticklabels(), rotation=45, ha="left", rotation_mode="anchor")
    ax.tick_params(length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(title, fontsize=15, pad=24)


def save_combined_corr_ellipse_matrix(
    pearson_corr: pd.DataFrame,
    spearman_corr: pd.DataFrame,
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(24, 10), constrained_layout=True)
    draw_corr_ellipse_matrix_on_ax(axes[0], pearson_corr, "Pearson 相关性椭圆矩阵")
    draw_corr_ellipse_matrix_on_ax(axes[1], spearman_corr, "Spearman 相关性椭圆矩阵")

    cmap = plt.get_cmap("RdBu_r")
    norm = colors.Normalize(vmin=-1, vmax=1)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02)
    cbar.set_label("相关系数", fontsize=10)

    fig.suptitle("第二阶段变量相关性椭圆矩阵", fontsize=17)
    note = "注：下三角为相关性椭圆，上三角为相关系数数值；相关性检验仅作描述性分析，图中不再展示显著性标记。"
    fig.text(0.01, 0.003, note, ha="left", va="bottom", fontsize=9, color="#4B5563")

    out_path = OUT_DIR / "相关椭圆矩阵组合图.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_corr_tables(
    pearson_corr: pd.DataFrame,
    spearman_corr: pd.DataFrame,
    pearson_pvals: pd.DataFrame,
    spearman_pvals: pd.DataFrame,
) -> list[Path]:
    outputs = {
        "皮尔逊相关系数矩阵.csv": pearson_corr,
        "斯皮尔曼相关系数矩阵.csv": spearman_corr,
        "皮尔逊显著性P值.csv": pearson_pvals,
        "斯皮尔曼显著性P值.csv": spearman_pvals,
    }
    paths: list[Path] = []
    for filename, table in outputs.items():
        path = OUT_DIR / filename
        table.to_csv(path, encoding="utf-8-sig")
        paths.append(path)
    return paths


def calculate_vif(df: pd.DataFrame, vars_to_use: list[str]) -> pd.DataFrame:
    x = df[vars_to_use].copy()
    for col in vars_to_use:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.dropna()

    design = add_constant(x, has_constant="add")
    vif_values = [float(variance_inflation_factor(design.values, i + 1)) for i in range(len(vars_to_use))]

    result = pd.DataFrame(
        {
            "variable": vars_to_use,
            "label": [LABELS[col].replace("\n", " ") for col in vars_to_use],
            "vif": vif_values,
            "tolerance": [1 / v for v in vif_values],
        }
    ).sort_values("vif", ascending=True)

    result["judge"] = result["vif"].apply(
        lambda v: "严重共线性" if v >= 10 else "需关注" if v >= 5 else "可接受"
    )
    return result


def save_vif_table(vif_df: pd.DataFrame) -> Path:
    out_path = OUT_DIR / "方差膨胀因子结果表.csv"
    vif_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def save_vif_cleveland_plot(vif_df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(10.5, 6.2), constrained_layout=True)
    y = np.arange(len(vif_df))
    colors_map = vif_df["vif"].map(lambda v: "#C0392B" if v >= 10 else "#F39C12" if v >= 5 else "#2E86AB")

    ax.hlines(y=y, xmin=0, xmax=vif_df["vif"], color="#CBD5E1", linewidth=2.2)
    ax.scatter(vif_df["vif"], y, s=85, c=colors_map, edgecolors="white", linewidths=0.9, zorder=3)

    ax.axvline(5, color="#F39C12", linestyle="--", linewidth=1.3, label="VIF=5")
    ax.axvline(10, color="#C0392B", linestyle="--", linewidth=1.3, label="VIF=10")

    for yi, value in zip(y, vif_df["vif"]):
        ax.text(value + 0.08, yi, f"{value:.2f}", va="center", ha="left", fontsize=10, color="#111827")

    ax.set_yticks(y)
    ax.set_yticklabels(vif_df["label"], fontsize=10)
    ax.set_xlabel("VIF")
    ax.set_title("VIF 检验克利夫兰图", fontsize=15, pad=12)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    x_max = max(12.0, float(vif_df["vif"].max()) + 2.0)
    ax.set_xlim(0, x_max)
    ax.spines["left"].set_visible(True)
    ax.spines["bottom"].set_visible(True)
    ax.legend(frameon=False, loc="upper right")

    out_path = OUT_DIR / "方差膨胀因子克利夫兰点图.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def build_markdown_table(df: pd.DataFrame, digits: int = 3) -> str:
    header = "| 变量 | VIF | Tolerance | 判定 |"
    sep = "|:---|---:|---:|:---|"
    rows = [
        f"| {row.label} | {row.vif:.{digits}f} | {row.tolerance:.{digits}f} | {row.judge} |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([header, sep, *rows])


def build_interpretation(
    df: pd.DataFrame,
    pearson_corr: pd.DataFrame,
    spearman_corr: pd.DataFrame,
    vif_df: pd.DataFrame,
) -> str:
    n_obs = len(df)
    pearson_eff = pearson_corr.loc[LABELS["eff"]].drop(LABELS["eff"]).sort_values(
        key=lambda s: s.abs(), ascending=False
    )
    spearman_eff = spearman_corr.loc[LABELS["eff"]].drop(LABELS["eff"]).sort_values(
        key=lambda s: s.abs(), ascending=False
    )

    high_vif = vif_df.loc[vif_df["vif"] >= 5, "label"].tolist()
    max_vif_row = vif_df.loc[vif_df["vif"].idxmax()]

    lines = [
        "# 相关性与 VIF 结果解释",
        "",
        f"- 样本量：{n_obs} 个省份-年份观测值。",
        f"- 相关性分析变量：{', '.join(CORR_VARS)}。",
        f"- VIF 检验变量：{', '.join(VIF_VARS)}。",
        "",
        "## 关于 eff 是否参与排序",
        "",
        (
            "`eff` 需要参与 Pearson 和 Spearman 相关性检验，因为相关系数矩阵需要展示"
            "被解释变量与核心解释变量、控制变量之间的两两关系。"
            "但在 VIF 检验中，`eff` 不进入模型，因为 VIF 只检验解释变量之间的多重共线性。"
        ),
        "",
        "## 椭圆相关图的判读方法",
        "",
        (
            "下三角区域的椭圆用于可视化相关方向和强度：椭圆越扁，说明绝对相关系数越大；"
            "向右上倾斜表示正相关，向左上倾斜表示负相关；越接近圆形，说明相关性越弱。"
            "上三角给出具体相关系数数值，从而兼顾可视化判断和精确比较。"
        ),
        "",
        "## 结果解读",
        "",
        (
            f"1. Pearson 下，与 `eff` 绝对相关性最高的三个变量分别是："
            f"{pearson_eff.index[0]} ({pearson_eff.iloc[0]:.3f})、"
            f"{pearson_eff.index[1]} ({pearson_eff.iloc[1]:.3f})、"
            f"{pearson_eff.index[2]} ({pearson_eff.iloc[2]:.3f})。"
        ),
        (
            f"2. Spearman 下，与 `eff` 绝对相关性最高的三个变量分别是："
            f"{spearman_eff.index[0]} ({spearman_eff.iloc[0]:.3f})、"
            f"{spearman_eff.index[1]} ({spearman_eff.iloc[1]:.3f})、"
            f"{spearman_eff.index[2]} ({spearman_eff.iloc[2]:.3f})。"
        ),
        (
            f"3. VIF 最大的变量是 {max_vif_row['label']}，其 VIF 为 {max_vif_row['vif']:.3f}。"
            + (
                f"其中需要重点关注的变量包括：{', '.join(high_vif)}。"
                if high_vif
                else "所有解释变量的 VIF 均低于 5，未见明显多重共线性风险。"
            )
        ),
        (
            "4. 若相关图中部分变量两两相关较高，而 VIF 同时偏高，说明这些变量在回归中可能存在信息重叠。"
            "此时需要结合变量定义判断是否存在口径相近、趋势同步或尺度高度一致的问题。"
        ),
        "",
        "## VIF 结果表",
        "",
        build_markdown_table(vif_df),
        "",
        "## 论文中可直接使用的表述",
        "",
        (
            "本文首先采用 Pearson 相关系数与 Spearman 秩相关系数考察变量间的两两相关关系。"
            "相关性椭圆矩阵显示，多数变量之间的相关方向在两种方法下保持一致，"
            "说明变量关系具有较好的稳定性。考虑到面板数据下显著性检验更适合作描述性参考，"
            "本文在图中仅展示相关系数与椭圆形态，不强调星号显著性。进一步地，本文对解释变量进行 VIF 检验，"
            "并结合克利夫兰图展示各变量的方差膨胀因子。若各变量 VIF 未超过常用阈值，"
            "则说明模型不存在严重多重共线性，可进入后续回归分析。"
        ),
    ]
    return "\n".join(lines)


def save_interpretation(text: str) -> Path:
    out_path = OUT_DIR / "相关性与VIF解读.md"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main() -> None:
    configure_matplotlib()
    df = load_data(DATA_PATH)

    pearson_corr, pearson_pvals = build_corr_and_pvalues(df, CORR_VARS, method="pearson")
    spearman_corr, spearman_pvals = build_corr_and_pvalues(df, CORR_VARS, method="spearman")
    save_corr_tables(pearson_corr, spearman_corr, pearson_pvals, spearman_pvals)

    combined_corr_plot = save_combined_corr_ellipse_matrix(pearson_corr, spearman_corr)

    vif_df = calculate_vif(df, VIF_VARS)
    vif_table = save_vif_table(vif_df)
    vif_plot = save_vif_cleveland_plot(vif_df)

    interpretation = save_interpretation(build_interpretation(df, pearson_corr, spearman_corr, vif_df))

    print(f"样本量: {len(df)}")
    print(f"合并相关性椭圆矩阵: {combined_corr_plot}")
    print(f"VIF 结果表: {vif_table}")
    print(f"VIF 克利夫兰图: {vif_plot}")
    print(f"结果说明: {interpretation}")


if __name__ == "__main__":
    main()
