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
from matplotlib.patches import Polygon, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "最终数据" / "第二阶段_基础.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "数据处理" / "20_夜间灯光指标检查"
MAP_PATHS = [
    PROJECT_ROOT / "data" / "外部资料" / "中国省级地图.geojson",
    PROJECT_ROOT / "data" / "china_provinces.geojson",
    PROJECT_ROOT / "data" / "china.geojson",
    PROJECT_ROOT / "data" / "中国省级.geojson",
]
MAP_YEAR = 2022
FONT_SIZE_DELTA = 4

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


def fs(size: float) -> float:
    return size + FONT_SIZE_DELTA


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
    plt.rcParams["font.family"] = ["Times New Roman", "SimSun", "DejaVu Serif"]
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif"]
    plt.rcParams["font.sans-serif"] = ["SimSun", "SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = fs(10)
    plt.rcParams["axes.titlesize"] = fs(12)
    plt.rcParams["axes.labelsize"] = fs(10)
    plt.rcParams["xtick.labelsize"] = fs(9)
    plt.rcParams["ytick.labelsize"] = fs(9)
    plt.rcParams["legend.fontsize"] = fs(9)


def gradient_colors(name: str, n: int, start: float = 0.35, end: float = 0.9) -> list:
    cmap = colormaps[name]
    if n <= 1:
        return [cmap((start + end) / 2)]
    return [cmap(start + (end - start) * i / (n - 1)) for i in range(n)]


# ═══════════════════════════════════════════════════════════════
# Figure 1: Distribution — clip x<0, remove density-side gridlines
# ═══════════════════════════════════════════════════════════════

def draw_gradient_histogram(
    ax, values, title, xlabel, cmap_name, kde_color,
    clip_negative=False, force_xlim_left=None,
):
    if clip_negative:
        values = values[values >= 0]

    counts, bin_edges = np.histogram(values, bins=30)
    if clip_negative:
        mask = bin_edges[:-1] >= 0
        counts = counts[mask]
        bin_edges = np.append(bin_edges[:-1][mask], bin_edges[1:][mask][-1])

    widths = np.diff(bin_edges)
    colors = gradient_colors(cmap_name, len(counts))
    ax.bar(bin_edges[:-1], counts, width=widths, align="edge",
           color=colors, edgecolor="white", linewidth=0.6, label="频数柱")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("频数")
    ax.set_ylim(bottom=0)
    if clip_negative:
        ax.set_xlim(left=0)
    if force_xlim_left is not None:
        ax.set_xlim(left=force_xlim_left)

    ax_density = ax.twinx()
    # KDE 从第二个柱开始画
    kde_clip = (bin_edges[1], values.max())
    kw = dict(color=kde_color, linewidth=2.2, label="核密度曲线",
              ax=ax_density, clip=kde_clip)
    sns.kdeplot(values, **kw)
    ax_density.set_ylabel("密度")
    ax_density.set_ylim(bottom=0)
    ax_density.grid(False)                    # ← 不画灰色横线
    ax_density.xaxis.set_visible(False)
    ax_density.spines["bottom"].set_visible(False)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax_density.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=fs(9), frameon=True, borderaxespad=0.8)


def save_distribution_plot(df):
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.2))
    draw_gradient_histogram(axes[0], df["ntl"], "ntl 分布", "ntl",
                            "Blues", "#1F4E79", clip_negative=True)
    draw_gradient_histogram(axes[1], df["lntl"], "lntl 分布", "lntl",
                            "Oranges", "#C65D00", force_xlim_left=0)
    fig.suptitle("夜间灯光指标分布检验", fontsize=fs(14))
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUTPUT_DIR / "01_指标分布图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Figures 2 & 3: Time series (unchanged)
# ═══════════════════════════════════════════════════════════════

def save_time_series_plots(df):
    year_mean = df.groupby("year", as_index=False)["ntl"].mean()
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    sns.lineplot(data=year_mean, x="year", y="ntl",
                 marker="o", linewidth=2, label="全国年度均值", ax=ax)
    ax.set_title("ntl 年度均值"); ax.set_xlabel("year"); ax.set_ylabel("mean ntl")
    ax.legend(fontsize=fs(9), frameon=True, borderaxespad=0.8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "02_年度均值图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(15.5, 8.2))
    sns.lineplot(data=df, x="year", y="ntl", hue="province",
                 legend="full", linewidth=1.2, alpha=0.8, ax=ax)
    ax.set_title("各省 ntl 年际变化"); ax.set_xlabel("year"); ax.set_ylabel("ntl")
    h, l = ax.get_legend_handles_labels()
    if h:
        ax.legend(handles=h, labels=l, title="province",
                  bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=fs(8), title_fontsize=fs(9),
                  frameon=True, borderaxespad=0.8, ncol=1)
    fig.tight_layout(rect=(0, 0, 0.83, 1))
    fig.savefig(OUTPUT_DIR / "03_各省变化趋势图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Figure 4: Province mean rank — blue-orange solid, dark→light
# ═══════════════════════════════════════════════════════════════

def save_spatial_proxy_plot(df):
    ps = (df.groupby("province", as_index=False)
          .agg(ntl=("ntl", "mean"), lntl=("lntl", "mean"))
          .sort_values("ntl", ascending=False))
    n = len(ps)
    # dark → light  (top = dark, bottom = light)
    blue_c  = gradient_colors("Blues",   n, start=0.85, end=0.25)
    orange_c = gradient_colors("Oranges", n, start=0.85, end=0.25)

    fig, ax = plt.subplots(figsize=(11.5, 12.0))
    y_pos = np.arange(n)
    ax.barh(y_pos, ps["ntl"].values, color=blue_c,
            edgecolor="none", linewidth=0, label="ntl 均值")
    ax.barh(y_pos, ps["lntl"].values, color=orange_c,
            edgecolor="none", linewidth=0, label="lntl 均值")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ps["province"].values)
    ax.invert_yaxis()
    ax.set_title("各省 ntl / lntl 均值排序")
    ax.set_xlabel("value"); ax.set_ylabel("province")
    ax.legend(fontsize=fs(9), frameon=True, borderaxespad=0.8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "04_各省均值排序图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# Figure 5: Cartographic lntl map
# ═══════════════════════════════════════════════════════════════

def find_map_path():
    for p in MAP_PATHS:
        if p.exists():
            return p
    return None

def normalize_province_name(name):
    return PROVINCE_NAME_MAP.get(str(name).strip(), str(name).strip())

def iter_feature_polygons(geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    polys = []
    if gtype == "Polygon":
        if coords:
            polys.append([(x, y) for x, y in coords[0]])
    elif gtype == "MultiPolygon":
        for polygon in coords:
            if polygon:
                polys.append([(x, y) for x, y in polygon[0]])
    return polys


def _draw_compass(ax, x, y, size):
    """Draw a north arrow (指北针) at data coordinates (x, y)."""
    arrow_len = size
    ax.annotate("", xy=(x, y + arrow_len), xytext=(x, y),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2))
    ax.text(x, y + arrow_len + size * 0.18, "N",
            ha="center", va="bottom", fontsize=fs(11), fontweight="bold", color="black")


def _draw_scale_bar(ax, x, y, bar_km, lat_ref):
    """Draw a scale bar at data coordinates; bar_km = length in km."""
    km_per_deg_lon = 111.32 * np.cos(np.radians(lat_ref))
    bar_deg = bar_km / km_per_deg_lon
    # draw alternating black/white segments (2 segments)
    half = bar_deg / 2
    ax.add_patch(Rectangle((x, y), half, 0.35, fc="black", ec="black", lw=0.8))
    ax.add_patch(Rectangle((x + half, y), half, 0.35, fc="white", ec="black", lw=0.8))
    ax.text(x, y - 0.3, "0", ha="center", va="top", fontsize=fs(7), color="black")
    ax.text(x + half, y - 0.3, f"{bar_km // 2:.0f}", ha="center", va="top", fontsize=fs(7), color="black")
    ax.text(x + bar_deg, y - 0.3, f"{bar_km:.0f} km", ha="center", va="top", fontsize=fs(7), color="black")


def save_lntl_map(df):
    map_path = find_map_path()
    if map_path is None:
        return "未生成省级地图: 缺少省级 GeoJSON 底图文件。"
    with map_path.open("r", encoding="utf-8") as f:
        geo = json.load(f)
    year_df = df.loc[df["year"] == MAP_YEAR, ["province", "lntl"]].copy()
    if year_df.empty:
        return f"未生成省级地图: 数据中没有 {MAP_YEAR} 年。"

    value_map = dict(zip(year_df["province"], year_df["lntl"]))

    # ── colour scheme: segmented YlOrRd ──
    seg_bounds = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    cmap = colormaps["YlOrRd"]
    norm = mcolors.BoundaryNorm(seg_bounds, cmap.N)

    # ── classify features ──
    main_features, scs_features, hainan_feature = [], [], None
    for feat in geo.get("features", []):
        props = feat.get("properties", {})
        raw = (props.get("name") or props.get("NAME")
               or props.get("province") or props.get("fullname") or "")
        if props.get("adchar") == "JD" or not raw.strip():
            scs_features.append(feat)
        else:
            main_features.append(feat)
            if "海南" in raw:
                hainan_feature = feat

    # ── figure layout ──
    fig = plt.figure(figsize=(16.5, 12.8))
    # main axes with room for ticks
    ax = fig.add_axes([0.09, 0.10, 0.78, 0.82])

    # ── draw main provinces ──
    patches, fcolors = [], []
    for feat in main_features:
        props = feat.get("properties", {})
        raw = (props.get("name") or props.get("NAME")
               or props.get("province") or props.get("fullname") or "")
        prov = normalize_province_name(raw)
        val = value_map.get(prov)
        color = "#D9D9D9" if val is None else cmap(norm(val))
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            patches.append(Polygon(poly, closed=True))
            fcolors.append(color)
    if not patches:
        return f"未生成省级地图: {map_path.name} 无法解析。"

    col = PatchCollection(patches, facecolor=fcolors,
                          edgecolor="black", linewidths=1.2)   # 黑色加粗边框
    ax.add_collection(col)

    # ── extent & aspect ──
    lon_min, lon_max = 73, 136
    lat_min, lat_max = 15, 55
    center_lat = (lat_min + lat_max) / 2
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect(1 / np.cos(np.radians(center_lat)))
    ax.grid(False)

    # ── lat / lon frame & ticks (四边主刻度 + 小刻度) ──
    lon_ticks = np.arange(75, 136, 5)
    lat_ticks = np.arange(15, 56, 5)
    lon_minor = np.arange(73, 137, 1)
    lat_minor = np.arange(15, 56, 1)
    ax.set_xticks(lon_ticks)
    ax.set_yticks(lat_ticks)
    ax.set_xticks(lon_minor, minor=True)
    ax.set_yticks(lat_minor, minor=True)
    ax.set_xticklabels([f"{int(v)}°E" for v in lon_ticks], fontsize=fs(8))
    ax.set_yticklabels([f"{int(v)}°N" for v in lat_ticks], fontsize=fs(8))
    ax.tick_params(which="major", direction="in", length=6, width=1.2,
                   top=True, bottom=True, left=True, right=True)
    ax.tick_params(which="minor", direction="in", length=3, width=0.8,
                   top=True, bottom=True, left=True, right=True)
    for sp in ax.spines.values():
        sp.set_linewidth(2.5)
        sp.set_color("black")
    ax.set_title(f"{MAP_YEAR} 年各省 lntl 分级图", fontsize=fs(16),
                 fontweight="bold", pad=12)

    # ══════════════ South China Sea inset (右下角) ══════════════
    ax_scs = fig.add_axes([0.70, 0.14, 0.14, 0.22])
    scs_p, scs_fc = [], []
    # Hainan in inset
    if hainan_feature:
        val = value_map.get("海南")
        c = "#D9D9D9" if val is None else cmap(norm(val))
        for poly in iter_feature_polygons(hainan_feature.get("geometry", {})):
            scs_p.append(Polygon(poly, closed=True)); scs_fc.append(c)
    # 九段线 islands
    for feat in scs_features:
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            scs_p.append(Polygon(poly, closed=True)); scs_fc.append("#D9D9D9")
    if scs_p:
        scs_col = PatchCollection(scs_p, facecolor=scs_fc,
                                  edgecolor="black", linewidths=0.6)
        ax_scs.add_collection(scs_col)
    ax_scs.set_xlim(106, 123); ax_scs.set_ylim(2, 26)
    ax_scs.set_aspect(1 / np.cos(np.radians(14)))
    ax_scs.set_xticks([]); ax_scs.set_yticks([])
    ax_scs.grid(False)
    for sp in ax_scs.spines.values():
        sp.set_linewidth(1.8); sp.set_color("black")
    ax_scs.set_title("南海诸岛", fontsize=fs(8), pad=4)

    # ══════════════ Legend area (左下角) ══════════════
    # Use a dedicated axes for legend elements
    ax_leg = fig.add_axes([0.08, 0.09, 0.22, 0.40])
    ax_leg.set_xlim(0, 10); ax_leg.set_ylim(0, 20)
    ax_leg.axis("off")

    # ── 1) Compass (指北针) — 在图例正上方 ──
    cx, cy_base = 3, 15.0
    arr_len = 2.2
    ax_leg.annotate("", xy=(cx, cy_base + arr_len), xytext=(cx, cy_base),
                    arrowprops=dict(arrowstyle="-|>", color="black", lw=2.5,
                                   mutation_scale=15))
    ax_leg.text(cx, cy_base + arr_len + 0.3, "N", ha="center", va="bottom",
                fontsize=fs(13), fontweight="bold", color="black")

    # ── 2) Scale bar (比例尺) — middle ──
    # At lat_ref ~ 25°N (bottom of main map area), 1° lon ≈ 100.9 km
    # Map width in degrees = 136 - 73 = 63°  → ~6360 km
    # Figure main axes width ≈ 0.78 * 14 in ≈ 10.92 in
    # Scale: 63° per 10.92 in → 1° ≈ 0.173 in
    # 500 km at 25°N ≈ 500 / 100.9 ≈ 4.96° → 0.86 in on map
    # In legend axes coords (0-10 over 0.18*14=2.52 in):
    # 1 legend-unit ≈ 0.252 in;  0.86 in ≈ 3.4 legend-units
    lat_ref = 25.0
    km_per_deg = 111.32 * np.cos(np.radians(lat_ref))
    bar_km = 500
    bar_deg = bar_km / km_per_deg           # in map degrees
    # convert map-degrees to legend-axes units
    map_width_deg = lon_max - lon_min       # 63
    main_ax_w_in = 0.78 * 14               # ~10.92 inches
    leg_ax_w_in = 0.18 * 14                # ~2.52 inches
    leg_units_total = 10                    # x range of legend axes
    map_deg_per_in = map_width_deg / main_ax_w_in
    bar_in = bar_deg / map_deg_per_in
    bar_leg = bar_in / leg_ax_w_in * leg_units_total
    sy = 13.2
    sx = 1.0
    half_b = bar_leg / 2
    ax_leg.add_patch(Rectangle((sx, sy), half_b, 0.40,
                               fc="black", ec="black", lw=0.8))
    ax_leg.add_patch(Rectangle((sx + half_b, sy), half_b, 0.40,
                               fc="white", ec="black", lw=0.8))
    ax_leg.text(sx, sy - 0.45, "0", ha="center", fontsize=fs(6.5), color="black")
    ax_leg.text(sx + half_b, sy - 0.45, f"{bar_km // 2}", ha="center", fontsize=fs(6.5), color="black")
    ax_leg.text(sx + bar_leg, sy - 0.45, f"{bar_km} km", ha="center", fontsize=fs(6.5), color="black")

    # ── 3) Segmented colour legend ──
    box_w, box_h = 2.0, 1.1
    lx = 1.0
    ly_start = 11.0      # start y for top segment
    for i in range(len(seg_bounds) - 1):
        lo, hi = seg_bounds[i], seg_bounds[i + 1]
        mid_val = (lo + hi) / 2
        c = cmap(norm(mid_val))
        y_pos = ly_start - i * (box_h + 0.25)
        ax_leg.add_patch(Rectangle((lx, y_pos), box_w, box_h,
                                   fc=c, ec="black", lw=0.8))
        ax_leg.text(lx + box_w + 0.35, y_pos + box_h / 2,
                    f"{lo:.1f} – {hi:.1f}",
                    va="center", ha="left", fontsize=fs(8), color="black")
    # ── legend title below segments ──
    bottom_y = ly_start - (len(seg_bounds) - 2) * (box_h + 0.25)
    ax_leg.text(lx + box_w, bottom_y - 0.6,
                "夜间灯光聚合度对数", ha="center", va="top",
                fontsize=fs(8), fontweight="bold", color="black")

    fig.savefig(OUTPUT_DIR / f"05_夜间灯光对数分级地图_{MAP_YEAR}.png",
                dpi=300, bbox_inches="tight")
    plt.close(fig)
    return f"已生成省级地图: {OUTPUT_DIR / f'05_夜间灯光对数分级地图_{MAP_YEAR}.png'}"


# ═══════════════════════════════════════════════════════════════
# Summary (unchanged)
# ═══════════════════════════════════════════════════════════════

def build_summary(df, map_message):
    year_mean = df.groupby("year")["ntl"].mean().round(4)
    changes = df.copy()
    changes["pct_change"] = changes.groupby("province")["ntl"].pct_change()
    jump_table = (
        changes.loc[changes["pct_change"].notna(),
                     ["province", "year", "ntl", "pct_change"]]
        .assign(abs_pct_change=lambda x: x["pct_change"].abs())
        .sort_values("abs_pct_change", ascending=False).head(10)
    )
    yearly_change_share = (
        changes.groupby("year")["pct_change"]
        .apply(lambda x: x.gt(0).mean() if x.notna().any() else np.nan).round(4)
    )
    province_mean = df.groupby("province")["ntl"].mean().sort_values(ascending=False).round(4)

    lines = [
        "# 夜间灯光指标检查摘要", "",
        "## 1. 样本概况",
        f"- 样本量: {len(df)}",
        f"- 年份范围: {df['year'].min()}-{df['year'].max()}",
        f"- 省份数量: {df['province'].nunique()}",
        f"- ntl 最小值: {df['ntl'].min():.6f}",
        f"- ntl 最大值: {df['ntl'].max():.6f}", "",
        "## 2. 年度均值",
    ]
    lines.extend([f"- {yr}: {v:.4f}" for yr, v in year_mean.items()])
    lines.extend(["", "## 3. 各年正增长省份占比",
        *[f"- {yr}: {'NA' if pd.isna(v) else f'{v:.2%}'}"
          for yr, v in yearly_change_share.items()],
        "", "## 4. 绝对跳变最大的 10 个观测"])
    for r in jump_table.itertuples(index=False):
        lines.append(f"- {r.province} {r.year}: ntl={r.ntl:.4f}, pct_change={r.pct_change:.2%}")
    lines.extend(["", "## 5. 省均值前 10 名",
        *[f"- {p}: {v:.4f}" for p, v in province_mean.head(10).items()],
        "", "## 6. 图形解释提示",
        "- 图1左轴是频数，右轴是核密度；核密度曲线只是直方图的平滑版，不要求严格对称。",
        "- `lntl` 只要比 `ntl` 偏态更弱、更接近单峰，就说明对数化有效。",
        "- 图4蓝色实心柱是 `ntl`，橙色实心柱是 `lntl`，从上往下逐渐变浅。",
        "", "## 7. 地图输出", f"- {map_message}"])
    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_style()
    df = load_data()
    df[["year", "province", "ntl"]].to_csv(
        OUTPUT_DIR / "夜间灯光检查数据.csv", index=False, encoding="utf-8-sig")
    save_distribution_plot(df)
    save_time_series_plots(df)
    save_spatial_proxy_plot(df)
    map_message = save_lntl_map(df)
    summary_text = build_summary(df, map_message)
    (OUTPUT_DIR / "夜间灯光检查总结.md").write_text(summary_text, encoding="utf-8")
    print(f"已生成输出目录: {OUTPUT_DIR}")
    print(f"已导出 ntl 数据: {OUTPUT_DIR / '夜间灯光检查数据.csv'}")
    print("已生成图形:")
    print(f"- {OUTPUT_DIR / '01_指标分布图.png'}")
    print(f"- {OUTPUT_DIR / '02_年度均值图.png'}")
    print(f"- {OUTPUT_DIR / '03_各省变化趋势图.png'}")
    print(f"- {OUTPUT_DIR / '04_各省均值排序图.png'}")
    print(f"- {map_message}")
    print(f"已生成摘要: {OUTPUT_DIR / '夜间灯光检查总结.md'}")


if __name__ == "__main__":
    main()
