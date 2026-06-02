from __future__ import annotations

STEP_SPEC = {
    "name": "空间效应森林图",
    "runner_type": "python",
    "command": [
        "python",
        "code/空间分析/50_空间效应森林图.py"
    ],
    "working_dir": "{PROJECT_ROOT}",
    "precheck_mode": "required_inputs",
    "required_inputs": [
        {
            "path": "{空间分析.output_root}/40_空间SDM主模型/空间效应分解表.csv",
            "kind": "csv",
            "required_columns": [
                "weight_type",
                "effect_type",
                "variable",
                "coef",
                "pvalue",
                "ll",
                "ul"
            ],
            "label": ""
        }
    ],
    "artifacts": {
        "tables": {
            "primary": None,
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
    "description": "根据 SDM 效应分解结果生成效应森林图、堆叠条形图、经济矩阵热力图和空间溢出网络图。",
    "notes": []
}

import argparse
import math
from pathlib import Path
import sys
import warnings

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import font_manager
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, stage_output_dir
from light_var_labels import light_var_label

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
OUT_DIR = stage_output_dir(CONFIG, "50_空间效应森林图")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EFFECT_TABLE_PATH = (
    resolve_project_path(CONFIG["output_root"]) / "40_空间SDM主模型" / "空间效应分解表.csv"
)
ECONOMIC_MATRIX_PATH = resolve_project_path(CONFIG["economic_matrix"])
GEO_INVERSE_MATRIX_PATH = resolve_project_path(CONFIG["geo_inverse_matrix"])
NESTED_MATRIX_PATH = resolve_project_path(CONFIG["economic_geo_nested_matrix"])
ADJACENCY_MATRIX_PATH = resolve_project_path(CONFIG["adjacency_matrix"])
GDP_PANEL_PATH = resolve_project_path(CONFIG["first_stage_panel"])
EFFICIENCY_PATH = resolve_project_path(CONFIG["efficiency_data"])
CAPITALS_PATH = resolve_project_path(CONFIG["capital_output"])
PROVINCE_GEOJSON_PATH = ROOT / "data" / "外部资料" / "中国_省.geojson"
LISA_PATH = (
    resolve_project_path(CONFIG["output_root"]) / "20_莫兰指数与LISA分析" / "局部莫兰指数_2015_2018_2022.csv"
)
DEFAULT_WEIGHT_TYPE = "economic_inv"
CORE_VARS = ["lntl", "ind", "urb", "rd", "open", "es"]
EFFECT_ORDER = ["LR_Direct", "LR_Indirect", "LR_Total"]
NETWORK_YEAR = 2022
NETWORK_EDGE_TOP_SHARE = 0.10
NETWORK_CURVE_STEPS = 48
NETWORK_BUNDLE_STRENGTH = 0.34
NETWORK_NODE_SIZE_RANGE = (90.0, 600.0)
NETWORK_LABEL_TOP_N = 10
NETWORK_TARGET_VARS = ["lntl", "es"]
NETWORK_PANEL_YEARS = [2015, 2018, 2022]
NETWORK_VAR_LABEL_MAP = {
    "lntl": light_var_label("lntl"),
    "es": "能源结构",
}
EFFECT_TITLE_MAP = {
    "LR_Direct": "直接效应",
    "LR_Indirect": "间接效应",
    "LR_Total": "总效应",
}
VAR_LABEL_MAP = {
    "lntl": light_var_label("lntl"),
    "ind": "产业结构",
    "urb": "城镇化水平",
    "rd": "研发投入",
    "open": "对外开放",
    "es": "能源结构",
}
ROW_SHADE_COLOR = "#F3F4F6"
EFFECT_Y_OFFSET = {
    "LR_Direct": -0.26,
    "LR_Indirect": 0.0,
    "LR_Total": 0.26,
}
EFFECT_COLOR_POSITION = {
    "LR_Direct": 0.15,
    "LR_Indirect": 0.50,
    "LR_Total": 0.85,
}
SIGNIFICANCE_ALPHA = {
    "sig_1": 0.98,
    "sig_5": 0.82,
    "sig_10": 0.64,
    "nonsig": 0.40,
}
LISA_COLORS = {
    "HH": "#B2182B",
    "LH": "#67A9CF",
    "LL": "#2166AC",
    "HL": "#EF8A62",
    "NS": "#D9D9D9",
}
WEIGHT_MATRIX_PATHS = {
    "economic_inv": ECONOMIC_MATRIX_PATH,
    "geographic_inv": GEO_INVERSE_MATRIX_PATH,
    "economic_geo_nested": NESTED_MATRIX_PATH,
    "adjacency_01": ADJACENCY_MATRIX_PATH,
}
WEIGHT_TYPE_LABEL_MAP = {
    "economic_inv": "经济倒数权重矩阵",
    "geographic_inv": "地理倒数权重矩阵",
    "economic_geo_nested": "经济地理嵌套权重矩阵",
    "adjacency_01": "邻接权重矩阵",
}


def parse_weight_type(argv: list[str]) -> str | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--weight-type", dest="weight_type")
    args, _ = parser.parse_known_args(argv)
    return args.weight_type


def configure_matplotlib() -> None:
    sns.set_theme(style="whitegrid")
    sns.set_context("talk")
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif_candidates = ["Times New Roman", "Times New Roman PS MT", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC"]
    serif = next((name for name in serif_candidates if name in available), "DejaVu Serif")
    chinese = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = [serif, chinese]
    matplotlib.rcParams["font.serif"] = [serif]
    matplotlib.rcParams["font.sans-serif"] = [chinese]
    matplotlib.rcParams["axes.unicode_minus"] = False
    matplotlib.rcParams["grid.linestyle"] = "--"
    matplotlib.rcParams["grid.linewidth"] = 0.7
    matplotlib.rcParams["grid.alpha"] = 0.20
    matplotlib.rcParams["grid.color"] = "#9CA3AF"
    matplotlib.rcParams["font.size"] = 11
    matplotlib.rcParams["axes.titlesize"] = 15
    matplotlib.rcParams["axes.labelsize"] = 11
    matplotlib.rcParams["xtick.labelsize"] = 10
    matplotlib.rcParams["ytick.labelsize"] = 10
    matplotlib.rcParams["legend.fontsize"] = 10
    matplotlib.rcParams["legend.title_fontsize"] = 11
    matplotlib.rcParams["figure.titlesize"] = 16


def format_decimal(value: float, digits: int = 4) -> str:
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}"


def significance_stars(p_value: float) -> str:
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def effect_group_color(effect_type: str, p_value: float):
    cmap = plt.get_cmap("twilight")
    rgba = list(cmap(EFFECT_COLOR_POSITION[effect_type]))
    if p_value < 0.01:
        rgba[3] = SIGNIFICANCE_ALPHA["sig_1"]
    elif p_value < 0.05:
        rgba[3] = SIGNIFICANCE_ALPHA["sig_5"]
    elif p_value < 0.10:
        rgba[3] = SIGNIFICANCE_ALPHA["sig_10"]
    else:
        rgba[3] = SIGNIFICANCE_ALPHA["nonsig"]
    return tuple(rgba)


def choose_weight_type(effect_df: pd.DataFrame, requested: str | None) -> str:
    available = effect_df["weight_type"].dropna().astype(str).unique().tolist()
    if requested:
        if requested not in available:
            raise ValueError(f"未找到权重矩阵 {requested!r}，可选值：{available}")
        return requested
    if DEFAULT_WEIGHT_TYPE in available:
        return DEFAULT_WEIGHT_TYPE
    if not available:
        raise ValueError("空间效应分解表中不存在可用的 weight_type。")
    return available[0]


def display_weight_type(weight_type: str) -> str:
    return WEIGHT_TYPE_LABEL_MAP.get(weight_type, weight_type)


def load_effect_table(weight_type: str | None) -> tuple[pd.DataFrame, str]:
    if not EFFECT_TABLE_PATH.exists():
        raise FileNotFoundError(f"未找到空间效应分解表：{EFFECT_TABLE_PATH}")

    df = pd.read_csv(EFFECT_TABLE_PATH, encoding="utf-8-sig")
    required = {"weight_type", "effect_type", "variable", "coef", "pvalue", "ll", "ul"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"空间效应分解表缺少字段：{sorted(missing)}")

    for col in ["coef", "pvalue", "ll", "ul"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["weight_type"] = df["weight_type"].astype(str).str.strip()
    df["effect_type"] = df["effect_type"].astype(str).str.strip()
    df["variable"] = df["variable"].astype(str).str.strip()

    chosen = choose_weight_type(df, weight_type)
    df = df.loc[
        df["weight_type"].eq(chosen)
        & df["effect_type"].isin(EFFECT_ORDER)
        & df["variable"].isin(CORE_VARS)
    ].copy()

    if df.empty:
        raise ValueError(f"权重矩阵 {chosen!r} 下没有可用的空间效应数据。")

    df["variable"] = pd.Categorical(df["variable"], categories=CORE_VARS, ordered=True)
    df["effect_type"] = pd.Categorical(df["effect_type"], categories=EFFECT_ORDER, ordered=True)
    df = df.sort_values(["variable", "effect_type"]).reset_index(drop=True)
    return df, chosen


def load_average_gdp_for_heatmap(matrix_index: list[str]) -> pd.Series:
    df = pd.read_csv(GDP_PANEL_PATH, encoding="utf-8-sig")
    required = {"province", "GDP_constant"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"GDP 数据缺少字段：{sorted(missing)}")

    df["province"] = df["province"].astype(str).str.strip()
    df["GDP_constant"] = pd.to_numeric(df["GDP_constant"], errors="coerce")
    df = df.dropna(subset=["province", "GDP_constant"]).copy()
    avg_gdp = df.groupby("province", sort=False)["GDP_constant"].mean()

    missing_provinces = [province for province in matrix_index if province not in avg_gdp.index]
    if missing_provinces:
        raise ValueError(f"GDP 数据缺少这些省份：{missing_provinces}")
    return avg_gdp.loc[matrix_index]


def row_standardize_matrix(matrix_df: pd.DataFrame) -> pd.DataFrame:
    values = matrix_df.to_numpy(dtype=float)
    row_sums = values.sum(axis=1, keepdims=True)
    normalized = np.divide(values, row_sums, out=np.zeros_like(values, dtype=float), where=row_sums != 0)
    return pd.DataFrame(normalized, index=matrix_df.index, columns=matrix_df.columns)


def minmax_scale(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    arr_min = float(np.nanmin(arr))
    arr_max = float(np.nanmax(arr))
    if not np.isfinite(arr_min) or not np.isfinite(arr_max):
        raise ValueError("缩放数据包含无效数值。")
    if math.isclose(arr_min, arr_max):
        return np.full(arr.shape, (lower + upper) / 2.0, dtype=float)
    return lower + (arr - arr_min) * (upper - lower) / (arr_max - arr_min)


def load_weight_matrix_by_type(weight_type: str) -> pd.DataFrame:
    path = WEIGHT_MATRIX_PATHS.get(weight_type)
    if path is None:
        raise ValueError(f"未配置权重矩阵路径：{weight_type}")
    if not path.exists():
        raise FileNotFoundError(f"未找到权重矩阵文件：{path}")

    matrix_df = pd.read_csv(path, encoding="utf-8-sig", index_col=0)
    matrix_df.index = matrix_df.index.astype(str).str.strip()
    matrix_df.columns = matrix_df.columns.astype(str).str.strip()
    matrix_df = matrix_df.loc[matrix_df.index, matrix_df.index]
    matrix_df = matrix_df.apply(pd.to_numeric, errors="coerce")
    if matrix_df.isna().any().any():
        raise ValueError(f"权重矩阵 {path.name} 含有非数值字段。")
    return row_standardize_matrix(matrix_df)


def load_capital_coordinates() -> pd.DataFrame:
    if not CAPITALS_PATH.exists():
        raise FileNotFoundError(f"未找到省会坐标表：{CAPITALS_PATH}")
    capitals = pd.read_csv(CAPITALS_PATH, encoding="utf-8-sig")
    required = {"province", "capital", "center_lon", "center_lat"}
    missing = required - set(capitals.columns)
    if missing:
        raise ValueError(f"省会坐标表缺少字段：{sorted(missing)}")

    capitals["province"] = capitals["province"].astype(str).str.strip()
    capitals["center_lon"] = pd.to_numeric(capitals["center_lon"], errors="coerce")
    capitals["center_lat"] = pd.to_numeric(capitals["center_lat"], errors="coerce")
    capitals = capitals.dropna(subset=["province", "center_lon", "center_lat"]).copy()
    return capitals[["province", "capital", "center_lon", "center_lat"]]


def load_lisa_clusters(year: int) -> pd.DataFrame:
    if not LISA_PATH.exists():
        raise FileNotFoundError(f"未找到 LISA 结果：{LISA_PATH}")
    lisa_df = pd.read_csv(LISA_PATH, encoding="utf-8-sig")
    required = {"year", "province", "cluster"}
    missing = required - set(lisa_df.columns)
    if missing:
        raise ValueError(f"LISA 结果缺少字段：{sorted(missing)}")

    lisa_df["year"] = pd.to_numeric(lisa_df["year"], errors="coerce")
    lisa_df["province"] = lisa_df["province"].astype(str).str.strip()
    lisa_df["cluster"] = lisa_df["cluster"].astype(str).str.strip().replace({"": "NS"})
    lisa_df = lisa_df.dropna(subset=["year"]).copy()
    lisa_df["year"] = lisa_df["year"].astype(int)
    lisa_df = lisa_df.loc[lisa_df["year"].eq(year), ["province", "cluster"]].drop_duplicates("province")
    if lisa_df.empty:
        raise ValueError(f"LISA 结果中不存在 {year} 年数据。")
    return lisa_df


def load_efficiency_snapshot(year: int) -> pd.DataFrame:
    if not EFFICIENCY_PATH.exists():
        raise FileNotFoundError(f"未找到效率数据：{EFFICIENCY_PATH}")
    eff_df = pd.read_csv(EFFICIENCY_PATH, encoding="utf-8-sig")
    required = {"year", "province", "eff"}
    missing = required - set(eff_df.columns)
    if missing:
        raise ValueError(f"效率数据缺少字段：{sorted(missing)}")

    eff_df["year"] = pd.to_numeric(eff_df["year"], errors="coerce")
    eff_df["province"] = eff_df["province"].astype(str).str.strip()
    eff_df["eff"] = pd.to_numeric(eff_df["eff"], errors="coerce")
    eff_df = eff_df.dropna(subset=["year", "province", "eff"]).copy()
    eff_df["year"] = eff_df["year"].astype(int)
    snapshot = eff_df.loc[eff_df["year"].eq(year), ["province", "eff"]].drop_duplicates("province")
    if snapshot.empty:
        raise ValueError(f"效率数据中不存在 {year} 年截面。")
    return snapshot


def build_network_node_table(weight_df: pd.DataFrame, year: int) -> pd.DataFrame:
    capitals = load_capital_coordinates()
    lisa_df = load_lisa_clusters(year)
    eff_df = load_efficiency_snapshot(year)

    node_df = capitals.merge(eff_df, on="province", how="inner").merge(lisa_df, on="province", how="left")
    node_df["cluster"] = node_df["cluster"].fillna("NS")
    node_df["node_color"] = node_df["cluster"].map(LISA_COLORS).fillna(LISA_COLORS["NS"])
    node_df["node_size"] = minmax_scale(node_df["eff"].to_numpy(dtype=float), *NETWORK_NODE_SIZE_RANGE)

    province_order = weight_df.index.tolist()
    missing = [province for province in province_order if province not in node_df["province"].tolist()]
    if missing:
        raise ValueError(f"网络节点数据缺少这些省份：{missing}")
    return node_df.set_index("province").loc[province_order].reset_index()


def build_spillover_edges(effect_df: pd.DataFrame, weight_df: pd.DataFrame, weight_type: str) -> pd.DataFrame:
    indirect_df = effect_df.loc[effect_df["effect_type"].eq("LR_Indirect"), ["variable", "coef", "pvalue"]].copy()
    indirect_df = indirect_df.rename(columns={"coef": "indirect_coef", "pvalue": "indirect_pvalue"})
    province_order = weight_df.index.tolist()

    edges: list[dict[str, object]] = []
    for row in indirect_df.itertuples(index=False):
        spillover_matrix = weight_df * float(row.indirect_coef)
        values = spillover_matrix.to_numpy(dtype=float)
        abs_values = np.abs(values)
        positive_abs = abs_values[abs_values > 0]
        if positive_abs.size == 0:
            threshold = float("inf")
        else:
            threshold = float(np.quantile(positive_abs, 1.0 - NETWORK_EDGE_TOP_SHARE))

        for i, source in enumerate(province_order):
            for j, target in enumerate(province_order):
                if i == j:
                    continue
                weight = float(values[i, j])
                abs_weight = abs(weight)
                if abs_weight <= 0:
                    continue
                edges.append(
                    {
                        "weight_type": weight_type,
                        "variable": row.variable,
                        "source": source,
                        "target": target,
                        "spillover_weight": weight,
                        "abs_weight": abs_weight,
                        "indirect_coef": float(row.indirect_coef),
                        "indirect_pvalue": float(row.indirect_pvalue),
                        "retained": int(abs_weight >= threshold),
                        "threshold": threshold,
                        "sign": "positive" if weight > 0 else "negative",
                    }
                )

    edge_df = pd.DataFrame(edges)
    if edge_df.empty:
        raise ValueError("未构造出空间溢出边数据。")
    edge_df["rank_within_variable"] = (
        edge_df.groupby("variable")["abs_weight"].rank(method="first", ascending=False).astype(int)
    )
    return edge_df.sort_values(["variable", "rank_within_variable", "source", "target"]).reset_index(drop=True)


def draw_background_map(ax, geo_df: gpd.GeoDataFrame) -> None:
    geo_df.boundary.plot(ax=ax, color="#4B5563", linewidth=0.9, zorder=0)
    ax.set_facecolor("#FCFCFD")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def add_north_arrow(ax, x: float = 0.50, y: float = 0.95, size: float = 0.08) -> None:
    ax.annotate(
        "",
        xy=(x, y),
        xytext=(x, y - size),
        xycoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", color="#111827", lw=1.4, shrinkA=0, shrinkB=0),
        zorder=6,
    )
    ax.text(
        x,
        y + 0.01,
        "N",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontweight="bold",
        color="#111827",
        zorder=6,
    )


def add_scale_bar(
    ax,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    length_km: float = 500.0,
) -> None:
    lat_ref = float(np.mean(ylim))
    km_per_degree_lon = 111.32 * math.cos(math.radians(lat_ref))
    if km_per_degree_lon <= 0:
        return
    bar_length_deg = length_km / km_per_degree_lon
    x_start = xlim[0] + 0.05 * (xlim[1] - xlim[0])
    y_base = ylim[0] + 0.06 * (ylim[1] - ylim[0])
    x_end = x_start + bar_length_deg
    tick_height = 0.012 * (ylim[1] - ylim[0])

    ax.plot([x_start, x_end], [y_base, y_base], color="#111827", linewidth=2.0, zorder=6)
    ax.plot([x_start, x_start], [y_base - tick_height, y_base + tick_height], color="#111827", linewidth=1.6, zorder=6)
    ax.plot([x_end, x_end], [y_base - tick_height, y_base + tick_height], color="#111827", linewidth=1.6, zorder=6)
    ax.text(
        (x_start + x_end) / 2.0,
        y_base + 1.5 * tick_height,
        f"{int(length_km)} km",
        ha="center",
        va="bottom",
        color="#111827",
        zorder=6,
    )


def plot_gradient_edge(
    ax,
    x: np.ndarray,
    y: np.ndarray,
    color: str,
    linewidth: float,
    edge_alpha: float,
    lighten_end: float = 0.72,
    zorder: int = 4,
) -> None:
    points = np.column_stack([x, y])
    segments = np.stack([points[:-1], points[1:]], axis=1)
    base_rgba = np.array(matplotlib.colors.to_rgba(color), dtype=float)
    white_rgba = np.array([1.0, 1.0, 1.0, 1.0], dtype=float)
    blend = np.linspace(0.0, lighten_end, len(segments))
    colors = np.array([(1.0 - t) * base_rgba + t * white_rgba for t in blend], dtype=float)
    colors[:, 3] = edge_alpha
    collection = LineCollection(
        segments,
        colors=colors,
        linewidths=linewidth,
        capstyle="round",
        joinstyle="round",
        zorder=zorder,
    )
    ax.add_collection(collection)


def compute_bundled_curve(
    source_xy: tuple[float, float],
    target_xy: tuple[float, float],
    centroid_xy: tuple[float, float],
    curvature: float,
    steps: int = NETWORK_CURVE_STEPS,
) -> tuple[np.ndarray, np.ndarray]:
    x0, y0 = source_xy
    x1, y1 = target_xy
    xc, yc = centroid_xy
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    dx, dy = x1 - x0, y1 - y0
    distance = math.hypot(dx, dy)
    if distance == 0:
        return np.array([x0, x1]), np.array([y0, y1])

    perp_x, perp_y = -dy / distance, dx / distance
    curve_sign = 1.0 if (x0 + y0) <= (x1 + y1) else -1.0
    bend = 0.08 * distance * curve_sign
    control_x = mx * (1.0 - curvature) + xc * curvature + perp_x * bend
    control_y = my * (1.0 - curvature) + yc * curvature + perp_y * bend
    t = np.linspace(0.0, 1.0, steps)
    x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * control_x + t**2 * x1
    y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * control_y + t**2 * y1
    return x, y


def add_network_legends(fig) -> None:
    lisa_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=0.7,
            markersize=8,
            label=label,
        )
        for label, color in [
            ("高-高", LISA_COLORS["HH"]),
            ("高-低", LISA_COLORS["HL"]),
            ("低-高", LISA_COLORS["LH"]),
            ("低-低", LISA_COLORS["LL"]),
            ("不显著", LISA_COLORS["NS"]),
        ]
    ]
    edge_handles = [
        Line2D([0], [0], color="#C2410C", linewidth=2.4, alpha=0.85, label="正向溢出"),
        Line2D([0], [0], color="#1D4ED8", linewidth=2.4, alpha=0.85, label="负向溢出"),
    ]

    size_values = np.array([0.30, 0.60, 0.90], dtype=float)
    size_markers = minmax_scale(size_values, *NETWORK_NODE_SIZE_RANGE)
    size_handles = [
        plt.scatter([], [], s=size, color="#9CA3AF", alpha=0.70, edgecolors="white", linewidths=0.7)
        for size in size_markers
    ]
    size_labels = [f"eff={value:.2f}" for value in size_values]

    fig.legend(
        lisa_handles,
        [handle.get_label() for handle in lisa_handles],
        loc="lower left",
        bbox_to_anchor=(0.01, 0.06, 0.38, 0.11),
        ncol=5,
        frameon=True,
        title="LISA 聚类",
        mode="expand",
        borderaxespad=0.0,
    )
    fig.legend(
        edge_handles,
        [handle.get_label() for handle in edge_handles],
        loc="lower left",
        bbox_to_anchor=(0.39, 0.06, 0.26, 0.11),
        ncol=2,
        frameon=True,
        title="边方向与符号",
        mode="expand",
        borderaxespad=0.0,
    )
    fig.legend(
        size_handles,
        size_labels,
        loc="lower left",
        bbox_to_anchor=(0.71, 0.06, 0.28, 0.11),
        ncol=3,
        frameon=True,
        title="节点大小",
        scatterpoints=1,
        mode="expand",
        borderaxespad=0.0,
    )


def add_network_legends_to_axis(ax) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    box_specs = [
        (0.04, 0.71, 0.92, 0.21, "LISA 聚类"),
        (0.04, 0.45, 0.92, 0.21, "边方向与符号"),
        (0.04, 0.19, 0.92, 0.21, "节点大小"),
    ]
    for x, y, w, h, title in box_specs:
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor="#D1D5DB", linewidth=1.0))
        ax.text(x + w / 2.0, y + h - 0.05, title, ha="center", va="center", color="black")

    lisa_items = [
        ("高-高", LISA_COLORS["HH"]),
        ("高-低", LISA_COLORS["HL"]),
        ("低-高", LISA_COLORS["LH"]),
        ("低-低", LISA_COLORS["LL"]),
        ("不显著", LISA_COLORS["NS"]),
    ]
    lisa_xs = [0.10, 0.28, 0.46, 0.64, 0.82]
    for x, (label, color) in zip(lisa_xs, lisa_items):
        ax.scatter(x, 0.79, s=95, color=color, edgecolors="white", linewidths=0.7)
        ax.text(x + 0.03, 0.79, label, ha="left", va="center", color="black")

    ax.plot([0.23, 0.41], [0.53, 0.53], color="#C2410C", linewidth=2.8, alpha=0.9, solid_capstyle="round")
    ax.text(0.43, 0.53, "正向溢出", ha="left", va="center", color="black")
    ax.plot([0.58, 0.76], [0.53, 0.53], color="#1D4ED8", linewidth=2.8, alpha=0.9, solid_capstyle="round")
    ax.text(0.78, 0.53, "负向溢出", ha="left", va="center", color="black")

    size_values = np.array([0.30, 0.60, 0.90], dtype=float)
    size_markers = minmax_scale(size_values, *NETWORK_NODE_SIZE_RANGE)
    xs = [0.24, 0.50, 0.76]
    for x, size, value in zip(xs, size_markers, size_values):
        ax.scatter(x, 0.285, s=size, color="#BFC5D1", edgecolors="white", linewidths=0.7, alpha=0.9)
        ax.text(x, 0.245, f"eff={value:.2f}", ha="center", va="top", color="black")

    ax.text(
        0.04,
        0.05,
        "注：边颜色由出发地深色向目的地浅色过渡，弱连接通过较低透明度淡化；比例尺按图幅中心纬度换算 500 km 的经度长度。",
        ha="left",
        va="bottom",
        color="black",
        wrap=True,
    )


def draw_spillover_panel(
    ax,
    geo_df: gpd.GeoDataFrame,
    node_df: pd.DataFrame,
    subset: pd.DataFrame,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    title: str,
    show_scale: bool = True,
    show_north: bool = True,
) -> None:
    draw_background_map(ax, geo_df)
    node_lookup = node_df.set_index("province")
    centroid_xy = (
        float(node_df["center_lon"].mean()),
        float(node_df["center_lat"].mean()),
    )
    top_label_provinces = set(node_df.nlargest(NETWORK_LABEL_TOP_N, "eff")["province"].tolist())
    top_label_provinces.update(
        node_df.loc[node_df["cluster"].isin(["HH", "HL", "LH", "LL"]), "province"].tolist()
    )

    max_abs = float(subset["abs_weight"].max()) if not subset.empty else 1.0
    for edge in subset.itertuples(index=False):
        source = node_lookup.loc[edge.source]
        target = node_lookup.loc[edge.target]
        x, y = compute_bundled_curve(
            (float(source["center_lon"]), float(source["center_lat"])),
            (float(target["center_lon"]), float(target["center_lat"])),
            centroid_xy,
            curvature=NETWORK_BUNDLE_STRENGTH,
        )
        strength_ratio = float(edge.abs_weight) / max_abs if max_abs > 0 else 0.0
        linewidth = 0.6 + 3.0 * strength_ratio
        edge_alpha = 0.16 + 0.78 * strength_ratio
        color = "#C2410C" if edge.spillover_weight > 0 else "#1D4ED8"
        plot_gradient_edge(
            ax=ax,
            x=x,
            y=y,
            color=color,
            linewidth=linewidth,
            edge_alpha=edge_alpha,
            lighten_end=0.78 if strength_ratio < 0.25 else 0.62,
            zorder=4,
        )

    ax.scatter(
        node_df["center_lon"],
        node_df["center_lat"],
        s=node_df["node_size"],
        c=node_df["node_color"],
        edgecolors="white",
        linewidths=0.9,
        alpha=0.94,
        zorder=2,
    )

    for row in node_df.itertuples(index=False):
        if row.province not in top_label_provinces:
            continue
        ax.text(
            row.center_lon + 0.25,
            row.center_lat + 0.18,
            row.province,
            color="#111827",
            zorder=3,
        )

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    if show_scale:
        add_scale_bar(ax, xlim, ylim, length_km=500.0)
    if show_north:
        add_north_arrow(ax)
    ax.set_title(title, pad=10)


def plot_spillover_network_maps(effect_df: pd.DataFrame, weight_type: str) -> tuple[list[Path], Path, Path]:
    weight_df = load_weight_matrix_by_type(weight_type)
    node_df = build_network_node_table(weight_df, NETWORK_YEAR)
    edge_df = build_spillover_edges(effect_df, weight_df, weight_type)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not parse column 'adcode' as JSON; leaving as string",
            category=UserWarning,
        )
        geo_df = gpd.read_file(PROVINCE_GEOJSON_PATH)

    x_padding = 2.0
    y_padding = 2.0
    xlim = (
        float(node_df["center_lon"].min() - x_padding),
        float(node_df["center_lon"].max() + x_padding),
    )
    ylim = (
        float(node_df["center_lat"].min() - y_padding),
        float(node_df["center_lat"].max() + y_padding),
    )

    network_paths: list[Path] = []
    for variable in NETWORK_TARGET_VARS:
        fig, ax = plt.subplots(figsize=(11.5, 9.8))
        subset = edge_df.loc[edge_df["variable"].eq(variable) & edge_df["retained"].eq(1)].copy()
        label = NETWORK_VAR_LABEL_MAP.get(variable, VAR_LABEL_MAP.get(variable, variable))
        indirect_coef = float(
            effect_df.loc[
                effect_df["effect_type"].eq("LR_Indirect") & effect_df["variable"].eq(variable), "coef"
            ].iloc[0]
        )
        indirect_p = float(
            effect_df.loc[
                effect_df["effect_type"].eq("LR_Indirect") & effect_df["variable"].eq(variable), "pvalue"
            ].iloc[0]
        )
        draw_spillover_panel(
            ax=ax,
            geo_df=geo_df,
            node_df=node_df,
            subset=subset,
            xlim=xlim,
            ylim=ylim,
            title=f"{label}\n间接效应={format_decimal(indirect_coef)}，p={format_decimal(indirect_p)}",
        )
        fig.tight_layout(rect=(0.01, 0.14, 0.99, 0.97))
        add_network_legends(fig)

        network_path = resolve_output_path(OUT_DIR / f"50_{label}空间溢出网络图_{weight_type}.png")
        fig.savefig(network_path, dpi=320, bbox_inches="tight")
        plt.close(fig)
        network_paths.append(network_path)

    edge_out = resolve_output_path(OUT_DIR / f"50_空间溢出网络边表_{weight_type}.csv")
    edge_df.to_csv(edge_out, index=False, encoding="utf-8-sig")
    node_out = resolve_output_path(OUT_DIR / f"50_空间溢出网络节点表_{weight_type}.csv")
    node_df.to_csv(node_out, index=False, encoding="utf-8-sig")
    return network_paths, edge_out, node_out


def plot_lntl_spillover_network_panel(effect_df: pd.DataFrame, weight_type: str) -> Path:
    weight_df = load_weight_matrix_by_type(weight_type)
    edge_df = build_spillover_edges(effect_df, weight_df, weight_type)
    subset = edge_df.loc[edge_df["variable"].eq("lntl") & edge_df["retained"].eq(1)].copy()
    if subset.empty:
        raise ValueError("夜间灯光强度未筛选出可绘制的核心溢出边。")

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not parse column 'adcode' as JSON; leaving as string",
            category=UserWarning,
        )
        geo_df = gpd.read_file(PROVINCE_GEOJSON_PATH)

    reference_nodes = build_network_node_table(weight_df, NETWORK_PANEL_YEARS[-1])
    x_padding = 2.0
    y_padding = 2.0
    xlim = (
        float(reference_nodes["center_lon"].min() - x_padding),
        float(reference_nodes["center_lon"].max() + x_padding),
    )
    ylim = (
        float(reference_nodes["center_lat"].min() - y_padding),
        float(reference_nodes["center_lat"].max() + y_padding),
    )

    indirect_coef = float(
        effect_df.loc[
            effect_df["effect_type"].eq("LR_Indirect") & effect_df["variable"].eq("lntl"), "coef"
        ].iloc[0]
    )
    indirect_p = float(
        effect_df.loc[
            effect_df["effect_type"].eq("LR_Indirect") & effect_df["variable"].eq("lntl"), "pvalue"
        ].iloc[0]
    )

    fig = plt.figure(figsize=(17.6, 12.4))
    gs = fig.add_gridspec(2, 2, left=0.015, right=0.985, bottom=0.055, top=0.93, wspace=0.035, hspace=0.06)
    axes = [
        fig.add_subplot(gs[0, 0]),
        fig.add_subplot(gs[0, 1]),
        fig.add_subplot(gs[1, 0]),
    ]
    note_ax = fig.add_subplot(gs[1, 1])

    for ax, year in zip(axes, NETWORK_PANEL_YEARS):
        node_df = build_network_node_table(weight_df, year)
        draw_spillover_panel(
            ax=ax,
            geo_df=geo_df,
            node_df=node_df,
            subset=subset,
            xlim=xlim,
            ylim=ylim,
            title=f"{year} 年",
            show_scale=True,
            show_north=True,
        )

    add_network_legends_to_axis(note_ax)
    fig.suptitle(
        f"夜间灯光强度空间溢出网络图（2015、2018、2022）\n间接效应={format_decimal(indirect_coef)}，p={format_decimal(indirect_p)}",
        y=0.98,
    )
    out_path = resolve_output_path(OUT_DIR / f"50_夜间灯光强度空间溢出网络图_2015_2018_2022_{weight_type}.png")
    fig.savefig(out_path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return out_path


def build_plot_frame(effect_df: pd.DataFrame) -> pd.DataFrame:
    index = pd.MultiIndex.from_product([CORE_VARS, EFFECT_ORDER], names=["variable", "effect_type"])
    frame = (
        effect_df.set_index(["variable", "effect_type"])[["coef", "pvalue", "ll", "ul"]]
        .reindex(index)
        .reset_index()
    )
    missing_mask = frame[["coef", "pvalue", "ll", "ul"]].isna().any(axis=1)
    if missing_mask.any():
        missing_rows = frame.loc[missing_mask, ["variable", "effect_type"]]
        raise ValueError(f"存在缺失效应结果：{missing_rows.to_dict(orient='records')}")
    return frame


def compute_ticks(xmin: float, xmax: float) -> list[float]:
    candidates = [-100.0, -10.0, -1.0, -0.1, 0.0, 0.1, 1.0, 10.0, 100.0]
    ticks = [tick for tick in candidates if xmin <= tick <= xmax]
    if 0.0 not in ticks:
        ticks.append(0.0)
    return sorted(set(ticks))


def resolve_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    try:
        with open(path, "a", encoding="utf-8"):
            return path
    except PermissionError:
        return path.with_name(f"{path.stem}_latest{path.suffix}")


def add_row_shading(ax, n_rows: int) -> None:
    for idx in range(n_rows):
        if idx % 2 == 0:
            ax.axhspan(idx - 0.5, idx + 0.5, color=ROW_SHADE_COLOR, zorder=0)


def add_figure_legend(fig, anchor_x: float) -> None:
    group_handles = [
        Line2D([0], [0], color=effect_group_color(effect_type, 0.001), marker="s", linewidth=2.0, markersize=7)
        for effect_type in EFFECT_ORDER
    ]
    group_labels = [EFFECT_TITLE_MAP[effect_type] for effect_type in EFFECT_ORDER]
    legend = fig.legend(
        group_handles,
        group_labels,
        loc="lower left",
        frameon=True,
        borderpad=0.35,
        labelspacing=0.5,
        handlelength=1.5,
        ncol=len(group_handles),
        bbox_to_anchor=(anchor_x, 0.02),
        columnspacing=0.75,
        handletextpad=0.4,
    )
    legend.get_frame().set_edgecolor("#D1D5DB")
    legend.get_frame().set_linewidth(0.8)
    legend.get_frame().set_alpha(0.96)


def plot_sorted_economic_matrix_heatmap() -> Path:
    matrix_df = pd.read_csv(ECONOMIC_MATRIX_PATH, encoding="utf-8-sig", index_col=0)
    matrix_df.index = matrix_df.index.astype(str).str.strip()
    matrix_df.columns = matrix_df.columns.astype(str).str.strip()
    matrix_df = matrix_df.loc[matrix_df.index, matrix_df.index]
    matrix_df = row_standardize_matrix(matrix_df)

    avg_gdp = load_average_gdp_for_heatmap(matrix_df.index.tolist())
    province_order = avg_gdp.sort_values(ascending=False).index.tolist()
    sorted_matrix = matrix_df.loc[province_order, province_order]
    positive_values = sorted_matrix.to_numpy(dtype=float)
    positive_values = positive_values[positive_values > 0]
    if positive_values.size == 0:
        raise ValueError("行标准化经济矩阵中不存在可用于对数色轴的正值。")
    vmin = float(np.nanmin(positive_values))
    vmax = float(np.nanmax(positive_values))

    fig, ax = plt.subplots(figsize=(13.8, 11.6))
    sns.heatmap(
        sorted_matrix,
        ax=ax,
        cmap="YlGnBu",
        norm=LogNorm(vmin=vmin, vmax=vmax),
        cbar_kws={"shrink": 0.88, "label": "行标准化经济权重（对数色轴）"},
        square=True,
        linewidths=0.15,
        linecolor="#F3F4F6",
    )
    ax.set_title("按 GDP 从高到低排序的行标准化经济矩阵热力图", pad=12)
    ax.set_xlabel("省份（按平均 GDP 降序）")
    ax.set_ylabel("省份（按平均 GDP 降序）")
    ax.tick_params(axis="x", rotation=90)
    ax.tick_params(axis="y", rotation=0)
    fig.tight_layout()

    out_path = resolve_output_path(OUT_DIR / "50_行标准化经济矩阵热力图_GDP降序.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_effect_stacked_bar(effect_df: pd.DataFrame, weight_type: str) -> Path:
    plot_df = build_plot_frame(effect_df).copy()
    weight_label = display_weight_type(weight_type)
    variable_order = list(reversed(CORE_VARS))
    label_order = [VAR_LABEL_MAP.get(var, var) for var in variable_order]
    pivot_df = (
        plot_df.assign(variable=plot_df["variable"].astype(str))
        .pivot(index="variable", columns="effect_type", values="coef")
        .reindex(variable_order)
    )

    fig, ax = plt.subplots(figsize=(12.0, 8.0))
    add_row_shading(ax, len(variable_order))

    y_pos = np.arange(len(variable_order))
    left_pos = np.zeros(len(variable_order), dtype=float)
    left_neg = np.zeros(len(variable_order), dtype=float)

    stack_effects = ["LR_Direct", "LR_Indirect"]
    for effect_type in stack_effects:
        values = pivot_df[effect_type].to_numpy(dtype=float)
        color = effect_group_color(effect_type, 0.001)
        positive = np.clip(values, 0, None)
        negative = np.clip(values, None, 0)

        ax.barh(
            y_pos,
            positive,
            left=left_pos,
            height=0.56,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
            label=EFFECT_TITLE_MAP[effect_type],
        )
        ax.barh(
            y_pos,
            negative,
            left=left_neg,
            height=0.56,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        left_pos = left_pos + positive
        left_neg = left_neg + negative

    totals = pivot_df["LR_Total"].to_numpy(dtype=float)
    ax.scatter(
        totals,
        y_pos,
        marker="D",
        s=52,
        color=effect_group_color("LR_Total", 0.001),
        edgecolor="white",
        linewidth=0.8,
        zorder=4,
        label=EFFECT_TITLE_MAP["LR_Total"],
    )
    for idx, total in enumerate(totals):
        offset = 0.15 if total >= 0 else -0.15
        ha = "left" if total >= 0 else "right"
        ax.text(
            total + offset,
            idx,
            format_decimal(total),
            ha=ha,
            va="center",
            color="black",
        )

    x_abs = max(
        float(np.abs(left_pos).max()),
        float(np.abs(left_neg).max()),
        float(np.abs(totals).max()),
        0.5,
    )
    x_lim = x_abs * 1.18
    ax.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax.set_xlim(-x_lim, x_lim)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(label_order)
    ax.invert_yaxis()
    ax.set_xlabel("效应估计值")
    ax.set_title(f"核心解释变量空间效应分解图（{weight_label}）", pad=12)
    ax.grid(axis="x", linestyle="--", alpha=0.22)
    ax.grid(axis="y", linestyle=":", alpha=0.10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend = ax.legend(
        loc="lower right",
        ncol=3,
        frameon=True,
        borderpad=0.5,
        handlelength=1.6,
        columnspacing=0.9,
    )
    legend.get_frame().set_edgecolor("#D1D5DB")
    legend.get_frame().set_linewidth(0.8)
    legend.get_frame().set_alpha(0.96)

    fig.tight_layout()
    out_path = resolve_output_path(OUT_DIR / f"50_核心解释变量空间效应分解堆叠条形图_{weight_type}.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_effect_forest(effect_df: pd.DataFrame, weight_type: str) -> Path:
    plot_df = build_plot_frame(effect_df)
    weight_label = display_weight_type(weight_type)
    variable_order = list(reversed(CORE_VARS))
    base_y_lookup = {var: idx for idx, var in enumerate(variable_order)}
    plot_df["base_y"] = plot_df["variable"].map(base_y_lookup).astype(float)
    plot_df["y"] = plot_df["base_y"] + plot_df["effect_type"].map(EFFECT_Y_OFFSET).astype(float)

    xmin = float(min(plot_df["ll"].min(), -0.5))
    xmax = float(max(plot_df["ul"].max(), 0.5))
    if xmin >= 0:
        xmin = -0.1
    if xmax <= 0:
        xmax = 0.1
    xmin *= 1.08
    xmax *= 1.08
    ticks = compute_ticks(xmin, xmax)

    fig = plt.figure(figsize=(14.0, 8.4))
    gs = fig.add_gridspec(1, 5, width_ratios=[1.65, 4.45, 1.55, 1.55, 1.55], wspace=0.03)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_plot = fig.add_subplot(gs[0, 1])
    ax_text_direct = fig.add_subplot(gs[0, 2], sharey=ax_plot)
    ax_text_indirect = fig.add_subplot(gs[0, 3], sharey=ax_plot)
    ax_text_total = fig.add_subplot(gs[0, 4], sharey=ax_plot)
    text_axes = {
        "LR_Direct": ax_text_direct,
        "LR_Indirect": ax_text_indirect,
        "LR_Total": ax_text_total,
    }

    for ax in [ax_left, ax_plot, ax_text_direct, ax_text_indirect, ax_text_total]:
        add_row_shading(ax, len(variable_order))

    plot_rows = plot_df.sort_values(["base_y", "effect_type"]).reset_index(drop=True)
    for row in plot_rows.itertuples(index=False):
        color = effect_group_color(str(row.effect_type), float(row.pvalue))
        ax_plot.hlines(row.y, row.ll, row.ul, color=color, linewidth=1.8, zorder=3)
        ax_plot.vlines([row.ll, row.ul], row.y - 0.07, row.y + 0.07, color=color, linewidth=1.25, zorder=3)
        ax_plot.scatter(row.coef, row.y, marker="s", s=28, color=color, edgecolor=color, linewidth=0.6, zorder=4)

    ax_plot.axvline(0, color="#6B7280", linewidth=1.0, zorder=2)
    ax_plot.set_xscale("symlog", linthresh=0.2)
    ax_plot.set_xlim(xmin, xmax)
    ax_plot.set_ylim(-0.5, len(variable_order) - 0.5)
    ax_plot.invert_yaxis()
    ax_plot.set_yticks(np.arange(len(variable_order)))
    ax_plot.set_yticklabels([])
    ax_plot.set_xticks(ticks)
    ax_plot.set_xticklabels([f"{tick:.1f}" if abs(tick) < 1 else f"{tick:.0f}" for tick in ticks])
    ax_plot.set_xlabel("效应估计值", labelpad=10)
    ax_plot.set_title("直接效应 / 间接效应 / 总效应", pad=10)
    ax_plot.grid(axis="y", linestyle=":", alpha=0.18)
    ax_plot.spines["top"].set_visible(False)
    ax_plot.spines["right"].set_visible(False)
    ax_plot.spines["left"].set_visible(False)
    add_figure_legend(fig, ax_text_direct.get_position().x0)

    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(ax_plot.get_ylim())
    ax_left.axis("off")
    ax_left.text(0.00, 1.02, "变量", transform=ax_left.transAxes, ha="left", va="bottom", color="black", fontweight="bold")
    for idx, variable in enumerate(variable_order):
        ax_left.text(0.00, idx, VAR_LABEL_MAP.get(variable, variable), ha="left", va="center", color="black")

    for effect_type, ax in text_axes.items():
        ax.set_xlim(0, 1)
        ax.set_ylim(ax_plot.get_ylim())
        ax.axis("off")
        ax.text(
            0.02,
            1.02,
            EFFECT_TITLE_MAP[effect_type],
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            color="black",
            fontweight="bold",
        )

    for row_idx, variable in enumerate(variable_order):
        row_data = plot_df.loc[plot_df["variable"].eq(variable)].set_index("effect_type")
        for effect_type, ax in text_axes.items():
            row = row_data.loc[effect_type]
            text = (
                f"{format_decimal(row['coef'])}{significance_stars(float(row['pvalue']))}\n"
                f"({format_decimal(row['ll'])}, {format_decimal(row['ul'])})\n"
                f"p={format_decimal(row['pvalue'])}"
            )
            ax.text(0.02, row_idx, text, ha="left", va="center", color="black", linespacing=1.20)

    fig.suptitle(f"核心解释变量空间效应森林图（{weight_label}）", y=0.98)
    fig.subplots_adjust(left=0.04, right=0.99, top=0.90, bottom=0.14, wspace=0.04)

    out_path = resolve_output_path(OUT_DIR / f"50_核心解释变量空间效应森林图_{weight_type}.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_report(
    effect_df: pd.DataFrame,
    weight_type: str,
    plot_paths: list[Path],
    extra_table_paths: list[Path] | None = None,
) -> Path:
    export_df = effect_df.copy()
    weight_label = display_weight_type(weight_type)
    export_df["variable_cn"] = export_df["variable"].map(VAR_LABEL_MAP).fillna(export_df["variable"])
    export_df["effect_type_cn"] = export_df["effect_type"].map(EFFECT_TITLE_MAP).fillna(export_df["effect_type"])
    export_df = export_df[["weight_type", "effect_type", "effect_type_cn", "variable", "variable_cn", "coef", "pvalue", "ll", "ul"]]

    csv_path = resolve_output_path(OUT_DIR / f"50_核心解释变量空间效应表_{weight_type}.csv")
    export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    report_path = resolve_output_path(OUT_DIR / f"50_空间效应森林图说明_{weight_type}.md")
    lines = [
        "# 空间效应森林图",
        "",
        "## 数据来源",
        "",
        f"- `{EFFECT_TABLE_PATH}`",
        f"- 权重矩阵：`{weight_label}`",
        f"- 节点属性年份：`{NETWORK_YEAR}`",
        f"- 节点大小：`eff` 水平",
        f"- 节点颜色：`LISA` 聚类类型",
        f"- 边权重：`row-standardized W_ij × LR_Indirect`",
        f"- 边筛选：保留绝对溢出强度前 `10%` 核心边",
        "",
        "## 图形输出",
        "",
        *[f"- `{path.name}`" for path in plot_paths],
        "",
        "## 结果表",
        "",
        f"- `{csv_path.name}`",
    ]
    if extra_table_paths:
        lines.extend([*[f"- `{path.name}`" for path in extra_table_paths], ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    configure_matplotlib()
    weight_type = parse_weight_type(sys.argv[1:])
    effect_df, chosen_weight_type = load_effect_table(weight_type)
    forest_path = plot_effect_forest(effect_df, chosen_weight_type)
    stacked_bar_path = plot_effect_stacked_bar(effect_df, chosen_weight_type)
    heatmap_path = plot_sorted_economic_matrix_heatmap()
    network_paths, edge_table_path, node_table_path = plot_spillover_network_maps(effect_df, chosen_weight_type)
    lntl_panel_path = plot_lntl_spillover_network_panel(effect_df, chosen_weight_type)
    report_path = save_report(
        effect_df,
        chosen_weight_type,
        [forest_path, stacked_bar_path, heatmap_path, *network_paths, lntl_panel_path],
        extra_table_paths=[edge_table_path, node_table_path],
    )

    print(f"weight_type: {chosen_weight_type}")
    print(f"effect_table: {EFFECT_TABLE_PATH}")
    print(f"saved plot: {forest_path}")
    print(f"saved plot: {stacked_bar_path}")
    print(f"saved plot: {heatmap_path}")
    for network_path in network_paths:
        print(f"saved plot: {network_path}")
    print(f"saved plot: {lntl_panel_path}")
    print(f"saved table: {edge_table_path}")
    print(f"saved table: {node_table_path}")
    print(f"saved report: {report_path}")


if __name__ == "__main__":
    main()
