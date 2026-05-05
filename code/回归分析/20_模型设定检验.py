from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS, RandomEffects
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "prcd" / "process2.csv"
OUT_DIR = ROOT / "prcd" / "model_spec_tests"

Y_VAR = "eff"
X_VARS = ["lntl", "ind", "urb", "rd", "open", "es"]
ENTITY_COL = "province"
TIME_COL = "year"


def fit_models(df: pd.DataFrame):
    panel_df = df.set_index([ENTITY_COL, TIME_COL])
    y = panel_df[Y_VAR].astype(float)

    x_tw = sm.add_constant(panel_df[X_VARS].astype(float))

    year_dummies = pd.get_dummies(df[TIME_COL], prefix="year", drop_first=True, dtype=float)
    x_re_fe = sm.add_constant(pd.concat([df[X_VARS].astype(float), year_dummies], axis=1))
    x_re_fe = x_re_fe.set_index(panel_df.index)

    fe_entity = PanelOLS(y, x_re_fe, entity_effects=True).fit(cov_type="unadjusted")
    re = RandomEffects(y, x_re_fe).fit(cov_type="unadjusted")
    fe_tw = PanelOLS(y, x_tw, entity_effects=True, time_effects=True).fit(cov_type="unadjusted")

    return fe_entity, re, fe_tw, year_dummies.columns.tolist()


def hausman_test(fe_entity, re) -> dict[str, float | int | str]:
    common = X_VARS
    b_diff = (fe_entity.params[common] - re.params[common]).values.reshape(-1, 1)
    v_diff = (fe_entity.cov.loc[common, common] - re.cov.loc[common, common]).values
    rank = int(np.linalg.matrix_rank(v_diff))
    stat = float((b_diff.T @ np.linalg.pinv(v_diff) @ b_diff).item())
    pvalue = float(1 - stats.chi2.cdf(stat, rank))
    return {
        "test": "Hausman",
        "statistic": stat,
        "pvalue": pvalue,
        "df": rank,
        "decision_5pct": "Reject H0" if pvalue < 0.05 else "Fail to reject H0",
        "null_hypothesis": "RE consistent and efficient",
        "interpretation": "Prefer FE" if pvalue < 0.05 else "RE also consistent",
    }


def pesaran_cd_test(fe_tw) -> dict[str, float | int | str]:
    resid = fe_tw.resids.copy().reset_index()
    resid.columns = [ENTITY_COL, TIME_COL, "resid"]
    resid_wide = resid.pivot(index=TIME_COL, columns=ENTITY_COL, values="resid")

    correlations: list[float] = []
    n_entities = resid_wide.shape[1]
    n_periods = resid_wide.shape[0]

    for i in range(n_entities):
        for j in range(i + 1, n_entities):
            e_i = resid_wide.iloc[:, i]
            e_j = resid_wide.iloc[:, j]
            valid = ~(e_i.isna() | e_j.isna())
            if int(valid.sum()) >= 3:
                correlations.append(float(np.corrcoef(e_i[valid], e_j[valid])[0, 1]))

    statistic = float(np.sqrt(2 * n_periods / (n_entities * (n_entities - 1))) * np.sum(correlations))
    pvalue = float(2 * (1 - stats.norm.cdf(abs(statistic))))
    avg_abs_corr = float(np.mean(np.abs(correlations)))

    return {
        "test": "Pesaran CD",
        "statistic": statistic,
        "pvalue": pvalue,
        "df": "",
        "decision_5pct": "Reject H0" if pvalue < 0.05 else "Fail to reject H0",
        "null_hypothesis": "No cross-sectional dependence",
        "interpretation": f"avg_abs_corr={avg_abs_corr:.3f}",
    }


def modified_wald_test(fe_tw) -> dict[str, float | int | str]:
    resid = fe_tw.resids.copy().reset_index()
    resid.columns = [ENTITY_COL, TIME_COL, "resid"]

    entity_vars = resid.groupby(ENTITY_COL)["resid"].var()
    entity_counts = resid.groupby(ENTITY_COL).size()
    n_entities = len(entity_vars)
    total_resid_sq = float(np.sum(resid["resid"] ** 2))
    total_obs = len(resid)
    k = len(fe_tw.params)
    pooled_var = total_resid_sq / (total_obs - n_entities - k)

    statistic = 0.0
    for entity in entity_vars.index:
        t_i = int(entity_counts[entity])
        sigma2_i = float(entity_vars[entity])
        if sigma2_i > 0:
            statistic += t_i * np.log(pooled_var / sigma2_i)

    pvalue = float(1 - stats.chi2.cdf(statistic, n_entities))
    var_ratio = float(entity_vars.max() / entity_vars.min())

    return {
        "test": "Modified Wald",
        "statistic": float(statistic),
        "pvalue": pvalue,
        "df": n_entities,
        "decision_5pct": "Reject H0" if pvalue < 0.05 else "Fail to reject H0",
        "null_hypothesis": "Homoskedasticity across entities",
        "interpretation": f"variance_ratio={var_ratio:.3f}",
    }


def wooldridge_test(fe_tw) -> dict[str, float | int | str]:
    resid = fe_tw.resids.copy().reset_index()
    resid.columns = [ENTITY_COL, TIME_COL, "resid"]
    resid = resid.sort_values([ENTITY_COL, TIME_COL])
    resid["resid_diff"] = resid.groupby(ENTITY_COL)["resid"].diff()
    resid["resid_diff_lag"] = resid.groupby(ENTITY_COL)["resid_diff"].shift(1)
    wd = resid.dropna(subset=["resid_diff", "resid_diff_lag"]).copy()

    y_ar = wd["resid_diff"].values
    x_ar = wd["resid_diff_lag"].values
    beta = float(np.sum(x_ar * y_ar) / np.sum(x_ar * x_ar))
    resid_reg = y_ar - beta * x_ar

    n_obs = len(y_ar)
    s2 = float(np.sum(resid_reg**2) / (n_obs - 1))
    se_beta = float(np.sqrt(s2 / np.sum(x_ar * x_ar)))
    t_stat = float((beta + 0.5) / se_beta)
    f_stat = float(t_stat**2)
    n_entities = wd[ENTITY_COL].nunique()
    pvalue = float(1 - stats.f.cdf(f_stat, 1, n_entities - 1))

    return {
        "test": "Wooldridge AR(1)",
        "statistic": f_stat,
        "pvalue": pvalue,
        "df": f"F(1,{n_entities - 1})",
        "decision_5pct": "Reject H0" if pvalue < 0.05 else "Fail to reject H0",
        "null_hypothesis": "No first-order serial correlation",
        "interpretation": f"beta={beta:.3f}, se={se_beta:.3f}",
    }


def f_tests(fe_entity, fe_tw, year_dummy_cols: list[str]) -> pd.DataFrame:
    pooled = fe_tw.f_pooled
    year_formula = " = 0, ".join(year_dummy_cols) + " = 0"
    year_wald = fe_entity.wald_test(formula=year_formula)

    rows = [
        {
            "test": "Pooled F",
            "statistic": float(pooled.stat),
            "pvalue": float(pooled.pval),
            "df": f"F({pooled.df},{pooled.df_denom})",
            "decision_5pct": "Reject H0" if float(pooled.pval) < 0.05 else "Fail to reject H0",
            "null_hypothesis": "All entity/time effects are jointly zero",
            "interpretation": "Effects needed" if float(pooled.pval) < 0.05 else "Pooled OLS acceptable",
        },
        {
            "test": "Time Effects Wald",
            "statistic": float(year_wald.stat),
            "pvalue": float(year_wald.pval),
            "df": f"chi2({year_wald.df})",
            "decision_5pct": "Reject H0" if float(year_wald.pval) < 0.05 else "Fail to reject H0",
            "null_hypothesis": "Year effects jointly zero",
            "interpretation": "Keep time effects" if float(year_wald.pval) < 0.05 else "Time effects weak",
        },
    ]
    return pd.DataFrame(rows)


def df_to_md(df: pd.DataFrame, floatfmt: str = ".6g") -> str:
    rendered = df.copy()
    for col in rendered.columns:
        rendered[col] = rendered[col].map(
            lambda x: format(x, floatfmt) if isinstance(x, float) else str(x)
        )
    headers = [str(col) for col in rendered.columns]
    rows = rendered.values.tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)

    fe_entity, re, fe_tw, year_dummy_cols = fit_models(df)

    f_df = f_tests(fe_entity, fe_tw, year_dummy_cols)
    diag_rows = [
        hausman_test(fe_entity, re),
        pesaran_cd_test(fe_tw),
        modified_wald_test(fe_tw),
        wooldridge_test(fe_tw),
    ]
    diag_df = pd.DataFrame(diag_rows)

    result_df = pd.concat([f_df, diag_df], ignore_index=True)
    result_df.to_csv(OUT_DIR / "model_specification_tests.csv", index=False, encoding="utf-8-sig")

    md_lines = [
        "# 模型设定与误差结构检验结果",
        "",
        "数据文件：`prcd/process2.csv`",
        "",
        "- 基准回归变量：`eff ~ lntl + ind + urb + rd + open + es`",
        "- `Pooled F` 基于双固定效应模型的 poolability 检验",
        "- `Hausman` 比较对象为“省份固定效应 + 年份虚拟变量”和“随机效应 + 年份虚拟变量”，仅对核心解释变量与控制变量系数作比较",
        "- `Pesaran CD`、`Modified Wald`、`Wooldridge` 基于双固定效应模型残差",
        "",
        "## 检验结果",
        "",
        df_to_md(result_df),
        "",
    ]
    (OUT_DIR / "model_specification_tests.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(result_df.to_string(index=False))
    print(f"\nSaved outputs to: {OUT_DIR}")


if __name__ == "__main__":
    main()
