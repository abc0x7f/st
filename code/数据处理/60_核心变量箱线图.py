from __future__ import annotations

STEP_SPEC = {
    "name": "核心变量箱线图",
    "runner_type": "python",
    "command": [
        "python",
        "code/数据处理/60_核心变量箱线图.py"
    ],
    "working_dir": "{PROJECT_ROOT}",
    "precheck_mode": "required_inputs",
    "required_inputs": [
        {
            "path": "{数据处理.first_stage_panel}",
            "kind": "csv",
            "required_columns": [
                "Population",
                "Capital",
                "energy_total",
                "GDP_constant",
                "Carbon"
            ],
            "label": ""
        },
        {
            "path": "{数据处理.second_stage_panel}",
            "kind": "csv",
            "required_columns": [
                "lntl",
                "ind",
                "urb",
                "rd",
                "open",
                "es"
            ],
            "label": ""
        }
    ],
    "artifacts": {
        "tables": {
            "primary": None,
            "patterns": []
        },
        "images": {
            "primary": "图6_核心变量箱线图.png",
            "patterns": [
                "*.png"
            ]
        },
        "markdown": {
            "primary": None,
            "patterns": []
        }
    },
    "console_success_markers": [],
    "description": "对第一阶段与第二阶段核心变量绘制对数坐标箱线图。",
    "notes": []
}

from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager, patches, ticker
from matplotlib.font_manager import FontProperties
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, script_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
OUT_DIR = script_output_dir(Path(__file__), CONFIG)
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIRST_STAGE_PANEL = resolve_project_path(CONFIG["first_stage_panel"])
SECOND_STAGE_PANEL = resolve_project_path(CONFIG["second_stage_panel"])

FIRST_STAGE_VARS = ["Population", "Capital", "energy_total", "GDP_constant", "Carbon"]
SECOND_STAGE_VARS = ["lntl", "ind", "urb", "rd", "open", "es"]
VAR_ORDER = [*FIRST_STAGE_VARS, *SECOND_STAGE_VARS]
LEGEND_LABELS = {
    "Population": ("Population", "人口规模"),
    "Capital": ("Capital", "资本投入"),
    "energy_total": ("energy_total", "能源投入"),
    "GDP_constant": ("GDP_constant", "不变价GDP"),
    "Carbon": ("Carbon", "碳排放"),
    "lntl": ("lntl", "夜间灯光"),
    "ind": ("ind", "产业结构"),
    "urb": ("urb", "城镇化水平"),
    "rd": ("rd", "研发投入"),
    "open": ("open", "对外开放"),
    "es": ("es", "能源结构"),
}


def configure_matplotlib() -> None:
    sns.set_theme(style="white")
    sns.set_context("talk")
    serif_candidates = ["Times New Roman", "Times New Roman PS MT", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    serif = next((name for name in serif_candidates if name in available), "DejaVu Serif")
    chinese = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    matplotlib.rcParams["font.family"] = [serif, chinese]
    matplotlib.rcParams["font.serif"] = [serif]
    matplotlib.rcParams["font.sans-serif"] = [chinese]
    matplotlib.rcParams["axes.unicode_minus"] = False


def load_stage_data(path: Path, variables: list[str], stage_name: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [col for col in variables if col not in df.columns]
    if missing:
        raise ValueError(f"{stage_name} 数据缺少字段: {missing}")

    long_df = df[variables].copy().melt(var_name="variable", value_name="value")
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
    long_df = long_df.dropna(subset=["value"]).copy()
    long_df = long_df.loc[long_df["value"] > 0].copy()
    long_df["stage"] = stage_name
    return long_df


def log_tick_formatter(value: float, _pos: int) -> str:
    if value <= 0:
        return ""
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:.0f}" if abs(value - round(value)) < 1e-8 else f"{value:g}"
    return f"{value:g}"


def darken_color(color: tuple[float, float, float], factor: float = 0.58) -> tuple[float, float, float]:
    rgb = colors.to_rgb(color)
    return tuple(channel * factor for channel in rgb)


def build_bilingual_label(variable: str) -> str:
    english, chinese = LEGEND_LABELS[variable]
    return f"{english} {chinese}"


def build_legend_font() -> FontProperties:
    english_candidates = ["Times New Roman", "Times New Roman PS MT", "Nimbus Roman", "DejaVu Serif"]
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC", "Microsoft YaHei"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    families: list[str] = []
    english = next((name for name in english_candidates if name in available), None)
    chinese = next((name for name in chinese_candidates if name in available), None)
    if english:
        families.append(english)
    if chinese and chinese not in families:
        families.append(chinese)
    if not families:
        families = ["DejaVu Serif"]
    return FontProperties(family=families, size=13)


def build_english_legend_font() -> FontProperties:
    english_candidates = ["Times New Roman", "Times New Roman PS MT", "Nimbus Roman", "DejaVu Serif"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    family = next((name for name in english_candidates if name in available), "DejaVu Serif")
    return FontProperties(family=[family], size=13)


def build_chinese_legend_font() -> FontProperties:
    chinese_candidates = ["SimSun", "NSimSun", "Songti SC", "Noto Serif CJK SC", "Microsoft YaHei"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    family = next((name for name in chinese_candidates if name in available), "DejaVu Sans")
    return FontProperties(family=[family], size=13)


def draw_bilingual_legend(ax, palette: list[tuple[float, float, float]]) -> None:
    english_font = build_english_legend_font()
    chinese_font = build_chinese_legend_font()

    left = 0.69
    right = 0.985
    top = 0.975
    row_h = 0.048
    swatch_x = left + 0.02
    english_x = left + 0.075
    chinese_x = right - 0.02
    swatch_w = 0.028
    swatch_h = 0.024
    box_h = row_h * len(VAR_ORDER) + 0.028
    bottom = top - box_h

    frame = patches.FancyBboxPatch(
        (left, bottom),
        right - left,
        box_h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        transform=ax.transAxes,
        facecolor=(1, 1, 1, 0.92),
        edgecolor="#c9d2dc",
        linewidth=1.1,
        zorder=4,
    )
    ax.add_patch(frame)

    for idx, var in enumerate(VAR_ORDER):
        color = palette[idx]
        edge_color = darken_color(color)
        english, chinese = LEGEND_LABELS[var]
        y = top - 0.024 - idx * row_h

        swatch = patches.Rectangle(
            (swatch_x, y - swatch_h / 2),
            swatch_w,
            swatch_h,
            transform=ax.transAxes,
            facecolor=(*color, 0.35),
            edgecolor=edge_color,
            linewidth=1.6,
            zorder=5,
        )
        ax.add_patch(swatch)
        ax.text(
            english_x,
            y,
            english,
            transform=ax.transAxes,
            ha="left",
            va="center",
            fontproperties=english_font,
            color="#18212b",
            zorder=5,
        )
        ax.text(
            chinese_x,
            y,
            chinese,
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontproperties=chinese_font,
            color="#18212b",
            zorder=5,
        )


def create_boxplots() -> None:
    df1 = load_stage_data(FIRST_STAGE_PANEL, FIRST_STAGE_VARS, "第一阶段变量")
    df2 = load_stage_data(SECOND_STAGE_PANEL, SECOND_STAGE_VARS, "第二阶段变量")
    plot_df = pd.concat([df1, df2], ignore_index=True)
    plot_df["variable"] = pd.Categorical(plot_df["variable"], categories=VAR_ORDER, ordered=True)

    palette = sns.color_palette("viridis", n_colors=len(VAR_ORDER))
    positions = list(range(1, len(VAR_ORDER) + 1))

    fig, ax = plt.subplots(figsize=(12.0, 8.0))

    for idx, variable in enumerate(VAR_ORDER):
        values = plot_df.loc[plot_df["variable"] == variable, "value"].to_numpy()
        color = palette[idx]
        edge_color = darken_color(color)
        ax.boxplot(
            values,
            positions=[positions[idx]],
            widths=0.55,
            patch_artist=True,
            boxprops={
                "facecolor": (*color, 0.35),
                "edgecolor": edge_color,
                "linewidth": 1.8,
            },
            whiskerprops={"color": edge_color, "linewidth": 1.6},
            capprops={"color": edge_color, "linewidth": 1.6},
            medianprops={"color": edge_color, "linewidth": 1.7},
            flierprops={
                "marker": "o",
                "markerfacecolor": color,
                "markeredgecolor": edge_color,
                "markersize": 4.2,
                "alpha": 0.95,
            },
        )

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(log_tick_formatter))
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())
    ax.yaxis.offsetText.set_visible(False)

    ax.axvline(len(FIRST_STAGE_VARS) + 0.5, color="#9CA3AF", linestyle="--", linewidth=1.2, alpha=0.95)
    ax.text(3.0, 1.02, "第一阶段变量", transform=ax.get_xaxis_transform(), ha="center", va="bottom", color="#111827")
    ax.text(8.5, 1.02, "第二阶段变量", transform=ax.get_xaxis_transform(), ha="center", va="bottom", color="#111827")

    # ax.set_title("图6 核心变量箱线图", pad=18)
    ax.set_xlabel("")
    ax.set_ylabel("变量取值（对数坐标）")
    ax.set_xticks(positions)
    ax.set_xticklabels([])
    ax.tick_params(axis="x", length=0, pad=8)
    ax.tick_params(axis="y", pad=6)
    ax.grid(axis="y", linestyle="--", linewidth=0.8, color="#D1D5DB", alpha=0.7)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    draw_bilingual_legend(ax, palette)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "图6_核心变量箱线图.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    configure_matplotlib()
    create_boxplots()
    print(f"saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
