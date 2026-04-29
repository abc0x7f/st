from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from arch.unitroot import PhillipsPerron
from panelbox.validation.unit_root.fisher import FisherTest
from panelbox.validation.unit_root.ips import IPSTest
from panelbox.validation.unit_root.llc import LLCTest
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "prcd" / "process2.csv"
OUT_DIR = ROOT / "prcd" / "unit_root_tests"
VARIABLES = ["eff", "lntl", "ind", "urb", "rd", "open", "es"]
ENTITY_COL = "province"
TIME_COL = "year"


@dataclass
class TestRow:
    variable: str
    test: str
    statistic: float
    pvalue: float
    decision_5pct: str
    note: str


def fisher_pp_test(
    data: pd.DataFrame,
    variable: str,
    entity_col: str,
    time_col: str,
    trend: str = "c",
    lags: int | None = None,
) -> tuple[float, float, dict[str, float]]:
    """Combine province-level Phillips-Perron p-values using Fisher's method."""
    pvalues: dict[str, float] = {}
    for entity, group in data.sort_values([entity_col, time_col]).groupby(entity_col):
        series = group[variable].astype(float).to_numpy()
        pp = PhillipsPerron(series, trend=trend, lags=lags)
        pvalue = float(np.clip(pp.pvalue, 1e-300, 1.0))
        pvalues[str(entity)] = pvalue

    fisher_stat = float(-2 * np.sum(np.log(list(pvalues.values()))))
    fisher_pvalue = float(1 - stats.chi2.cdf(fisher_stat, 2 * len(pvalues)))
    return fisher_stat, fisher_pvalue, pvalues


def run_level_tests(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[TestRow] = []
    pp_detail_rows: list[dict[str, float | str]] = []

    for variable in VARIABLES:
        llc = LLCTest(df, variable, ENTITY_COL, TIME_COL, trend="c").run()
        ips = IPSTest(df, variable, ENTITY_COL, TIME_COL, trend="c").run()
        adf_fisher = FisherTest(
            df,
            variable,
            ENTITY_COL,
            TIME_COL,
            test_type="adf",
            trend="c",
        ).run()
        pp_stat, pp_pvalue, pp_individual = fisher_pp_test(
            df,
            variable,
            ENTITY_COL,
            TIME_COL,
            trend="c",
            lags=None,
        )

        rows.extend(
            [
                TestRow(
                    variable,
                    "LLC",
                    float(llc.statistic),
                    float(llc.pvalue),
                    "Reject H0" if llc.pvalue < 0.05 else "Fail to reject H0",
                    f"lags={llc.lags}",
                ),
                TestRow(
                    variable,
                    "IPS",
                    float(ips.statistic),
                    float(ips.pvalue),
                    "Reject H0" if ips.pvalue < 0.05 else "Fail to reject H0",
                    f"mean_lag={np.mean(ips.lags):.2f}",
                ),
                TestRow(
                    variable,
                    "ADF-Fisher",
                    float(adf_fisher.statistic),
                    float(adf_fisher.pvalue),
                    "Reject H0" if adf_fisher.pvalue < 0.05 else "Fail to reject H0",
                    "statsmodels.adfuller + Fisher combine",
                ),
                TestRow(
                    variable,
                    "PP-Fisher",
                    pp_stat,
                    pp_pvalue,
                    "Reject H0" if pp_pvalue < 0.05 else "Fail to reject H0",
                    "arch.unitroot.PhillipsPerron + Fisher combine",
                ),
            ]
        )

        for entity, pvalue in pp_individual.items():
            pp_detail_rows.append(
                {
                    "variable": variable,
                    "province": entity,
                    "pp_pvalue": pvalue,
                }
            )

    return pd.DataFrame(rows), pd.DataFrame(pp_detail_rows)


def run_first_difference_checks(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    rows: list[TestRow] = []

    for variable in variables:
        diff_df = df[[ENTITY_COL, TIME_COL, variable]].copy()
        diff_df[variable] = diff_df.groupby(ENTITY_COL)[variable].diff()
        diff_df = diff_df.dropna().reset_index(drop=True)

        llc = LLCTest(diff_df, variable, ENTITY_COL, TIME_COL, trend="c").run()
        ips = IPSTest(diff_df, variable, ENTITY_COL, TIME_COL, trend="c").run()
        adf_fisher = FisherTest(
            diff_df,
            variable,
            ENTITY_COL,
            TIME_COL,
            test_type="adf",
            trend="c",
        ).run()
        pp_stat, pp_pvalue, _ = fisher_pp_test(
            diff_df,
            variable,
            ENTITY_COL,
            TIME_COL,
            trend="c",
            lags=1,
        )

        rows.extend(
            [
                TestRow(
                    f"D.{variable}",
                    "LLC",
                    float(llc.statistic),
                    float(llc.pvalue),
                    "Reject H0" if llc.pvalue < 0.05 else "Fail to reject H0",
                    f"lags={llc.lags}",
                ),
                TestRow(
                    f"D.{variable}",
                    "IPS",
                    float(ips.statistic),
                    float(ips.pvalue),
                    "Reject H0" if ips.pvalue < 0.05 else "Fail to reject H0",
                    f"mean_lag={np.mean(ips.lags):.2f}",
                ),
                TestRow(
                    f"D.{variable}",
                    "ADF-Fisher",
                    float(adf_fisher.statistic),
                    float(adf_fisher.pvalue),
                    "Reject H0" if adf_fisher.pvalue < 0.05 else "Fail to reject H0",
                    "first difference check",
                ),
                TestRow(
                    f"D.{variable}",
                    "PP-Fisher",
                    pp_stat,
                    pp_pvalue,
                    "Reject H0" if pp_pvalue < 0.05 else "Fail to reject H0",
                    "first difference check; PP lags=1",
                ),
            ]
        )

    return pd.DataFrame(rows)


def decision_summary(result_df: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    for variable, group in result_df.groupby("variable"):
        reject_count = int((group["pvalue"] < 0.05).sum())
        tests = group.set_index("test")["decision_5pct"].to_dict()
        summary_rows.append(
            {
                "variable": variable,
                "reject_count_5pct": reject_count,
                "llc": tests.get("LLC", ""),
                "ips": tests.get("IPS", ""),
                "adf_fisher": tests.get("ADF-Fisher", ""),
                "pp_fisher": tests.get("PP-Fisher", ""),
            }
        )
    return pd.DataFrame(summary_rows)


def write_markdown(
    level_df: pd.DataFrame,
    diff_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    def df_to_md(df: pd.DataFrame, floatfmt: str = ".6g") -> str:
        rendered = df.copy()
        for col in rendered.columns:
            rendered[col] = rendered[col].map(
                lambda x: format(x, floatfmt) if isinstance(x, float) else str(x)
            )
        headers = [str(col) for col in rendered.columns]
        rows = rendered.values.tolist()
        table = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in rows:
            table.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return "\n".join(table)

    lines = [
        "# 面板单位根检验结果",
        "",
        "数据文件：`prcd/process2.csv`",
        "",
        "- 面板：30 个省份 × 8 年（2015-2022），平衡面板",
        "- 水平值检验设定：常数项 `c`",
        "- `LLC`、`IPS` 使用 `panelbox`",
        "- `ADF-Fisher` 使用 `statsmodels.adfuller` 的 Fisher 合并实现",
        "- `PP-Fisher` 使用 `arch.unitroot.PhillipsPerron` 的 Fisher 合并实现",
        "",
        "## 水平值结果汇总",
        "",
        df_to_md(summary_df),
        "",
        "## 水平值详细结果",
        "",
        df_to_md(level_df),
        "",
        "## 一阶差分复检（边界变量）",
        "",
        df_to_md(diff_df),
        "",
        "## 结果解读口径",
        "",
        "1. 若大多数单位根检验在 5% 水平拒绝原假设，可将该变量视为总体平稳。",
        "2. 若结果出现分歧，优先结合短面板 `T=8` 的低检验功效来解释，不机械按单一检验下结论。",
        "3. 对于水平值存在争议但一阶差分稳定拒绝单位根的变量，可表述为“可能处于边界平稳或弱平稳状态，回归时需结合双固定效应与稳健标准误谨慎解释”。",
    ]
    (OUT_DIR / "panel_unit_root_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH).sort_values([ENTITY_COL, TIME_COL]).reset_index(drop=True)

    level_df, pp_detail_df = run_level_tests(df)
    diff_df = run_first_difference_checks(df, ["eff", "rd"])
    summary_df = decision_summary(level_df)

    level_df.to_csv(OUT_DIR / "panel_unit_root_results.csv", index=False, encoding="utf-8-sig")
    pp_detail_df.to_csv(OUT_DIR / "pp_fisher_individual_pvalues.csv", index=False, encoding="utf-8-sig")
    diff_df.to_csv(
        OUT_DIR / "panel_unit_root_first_difference_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary_df.to_csv(OUT_DIR / "panel_unit_root_summary.csv", index=False, encoding="utf-8-sig")
    write_markdown(level_df, diff_df, summary_df)

    print(summary_df.to_string(index=False))
    print(f"\nSaved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
