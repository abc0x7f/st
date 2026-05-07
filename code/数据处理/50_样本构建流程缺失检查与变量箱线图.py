from __future__ import annotations

from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import BoundaryNorm
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "流水线"))
from stage_config import load_script_context, stage_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
OUT_DIR = stage_output_dir(CONFIG, "50_样本构建流程缺失检查与变量箱线图")
OUT_DIR.mkdir(parents=True, exist_ok=True)
ENERGY_YEARBOOK_GLOB = CONFIG["energy_yearbook_glob"]
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


def create_missing_heatmap() -> None:
    path = next((ROOT / "data").rglob(ENERGY_YEARBOOK_GLOB))
    xls = pd.ExcelFile(path)
    df = pd.read_excel(path, sheet_name=xls.sheet_names[0])

    df = df.iloc[2:].copy()
    df = df.rename(columns={df.columns[0]: "province", df.columns[1]: "year"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)
    df = df[df["year"] >= 2015].copy()
    df["sample"] = df["province"].astype(str) + "-" + df["year"].astype(str)

    meta_cols = ["province", "year", "sample"]
    value_cols = [c for c in df.columns if c not in meta_cols]
    zero_as_missing = df[value_cols].apply(pd.to_numeric, errors="coerce").eq(0)
    na_missing = df[value_cols].isna()
    missing_count = (zero_as_missing | na_missing).sum(axis=1)
    heatmap_df = (
        pd.DataFrame({"province": df["province"], "year": df["year"], "missing_count": missing_count})
        .pivot(index="province", columns="year", values="missing_count")
        .sort_index()
    )
    heatmap_df = heatmap_df.reindex(sorted(heatmap_df.columns), axis=1)
    max_missing = int(heatmap_df.max().max()) if not heatmap_df.empty else 0
    levels = max_missing + 1 if max_missing > 0 else 1
    boundaries = list(range(levels + 1))
    cmap = plt.get_cmap("YlOrRd", levels)
    norm = BoundaryNorm(boundaries, cmap.N)

    fig, ax = plt.subplots(figsize=(13.5, 10.2))
    sns.heatmap(
        heatmap_df,
        cmap=cmap,
        norm=norm,
        cbar=True,
        linewidths=0.8,
        linecolor="white",
        annot=False,
        vmin=0,
        vmax=max_missing if max_missing > 0 else 1,
        cbar_kws={
            "ticks": list(range(levels)),
            "boundaries": boundaries,
            "spacing": "proportional",
            "location": "right",
        },
        ax=ax,
    )
    colorbar = ax.collections[0].colorbar
    colorbar.set_ticks(list(range(levels)))
    colorbar.set_label("缺失项个数", rotation=90, labelpad=14, fontsize=fs(10), color="black")
    colorbar.ax.tick_params(labelsize=fs(9), colors="black")

    ax.set_title("图5 各省能源结构原始数据缺失项计数热力图", fontsize=fs(17), pad=16)
    ax.set_xlabel("年份")
    ax.set_ylabel("省份")
    years = list(heatmap_df.columns)
    ax.set_xticks([i + 0.5 for i in range(len(years))])
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    ax.tick_params(axis="x", labelsize=fs(9), pad=6)
    ax.tick_params(axis="y", labelsize=fs(9), rotation=0, pad=6)

    flagged_rows = (
        pd.DataFrame({"province": df["province"], "year": df["year"], "missing_count": missing_count})
        .loc[lambda x: x["missing_count"] > 0, ["province", "year", "missing_count"]]
        .drop_duplicates()
    )
    note = "注：0 值和空值均视为缺失；色阶表示该省份-年份样本的缺失项个数。"
    fig.text(0.01, 0.02, note, ha="left", va="bottom", fontsize=fs(9.5), color="black")

    fig.tight_layout(rect=(0, 0.08, 0.95, 1))
    fig.savefig(OUT_DIR / "图5_变量缺失热力图.png", dpi=300)
    plt.close(fig)


def main() -> None:
    configure_matplotlib()
    create_missing_heatmap()
    print(f"saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
