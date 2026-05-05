from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Rectangle
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parent
WEIGHT_PATH = ROOT / "prcd" / "matrix01.csv"
EFF_PATH = ROOT / "prcd" / "dearun_eff.csv"
GEOJSON_PATH = ROOT / "data" / "china.geojson"
OUT_DIR = ROOT / "prcd" / "spatial_plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_YEARS = list(range(2015, 2023))
LOCAL_PLOT_YEARS = [2015, 2018, 2022]
N_PERMUTATIONS = 9999
RANDOM_SEED = 42
LOCAL_SIGNIFICANCE_ALPHA = 0.10
PROVINCE_NAME_MAP = {
    "北京": "北京市",
    "天津": "天津市",
    "上海": "上海市",
    "重庆": "重庆市",
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "西藏": "西藏自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
    "黑龙江": "黑龙江省",
    "吉林": "吉林省",
    "辽宁": "辽宁省",
    "河北": "河北省",
    "山西": "山西省",
    "陕西": "陕西省",
    "甘肃": "甘肃省",
    "青海": "青海省",
    "山东": "山东省",
    "江苏": "江苏省",
    "浙江": "浙江省",
    "安徽": "安徽省",
    "福建": "福建省",
    "江西": "江西省",
    "河南": "河南省",
    "湖北": "湖北省",
    "湖南": "湖南省",
    "广东": "广东省",
    "海南": "海南省",
    "四川": "四川省",
    "贵州": "贵州省",
    "云南": "云南省",
}
LISA_COLORS = {
    "HH": "#B2182B",
    "LH": "#67A9CF",
    "LL": "#2166AC",
    "HL": "#EF8A62",
    "NS": "#D9D9D9",
}
SCATTER_COLORS = {
    "HH": "#B2182B",
    "HL": "#EF8A62",
    "LH": "#67A9CF",
    "LL": "#2166AC",
}
MISSING_COLOR = "#FFFFFF"
QUADRANT_LABELS = {
    "HH": "高-高",
    "LH": "低-高",
    "LL": "低-低",
    "HL": "高-低",
    "NS": "不显著",
}


def configure_matplotlib() -> None:
    sns.set_theme(style="whitegrid")
    candidates = ["Times New Roman", "SimSun"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [name for name in candidates if name in available] or ["DejaVu Serif"]
    matplotlib.rcParams["font.family"] = chosen
    matplotlib.rcParams["axes.unicode_minus"] = False


def load_weight_matrix(path: Path) -> pd.DataFrame:
    w = pd.read_csv(path, index_col=0)
    w.index = w.index.astype(str).str.strip()
    w.columns = w.columns.astype(str).str.strip()
    w = w.loc[w.index, w.index]
    return w


def load_efficiency(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"year", "province", "eff"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"dearun_eff.csv 缺少字段: {sorted(missing)}")

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["province"] = df["province"].astype(str).str.strip()
    df["eff"] = pd.to_numeric(df["eff"], errors="coerce")
    df = df.dropna(subset=["year", "province", "eff"]).copy()
    df["year"] = df["year"].astype(int)
    return df


def load_geojson(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def row_standardize(matrix: np.ndarray) -> np.ndarray:
    row_sums = matrix.sum(axis=1, keepdims=True)
    return np.divide(matrix, row_sums, out=np.zeros_like(matrix, dtype=float), where=row_sums != 0)


def morans_i(values: np.ndarray, weights: np.ndarray) -> float:
    n = len(values)
    centered = values - values.mean()
    s0 = weights.sum()
    return float((n / s0) * (centered @ weights @ centered) / (centered @ centered))


def permutation_test(
    values: np.ndarray,
    weights: np.ndarray,
    n_permutations: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, float, float]:
    observed = morans_i(values, weights)
    centered = values - values.mean()
    denom = float(centered @ centered)
    n = len(values)
    s0 = float(weights.sum())

    sims = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        permuted = rng.permutation(centered)
        sims[i] = (n / s0) * (permuted @ weights @ permuted) / denom

    p_one_sided = float((np.sum(sims >= observed) + 1) / (n_permutations + 1))
    sim_mean = float(sims.mean())
    sim_std = float(sims.std(ddof=1))
    z_value = float((observed - sim_mean) / sim_std) if sim_std > 0 else float("nan")
    return observed, z_value, p_one_sided, sim_mean, sim_std


def calculate_global_morans_i() -> pd.DataFrame:
    w_df = load_weight_matrix(WEIGHT_PATH)
    weights = row_standardize(w_df.to_numpy(dtype=float))
    provinces = w_df.index.tolist()
    eff_df = load_efficiency(EFF_PATH)
    rng = np.random.default_rng(RANDOM_SEED)

    rows: list[dict[str, float | int]] = []
    for year in TARGET_YEARS:
        year_df = eff_df.loc[eff_df["year"] == year].set_index("province")
        missing = [p for p in provinces if p not in year_df.index]
        if missing:
            raise ValueError(f"{year} 年缺少省份数据: {missing}")

        values = year_df.loc[provinces, "eff"].to_numpy(dtype=float)
        moran_i_value, z_value, p_value, sim_mean, sim_std = permutation_test(
            values=values,
            weights=weights,
            n_permutations=N_PERMUTATIONS,
            rng=rng,
        )
        rows.append(
            {
                "year": year,
                "moran_i": moran_i_value,
                "z_value": z_value,
                "p_value": p_value,
                "perm_mean": sim_mean,
                "perm_std": sim_std,
            }
        )

    result = pd.DataFrame(rows)
    result["significance"] = result["p_value"].apply(
        lambda p: "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
    )
    return result


def get_year_values(eff_df: pd.DataFrame, provinces: list[str], year: int) -> np.ndarray:
    year_df = eff_df.loc[eff_df["year"] == year].set_index("province")
    missing = [p for p in provinces if p not in year_df.index]
    if missing:
        raise ValueError(f"{year} 年缺少省份数据: {missing}")
    return year_df.loc[provinces, "eff"].to_numpy(dtype=float)


def local_morans_i(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    centered = values - values.mean()
    std = centered.std(ddof=0)
    if std == 0:
        raise ValueError("局部 Moran's I 无法计算：样本标准差为 0。")
    z_scores = centered / std
    spatial_lag = weights @ z_scores
    local_i = z_scores * spatial_lag
    return z_scores, spatial_lag, local_i


def local_permutation_test(
    z_scores: np.ndarray,
    weights: np.ndarray,
    n_permutations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    observed = z_scores * (weights @ z_scores)
    sims = np.empty((n_permutations, len(z_scores)), dtype=float)
    for i in range(n_permutations):
        permuted = rng.permutation(z_scores)
        sims[i] = z_scores * (weights @ permuted)
    p_values = (np.sum(np.abs(sims) >= np.abs(observed), axis=0) + 1) / (n_permutations + 1)
    z_values = np.divide(
        observed - sims.mean(axis=0),
        sims.std(axis=0, ddof=1),
        out=np.full_like(observed, np.nan, dtype=float),
        where=sims.std(axis=0, ddof=1) > 0,
    )
    return p_values.astype(float), z_values.astype(float)


def classify_lisa(z_scores: np.ndarray, spatial_lag: np.ndarray, p_values: np.ndarray) -> list[str]:
    clusters: list[str] = []
    for z_val, lag_val, p_val in zip(z_scores, spatial_lag, p_values):
        if p_val >= LOCAL_SIGNIFICANCE_ALPHA:
            clusters.append("NS")
        elif z_val >= 0 and lag_val >= 0:
            clusters.append("HH")
        elif z_val < 0 and lag_val < 0:
            clusters.append("LL")
        elif z_val >= 0 and lag_val < 0:
            clusters.append("HL")
        else:
            clusters.append("LH")
    return clusters


def classify_quadrant(z_scores: np.ndarray, spatial_lag: np.ndarray) -> list[str]:
    quadrants: list[str] = []
    for z_val, lag_val in zip(z_scores, spatial_lag):
        if z_val >= 0 and lag_val >= 0:
            quadrants.append("HH")
        elif z_val < 0 and lag_val < 0:
            quadrants.append("LL")
        elif z_val >= 0 and lag_val < 0:
            quadrants.append("HL")
        else:
            quadrants.append("LH")
    return quadrants


def build_local_moran_results() -> pd.DataFrame:
    w_df = load_weight_matrix(WEIGHT_PATH)
    weights = row_standardize(w_df.to_numpy(dtype=float))
    provinces = w_df.index.tolist()
    eff_df = load_efficiency(EFF_PATH)

    rows: list[dict[str, float | int | str]] = []
    for idx, year in enumerate(LOCAL_PLOT_YEARS):
        values = get_year_values(eff_df, provinces, year)
        z_scores, spatial_lag, local_i = local_morans_i(values, weights)
        p_values, z_values = local_permutation_test(
            z_scores=z_scores,
            weights=weights,
            n_permutations=N_PERMUTATIONS,
            rng=np.random.default_rng(RANDOM_SEED + idx + year),
        )
        quadrants = classify_quadrant(z_scores, spatial_lag)
        clusters = classify_lisa(z_scores, spatial_lag, p_values)
        for province, eff, z_score, lag, local_stat, p_val, z_val, quadrant, cluster in zip(
            provinces, values, z_scores, spatial_lag, local_i, p_values, z_values, quadrants, clusters
        ):
            rows.append(
                {
                    "year": year,
                    "province": province,
                    "eff": eff,
                    "z_score": z_score,
                    "spatial_lag": lag,
                    "local_moran_i": local_stat,
                    "local_p_value": p_val,
                    "local_z_value": z_val,
                    "quadrant": quadrant,
                    "cluster": cluster,
                    "is_significant": int(p_val < LOCAL_SIGNIFICANCE_ALPHA),
                }
            )
    return pd.DataFrame(rows)


def significance_marker(p_value: float) -> str:
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def save_result_table(result: pd.DataFrame) -> Path:
    out_path = OUT_DIR / "global_morans_i_2015_2022.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def save_local_result_table(local_result: pd.DataFrame) -> Path:
    out_path = OUT_DIR / "local_morans_i_2015_2018_2022.csv"
    local_result.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def save_plot(result: pd.DataFrame) -> Path:
    fig, ax_left = plt.subplots(figsize=(12.2, 7.4))
    ax_right = ax_left.twinx()
    ax_left.set_zorder(2)
    ax_right.set_zorder(1)
    ax_left.patch.set_visible(False)
    ax_left.grid(False)
    ax_right.grid(False)

    x = np.arange(len(result))
    width = 0.16
    p_color = "#D62728"
    z_color = "#F28E2B"
    i_color = "#1F77B4"
    p_sig = ("p值5%显著性（p=0.05）", 0.05, "#C44E52", "--")
    z_sig = ("z值10%显著性（z=1.645）", 1.645, "#8172B2", "-.")

    p_bars = ax_left.bar(x - width / 2, result["p_value"], width=width, color=p_color, label="p 值", zorder=3)
    (i_line,) = ax_left.plot(
        x,
        result["moran_i"],
        color=i_color,
        linewidth=2.2,
        marker="o",
        markersize=6.2,
        markerfacecolor="white",
        markeredgewidth=1.4,
        label="Moran's I",
        zorder=6,
    )
    z_bars = ax_right.bar(x + width / 2, result["z_value"], width=width, color=z_color, label="z 值", zorder=3)

    ax_left.axhline(p_sig[1], color=p_sig[2], linestyle=p_sig[3], linewidth=1.4, alpha=0.95, zorder=2)
    ax_right.axhline(z_sig[1], color=z_sig[2], linestyle=z_sig[3], linewidth=1.4, alpha=0.95, zorder=2)

    legend_handles: list[object] = [
        p_bars[0],
        z_bars[0],
        i_line,
        Line2D([0], [0], color=z_sig[2], linestyle=z_sig[3], linewidth=1.5),
        Line2D([0], [0], color=p_sig[2], linestyle=p_sig[3], linewidth=1.5),
    ]
    legend_labels = ["p 值", "z 值", "Moran's I", z_sig[0], p_sig[0]]

    ax_left.set_title("2015-2022 年 Global Moran's I、p 值与 z 值", fontsize=15, pad=14)
    ax_left.set_xlabel("年份")
    ax_left.set_ylabel("p 值 / Global Moran's I")
    ax_right.set_ylabel("z 值")
    ax_left.set_xticks(x)
    ax_left.set_xticklabels(result["year"])

    left_step = 0.05
    left_upper = max(float(result["p_value"].max()), float(result["moran_i"].max()), p_sig[1])
    left_upper = float(np.ceil(left_upper / left_step) * left_step) + left_step * 2
    right_upper = max(float(result["z_value"].max()), z_sig[1])
    n_intervals = max(int(round(left_upper / left_step)), int(np.ceil(right_upper)))
    left_upper = n_intervals * left_step
    right_upper = float(n_intervals)

    ax_left.set_ylim(0, left_upper)
    ax_right.set_ylim(0, right_upper)
    left_ticks = np.arange(0.0, left_upper + left_step / 2, left_step)
    right_ticks = np.arange(0.0, right_upper + 0.5, 1.0)
    ax_left.set_yticks(left_ticks)
    ax_right.set_yticks(right_ticks)
    ax_right.yaxis.set_major_locator(MultipleLocator(1.0))

    for bar, value, stars in zip(p_bars, result["p_value"], result["significance"]):
        ax_left.annotate(
            f"{value:.3f}{stars}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#1F2933",
        )

    for x_pos, value in zip(x, result["moran_i"]):
        ax_left.annotate(
            f"{value:.3f}",
            xy=(x_pos, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color=i_color,
        )

    for bar, value in zip(z_bars, result["z_value"]):
        ax_right.annotate(
            f"{value:.3f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#1F2933",
        )

    ax_left.legend(legend_handles, legend_labels, loc="upper right", frameon=True, fontsize=9)

    note = "注：采用 0-1 邻接矩阵并进行行标准化；p 值为单侧置换检验结果（9999 次），z 值基于置换分布的均值与标准差计算。"
    fig.text(0.01, 0.01, note, ha="left", va="bottom", fontsize=9, color="#52606D")
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    out_path = OUT_DIR / "18_global_morans_i_2015_2022.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_moran_scatter_plot(local_result: pd.DataFrame, global_result: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8), sharex=True, sharey=True)
    year_to_global = global_result.set_index("year")["moran_i"].to_dict()
    for ax, year in zip(axes, LOCAL_PLOT_YEARS):
        subset = local_result.loc[local_result["year"] == year].copy()
        colors = subset["quadrant"].map(SCATTER_COLORS)
        ax.scatter(
            subset["z_score"],
            subset["spatial_lag"],
            s=58,
            c=colors,
            edgecolors="white",
            linewidths=0.7,
            alpha=0.92,
            zorder=3,
        )
        xline = np.linspace(subset["z_score"].min() - 0.2, subset["z_score"].max() + 0.2, 200)
        ax.plot(xline, year_to_global[year] * xline, color="#333333", linewidth=1.8, zorder=4)
        ax.axhline(0, color="#666666", linewidth=1.0, linestyle="--", zorder=1)
        ax.axvline(0, color="#666666", linewidth=1.0, linestyle="--", zorder=1)
        significant_subset = subset.loc[subset["is_significant"] == 1].copy()
        for row in significant_subset.itertuples(index=False):
            xytext = (5, 5)
            ha = "left"
            va = "bottom"
            if year == 2015 and row.province == "山西":
                xytext = (5, -6)
                ha = "left"
                va = "top"
            if year == 2018 and row.province == "海南":
                xytext = (5, -6)
                ha = "left"
                va = "top"
            ax.annotate(
                f"{row.province}{significance_marker(row.local_p_value)}",
                xy=(row.z_score, row.spatial_lag),
                xytext=xytext,
                textcoords="offset points",
                ha=ha,
                va=va,
                fontsize=9,
                color="#111827",
                zorder=5,
            )
        ax.text(0.98, 0.96, f"I = {year_to_global[year]:.3f}", transform=ax.transAxes, ha="right", va="top", fontsize=10)
        ax.text(
            0.98,
            0.88,
            f"显著省份:{len(significant_subset)}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            color="#4B5563",
        )
        ax.set_title(f"{year} 年", fontsize=13, pad=10)
        ax.grid(True, linestyle=":", alpha=0.35)

    axes[0].set_ylabel("空间滞后值")
    for ax in axes:
        ax.set_xlabel("标准化 eff")

    legend_handles = [
        Line2D([0], [0], marker="o", color="w", label="高-高", markerfacecolor=SCATTER_COLORS["HH"], markersize=8),
        Line2D([0], [0], marker="o", color="w", label="低-低", markerfacecolor=SCATTER_COLORS["LL"], markersize=8),
        Line2D([0], [0], marker="o", color="w", label="高-低", markerfacecolor=SCATTER_COLORS["HL"], markersize=8),
        Line2D([0], [0], marker="o", color="w", label="低-高", markerfacecolor=SCATTER_COLORS["LH"], markersize=8),
        Line2D([0], [0], color="#333333", linewidth=1.8, label="Moran 回归线"),
        Line2D([0], [0], marker="o", color="w", label="显著省份标注*/**/***", markerfacecolor="#9CA3AF", markersize=8),
    ]
    fig.legend(legend_handles, [h.get_label() for h in legend_handles], loc="upper right", ncol=3, frameon=True, fontsize=9)
    fig.suptitle("图24 eff 的 Moran 散点图（2015、2018、2022）", fontsize=17, y=0.99)
    fig.text(0.01, 0.02, "注：基于 0-1 邻接矩阵行标准化结果绘制；散点按 Moran 象限着色；局部显著省份按 10%、5%、1% 阈值分别标注 */**/***。",
             ha="left", va="bottom", fontsize=9, color="#52606D")
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))

    out_path = OUT_DIR / "24_eff_moran_scatter_2015_2018_2022.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def iter_polygon_rings(geometry: dict) -> list[list[list[float]]]:
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        return coords
    if geom_type == "MultiPolygon":
        rings: list[list[list[float]]] = []
        for polygon in coords:
            rings.extend(polygon)
        return rings
    return []


def draw_geojson_feature(ax: plt.Axes, geometry: dict, facecolor: str, edgecolor: str = "white", linewidth: float = 0.6) -> None:
    patches: list[Polygon] = []
    for ring in iter_polygon_rings(geometry):
        if len(ring) >= 3:
            patches.append(Polygon(ring, closed=True))
    if patches:
        collection = PatchCollection(
            patches,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            zorder=2,
        )
        ax.add_collection(collection)


def normalize_province_name(name: str) -> str:
    reverse_map = {v: k for k, v in PROVINCE_NAME_MAP.items()}
    return reverse_map.get(str(name).strip(), str(name).strip())


def iter_feature_polygons(geometry: dict) -> list[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    polygons: list[list[tuple[float, float]]] = []
    if gtype == "Polygon":
        if coords:
            polygons.append([(x, y) for x, y in coords[0]])
    elif gtype == "MultiPolygon":
        for polygon in coords:
            if polygon:
                polygons.append([(x, y) for x, y in polygon[0]])
    return polygons


def split_geo_features(geojson: dict) -> tuple[list[dict], list[dict], dict | None, dict | None, dict | None]:
    main_features: list[dict] = []
    scs_features: list[dict] = []
    hainan_feature = None
    guangdong_feature = None
    guangxi_feature = None
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        raw_name = props.get("name", "")
        if props.get("adchar") == "JD" or "南海诸岛" in str(raw_name):
            scs_features.append(feat)
            continue
        main_features.append(feat)
        if "海南" in str(raw_name):
            hainan_feature = feat
        if "广东" in str(raw_name):
            guangdong_feature = feat
        if "广西" in str(raw_name):
            guangxi_feature = feat
    return main_features, scs_features, hainan_feature, guangdong_feature, guangxi_feature


def draw_north_arrow(ax: plt.Axes, lon_min: float, lat_max: float) -> None:
    compass_x = lon_min + 3.2
    compass_y = lat_max - 5.3
    ax.annotate(
        "",
        xy=(compass_x, compass_y + 2.2),
        xytext=(compass_x, compass_y),
        arrowprops=dict(arrowstyle="-|>", color="black", lw=2.5, mutation_scale=15),
        zorder=6,
    )
    ax.text(compass_x, compass_y + 2.55, "N", ha="center", va="bottom", fontsize=13, fontweight="bold", zorder=6)


def draw_scale_and_legend(fig: plt.Figure, cmap_labels: list[tuple[str, str]]) -> None:
    ax_leg = fig.add_axes([0.09, 0.10, 0.18, 0.36])
    ax_leg.set_xlim(0, 10)
    ax_leg.set_ylim(0, 20)
    ax_leg.axis("off")

    lon_min, lon_max = 73, 136
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
    for idx, (label, color) in enumerate(cmap_labels):
        y_pos = ly_start - idx * (box_h + 0.25)
        ax_leg.add_patch(Rectangle((lx, y_pos), box_w, box_h, fc=color, ec="black", lw=0.8))
        ax_leg.text(lx + box_w + 0.35, y_pos + box_h / 2, label, va="center", ha="left", fontsize=8)
    ax_leg.text(lx + box_w / 2 + 1.0, 3.0, "LISA 聚类类型", ha="center", va="center", fontsize=10, fontweight="bold")


def add_map_frame(ax: plt.Axes, title: str) -> None:
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
    ax.set_title(title, fontsize=16, fontweight="bold", pad=12)
    draw_north_arrow(ax, lon_min, lat_max)


def draw_scs_inset(
    fig: plt.Figure,
    scs_features: list[dict],
    hainan_feature: dict | None,
    guangdong_feature: dict | None,
    guangxi_feature: dict | None,
    color_lookup: dict[str, str],
) -> None:
    ax_scs = fig.add_axes([0.71, 0.14, 0.14, 0.22])
    scs_patches: list[Polygon] = []
    scs_colors: list[str] = []

    def append_feature(feat: dict | None, province_key: str) -> None:
        if feat is None:
            return
        facecolor = color_lookup.get(province_key, LISA_COLORS["NS"])
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            scs_patches.append(Polygon(poly, closed=True))
            scs_colors.append(facecolor)

    append_feature(guangdong_feature, "广东")
    append_feature(guangxi_feature, "广西")
    append_feature(hainan_feature, "海南")
    for feat in scs_features:
        for poly in iter_feature_polygons(feat.get("geometry", {})):
            scs_patches.append(Polygon(poly, closed=True))
            scs_colors.append("#D9D9D9")

    if scs_patches:
        scs_collection = PatchCollection(scs_patches, facecolor=scs_colors, edgecolor="black", linewidths=0.6)
        ax_scs.add_collection(scs_collection)
    ax_scs.set_xlim(104, 123)
    ax_scs.set_ylim(2, 23)
    ax_scs.set_aspect(1 / np.cos(np.radians(14)))
    ax_scs.set_xticks([])
    ax_scs.set_yticks([])
    ax_scs.grid(False)
    for spine in ax_scs.spines.values():
        spine.set_linewidth(1.8)
        spine.set_color("black")
    ax_scs.set_title("南海诸岛", fontsize=8, pad=2)


def save_lisa_cluster_map(local_result: pd.DataFrame) -> Path:
    geojson = load_geojson(GEOJSON_PATH)
    main_features, scs_features, hainan_feature, guangdong_feature, guangxi_feature = split_geo_features(geojson)

    for year in LOCAL_PLOT_YEARS:
        fig = plt.figure(figsize=(14, 11))
        ax = fig.add_axes([0.09, 0.10, 0.78, 0.82])
        subset = local_result.loc[local_result["year"] == year].set_index("province")
        color_lookup: dict[str, str] = {}

        patches: list[Polygon] = []
        facecolors: list[str] = []
        for feature in main_features:
            name = feature["properties"].get("name", "")
            if name in {"香港特别行政区", "澳门特别行政区", ""}:
                continue
            simple_name = normalize_province_name(name)
            if simple_name in {"西藏", "台湾"}:
                facecolor = MISSING_COLOR
                cluster = "MISSING"
            elif simple_name not in subset.index:
                facecolor = MISSING_COLOR
                cluster = "MISSING"
            else:
                cluster = subset.at[simple_name, "cluster"]
                facecolor = LISA_COLORS[cluster]
            color_lookup[simple_name] = facecolor
            for poly in iter_feature_polygons(feature.get("geometry", {})):
                patches.append(Polygon(poly, closed=True))
                facecolors.append(facecolor)
            if cluster not in {"NS", "MISSING"}:
                centroid = feature["properties"].get("centroid") or feature["properties"].get("center")
                if centroid and len(centroid) == 2:
                    ax.text(
                        centroid[0],
                        centroid[1],
                        f"{simple_name}{significance_marker(float(subset.at[simple_name, 'local_p_value']))}",
                        fontsize=8.5,
                        ha="center",
                        va="center",
                        color="#111827",
                        bbox={
                            "boxstyle": "round,pad=0.15",
                            "facecolor": "white",
                            "edgecolor": "none",
                            "alpha": 0.8,
                        },
                        zorder=4,
                    )
        collection = PatchCollection(patches, facecolor=facecolors, edgecolor="black", linewidths=1.2)
        ax.add_collection(collection)
        add_map_frame(ax, f"{year} 年 eff 的 LISA 聚类图")
        draw_scs_inset(fig, scs_features, hainan_feature, guangdong_feature, guangxi_feature, color_lookup)
        draw_scale_and_legend(
            fig,
            [
                ("高-高", LISA_COLORS["HH"]),
                ("低-低", LISA_COLORS["LL"]),
                ("高-低", LISA_COLORS["HL"]),
                ("低-高", LISA_COLORS["LH"]),
                ("不显著", LISA_COLORS["NS"]),
                ("数据缺失", MISSING_COLOR),
            ],
        )
        fig.text(
            0.09,
            0.04,
            "注：局部 Moran's I 采用 9999 次置换检验，10%、5%、1% 水平分别标注 */**/***；未达阈值省份填灰。",
            ha="left",
            va="bottom",
            fontsize=9,
            color="#52606D",
        )
        out_path = OUT_DIR / f"25_eff_lisa_cluster_{year}.png"
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    return OUT_DIR / "25_eff_lisa_cluster_2022.png"


def build_markdown_table(result: pd.DataFrame) -> str:
    header = "| year | moran_i | z_value | p_value | significance |"
    sep = "|---:|---:|---:|---:|:---:|"
    rows = [
        f"| {int(row.year)} | {row.moran_i:.6f} | {row.z_value:.4f} | {row.p_value:.4f} | {row.significance} |"
        for row in result.itertuples(index=False)
    ]
    return "\n".join([header, sep, *rows])


def save_analysis(result: pd.DataFrame) -> Path:
    peak_row = result.loc[result["moran_i"].idxmax()]
    low_row = result.loc[result["moran_i"].idxmin()]
    strongest_z_row = result.loc[result["z_value"].idxmax()]
    significant_years = result.loc[result["p_value"] < 0.05, "year"].tolist()
    marginal_years = result.loc[(result["p_value"] >= 0.05) & (result["p_value"] < 0.10), "year"].tolist()

    lines = [
        "# 2015-2022 年全局 Moran's I 分析",
        "",
        "## 结果概览",
        "",
        build_markdown_table(result),
        "",
        "## 分析",
        "",
        (
            f"1. 2015-2022 年 Moran's I 均为正值，介于 {result['moran_i'].min():.3f} 到 "
            f"{result['moran_i'].max():.3f} 之间，说明省际碳排放效率整体存在正向空间自相关。"
        ),
        (
            f"2. 从变化趋势看，2015 年 Moran's I 为 "
            f"{result.loc[result['year'] == 2015, 'moran_i'].iloc[0]:.3f}，"
            f"2022 年升至 {result.loc[result['year'] == 2022, 'moran_i'].iloc[0]:.3f}；"
            f"样本期最低值出现在 {int(low_row['year'])} 年，为 {low_row['moran_i']:.3f}，"
            f"最高值出现在 {int(peak_row['year'])} 年，为 {peak_row['moran_i']:.3f}。"
        ),
        (
            f"3. 置换检验下，z 值最高的年份为 {int(strongest_z_row['year'])} 年，"
            f"对应 z={strongest_z_row['z_value']:.3f}；"
            f"{('、'.join(map(str, significant_years)) + ' 年') if significant_years else '无年份'}"
            f"在 5% 水平上显著，"
            f"{('、'.join(map(str, marginal_years)) + ' 年') if marginal_years else '无年份'}"
            "在 10% 水平上边际显著。"
        ),
        "4. 就论文表述而言，可以据此说明省际碳排放效率存在一定空间依赖性，继续使用空间计量模型具备经验依据。",
        "",
        "## 写作建议",
        "",
        (
            "可在正文中表述为：2015-2022 年我国省际碳排放效率的全局 Moran's I 均为正，"
            "且样本期末的空间集聚信号较强，说明碳排放效率存在一定的正向空间集聚特征，"
            "邻近省份之间呈现相似效率水平，为后续空间计量分析提供了依据。"
        ),
    ]

    out_path = OUT_DIR / "global_morans_i_2015_2022_analysis.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    configure_matplotlib()
    result = calculate_global_morans_i()
    local_result = build_local_moran_results()
    table_path = save_result_table(result)
    local_table_path = save_local_result_table(local_result)
    plot_path = save_plot(result)
    scatter_plot_path = save_moran_scatter_plot(local_result, result)
    lisa_plot_path = save_lisa_cluster_map(local_result)
    analysis_path = save_analysis(result)

    print(result.to_string(index=False))
    print(f"saved table: {table_path}")
    print(f"saved local table: {local_table_path}")
    print(f"saved plot: {plot_path}")
    print(f"saved plot: {scatter_plot_path}")
    print(f"saved plot: {lisa_plot_path}")
    print(f"saved analysis: {analysis_path}")


if __name__ == "__main__":
    main()
