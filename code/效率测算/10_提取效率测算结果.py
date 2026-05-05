from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "prcd" / "dearun_eff.csv"


def find_source_file() -> Path:
    candidates = [
        path
        for path in (BASE_DIR / "prcd").rglob("*规模报酬可变VRS_0.xlsx")
        if not path.name.startswith("~$")
    ]
    if not candidates:
        raise FileNotFoundError("未找到 VRS 结果文件。")
    return candidates[0]


def load_global_efficiency(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    required_columns = {"year", "province", "e-g-t+1", "e-g-t"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"源文件缺少必要字段: {sorted(missing)}")

    year_split = df["year"].astype(str).str.split("-", expand=True)
    if year_split.shape[1] != 2:
        raise ValueError("year 字段不是类似 2015-2016 的区间格式。")

    df["start_year"] = pd.to_numeric(year_split[0], errors="coerce")
    df["end_year"] = pd.to_numeric(year_split[1], errors="coerce")
    df["e-g-t"] = pd.to_numeric(df["e-g-t"], errors="coerce")
    df["e-g-t+1"] = pd.to_numeric(df["e-g-t+1"], errors="coerce")

    long_t = (
        df[["start_year", "province", "e-g-t"]]
        .rename(columns={"start_year": "year", "e-g-t": "eff"})
    )
    long_t1 = (
        df[["end_year", "province", "e-g-t+1"]]
        .rename(columns={"end_year": "year", "e-g-t+1": "eff"})
    )

    result = pd.concat([long_t, long_t1], ignore_index=True)
    result = result.dropna(subset=["year", "province", "eff"]).copy()
    result["year"] = result["year"].astype(int)
    result["province"] = result["province"].astype(str).str.strip()

    # 相邻区间的共享年份效率值一致，这里保留第一条并做稳妥去重。
    result = (
        result.sort_values(["year", "province"])
        .drop_duplicates(subset=["year", "province"], keep="first")
        .reset_index(drop=True)
    )
    return result[["year", "province", "eff"]]


def main() -> None:
    source_path = find_source_file()
    eff_df = load_global_efficiency(source_path)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    eff_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"已输出: {OUTPUT_PATH}")
    print(f"记录数: {len(eff_df)}")
    print(
        f"年份范围: {eff_df['year'].min()}-{eff_df['year'].max()} | "
        f"省份数: {eff_df['province'].nunique()}"
    )


if __name__ == "__main__":
    main()

# python connect.py --left prcd/process2_no_eff.csv --right prcd/dearun_eff.csv --output prcd/process2.csv --include-right eff --how left