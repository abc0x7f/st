from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colors, font_manager


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "prcd" / "process2.csv"
OUT_DIR = ROOT / "prcd" / "eff_plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def configure_matplotlib() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif_font = "Times New Roman" if "Times New Roman" in available else "DejaVu Serif"
    cjk_font = "SimSun" if "SimSun" in available else ("SimHei" if "SimHei" in available else serif_font)
    matplotlib.rcParams["font.family"] = [serif_font, cjk_font]
    matplotlib.rcParams["axes.unicode_minus"] = False


def build_gradient(start: str, end: str, n: int) -> list[tuple[float, float, float, float]]:
    cmap = colors.LinearSegmentedColormap.from_list("custom_gradient", [start, end])
    if n == 1:
        return [cmap(0.0)]
    return [cmap(i / (n - 1)) for i in range(n)]


def load_ranked_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    grouped = (
        df.groupby("province", as_index=False)
        .agg(mean_eff=("eff", "mean"), mean_lntl=("lntl", "mean"))
        .sort_values("mean_eff", ascending=False, kind="mergesort")
        .reset_index(drop=True)
    )
    grouped["rank"] = np.arange(1, len(grouped) + 1)
    return grouped


def draw_plot(df: pd.DataFrame) -> Path:
    n = len(df)
    y = np.arange(n)

    eff_colors = build_gradient("#0b5d1e", "#d7f2d9", n)
    lntl_colors = build_gradient("#e67e22", "#f6de6f", n)
    eff_max = float(df["mean_eff"].max())
    lntl_max = float(df["mean_lntl"].max())

    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.45, 0.42, 1.45], wspace=0.005)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_mid = fig.add_subplot(gs[0, 1], sharey=ax_left)
    ax_right = fig.add_subplot(gs[0, 2], sharey=ax_left)

    bar_height = 0.72
    ax_left.barh(y, df["mean_lntl"], color=lntl_colors, edgecolor="white", linewidth=0.8, height=bar_height)
    ax_right.barh(y, df["mean_eff"], color=eff_colors, edgecolor="white", linewidth=0.8, height=bar_height)

    ax_left.invert_xaxis()
    ax_left.invert_yaxis()

    ax_right.axvline(1.0, color="#3c763d", linestyle="--", linewidth=1.2, alpha=0.9)
    ax_right.text(
        1.0,
        -1.0,
        "效率值=1",
        ha="center",
        va="bottom",
        fontsize=10,
        color="#2f5d34",
    )

    for i, value in enumerate(df["mean_lntl"]):
        ax_left.text(
            value + lntl_max * 0.06,
            i,
            f"{value:.3f}",
            ha="left",
            va="center",
            fontsize=9,
            color="#7a4a14",
        )

    for i, value in enumerate(df["mean_eff"]):
        ax_right.text(
            value + eff_max * 0.015,
            i,
            f"{value:.3f}",
            ha="left",
            va="center",
            fontsize=9,
            color="#17351e",
        )

    ax_mid.set_xlim(0, 1)
    ax_mid.set_ylim(ax_left.get_ylim())
    ax_mid.axis("off")
    for i, province in enumerate(df["province"]):
        ax_mid.text(0.5, i, province, ha="center", va="center", fontsize=10.5)

    ax_left.set_title("各省平均 lntl", fontsize=14, pad=10)
    ax_right.set_title("各省平均效率", fontsize=14, pad=10)
    ax_left.set_xlabel("平均 lntl", fontsize=11)
    ax_right.set_xlabel("平均效率值", fontsize=11)
    ax_left.set_xlim(lntl_max * 1.18, 0)
    ax_right.set_xlim(0, max(eff_max * 1.16, 1.08))

    ax_left.set_yticks(y)
    ax_left.set_yticklabels([])
    ax_right.set_yticks(y)
    ax_right.set_yticklabels([])

    ax_left.tick_params(axis="y", length=0)
    ax_right.tick_params(axis="y", length=0)
    ax_mid.tick_params(axis="y", length=0)

    ax_left.grid(axis="x", linestyle=":", alpha=0.35)
    ax_right.grid(axis="x", linestyle=":", alpha=0.35)
    ax_left.grid(axis="y", visible=False)
    ax_right.grid(axis="y", visible=False)

    for ax in (ax_left, ax_right):
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(1.0)

    fig.suptitle("各省平均效率与平均 lntl 对比排序图", fontsize=16, y=0.98)
    fig.text(0.5, 0.02, "注：省份顺序按平均效率值由高到低排列。", ha="center", fontsize=10)
    fig.subplots_adjust(left=0.05, right=0.97, top=0.93, bottom=0.06, wspace=0.005)

    output_path = OUT_DIR / "各省平均效率与平均lntl对比排序图.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def draw_eff_only_plot(df: pd.DataFrame) -> Path:
    n = len(df)
    y = np.arange(n)
    eff_colors = build_gradient("#0b5d1e", "#d7f2d9", n)
    eff_max = float(df["mean_eff"].max())

    fig, ax_bar = plt.subplots(figsize=(9.2, 10))

    ax_bar.barh(y, df["mean_eff"], color=eff_colors, edgecolor="white", linewidth=0.8, height=0.72)
    ax_bar.invert_yaxis()
    ax_bar.axvline(1.0, color="#3c763d", linestyle="--", linewidth=1.2, alpha=0.9)
    ax_bar.text(1.0, -1.0, "效率值=1", ha="center", va="bottom", fontsize=10, color="#2f5d34")

    for i, value in enumerate(df["mean_eff"]):
        ax_bar.text(
            value + eff_max * 0.015,
            i,
            f"{value:.3f}",
            ha="left",
            va="center",
            fontsize=9,
            color="#17351e",
        )

    ax_bar.set_title("各省平均效率排序图", fontsize=15, pad=10)
    ax_bar.set_xlabel("平均效率值", fontsize=11)
    ax_bar.set_xlim(0, max(eff_max * 1.12, 1.08))
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(df["province"], fontsize=11)
    ax_bar.tick_params(axis="y", length=0, pad=6)
    ax_bar.grid(axis="x", linestyle=":", alpha=0.35)
    ax_bar.grid(axis="y", visible=False)
    for spine in ax_bar.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(1.0)

    fig.subplots_adjust(left=0.17, right=0.97, top=0.93, bottom=0.08)

    output_path = OUT_DIR / "各省平均效率排序图.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> None:
    configure_matplotlib()
    ranked = load_ranked_data()
    output_path_1 = draw_plot(ranked)
    output_path_2 = draw_eff_only_plot(ranked)
    print(f"saved: {output_path_1}")
    print(f"saved: {output_path_2}")


if __name__ == "__main__":
    main()
