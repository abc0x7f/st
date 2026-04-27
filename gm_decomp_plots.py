from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns


BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "prcd" / "结果_process1" / "分解_超效率SBM Malmquist 指数 -全局参比"
OUTPUT_DIR = BASE_DIR / "prcd" / "gm_decomp_plots"

REGION_MAP = {
    "北京": "东部", "天津": "东部", "河北": "东部", "上海": "东部", "江苏": "东部",
    "浙江": "东部", "福建": "东部", "山东": "东部", "广东": "东部", "海南": "东部",
    "山西": "中部", "安徽": "中部", "江西": "中部", "河南": "中部", "湖北": "中部", "湖南": "中部",
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
    "内蒙古": "西部", "广西": "西部", "重庆": "西部", "四川": "西部", "贵州": "西部", "云南": "西部",
    "西藏": "西部", "陕西": "西部", "甘肃": "西部", "青海": "西部", "宁夏": "西部", "新疆": "西部",
}


def configure_style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def find_file(pattern: str) -> Path:
    matches = [p for p in RESULT_DIR.rglob(pattern) if not p.name.startswith("~$")]
    if not matches:
        raise FileNotFoundError(f"未找到匹配文件: {pattern}")
    return matches[0]


def load_panel(path: Path, value_columns: list[str]) -> pd.DataFrame:
    df = pd.read_excel(path)
    required = {"year", "province", *value_columns}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} 缺少必要字段: {sorted(missing)}")

    df["province"] = df["province"].astype(str).str.strip()
    for col in value_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["year", "province", *value_columns]).copy()
    df["region"] = df["province"].map(REGION_MAP)
    return df.sort_values(["year", "province"]).reset_index(drop=True)


def load_and_average(path: Path, value_columns: list[str]) -> pd.DataFrame:
    df = load_panel(path, value_columns)
    return (
        df.groupby("year", as_index=False)[value_columns]
        .mean()
        .sort_values("year")
        .reset_index(drop=True)
    )


def _finalize_legend(ax: plt.Axes, ymax: float | None = None) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper right", ncol=2)
    if ymax is not None:
        ax.set_ylim(top=ymax)


def draw_trend_plot(
    df: pd.DataFrame,
    title: str,
    ylabel: str,
    series_config: list[tuple[str, str, str]],
    output_name: str,
) -> Path:
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ymax = max(float(df[col].max()) for col, _, _ in series_config)
    upper = max(1.12, ymax * 1.08)

    for col, label, color in series_config:
        sns.lineplot(
            data=df,
            x="year",
            y=col,
            marker="o",
            linewidth=2.2,
            color=color,
            label=label,
            ax=ax,
        )

    ax.axhline(1, color="#666666", linestyle="--", linewidth=1.2, label="基线 y=1")
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("时期")
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(7))
    ax.set_ylim(bottom=min(float(df[[c for c, _, _ in series_config]].min().min()) * 0.98, 0.95), top=upper)
    _finalize_legend(ax, upper)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()

    out = OUTPUT_DIR / output_name
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def draw_distribution_boxplot(panel_df: pd.DataFrame) -> Path:
    long_df = panel_df.melt(
        id_vars=["year", "province", "region"],
        value_vars=["tfpch", "effch", "techch"],
        var_name="指标",
        value_name="数值",
    )
    label_map = {"tfpch": "tfpch", "effch": "effch", "techch": "techch"}
    long_df["指标"] = long_df["指标"].map(label_map)

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    sns.boxplot(
        data=long_df,
        x="指标",
        y="数值",
        hue="指标",
        palette=["#2E8B57", "#5DADE2", "#E67E22"],
        width=0.55,
        linewidth=1.1,
        fliersize=3,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=long_df,
        x="指标",
        y="数值",
        color="#2F2F2F",
        alpha=0.20,
        jitter=0.18,
        size=2.2,
        ax=ax,
    )
    ax.axhline(1, color="#666666", linestyle="--", linewidth=1.2, label="基线 y=1")
    ymax = max(1.15, float(long_df["数值"].max()) * 1.08)
    ax.set_ylim(top=ymax)
    ax.set_title("tfpch、effch 与 techch 省际分布并列箱线图", fontsize=14)
    ax.set_xlabel("指标")
    ax.set_ylabel("指数数值")
    _finalize_legend(ax, ymax)
    fig.tight_layout()

    out = OUTPUT_DIR / "14-1_tfpch与effch与techch省际分布并列箱线图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def draw_region_trend_plot(panel_df: pd.DataFrame) -> Path:
    region_df = (
        panel_df.dropna(subset=["region"])
        .groupby(["year", "region"], as_index=False)[["tfpch", "effch", "techch"]]
        .mean()
    )
    region_order = ["东部", "中部", "西部", "东北"]
    palette = {"东部": "#2E8B57", "中部": "#5DADE2", "西部": "#E67E22", "东北": "#8E44AD"}

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), sharex=True, sharey=True)
    metric_config = [("tfpch", "GM（tfpch）"), ("effch", "effch"), ("techch", "techch")]
    ymax = max(float(region_df[col].max()) for col, _ in metric_config)
    upper = max(1.12, ymax * 1.10)
    ymin = min(float(region_df[col].min()) for col, _ in metric_config)
    lower = min(0.95, ymin * 0.98)

    for ax, (metric, title) in zip(axes, metric_config):
        sns.lineplot(
            data=region_df,
            x="year",
            y=metric,
            hue="region",
            hue_order=region_order,
            palette=palette,
            marker="o",
            linewidth=2.0,
            ax=ax,
        )
        ax.axhline(1, color="#666666", linestyle="--", linewidth=1.1, label="基线 y=1")
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("时期")
        ax.set_ylabel("指数均值")
        ax.set_ylim(lower, upper)
        plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    handles, labels = axes[-1].get_legend_handles_labels()
    if handles:
        axes[-1].legend(handles, labels, loc="upper right", ncol=1, fontsize=8.5)
    for ax in axes[:-1]:
        leg = ax.get_legend()
        if leg is not None:
            leg.remove()

    fig.suptitle("分区域 GM 趋势图", fontsize=14, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = OUTPUT_DIR / "14-2_分区域GM趋势图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def draw_province_rank_plot(panel_df: pd.DataFrame) -> Path:
    rank_df = (
        panel_df.groupby("province", as_index=False)["tfpch"]
        .mean()
        .sort_values("tfpch", ascending=False)
    )
    colors = sns.color_palette("Greens_r", n_colors=len(rank_df) + 2)[2:]

    fig, ax = plt.subplots(figsize=(9.5, 8.8))
    ax.barh(rank_df["province"], rank_df["tfpch"], color=colors, edgecolor="white", linewidth=0.6)
    ax.axvline(1, color="#666666", linestyle="--", linewidth=1.2, label="基线 y=1")
    ax.invert_yaxis()
    xmax = max(1.08, float(rank_df["tfpch"].max()) * 1.08)
    ax.set_xlim(left=min(float(rank_df["tfpch"].min()) * 0.98, 0.95), right=xmax)
    ax.set_title("各省平均 tfpch 排序图", fontsize=14)
    ax.set_xlabel("平均 tfpch")
    ax.set_ylabel("省份")
    _finalize_legend(ax, None)
    fig.tight_layout()

    out = OUTPUT_DIR / "14-3_各省平均tfpch排序图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    configure_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gm_file = find_file("*规模报酬可变VRS_0.xlsx")
    fgnz_file = find_file("FGNZ*.xlsx")
    rd_file = find_file("R&D*.xlsx")

    gm_panel = load_panel(gm_file, ["tfpch", "effch", "techch"])
    gm_df = (
        gm_panel.groupby("year", as_index=False)[["tfpch", "effch", "techch"]]
        .mean()
        .sort_values("year")
        .reset_index(drop=True)
    )
    fgnz_df = load_and_average(fgnz_file, ["tfpch", "effch", "techch", "pech", "sech"])
    rd_df = load_and_average(rd_file, ["tfpch", "pech", "ptechch", "SCH"])

    outputs = [
        draw_trend_plot(
            gm_df,
            "GM 及其分解项年度趋势图",
            "指数均值",
            [
                ("tfpch", "GM（tfpch）", "#2E8B57"),
                ("effch", "效率变化（effch）", "#5DADE2"),
                ("techch", "技术变化（techch）", "#E67E22"),
            ],
            "14_GM及其分解项年度趋势图.png",
        ),
        draw_distribution_boxplot(gm_panel),
        draw_region_trend_plot(gm_panel),
        draw_province_rank_plot(gm_panel),
        draw_trend_plot(
            fgnz_df,
            "FGNZ 分解趋势图",
            "指数均值",
            [
                ("tfpch", "tfpch", "#2E8B57"),
                ("effch", "effch", "#5DADE2"),
                ("techch", "techch", "#E67E22"),
                ("pech", "pech", "#8E44AD"),
                ("sech", "sech", "#C0392B"),
            ],
            "15_FGNZ分解趋势图.png",
        ),
        draw_trend_plot(
            rd_df,
            "RD 分解趋势图",
            "指数均值",
            [
                ("tfpch", "tfpch", "#2E8B57"),
                ("pech", "pech", "#8E44AD"),
                ("ptechch", "ptechch", "#E67E22"),
                ("SCH", "SCH", "#C0392B"),
            ],
            "16_RD分解趋势图.png",
        ),
    ]

    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
