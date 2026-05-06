from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from libpysal.weights import full2W
from scipy import sparse
from spreg import LMtests, ML_Error, ML_Lag, OLS, Wald, likratiotest


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "最终数据" / "第二阶段_基础.csv"
WEIGHT_PATHS = {
    "adjacency_01": ROOT / "data" / "最终数据" / "省际01邻接矩阵.csv",
    "economic_inverse": ROOT / "data" / "最终数据" / "省际经济距离矩阵.csv",
}
OUT_DIR = ROOT / "outputs" / "回归分析" / "70_空间权重矩阵检验"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEP_VAR = "eff"
BASE_X_VARS = ["lntl", "ind", "urb", "rd", "open", "es"]
ENTITY_COL = "province"
TIME_COL = "year"


def format_decimal(value: float, digits: int = 6) -> str:
    rounded = round(float(value), digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}"


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


def load_panel_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    needed = [ENTITY_COL, TIME_COL, DEP_VAR, *BASE_X_VARS]
    missing = sorted(set(needed) - set(df.columns))
    if missing:
        raise ValueError(f"{DATA_PATH.name} 缺少字段: {missing}")

    df = df[needed].copy()
    df[ENTITY_COL] = df[ENTITY_COL].astype(str).str.strip()
    df[TIME_COL] = pd.to_numeric(df[TIME_COL], errors="coerce")
    for col in [DEP_VAR, *BASE_X_VARS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().copy()
    df[TIME_COL] = df[TIME_COL].astype(int)
    return df.sort_values([TIME_COL, ENTITY_COL]).reset_index(drop=True)


def build_design_matrix(df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame, list[bool]]:
    province_dummies = pd.get_dummies(df[ENTITY_COL], prefix="prov", drop_first=True, dtype=float)
    year_dummies = pd.get_dummies(df[TIME_COL], prefix="year", drop_first=True, dtype=float)
    x_df = pd.concat([df[BASE_X_VARS].astype(float), province_dummies, year_dummies], axis=1)
    slx_vars = [col in BASE_X_VARS for col in x_df.columns]
    y = df[[DEP_VAR]].astype(float).to_numpy()
    return y, x_df, slx_vars


def load_weight_matrix(path: Path, provinces: list[str]) -> np.ndarray:
    w_df = pd.read_csv(path, index_col=0, encoding="utf-8-sig")
    w_df.index = w_df.index.astype(str).str.strip()
    w_df.columns = w_df.columns.astype(str).str.strip()
    missing = sorted(set(provinces) - set(w_df.index))
    if missing:
        raise ValueError(f"{path.name} 缺少省份: {missing}")
    w_df = w_df.loc[provinces, provinces]
    return w_df.to_numpy(dtype=float)


def build_panel_weights(w_cross: np.ndarray, n_periods: int):
    w_big = sparse.kron(
        sparse.eye(n_periods, format="csr"),
        sparse.csr_matrix(w_cross),
        format="csr",
    ).toarray()
    w = full2W(w_big)
    original_transform = w.transform
    w.transform = "r"
    return w, original_transform


def run_spatial_tests(
    y: np.ndarray,
    x_df: pd.DataFrame,
    slx_vars: list[bool],
    w,
    weight_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = x_df.to_numpy()
    x_names = list(x_df.columns)

    ols = OLS(
        y,
        x,
        w=w,
        spat_diag=True,
        name_y=DEP_VAR,
        name_x=x_names,
        name_w=weight_name,
        name_ds=DATA_PATH.name,
    )
    lm = LMtests(ols, w)

    sar = ML_Lag(
        y,
        x,
        w,
        slx_lags=0,
        name_y=DEP_VAR,
        name_x=x_names,
        name_w=weight_name,
        name_ds=DATA_PATH.name,
        spat_impacts=None,
    )
    sem = ML_Error(
        y,
        x,
        w,
        name_y=DEP_VAR,
        name_x=x_names,
        name_w=weight_name,
        name_ds=DATA_PATH.name,
    )
    sdm = ML_Lag(
        y,
        x,
        w,
        slx_lags=1,
        slx_vars=slx_vars,
        name_y=DEP_VAR,
        name_x=x_names,
        name_w=weight_name,
        name_ds=DATA_PATH.name,
        spat_impacts=None,
    )

    lm_rows = [
        ("LM Lag", *lm.lml),
        ("Robust LM Lag", *lm.rlml),
        ("LM Error", *lm.lme),
        ("Robust LM Error", *lm.rlme),
        ("LM SDM Joint", *lm.lmspdurbin),
        ("Robust LM Lag-SDM", *lm.rlmdurlag),
    ]
    lm_df = pd.DataFrame(lm_rows, columns=["test", "statistic", "pvalue"])
    lm_df.insert(0, "weight_type", weight_name)
    lm_df["decision_5pct"] = np.where(lm_df["pvalue"] < 0.05, "Reject H0", "Fail to reject H0")

    wx_idx = [i for i, name in enumerate(sdm.name_x) if name.startswith("W_") and name != "W_eff"]
    restriction = np.zeros((len(wx_idx), len(sdm.name_x)))
    for row_id, coef_idx in enumerate(wx_idx):
        restriction[row_id, coef_idx] = 1.0
    wald_sdm_to_sar = Wald(sdm, restriction)

    compare_rows = [
        (
            "LR: OLS vs SAR",
            likratiotest(ols, sar)["likr"],
            likratiotest(ols, sar)["p-value"],
            likratiotest(ols, sar)["df"],
        ),
        (
            "LR: OLS vs SEM",
            likratiotest(ols, sem)["likr"],
            likratiotest(ols, sem)["p-value"],
            likratiotest(ols, sem)["df"],
        ),
        (
            "LR: SAR vs SDM",
            likratiotest(sar, sdm)["likr"],
            likratiotest(sar, sdm)["p-value"],
            likratiotest(sar, sdm)["df"],
        ),
        (
            "Wald: SDM -> SAR",
            float(wald_sdm_to_sar.w),
            float(wald_sdm_to_sar.pvalue),
            int(len(wx_idx)),
        ),
    ]
    compare_df = pd.DataFrame(compare_rows, columns=["test", "statistic", "pvalue", "df"])
    compare_df.insert(0, "weight_type", weight_name)
    compare_df["decision_5pct"] = np.where(compare_df["pvalue"] < 0.05, "Reject H0", "Fail to reject H0")
    compare_df["rho_or_lambda"] = [
        float(sar.rho),
        float(sem.lam),
        float(sdm.rho),
        float(sdm.rho),
    ]
    compare_df["aic_reference"] = [
        float(sar.aic),
        float(sem.aic),
        float(sdm.aic),
        float(sdm.aic),
    ]
    return lm_df, compare_df


def build_analysis_text(lm_df: pd.DataFrame, compare_df: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for weight_name in compare_df["weight_type"].unique():
        lm_part = lm_df.loc[lm_df["weight_type"] == weight_name].set_index("test")
        cp_part = compare_df.loc[compare_df["weight_type"] == weight_name].set_index("test")

        lm_lag_p = float(lm_part.loc["LM Lag", "pvalue"])
        rlm_lag_p = float(lm_part.loc["Robust LM Lag", "pvalue"])
        lm_err_p = float(lm_part.loc["LM Error", "pvalue"])
        rlm_err_p = float(lm_part.loc["Robust LM Error", "pvalue"])
        lr_sdm_p = float(cp_part.loc["LR: SAR vs SDM", "pvalue"])
        wald_sdm_p = float(cp_part.loc["Wald: SDM -> SAR", "pvalue"])
        lr_sar_p = float(cp_part.loc["LR: OLS vs SAR", "pvalue"])
        lr_sem_p = float(cp_part.loc["LR: OLS vs SEM", "pvalue"])

        if weight_name == "adjacency_01":
            title = "0-1 邻接矩阵"
        else:
            title = "经济倒数权重矩阵"

        lines.append(f"### {title}")
        lines.append("")
        lines.append(
            f"- LM 检验方面，`LM Lag` 的 `p={format_decimal(lm_lag_p)}`，`LM Error` 的 `p={format_decimal(lm_err_p)}`；"
            f"`Robust LM Lag` 的 `p={format_decimal(rlm_lag_p)}`，`Robust LM Error` 的 `p={format_decimal(rlm_err_p)}`。"
        )
        if rlm_lag_p >= 0.05 and rlm_err_p >= 0.05:
            lines.append(
                "- 两个稳健 LM 都未在 5% 水平下显著，说明在控制另一类空间依赖后，纯 SAR 或纯 SEM 的证据都不强。"
            )
        elif rlm_lag_p < 0.05 and rlm_err_p < 0.05:
            lines.append(
                "- 两个稳健 LM 都显著，说明残差中同时存在滞后型与误差型空间依赖，单一 SAR/SEM 难以充分刻画，宜优先从更一般的 SDM 出发。"
            )
        elif rlm_lag_p < 0.05:
            lines.append("- 仅稳健滞后 LM 显著，偏向优先考虑 SAR 或 SDM。")
        else:
            lines.append("- 仅稳健误差 LM 显著，偏向优先考虑 SEM 或更一般模型。")

        lines.append(
            f"- LR 检验方面，`OLS vs SAR` 的 `p={format_decimal(lr_sar_p)}`，`OLS vs SEM` 的 `p={format_decimal(lr_sem_p)}`，"
            f"`SAR vs SDM` 的 `p={format_decimal(lr_sdm_p)}`。"
        )
        lines.append(
            f"- Wald 对 `SDM -> SAR` 的零假设为“所有空间滞后解释变量系数同时为 0”，其 `p={format_decimal(wald_sdm_p)}`。"
        )
        if lr_sdm_p < 0.05 and wald_sdm_p < 0.05:
            lines.append("- `SAR vs SDM` 的 LR 和 `SDM -> SAR` 的 Wald 都显著，说明加入 `WX` 项后模型明显改进，SDM 比纯 SAR 更合适。")
        else:
            lines.append("- `SAR vs SDM` 的 LR 或 `SDM -> SAR` 的 Wald 未形成一致显著证据，说明是否需要 `WX` 项仍应结合理论判断。")
        lines.append("")

    lines.extend(
        [
            "### 综合判断",
            "",
            "- 若以模型设定检验为主，两类空间矩阵下都不宜直接停在单一 SAR 或单一 SEM。",
            "- `0-1` 邻接矩阵下，简单 LM 在 10% 附近边际显著，但稳健 LM 不显著，说明空间依赖存在但类型并不干净；同时 SDM 相对 SAR 的 LR/Wald 明显显著，更像是“解释变量空间溢出”比单纯因变量滞后更重要。",
            "- 经济倒数权重矩阵下，简单 LM 不显著而稳健 LM 同时显著，属于较典型的相互污染情形；这通常意味着从一般模型起步更稳妥，先估 SDM，再视约束检验决定是否简化。",
            "- 因而在论文或实证报告里，更稳妥的路径是：先以 SDM 为母模型，再根据后续约束检验决定是否退化为 SAR 或 SEM。",
            "",
            "### 关于行标准化",
            "",
            "- `libpysal` 和 `spreg` **不会**替你把自定义矩阵自动行标准化。",
            "- 例如 `full2W(...)` 生成的权重对象默认 `transform` 是 `O`，表示保留原始矩阵。",
            "- 若要行标准化，必须显式写：`w.transform = \"r\"`。",
            "- 本脚本已显式采用行标准化后权重开展全部检验，因此当前输出结果对应的是行标准化矩阵。",
        ]
    )
    return lines


def main() -> None:
    df = load_panel_data()
    y, x_df, slx_vars = build_design_matrix(df)
    first_year = int(df[TIME_COL].min())
    province_order = df.loc[df[TIME_COL] == first_year, ENTITY_COL].tolist()
    n_periods = int(df[TIME_COL].nunique())

    all_lm: list[pd.DataFrame] = []
    all_compare: list[pd.DataFrame] = []
    weight_meta_rows: list[dict[str, object]] = []

    for weight_name, path in WEIGHT_PATHS.items():
        w_cross = load_weight_matrix(path, province_order)
        w, original_transform = build_panel_weights(w_cross, n_periods)
        row_sums = np.asarray(w.full()[0].sum(axis=1)).reshape(-1)
        weight_meta_rows.append(
            {
                "weight_type": weight_name,
                "source_file": path.relative_to(ROOT).as_posix(),
                "n_cross_section": w_cross.shape[0],
                "n_periods": n_periods,
                "n_panel_obs": int(w.n),
                "original_transform": original_transform,
                "final_transform": w.transform,
                "row_sum_min": float(row_sums.min()),
                "row_sum_max": float(row_sums.max()),
            }
        )
        lm_df, compare_df = run_spatial_tests(y, x_df, slx_vars, w, weight_name)
        all_lm.append(lm_df)
        all_compare.append(compare_df)

    meta_df = pd.DataFrame(weight_meta_rows)
    lm_df = pd.concat(all_lm, ignore_index=True)
    compare_df = pd.concat(all_compare, ignore_index=True)

    meta_df.to_csv(OUT_DIR / "空间权重矩阵信息.csv", index=False, encoding="utf-8-sig")
    lm_df.to_csv(OUT_DIR / "LM与RobustLM检验结果.csv", index=False, encoding="utf-8-sig")
    compare_df.to_csv(OUT_DIR / "LR与Wald检验结果.csv", index=False, encoding="utf-8-sig")

    md_lines = [
        "# 空间权重矩阵检验结果",
        "",
        f"数据文件：`{DATA_PATH.relative_to(ROOT).as_posix()}`",
        "",
        "基准解释式：",
        "",
        "$$",
        "eff_{it} = \\beta_1 lntl_{it} + \\beta_2 ind_{it} + \\beta_3 urb_{it} + \\beta_4 rd_{it} + \\beta_5 open_{it} + \\beta_6 es_{it} + \\mu_i + \\lambda_t + \\varepsilon_{it}",
        "$$",
        "",
        "处理方式说明：",
        "",
        "- 将 2015-2022 年 30 个省份面板按 `year-province` 顺序堆叠为 `240` 个观测值。",
        "- 对每个年份重复同一 `30 x 30` 空间矩阵，构造成块对角的面板权重矩阵。",
        "- 省份固定效应和年份固定效应通过虚拟变量进入回归设计矩阵。",
        "- 所有空间检验均在 `w.transform = \"r\"` 的行标准化权重下完成。",
        "",
        "## 空间权重矩阵信息",
        "",
        df_to_md(meta_df),
        "",
        "## LM 与 Robust LM 检验结果",
        "",
        df_to_md(lm_df),
        "",
        "## LR 与 Wald 检验结果",
        "",
        df_to_md(compare_df),
        "",
        *build_analysis_text(lm_df, compare_df),
        "",
    ]
    (OUT_DIR / "空间权重矩阵检验报告.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(f"saved: {OUT_DIR / '空间权重矩阵信息.csv'}")
    print(f"saved: {OUT_DIR / 'LM与RobustLM检验结果.csv'}")
    print(f"saved: {OUT_DIR / 'LR与Wald检验结果.csv'}")
    print(f"saved: {OUT_DIR / '空间权重矩阵检验报告.md'}")


if __name__ == "__main__":
    main()
