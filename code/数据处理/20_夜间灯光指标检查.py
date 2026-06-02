STEP_SPEC = {
    "name": "夜间灯光强度检查",
    "runner_type": "python",
    "command": [
        "python",
        "code/数据处理/20_夜间灯光指标检查.py"
    ],
    "working_dir": "{PROJECT_ROOT}",
    "precheck_mode": "none",
    "required_inputs": [
        {
            "path": "{数据处理.second_stage_panel}",
            "kind": "csv",
            "required_columns": [
                "province",
                "year",
                "lntl"
            ],
            "label": ""
        },
        {
            "path": "{数据处理.map_geojson_paths[0]}",
            "kind": "file",
            "required_columns": [],
            "label": ""
        }
    ],
    "artifacts": {
        "tables": {
            "primary": "夜间灯光检查数据.csv",
            "patterns": [
                "*.csv"
            ]
        },
        "images": {
            "primary": None,
            "patterns": [
                "*.png"
            ]
        },
        "markdown": {
            "primary": None,
            "patterns": [
                "*.md"
            ]
        }
    },
    "console_success_markers": [],
    "description": "检查夜间灯光强度的分布、趋势与空间分级效果。",
    "notes": []
}

import json
from pathlib import Path
import sys

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
sys.path.insert(0, str(PROJECT_ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, script_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
DATA_PATH = resolve_project_path(CONFIG["second_stage_panel"])
OUTPUT_DIR = script_output_dir(Path(__file__), CONFIG)
MAP_PATHS = [PROJECT_ROOT / "data" / "外部资料" / "中国_省.geojson"]
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
    sns.set_context("talk")
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
    ax.legend(h1 + h2, l1 + l2, loc="upper right", frameon=True, borderaxespad=0.8)


def save_distribution_plot(df):
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.2))
    draw_gradient_histogram(axes[0], df["ntl"], "夜间灯光强度（取对数前）分布", "夜间灯光强度（取对数前）",
                            "Blues", "#1F4E79", clip_negative=True)
    draw_gradient_histogram(axes[1], df["lntl"], "夜间灯光强度分布", "夜间灯光强度",
                            "Oranges", "#C65D00", force_xlim_left=0)
    fig.suptitle("夜间灯光强度分布检验")
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
    ax.set_title("夜间灯光强度（取对数前）年度均值"); ax.set_xlabel("year"); ax.set_ylabel("夜间灯光强度（取对数前）均值")
    ax.legend(frameon=True, borderaxespad=0.8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "02_年度均值图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(15.5, 8.2))
    sns.lineplot(data=df, x="year", y="ntl", hue="province",
                 legend="full", linewidth=1.2, alpha=0.8, ax=ax)
    ax.set_title("各省夜间灯光强度（取对数前）年际变化"); ax.set_xlabel("year"); ax.set_ylabel("夜间灯光强度（取对数前）")
    h, l = ax.get_legend_handles_labels()
    if h:
        ax.legend(handles=h, labels=l, title="province",
                  bbox_to_anchor=(1.02, 1), loc="upper left",
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
            edgecolor="none", linewidth=0, label="夜间灯光强度（取对数前）均值")
    ax.barh(y_pos, ps["lntl"].values, color=orange_c,
            edgecolor="none", linewidth=0, label="夜间灯光强度均值")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ps["province"].values)
    ax.invert_yaxis()
    ax.set_title("各省夜间灯光强度均值排序")
    ax.set_xlabel("value"); ax.set_ylabel("province")
    ax.legend(frameon=True, borderaxespad=0.8)
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


def iter_line_strings(geometry: dict) -> list[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    lines: list[list[tuple[float, float]]] = []
    if gtype == "LineString":
        if coords:
            lines.append([(x, y) for x, y in coords])
    elif gtype == "MultiLineString":
        for line in coords:
            if line:
                lines.append([(x, y) for x, y in line])
    return lines






def save_lntl_map(df):
    import cartopy.crs as ccrs
    from collections import defaultdict
    from shapely.geometry import Polygon as ShapelyPolygon

    map_path = find_map_path()
    if map_path is None:
        return "未生成省级地图: 缺少省级 GeoJSON 底图文件。"
    with map_path.open("r", encoding="utf-8") as f:
        geo = json.load(f)
    year_df = df.loc[df["year"] == MAP_YEAR, ["province", "lntl"]].copy()
    if year_df.empty:
        return f"未生成省级地图: 数据中没有 {MAP_YEAR} 年。"

    value_map = dict(zip(year_df["province"], year_df["lntl"]))
    seg_bounds = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    cmap = colormaps["YlOrRd"]
    norm = mcolors.BoundaryNorm(seg_bounds, cmap.N)

    main_features, scs_features, line_features, hainan_feature = [], [], [], None
    for feat in geo.get("features", []):
        props = feat.get("properties", {})
        raw = (props.get("name") or props.get("NAME")
               or props.get("province") or props.get("fullname") or "")
        gtype = feat.get("geometry", {}).get("type", "")
        if gtype in ("LineString", "MultiLineString"):
            line_features.append(feat)
            continue
        if props.get("adchar") == "JD" or not raw.strip():
            scs_features.append(feat)
        else:
            main_features.append(feat)
            if "海南" in raw:
                hainan_feature = feat

    proj = ccrs.AlbersEqualArea(central_longitude=105, standard_parallels=(25, 47),
                               false_easting=0, false_northing=0,
                               globe=ccrs.Globe(ellipse="GRS80"))
    data_crs = ccrs.PlateCarree()

    fig = plt.figure(figsize=(16.5, 13.5))
    ax = fig.add_axes([0.09, 0.11, 0.78, 0.80], projection=proj)
    ax.set_extent([73, 146, 15, 55], crs=data_crs)

    color_geoms = defaultdict(list)
    for feat in main_features:
        props = feat.get("properties", {})
        raw = (props.get("name") or props.get("NAME")
               or props.get("province") or props.get("fullname") or "")
        prov = normalize_province_name(raw)
        val = value_map.get(prov)
        color = "#D9D9D9" if val is None else cmap(norm(val))
        for coords in iter_feature_polygons(feat.get("geometry", {})):
            color_geoms[color].append(ShapelyPolygon(coords))
    if not color_geoms:
        return f"未生成省级地图: {map_path.name} 无法解析。"

    for color, geoms in color_geoms.items():
        ax.add_geometries(geoms, crs=data_crs, facecolor=color,
                          edgecolor="black", linewidth=0.5)

    for feat in line_features:
        for line_coords in iter_line_strings(feat.get("geometry", {})):
            xs, ys = zip(*line_coords)
            ax.plot(xs, ys, color="black", linewidth=0.5, linestyle="--",
                    transform=data_crs, zorder=5)

    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color="gray", linestyle="--",
                      x_inline=False, y_inline=False)
    gl.top_labels = False; gl.right_labels = False
    gl.left_labels = True; gl.bottom_labels = True
    gl.xlabel_style = {"size": fs(0)}; gl.ylabel_style = {"size": fs(0)}

    for sp in ax.spines.values():
        sp.set_linewidth(2.5); sp.set_color("black")
    ax.set_title(f"{MAP_YEAR} 年各省夜间灯光强度分级图", fontweight="bold", pad=12)

    # SCS inset
    ax_scs = fig.add_axes([0.72, 0.14, 0.12, 0.20], projection=data_crs)
    ax_scs.set_extent([104, 123, 2, 23], crs=data_crs)
    if hainan_feature:
        val = value_map.get("海南"); c = "#D9D9D9" if val is None else cmap(norm(val))
        for coords in iter_feature_polygons(hainan_feature.get("geometry", {})):
            ax_scs.add_geometries([ShapelyPolygon(coords)], crs=data_crs,
                                  facecolor=c, edgecolor="black", linewidth=0.6)
    for feat in scs_features:
        for coords in iter_feature_polygons(feat.get("geometry", {})):
            ax_scs.add_geometries([ShapelyPolygon(coords)], crs=data_crs,
                                  facecolor="#D9D9D9", edgecolor="black", linewidth=0.6)
    for feat in line_features:
        for line_coords in iter_line_strings(feat.get("geometry", {})):
            xs, ys = zip(*line_coords)
            ax_scs.plot(xs, ys, color="black", linewidth=0.5, linestyle="--",
                        transform=data_crs, zorder=5)
    for sp in ax_scs.spines.values():
        sp.set_linewidth(1.8); sp.set_color("black")
    ax_scs.set_title("南海诸岛", pad=4)

    # North arrow
    ax_n = fig.add_axes([0.82, 0.88, 0.06, 0.08])
    ax_n.set_xlim(-1, 1); ax_n.set_ylim(-1, 1); ax_n.axis("off")
    ax_n.add_patch(plt.Circle((0, 0), 0.55, fc="none", ec="black", lw=1.2))
    ax_n.plot([0, 0], [-0.45, 0.55], color="black", lw=0.8)
    ax_n.plot([-0.45, 0.45], [0, 0], color="black", lw=0.8)
    ax_n.add_patch(Polygon([[0, 0.45], [-0.18, 0], [0.18, 0]], closed=True,
                           fc="black", ec="black", lw=0.5))
    ax_n.text(0, 0.72, "N", ha="center", va="bottom", fontweight="bold", fontsize=10)

    # Scale bar
    ax_sb = fig.add_axes([0.38, 0.88, 0.18, 0.03])
    ax_sb.set_xlim(0, 1); ax_sb.set_ylim(0, 1); ax_sb.axis("off")
    ax_sb.add_patch(Rectangle((0.1, 0.3), 0.4, 0.4, fc="black", ec="black", lw=0.5))
    ax_sb.add_patch(Rectangle((0.5, 0.3), 0.4, 0.4, fc="white", ec="black", lw=0.5))
    ax_sb.text(0.1, 0.1, "0", ha="center", va="top", fontsize=7)
    ax_sb.text(0.5, 0.1, "250", ha="center", va="top", fontsize=7)
    ax_sb.text(0.9, 0.1, "500 km", ha="center", va="top", fontsize=7)

    # Legend
    ax_leg = fig.add_axes([0.09, 0.09, 0.18, 0.38])
    ax_leg.set_xlim(0, 10); ax_leg.set_ylim(0, 20); ax_leg.axis("off")
    box_w, box_h = 1.4, 0.75; lx = 1.0; ly_start = 18.0
    ax_leg.add_patch(Rectangle((lx, ly_start), box_w, box_h, fc="#D9D9D9", ec="black", lw=0.6))
    ax_leg.text(lx + box_w + 0.3, ly_start + box_h / 2, "无数据", va="center", ha="left", fontsize=8, color="black")
    ly_start -= box_h + 0.3
    for i in range(len(seg_bounds) - 1):
        lo, hi = seg_bounds[i], seg_bounds[i + 1]
        mid_val = (lo + hi) / 2; c = cmap(norm(mid_val))
        y_pos = ly_start - i * (box_h + 0.2)
        ax_leg.add_patch(Rectangle((lx, y_pos), box_w, box_h, fc=c, ec="black", lw=0.6))
        ax_leg.text(lx + box_w + 0.3, y_pos + box_h / 2, f"{lo:.1f} - {hi:.1f}",
                    va="center", ha="left", fontsize=8, color="black")
    bottom_y = ly_start - (len(seg_bounds) - 2) * (box_h + 0.2)
    ax_leg.text(lx + box_w / 2, bottom_y - 0.8, "夜间灯光强度", ha="center", va="top",
                fontsize=9, fontweight="bold", color="black")

    fig.text(0.09, 0.035,
        '注：底图来源于国家地理信息公共服务平台"天地图"（审图号：GS（2024）0650号），无修改',
        ha='left', va='bottom', fontsize=12, color='black')
    fig.savefig(OUTPUT_DIR / f"05_夜间灯光强度分级地图_{MAP_YEAR}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return f"已生成省级地图: 05_夜间灯光强度分级地图_{MAP_YEAR}.png"


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
        "# 夜间灯光强度检查摘要", "",
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
