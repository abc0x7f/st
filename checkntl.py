import json
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import colormaps
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "prcd" / "process2.csv"
OUTPUT_DIR = BASE_DIR / "prcd" / "ntl_check"
MAP_PATHS = [
    BASE_DIR / "data" / "china_provinces.geojson",
    BASE_DIR / "data" / "china.geojson",
    BASE_DIR / "data" / "中国省级.geojson",
]
MAP_YEAR = 2022

PROVINCE_NAME_MAP = {
    "北京市": "北京",
    "天津市": "天津",
    "上海市": "上海",
    "重庆市": "重庆",
    "河北省": "河北",
    "山西省": "山西",
    "辽宁省": "辽宁",
    "吉林省": "吉林",
    "黑龙江省": "黑龙江",
    "江苏省": "江苏",
    "浙江省": "浙江",
    "安徽省": "安徽",
    "福建省": "福建",
    "江西省": "江西",
    "山东省": "山东",
    "河南省": "河南",
    "湖北省": "湖北",
    "湖南省": "湖南",
    "广东省": "广东",
    "海南省": "海南",
    "四川省": "四川",
    "贵州省": "贵州",
    "云南省": "云南",
    "陕西省": "陕西",
    "甘肃省": "甘肃",
    "青海省": "青海",
    "台湾省": "台湾",
    "内蒙古自治区": "内蒙古",
    "广西壮族自治区": "广西",
    "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏",
    "新疆维吾尔自治区": "新疆",
    "香港特别行政区": "香港",
    "澳门特别行政区": "澳门",
}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    required_columns = {"province", "year", "lntl"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"缺少必要字段: {sorted(missing)}")

    df["year"] = df["year"].astype(int)
    df["lntl"] = pd.to_numeric(df["lntl"], errors="coerce")
    df["ntl"] = np.exp(df["lntl"]) - 1
    return df.sort_values(["province", "year"]).reset_index(drop=True)


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


def gradient_colors(name: str, n: int, start: float = 0.35, end: float = 0.9) -> list:
    cmap = colormaps[name]
    if n <= 1:
        return [cmap((start + end) / 2)]
    return [cmap(start + (end - start) * i / (n - 1)) for i in range(n)]


def draw_gradient_histogram(
    ax: plt.Axes,
    values: pd.Series,
    title: str,
    xlabel: str,
    cmap_name: str,
    kde_color: str,
) -> None:
    counts, bin_edges = np.histogram(values, bins=30)
    widths = np.diff(bin_edges)
    colors = gradient_colors(cmap_name, len(counts))

    ax.bar(
        bin_edges[:-1],
        counts,
        width=widths,
        align="edge",
        color=colors,
        edgecolor="white",
        linewidth=0.6,
        label="频数柱",
    )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("频数")
    ax.set_ylim(bottom=0)

    ax_density = ax.twinx()
    sns.kdeplot(values, color=kde_color, linewidth=2.2, label="核密度曲线", ax=ax_density)
    ax_density.set_ylabel("密度")
    ax_density.set_ylim(bottom=0)
    ax_density.xaxis.set_visible(False)
    ax_density.spines["bottom"].set_visible(False)

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax_density.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper right")


def save_distribution_plot(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    draw_gradient_histogram(axes[0], df["ntl"], "ntl 分布", "ntl", "Blues", "#1F4E79")
    draw_gradient_histogram(axes[1], df["lntl"], "lntl 分布", "lntl", "Oranges", "#C65D00")
    fig.suptitle("夜间灯光指标分布检验", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "01_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_time_series_plots(df: pd.DataFrame) -> None:
    year_mean = df.groupby("year", as_index=False)["ntl"].mean()

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.lineplot(
        data=year_mean,
        x="year",
        y="ntl",
        marker="o",
        linewidth=2,
        label="全国年度均值",
        ax=ax,
    )
    ax.set_title("ntl 年度均值")
    ax.set_xlabel("year")
    ax.set_ylabel("mean ntl")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "02_year_mean.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.5))
    sns.lineplot(
        data=df,
        x="year",
        y="ntl",
        hue="province",
        legend="full",
        linewidth=1.2,
        alpha=0.8,
        ax=ax,
    )
    ax.set_title("各省 ntl 年际变化")
    ax.set_xlabel("year")
    ax.set_ylabel("ntl")
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(
            handles=handles,
            labels=labels,
            title="province",
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            fontsize=8,
            title_fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "03_province_trend.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_spatial_proxy_plot(df: pd.DataFrame) -> None:
    province_stats = (
        df.groupby("province", as_index=False)
        .agg(ntl=("ntl", "mean"), lntl=("lntl", "mean"))
        .sort_values("ntl", ascending=False)
    )

    fig, ax = plt.subplots(figsize=(9.5, 10))
    ax.barh(
        province_stats["province"],
        province_stats["ntl"],
        color="#54A24B",
        edgecolor="#2E6B33",
        linewidth=0.6,
        label="ntl 均值",
    )
    ax.barh(
        province_stats["province"],
        province_stats["lntl"],
        facecolor=(1, 1, 1, 0),
        edgecolor="#C65D00",
        linewidth=1.2,
        hatch="///",
        label="lntl 均值",
    )
    ax.invert_yaxis()
    ax.set_title("各省 ntl / lntl 均值排序")
    ax.set_xlabel("value")
    ax.set_ylabel("province")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "04_province_mean_rank.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def find_map_path() -> Path | None:
    for path in MAP_PATHS:
        if path.exists():
            return path
    return None


def normalize_province_name(name: str) -> str:
    return PROVINCE_NAME_MAP.get(str(name).strip(), str(name).strip())


def iter_feature_polygons(geometry: dict) -> list[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    polygons = []

    if gtype == "Polygon":
        if coords:
            polygons.append([(x, y) for x, y in coords[0]])
    elif gtype == "MultiPolygon":
        for polygon in coords:
            if polygon:
                polygons.append([(x, y) for x, y in polygon[0]])
    return polygons


def save_lntl_map(df: pd.DataFrame) -> str:
    map_path = find_map_path()
    if map_path is None:
        return "未生成省级地图: 缺少省级 GeoJSON 底图文件。"

    with map_path.open("r", encoding="utf-8") as f:
        geo = json.load(f)

    year_df = df.loc[df["year"] == MAP_YEAR, ["province", "lntl"]].copy()
    if year_df.empty:
        return f"未生成省级地图: 数据中没有 {MAP_YEAR} 年。"

    value_map = dict(zip(year_df["province"], year_df["lntl"]))
    cmap = colormaps["YlOrRd"]
    norm = mcolors.Normalize(vmin=year_df["lntl"].min(), vmax=year_df["lntl"].max())

    fig, ax = plt.subplots(figsize=(10, 8))
    patches = []
    facecolors = []

    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        raw_name = props.get("name") or props.get("NAME") or props.get("province") or props.get("fullname")
        province = normalize_province_name(raw_name)
        value = value_map.get(province)
        color = "#D9D9D9" if value is None else cmap(norm(value))

        for polygon in iter_feature_polygons(feature.get("geometry", {})):
            patches.append(Polygon(polygon, closed=True))
            facecolors.append(color)

    if not patches:
        return f"未生成省级地图: {map_path.name} 无法解析为省级面数据。"

    collection = PatchCollection(patches, facecolor=facecolors, edgecolor="white", linewidths=0.5)
    ax.add_collection(collection)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{MAP_YEAR} 年各省 lntl 分级图", fontsize=14)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("lntl")

    fig.tight_layout()
    output_path = OUTPUT_DIR / f"05_lntl_map_{MAP_YEAR}.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return f"已生成省级地图: {output_path}"


def build_summary(df: pd.DataFrame, map_message: str) -> str:
    year_mean = df.groupby("year")["ntl"].mean().round(4)

    changes = df.copy()
    changes["pct_change"] = changes.groupby("province")["ntl"].pct_change()
    jump_table = (
        changes.loc[changes["pct_change"].notna(), ["province", "year", "ntl", "pct_change"]]
        .assign(abs_pct_change=lambda x: x["pct_change"].abs())
        .sort_values("abs_pct_change", ascending=False)
        .head(10)
    )

    yearly_change_share = (
        changes.groupby("year")["pct_change"]
        .apply(lambda x: x.gt(0).mean() if x.notna().any() else np.nan)
        .round(4)
    )

    province_mean = df.groupby("province")["ntl"].mean().sort_values(ascending=False).round(4)

    lines = [
        "# 夜间灯光指标检查摘要",
        "",
        "## 1. 样本概况",
        f"- 样本量: {len(df)}",
        f"- 年份范围: {df['year'].min()}-{df['year'].max()}",
        f"- 省份数量: {df['province'].nunique()}",
        f"- ntl 最小值: {df['ntl'].min():.6f}",
        f"- ntl 最大值: {df['ntl'].max():.6f}",
        "",
        "## 2. 年度均值",
    ]
    lines.extend([f"- {year}: {value:.4f}" for year, value in year_mean.items()])

    lines.extend(
        [
            "",
            "## 3. 各年正增长省份占比",
            *[
                f"- {year}: {'NA' if pd.isna(value) else f'{value:.2%}'}"
                for year, value in yearly_change_share.items()
            ],
            "",
            "## 4. 绝对跳变最大的 10 个观测",
        ]
    )

    for row in jump_table.itertuples(index=False):
        lines.append(f"- {row.province} {row.year}: ntl={row.ntl:.4f}, pct_change={row.pct_change:.2%}")

    lines.extend(
        [
            "",
            "## 5. 省均值前 10 名",
            *[f"- {province}: {value:.4f}" for province, value in province_mean.head(10).items()],
            "",
            "## 6. 图形解释提示",
            "- 图1左轴是频数，右轴是核密度；核密度曲线只是直方图的平滑版，不要求严格对称。",
            "- `lntl` 只要比 `ntl` 偏态更弱、更接近单峰，就说明对数化有效。",
            "- 图4中绿色实心柱是 `ntl`，橙色斜线透明柱是 `lntl`。",
            "",
            "## 7. 地图输出",
            f"- {map_message}",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_style()

    df = load_data()
    df[["year", "province", "ntl"]].to_csv(OUTPUT_DIR / "ntl.csv", index=False, encoding="utf-8-sig")

    save_distribution_plot(df)
    save_time_series_plots(df)
    save_spatial_proxy_plot(df)
    map_message = save_lntl_map(df)

    summary_text = build_summary(df, map_message)
    (OUTPUT_DIR / "summary.md").write_text(summary_text, encoding="utf-8")

    print(f"已生成输出目录: {OUTPUT_DIR}")
    print(f"已导出 ntl 数据: {OUTPUT_DIR / 'ntl.csv'}")
    print("已生成图形:")
    print(f"- {OUTPUT_DIR / '01_distribution.png'}")
    print(f"- {OUTPUT_DIR / '02_year_mean.png'}")
    print(f"- {OUTPUT_DIR / '03_province_trend.png'}")
    print(f"- {OUTPUT_DIR / '04_province_mean_rank.png'}")
    print(f"- {map_message}")
    print(f"已生成摘要: {OUTPUT_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
