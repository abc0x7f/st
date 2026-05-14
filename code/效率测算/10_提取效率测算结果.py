STEP_SPEC = {
    "name": "提取效率测算结果",
    "runner_type": "python",
    "command": [
        "python",
        "code/效率测算/10_提取效率测算结果.py"
    ],
    "working_dir": "{PROJECT_ROOT}",
    "precheck_mode": "required_inputs",
    "required_inputs": [
        {
            "path": "{效率测算.dearun_result_dir}",
            "kind": "directory",
            "required_columns": [],
            "label": ""
        }
    ],
    "artifacts": {
        "tables": {
            "primary": "碳排放效率结果_2015_2022.csv",
            "patterns": [
                "*.csv"
            ]
        },
        "images": {
            "primary": None,
            "patterns": []
        },
        "markdown": {
            "primary": None,
            "patterns": []
        }
    },
    "console_success_markers": [],
    "description": "从 Dearun 结果目录提取年度省级效率结果。",
    "notes": []
}

from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "code" / "流水线"))
from stage_config import derived_dearun_result_dir, load_script_context, script_output_dir

CONFIG = load_script_context(Path(__file__), sys.argv[1:]).config
RESULT_DIR = derived_dearun_result_dir(CONFIG)
OUTPUT_DIR = script_output_dir(Path(__file__), CONFIG)
OUTPUT_PATH = OUTPUT_DIR / "碳排放效率结果_2015_2022.csv"


def find_source_file() -> Path:
    candidates = [
        path
        for path in RESULT_DIR.rglob("*规模报酬可变VRS_0.xlsx")
        if not path.name.startswith("~$") and path.name.startswith("结果_")
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

# 后续如需回写第二阶段面板，可将当前输出与 `data/最终数据/第二阶段_基础.csv` 中的 `eff` 列做一致性核对。
