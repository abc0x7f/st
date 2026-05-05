from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "最终数据" / "第一阶段_基础.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "数据处理" / "30_投入产出关系预检"
OUTPUT_PATH = OUTPUT_DIR / "09_投入产出关系散点图.png"

INPUT_COLUMNS = ["Population", "Capital", "energy_total"]
OUTPUT_COLUMNS = ["GDP_constant", "Carbon"]
COLUMN_LABELS = {
    "Population": "劳动投入（Population）",
    "Capital": "资本投入（Capital）",
    "energy_total": "能源投入（energy_total）",
    "GDP_constant": "期望产出（GDP_constant）",
    "Carbon": "非期望产出（Carbon）",
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

    fig, axes = plt.subplots(3, 2, figsize=(15, 18))
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
            s=55,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.4,
            ax=ax,
        )
        add_fit_curve(ax, df[x_col], df[y_col])
        ax.set_title(f"{COLUMN_LABELS[x_col]} 与 {COLUMN_LABELS[y_col]}", fontsize=12)
        ax.set_xlabel(COLUMN_LABELS[x_col], fontsize=10)
        ax.set_ylabel(COLUMN_LABELS[y_col], fontsize=10)
        ax.ticklabel_format(style="plain", axis="both", useOffset=False)
        ax.legend(title="年份", fontsize=8, title_fontsize=9, loc="best", ncol=2)

    fig.suptitle("投入-产出关系散点图", fontsize=16, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
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
