import json
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import colormaps
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon, Rectangle


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "prcd" / "process2.csv"
STAGE1_DATA_PATH = BASE_DIR / "prcd" / "process1.csv"
MAP_PATH = BASE_DIR / "data" / "china.geojson"
OUTPUT_DIR = BASE_DIR / "prcd" / "eff_plots"
MAP_YEAR = 2022
KDE_YEARS = None
WEST_PROVINCES = ["内蒙古", "广西", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]

PROVINCE_NAME_MAP = {
    "北京市": "北京", "天津市": "天津", "上海市": "上海", "重庆市": "重庆",
    "河北省": "河北", "山西省": "山西", "辽宁省": "辽宁", "吉林省": "吉林",
    "黑龙江省": "黑龙江", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
    "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "海南省": "海南",
    "四川省": "四川", "贵州省": "贵州", "云南省": "云南", "陕西省": "陕西",
    "甘肃省": "甘肃", "青海省": "青海", "台湾省": "台湾",
    "内蒙古自治区": "内蒙古", "广西壮族自治区": "广西", "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}

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


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    required_columns = {"province", "year", "eff"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"缺少必要字段: {sorted(missing)}")

    df["province"] = df["province"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["eff"] = pd.to_numeric(df["eff"], errors="coerce")
    df = df.dropna(subset=["province", "year", "eff"]).copy()
    df["year"] = df["year"].astype(int)
    df["region"] = df["province"].map(REGION_MAP)
    return df.sort_values(["year", "province"]).reset_index(drop=True)


def load_stage1_data() -> pd.DataFrame:
    df = pd.read_csv(STAGE1_DATA_PATH)
    required_columns = {"province", "year", "GDP_constant", "Carbon"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"process1.csv 缺少必要字段: {sorted(missing)}")

    df["province"] = df["province"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["GDP_constant"] = pd.to_numeric(df["GDP_constant"], errors="coerce")
    df["Carbon"] = pd.to_numeric(df["Carbon"], errors="coerce")
    df = df.dropna(subset=["province", "year", "GDP_constant", "Carbon"]).copy()
    df["year"] = df["year"].astype(int)
    df = df.loc[df["GDP_constant"] > 0].copy()
    df["carbon_gdp"] = df["Carbon"] / df["GDP_constant"]
    return df.sort_values(["year", "province"]).reset_index(drop=True)


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


def save_year_mean_plot(df: pd.DataFrame) -> Path:
    year_mean = df.groupby("year", as_index=False)["eff"].mean()
    fig, ax = plt.subplots(figsize=(8.5, 5))
    sns.lineplot(
        data=year_mean,
        x="year",
        y="eff",
        marker="o",
        linewidth=2.4,
        color="#2E8B57",
        ax=ax,
        label="全国年度均值",
    )
    ax.set_title("全国碳排放效率年度均值折线图", fontsize=14)
    ax.set_xlabel("年份")
    ax.set_ylabel("碳排放效率年度均值")
    ax.set_xticks(year_mean["year"])
    ax.yaxis.set_major_locator(mticker.MaxNLocator(6))
    ax.legend(loc="best")
    fig.tight_layout()
    out = OUTPUT_DIR / "10_全国碳排放效率年度均值折线图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_kde_plot(df: pd.DataFrame) -> Path:
    years = sorted(df["year"].unique().tolist())
    if KDE_YEARS:
        years = [year for year in years if year in KDE_YEARS]
    colors = sns.color_palette("Greens", n_colors=len(years) + 2)[2:]

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    for color, year in zip(colors, years):
        year_values = df.loc[df["year"] == year, "eff"]
        sns.kdeplot(
            year_values,
            ax=ax,
            color=color,
            linewidth=2.2,
            fill=False,
            label=str(year),
            clip=(0, float(df["eff"].max())),
        )

    ax.set_title("省际碳排放效率核密度图", fontsize=14)
    ax.set_xlabel("碳排放效率")
    ax.set_ylabel("核密度")
    ax.set_xlim(left=0)
    ax.legend(title="年份", ncol=2, fontsize=9, title_fontsize=10, loc="best")
    fig.tight_layout()
    out = OUTPUT_DIR / "11_省际碳排放效率核密度图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_region_boxplot(df: pd.DataFrame) -> Path:
    box_df = df.dropna(subset=["region"]).copy()
    region_order = ["东部", "中部", "西部", "东北"]
    palette = ["#2E8B57", "#66C2A4", "#9ADBC4", "#CFEEDC"]

    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    sns.boxplot(
        data=box_df,
        x="region",
        y="eff",
        hue="region",
        order=region_order,
        palette=palette,
        width=0.55,
        linewidth=1.1,
        fliersize=3,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=box_df,
        x="region",
        y="eff",
        order=region_order,
        color="#1F5133",
        alpha=0.28,
        size=2.8,
        jitter=0.18,
        ax=ax,
    )
    ax.set_title("区域效率差异箱线图", fontsize=14)
    ax.set_xlabel("区域")
    ax.set_ylabel("碳排放效率")
    fig.tight_layout()
    out = OUTPUT_DIR / "13_区域效率差异箱线图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_west_eff_trend_plot(df: pd.DataFrame) -> Path:
    west_df = df.loc[df["province"].isin(WEST_PROVINCES)].copy()
    province_order = (
        west_df.groupby("province")["eff"]
        .mean()
        .sort_values(ascending=False)
        .index
        .tolist()
    )
    palette = sns.color_palette("tab20", n_colors=len(province_order))
    color_map = {province: color for province, color in zip(province_order, palette)}

    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    sns.lineplot(
        data=west_df,
        x="year",
        y="eff",
        hue="province",
        hue_order=province_order,
        palette=color_map,
        marker="o",
        linewidth=1.9,
        ax=ax,
    )
    ax.set_title("西部各省碳排放效率年际变化图", fontsize=14)
    ax.set_xlabel("年份")
    ax.set_ylabel("碳排放效率")
    ax.set_xticks(sorted(west_df["year"].unique()))
    ax.set_ylim(0, 1.5)
    ax.legend(title="省份", ncol=2, fontsize=8.5, title_fontsize=9.5, loc="upper right")
    fig.tight_layout()
    out = OUTPUT_DIR / "13-1_西部各省碳排放效率年际变化图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_west_carbon_gdp_plot(stage1_df: pd.DataFrame) -> Path:
    west_df = stage1_df.loc[stage1_df["province"].isin(WEST_PROVINCES)].copy()
    summary = (
        west_df.groupby("province", as_index=False)["carbon_gdp"]
        .mean()
        .sort_values("carbon_gdp")
    )
    colors = sns.color_palette("Greens", n_colors=len(summary) + 2)[2:]

    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    ax.barh(
        summary["province"],
        summary["carbon_gdp"],
        color=colors,
        edgecolor="white",
        linewidth=0.6,
    )
    ax.set_title("西部各省单位 GDP 碳排放对比图", fontsize=14)
    ax.set_xlabel("单位 GDP 碳排放（Carbon / GDP_constant）")
    ax.set_ylabel("省份")
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    fig.tight_layout()
    out = OUTPUT_DIR / "13-2_西部各省单位GDP碳排放对比图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def save_eff_map(df: pd.DataFrame) -> Path:
    with MAP_PATH.open("r", encoding="utf-8") as f:
        geo = json.load(f)

    year_df = df.loc[df["year"] == MAP_YEAR, ["province", "eff"]].copy()
    if year_df.empty:
        raise ValueError(f"数据中不存在 {MAP_YEAR} 年。")
    value_map = dict(zip(year_df["province"], year_df["eff"]))

    eff_min = float(year_df["eff"].min())
    eff_max = float(year_df["eff"].max())
    seg_bounds = np.linspace(eff_min, eff_max, 7)
    seg_bounds[0] = np.floor(seg_bounds[0] * 10) / 10
    seg_bounds[-1] = np.ceil(seg_bounds[-1] * 10) / 10
    seg_bounds = np.unique(np.round(seg_bounds, 2))
    if len(seg_bounds) < 3:
        seg_bounds = np.array([
            round(eff_min, 2),
            round((eff_min + eff_max) / 2, 2),
            round(eff_max, 2),
        ])

    cmap = colormaps["Greens"]
    norm = mcolors.BoundaryNorm(seg_bounds, cmap.N)

    main_features = []
    scs_features = []
    hainan_feature = None
    for feat in geo.get("features", []):
        props = feat.get("properties", {})
        raw_name = (
            props.get("name")
            or props.get("NAME")
            or props.get("province")
            or props.get("fullname")
            or ""
        )
        if props.get("adchar") == "JD" or "南海诸岛" in str(raw_name):
            scs_features.append(feat)
            continue
        main_features.append(feat)
        if "海南" in str(raw_name):
            hainan_feature = feat

    fig = plt.figure(figsize=(14, 11))
    ax = fig.add_axes([0.09, 0.10, 0.78, 0.82])

    patches = []
    facecolors = []
    for feat in main_features:
        props = feat.get("properties", {})
        raw_name = (
            props.get("name")
            or props.get("NAME")
            or props.get("province")
            or props.get("fullname")
            or ""
        )
        province = normalize_province_name(raw_name)
        value = value_map.get(province)
        color = "#D9D9D9" if value is None else cmap(norm(value))
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            patches.append(Polygon(poly, closed=True))
            facecolors.append(color)

    collection = PatchCollection(
        patches,
        facecolor=facecolors,
        edgecolor="black",
        linewidths=1.2,
    )
    ax.add_collection(collection)

    lon_min, lon_max = 73, 136
    lat_min, lat_max = 15, 55
    center_lat = (lat_min + lat_max) / 2
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect(1 / np.cos(np.radians(center_lat)))
    ax.grid(False)

    lon_ticks = np.arange(75, 136, 5)
    lat_ticks = np.arange(15, 56, 5)
    lon_minor = np.arange(73, 137, 1)
    lat_minor = np.arange(15, 56, 1)
    ax.set_xticks(lon_ticks)
    ax.set_yticks(lat_ticks)
    ax.set_xticks(lon_minor, minor=True)
    ax.set_yticks(lat_minor, minor=True)
    ax.set_xticklabels([f"{int(v)}°E" for v in lon_ticks], fontsize=8)
    ax.set_yticklabels([f"{int(v)}°N" for v in lat_ticks], fontsize=8)
    ax.tick_params(which="major", direction="in", length=6, width=1.2, top=True, bottom=True, left=True, right=True)
    ax.tick_params(which="minor", direction="in", length=3, width=0.8, top=True, bottom=True, left=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(2.5)
        spine.set_color("black")
    ax.set_title(f"{MAP_YEAR} 年省际碳排放效率分级地图", fontsize=16, fontweight="bold", pad=12)

    ax_scs = fig.add_axes([0.70, 0.14, 0.14, 0.22])
    scs_patches = []
    scs_colors = []
    if hainan_feature is not None:
        hainan_value = value_map.get("海南")
        hainan_color = "#D9D9D9" if hainan_value is None else cmap(norm(hainan_value))
        for poly in iter_feature_polygons(hainan_feature.get("geometry", {})):
            scs_patches.append(Polygon(poly, closed=True))
            scs_colors.append(hainan_color)
    for feat in scs_features:
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            scs_patches.append(Polygon(poly, closed=True))
            scs_colors.append("#D9D9D9")
    if scs_patches:
        scs_collection = PatchCollection(
            scs_patches,
            facecolor=scs_colors,
            edgecolor="black",
            linewidths=0.6,
        )
        ax_scs.add_collection(scs_collection)
    ax_scs.set_xlim(106, 123)
    ax_scs.set_ylim(2, 26)
    ax_scs.set_aspect(1 / np.cos(np.radians(14)))
    ax_scs.set_xticks([])
    ax_scs.set_yticks([])
    ax_scs.grid(False)
    for spine in ax_scs.spines.values():
        spine.set_linewidth(1.8)
        spine.set_color("black")
    ax_scs.set_title("南海诸岛", fontsize=8, pad=2)

    compass_x = lon_min + 3.2
    compass_y = lat_max - 5.3
    ax.annotate(
        "",
        xy=(compass_x, compass_y + 2.2),
        xytext=(compass_x, compass_y),
        arrowprops=dict(arrowstyle="-|>", color="black", lw=2.5, mutation_scale=15),
        zorder=6,
    )
    ax.text(
        compass_x,
        compass_y + 2.55,
        "N",
        ha="center",
        va="bottom",
        fontsize=13,
        fontweight="bold",
        zorder=6,
    )

    ax_leg = fig.add_axes([0.09, 0.10, 0.18, 0.36])
    ax_leg.set_xlim(0, 10)
    ax_leg.set_ylim(0, 20)
    ax_leg.axis("off")

    lat_ref = 25.0
    km_per_deg = 111.32 * np.cos(np.radians(lat_ref))
    bar_km = 500
    bar_deg = bar_km / km_per_deg
    main_ax_w_in = 0.78 * 14
    leg_ax_w_in = 0.18 * 14
    map_deg_per_in = (lon_max - lon_min) / main_ax_w_in
    bar_in = bar_deg / map_deg_per_in
    bar_leg = bar_in / leg_ax_w_in * 10
    sx, sy = 1.0, 13.2
    half_bar = bar_leg / 2
    ax_leg.add_patch(Rectangle((sx, sy), half_bar, 0.40, fc="black", ec="black", lw=0.8))
    ax_leg.add_patch(Rectangle((sx + half_bar, sy), half_bar, 0.40, fc="white", ec="black", lw=0.8))
    ax_leg.text(sx, sy - 0.45, "0", ha="center", fontsize=6.5)
    ax_leg.text(sx + half_bar, sy - 0.45, f"{bar_km // 2}", ha="center", fontsize=6.5)
    ax_leg.text(sx + bar_leg, sy - 0.45, f"{bar_km} km", ha="center", fontsize=6.5)

    box_w, box_h = 2.0, 1.1
    lx, ly_start = 1.0, 11.0
    for idx in range(len(seg_bounds) - 1):
        lo, hi = seg_bounds[idx], seg_bounds[idx + 1]
        mid_val = (lo + hi) / 2
        color = cmap(norm(mid_val))
        y_pos = ly_start - idx * (box_h + 0.25)
        ax_leg.add_patch(Rectangle((lx, y_pos), box_w, box_h, fc=color, ec="black", lw=0.8))
        ax_leg.text(lx + box_w + 0.35, y_pos + box_h / 2, f"{lo:.2f} – {hi:.2f}", va="center", ha="left", fontsize=8)
    ax_leg.text(lx + box_w / 2 + 1.0, 3.0, "碳排放效率", ha="center", va="center", fontsize=10, fontweight="bold")

    out = OUTPUT_DIR / "12_省际碳排放效率分级地图.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    configure_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    stage1_df = load_stage1_data()

    outputs = [
        save_year_mean_plot(df),
        save_kde_plot(df),
        save_eff_map(df),
        save_region_boxplot(df),
        save_west_eff_trend_plot(df),
        save_west_carbon_gdp_plot(stage1_df),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
