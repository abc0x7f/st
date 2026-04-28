from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "prcd" / "chapter4_figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def draw_box(ax, x: float, y: float, w: float, h: float, title: str, lines: list[str], fc: str) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.2,
        edgecolor="#385170",
        facecolor=fc,
    )
    ax.add_patch(patch)
    text = title + "\n" + "\n".join(lines)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=10,
        color="#102A43",
        linespacing=1.35,
    )


def draw_arrow(ax, start: tuple[float, float], end: tuple[float, float]) -> None:
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=16,
        linewidth=1.5,
        color="#486581",
    )
    ax.add_patch(arrow)


def create_flowchart() -> None:
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    draw_box(
        ax,
        0.05,
        0.73,
        0.26,
        0.2,
        "统计年鉴与公报",
        [
            "中国统计年鉴：人口、GDP、第二产业占比、城镇化、开放度",
            "全国科技经费投入统计公报：R&D 强度",
            "资本存量测算表：Capital",
        ],
        "#EAF2F8",
    )
    draw_box(
        ax,
        0.37,
        0.73,
        0.26,
        0.2,
        "能源与排放数据",
        [
            "中国能源统计年鉴：能源消费总量、煤炭消费",
            "构造 es=煤炭消费/能源消费总量",
            "CEADs：Carbon",
        ],
        "#E8F8F5",
    )
    draw_box(
        ax,
        0.69,
        0.73,
        0.26,
        0.2,
        "夜间灯光遥感数据",
        [
            "年度夜间灯光影像",
            "省级聚合后得到 ntl",
            "进一步构造 lntl=ln(ntl+1)",
        ],
        "#FEF5E7",
    )

    draw_box(
        ax,
        0.2,
        0.47,
        0.6,
        0.16,
        "样本统一与预处理",
        [
            "保留 2015-2022 年、30 省面板样本",
            "统一省份名称、年份格式与指标单位",
            "缺失值优先查补，少量连续变量拟合或插值",
            "GDP 平减到 2015 年不变价",
        ],
        "#F4ECF7",
    )

    draw_box(
        ax,
        0.08,
        0.2,
        0.38,
        0.17,
        "第一阶段样本表：process1.csv",
        [
            "字段：year, province, Population, Capital,",
            "energy_total, GDP_constant, Carbon",
            "用于超效率 SBM 测算碳排放效率 eff",
        ],
        "#EBF5FB",
    )
    draw_box(
        ax,
        0.54,
        0.2,
        0.38,
        0.17,
        "第二阶段样本表：process2.csv",
        [
            "字段：province, year, lntl, ind, urb, rd,",
            "open, es, eff",
            "用于双固定效应与机制检验",
        ],
        "#EAF7EE",
    )

    draw_box(
        ax,
        0.33,
        0.03,
        0.34,
        0.1,
        "最终研究样本",
        [
            "2015-2022 年中国 30 省平衡面板",
            "形成效率测度样本与回归样本",
        ],
        "#FCF3CF",
    )

    for xpos in (0.18, 0.5, 0.82):
        draw_arrow(ax, (xpos, 0.73), (0.5, 0.63))
    draw_arrow(ax, (0.39, 0.47), (0.27, 0.37))
    draw_arrow(ax, (0.61, 0.47), (0.73, 0.37))
    draw_arrow(ax, (0.27, 0.2), (0.43, 0.13))
    draw_arrow(ax, (0.73, 0.2), (0.57, 0.13))

    ax.set_title("图4 样本构建流程图", fontsize=18, pad=18, color="#102A43")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "图4_样本构建流程图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_missing_heatmap() -> None:
    path = next((ROOT / "data").rglob("各省能源结构2003-2022.xlsx"))
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

    fig, ax = plt.subplots(figsize=(11, 8.5))
    sns.heatmap(
        heatmap_df,
        cmap=sns.light_palette("#D64541", as_cmap=True),
        cbar=True,
        linewidths=0.6,
        linecolor="#D9E2EC",
        annot=True,
        fmt=".0f",
        annot_kws={"fontsize": 8},
        ax=ax,
    )
    colorbar = ax.collections[0].colorbar
    max_missing = int(heatmap_df.max().max()) if not heatmap_df.empty else 0
    ticks = list(range(0, max_missing + 1))
    if len(ticks) > 8:
        step = max(1, round(max_missing / 6))
        ticks = list(range(0, max_missing + 1, step))
        if ticks[-1] != max_missing:
            ticks.append(max_missing)
    colorbar.set_ticks(ticks)
    colorbar.set_label("缺失项个数", rotation=90, labelpad=12)

    ax.set_title("图5 各省能源结构原始数据缺失项计数热力图", fontsize=17, pad=14)
    ax.set_xlabel("年份")
    ax.set_ylabel("省份")
    years = list(heatmap_df.columns)
    ax.set_xticks([i + 0.5 for i in range(len(years))])
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    ax.tick_params(axis="y", rotation=0)

    flagged_rows = (
        pd.DataFrame({"province": df["province"], "year": df["year"], "missing_count": missing_count})
        .loc[lambda x: x["missing_count"] > 0, ["province", "year", "missing_count"]]
        .drop_duplicates()
    )
    note = "注：0 值和空值均视为缺失；色阶与单元格数字表示该省份-年份样本的缺失项个数。"
    fig.text(0.01, 0.02, note, ha="left", va="bottom", fontsize=9.5, color="#52606D")

    fig.tight_layout(rect=(0, 0.06, 0.96, 1))
    fig.savefig(OUT_DIR / "图5_变量缺失热力图.png", dpi=300)
    plt.close(fig)


def create_boxplots() -> None:
    df1 = pd.read_csv(ROOT / "prcd" / "process1.csv")
    df2 = pd.read_csv(ROOT / "prcd" / "process2.csv")

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

    fig, axes = plt.subplots(3, 4, figsize=(16, 10))
    axes = axes.flatten()

    for ax, (name, series, color, source) in zip(axes, items):
        sns.boxplot(y=series, ax=ax, color=color, width=0.42, linewidth=1.2, fliersize=3)
        ax.set_title(f"{name}\n({source})", fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

    for ax in axes[len(items):]:
        ax.axis("off")

    fig.suptitle("图6 核心变量箱线图", fontsize=18, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT_DIR / "图6_核心变量箱线图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    configure_matplotlib()
    create_flowchart()
    create_missing_heatmap()
    create_boxplots()
    print(f"saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
