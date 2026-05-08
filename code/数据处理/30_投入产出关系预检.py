from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "code" / "流水线"))
from stage_config import load_script_context, resolve_project_path, stage_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
DATA_PATH = resolve_project_path(CONFIG["first_stage_panel"])
OUTPUT_DIR = stage_output_dir(CONFIG, "30_投入产出关系预检")
OUTPUT_PATH = OUTPUT_DIR / "09_投入产出关系散点图.png"
FONT_SIZE_DELTA = 4

INPUT_COLUMNS = ["Population", "Capital", "energy_total"]
OUTPUT_COLUMNS = ["GDP_constant", "Carbon"]
COLUMN_LABELS = {
    "Population": "劳动投入（Population）",
    "Capital": "资本投入（Capital）",
    "energy_total": "能源投入（energy_total）",
    "GDP_constant": "期望产出（GDP_constant）",
    "Carbon": "非期望产出（Carbon）",
}


def fs(size: float) -> float:
    return size + FONT_SIZE_DELTA


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
    plt.rcParams["legend.fontsize"] = fs(8)


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    required_columns = {"year", "province", *INPUT_COLUMNS, *OUTPUT_COLUMNS}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"缺少必要字段: {sorted(missing)}")

    for col in ["year", *INPUT_COLUMNS, *OUTPUT_COLUMNS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["year", *INPUT_COLUMNS, *OUTPUT_COLUMNS]).copy()
    df["year"] = df["year"].astype(int)
    return df.sort_values(["year", "province"]).reset_index(drop=True)


def build_year_palette(years: list[int]) -> dict[int, tuple]:
    colors = sns.color_palette("viridis", n_colors=len(years))
    return {year: colors[idx] for idx, year in enumerate(years)}


def add_fit_curve(ax: plt.Axes, x: pd.Series, y: pd.Series) -> None:
    x_vals = x.to_numpy(dtype=float)
    y_vals = y.to_numpy(dtype=float)
    order = 2 if np.unique(x_vals).size >= 3 else 1

    try:
        coefficients = np.polyfit(x_vals, y_vals, deg=order)
    except np.linalg.LinAlgError:
        coefficients = np.polyfit(x_vals, y_vals, deg=1)

    poly = np.poly1d(coefficients)
    x_grid = np.linspace(x_vals.min(), x_vals.max(), 300)
    ax.plot(x_grid, poly(x_grid), color="black", linewidth=2, label="拟合曲线")


def draw_input_output_scatter(df: pd.DataFrame) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    years = sorted(df["year"].unique().tolist())
    palette = build_year_palette(years)

    fig, axes = plt.subplots(3, 2, figsize=(18.5, 21.5))
    subplot_pairs = [
        ("Population", "GDP_constant"),
        ("Capital", "GDP_constant"),
        ("energy_total", "GDP_constant"),
        ("Population", "Carbon"),
        ("Capital", "Carbon"),
        ("energy_total", "Carbon"),
    ]

    for ax, (x_col, y_col) in zip(axes.flat, subplot_pairs):
        sns.scatterplot(
            data=df,
            x=x_col,
            y=y_col,
            hue="year",
            hue_order=years,
            palette=palette,
            s=70,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.4,
            ax=ax,
        )
        add_fit_curve(ax, df[x_col], df[y_col])
        ax.set_title(f"{COLUMN_LABELS[x_col]} 与 {COLUMN_LABELS[y_col]}", pad=10)
        ax.set_xlabel(COLUMN_LABELS[x_col])
        ax.set_ylabel(COLUMN_LABELS[y_col])
        ax.ticklabel_format(style="plain", axis="both", useOffset=False)
        ax.tick_params(axis="both", pad=6)
        ax.legend(title="年份", loc="best", ncol=2, frameon=True, borderaxespad=0.8)

    fig.suptitle("投入-产出关系散点图", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.982))
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def main() -> None:
    configure_style()
    df = load_data()
    output_path = draw_input_output_scatter(df)
    print(f"图已保存至: {output_path}")


if __name__ == "__main__":
    main()
