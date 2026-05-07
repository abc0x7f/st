from __future__ import annotations

from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, stage_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
OUT_DIR = stage_output_dir(CONFIG, "60_核心变量箱线图")
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIRST_STAGE_PANEL = resolve_project_path(CONFIG["first_stage_panel"])
SECOND_STAGE_PANEL = resolve_project_path(CONFIG["second_stage_panel"])
FONT_SIZE_DELTA = 4


def fs(size: float) -> float:
    return size + FONT_SIZE_DELTA


def configure_matplotlib() -> None:
    sns.set_theme(style="whitegrid")
    candidates = [
        "Times New Roman",
        "SimSun",
        "SimHei",
        "Microsoft YaHei",
        "Noto Serif CJK SC",
        "Noto Sans CJK SC",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [name for name in candidates if name in available]
    if not chosen:
        chosen = ["DejaVu Serif"]
    matplotlib.rcParams["font.family"] = chosen
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["font.size"] = fs(10)
    matplotlib.rcParams["axes.titlesize"] = fs(12)
    matplotlib.rcParams["axes.labelsize"] = fs(10)
    matplotlib.rcParams["xtick.labelsize"] = fs(9)
    matplotlib.rcParams["ytick.labelsize"] = fs(9)
    matplotlib.rcParams["legend.fontsize"] = fs(9)


def create_boxplots() -> None:
    df1 = pd.read_csv(FIRST_STAGE_PANEL)
    df2 = pd.read_csv(SECOND_STAGE_PANEL)

    items = [
        ("Population", df1["Population"], "#4C78A8", "第一阶段"),
        ("Capital", df1["Capital"], "#9C755F", "第一阶段"),
        ("energy_total", df1["energy_total"], "#F58518", "第一阶段"),
        ("GDP_constant", df1["GDP_constant"], "#E45756", "第一阶段"),
        ("Carbon", df1["Carbon"], "#72B7B2", "第一阶段"),
        ("lntl", df2["lntl"], "#B279A2", "第二阶段"),
        ("ind", df2["ind"], "#FF9DA6", "第二阶段"),
        ("urb", df2["urb"], "#54A24B", "第二阶段"),
        ("rd", df2["rd"], "#EECA3B", "第二阶段"),
        ("open", df2["open"], "#BAB0AC", "第二阶段"),
        ("es", df2["es"], "#8C6D31", "第二阶段"),
        ("eff", df2["eff"], "#2CA02C", "第二阶段"),
    ]

    fig, axes = plt.subplots(3, 4, figsize=(18.5, 12.2))
    axes = axes.flatten()

    for ax, (name, series, color, source) in zip(axes, items):
        sns.boxplot(y=series, ax=ax, color=color, width=0.42, linewidth=1.2, fliersize=4)
        ax.set_title(f"{name}\n({source})", fontsize=fs(11), pad=8, color="black")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", labelsize=fs(9), pad=5)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

    for ax in axes[len(items):]:
        ax.axis("off")

    fig.suptitle("图6 核心变量箱线图", fontsize=fs(18), y=0.985, color="black")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(OUT_DIR / "图6_核心变量箱线图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    configure_matplotlib()
    create_boxplots()
    print(f"saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
