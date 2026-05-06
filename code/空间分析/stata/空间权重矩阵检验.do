version 17.0
clear all
set more off

* ============================================================
* 空间权重矩阵检验
* 参考：docs/参考资料/小鲜烽的空间计量代码.do
* 内容：
* 1. 对 0-1 邻接矩阵、经济倒数权重矩阵进行 LM / Robust LM 检验
* 2. 基于 SDM 分别估计个体、时间、双固定效应模型，并做 LR 检验
* 3. 基于双固定 SDM 做 Wald-SAR / Wald-SEM 检验
* 4. 输出日志与结果表
* ============================================================

global PROJECT_ROOT "C:/Users/abc0x7f/Desktop/PRO/统计建模"
cd "${PROJECT_ROOT}"

global DATA_FILE   "data/最终数据/第二阶段_基础.csv"
global W_ADJ_FILE  "data/最终数据/省际01邻接矩阵.csv"
global W_ECO_FILE  "data/最终数据/省际经济距离矩阵.csv"
global W_GEO_INV_FILE "data/最终数据/省际地理距离倒数矩阵_省会版.csv"
global W_ECO_GEO_NEST_FILE "data/最终数据/省际经济地理嵌套矩阵_省会版.csv"
global OUT_DIR     "outputs/回归分析/70_空间权重矩阵检验"
global STATA_DIR   "${OUT_DIR}/stata"

cap mkdir "${OUT_DIR}"
cap mkdir "${STATA_DIR}"
cap log close _all
log using "${STATA_DIR}/空间权重矩阵检验总日志.log", text replace

display as text "当前工作目录: `c(pwd)'"
display as text "数据文件: ${DATA_FILE}"
display as text "输出目录: ${OUT_DIR}"

* ------------------------------
* 1. 依赖命令检查
* ------------------------------
cap which xsmle
if _rc {
    display as error "未检测到 xsmle。请先执行：ssc install xsmle, replace"
    exit 499
}

cap which spatdiag
if _rc {
    display as error "未检测到 spatdiag。请先执行：ssc install spatdiag, replace"
    exit 499
}

cap which spatwmat
if _rc {
    display as error "未检测到 spatwmat。请先执行：ssc install spatwmat, replace"
    exit 499
}

* ------------------------------
* 2. Mata 辅助函数
* ------------------------------
mata:
real matrix row_normalize(real matrix W)
{
    real scalar i, s
    real matrix R

    R = W
    for (i = 1; i <= rows(R); i++) {
        s = sum(R[i,])
        if (s != 0) {
            R[i,] = R[i,] :/ s
        }
    }
    return(R)
}

real matrix panel_blockdiag(real matrix W, real scalar T)
{
    real scalar t, n, r1, r2, c1, c2
    real matrix P

    n = rows(W)
    P = J(n*T, n*T, 0)
    for (t = 1; t <= T; t++) {
        r1 = (t - 1) * n + 1
        r2 = t * n
        c1 = (t - 1) * n + 1
        c2 = t * n
        P[|r1, c1 \ r2, c2|] = W
    }
    return(P)
}
end

* ------------------------------
* 3. 读取矩阵
* ------------------------------
capture program drop build_w_matrix
program define build_w_matrix, rclass
    syntax , WFILE(string) WNAME(name)

    preserve
        import delimited using "`wfile'", clear varnames(1) encoding(utf8) stringcols(1)
        drop province
        unab wvars : _all
        mkmat `wvars', matrix(`wname'_raw)
    restore

    mata: st_matrix("`wname'", row_normalize(st_matrix("`wname'_raw")))
    matrix drop `wname'_raw

    return local wname "`wname'"
end

* ------------------------------
* 4. 主面板数据
* ------------------------------
tempfile panel_raw
import delimited using "${DATA_FILE}", clear varnames(1) encoding(utf8)

keep province year eff lntl ind urb rd open es
drop if missing(province, year, eff, lntl, ind, urb, rd, open, es)

replace province = trim(province)
destring year eff lntl ind urb rd open es, replace force
sort province year
save "`panel_raw'", replace
global TMP_PANEL_RAW "`panel_raw'"

quietly levelsof province, local(province_list)
local N : word count `province_list'
quietly levelsof year, local(year_list)
local T : word count `year_list'
global N_CROSS = `N'
global T_PERIOD = `T'

display as text "截面个数 N = ${N_CROSS}"
display as text "时期个数 T = ${T_PERIOD}"

* ------------------------------
* 5. 结果输出表
* ------------------------------
tempfile lm_results lr_results wald_results
postfile lm_handle str32 weight_type str20 test_name ///
    double statistic double df double pvalue using "`lm_results'", replace
postfile lr_handle str32 weight_type str30 test_name ///
    double statistic double df double pvalue using "`lr_results'", replace
postfile wald_handle str32 weight_type str30 test_name ///
    double statistic double df double pvalue using "`wald_results'", replace

* ------------------------------
* 6. 单个矩阵的完整检验流程
* ------------------------------
capture program drop run_one_matrix
program define run_one_matrix
    syntax , TAG(string) LABEL(string) WFILE(string)

    tempname W WLM
    tempfile province_order wdiag_dta
    local df_time = ${T_PERIOD} - 1
    local df_ind  = ${N_CROSS} - 1

    preserve
        import delimited using "`wfile'", clear varnames(1) encoding(utf8) stringcols(1)
        gen order_id = _n
        keep province order_id
        save "`province_order'", replace
    restore

    quietly build_w_matrix, wfile("`wfile'") wname(`W')
    local WNAME "`r(wname)'"

    use "${TMP_PANEL_RAW}", clear
    merge m:1 province using "`province_order'", keep(match) nogen
    sort order_id year

    gen pid = order_id
    xtset pid year

    preserve
        clear
        mata: st_matrix("`WLM'", panel_blockdiag(st_matrix("`WNAME'"), ${T_PERIOD}))
        svmat `WLM', names(col)
        save "`wdiag_dta'", replace
    restore

    capture spatwmat drop `WLM'
    quietly spatwmat using "`wdiag_dta'", name(`WLM') standardize

    * ----------------------------------------
    * A. LM / Robust LM
    * ----------------------------------------
    capture log close lm_`tag'
    log using "${STATA_DIR}/LM_`tag'.log", text replace name(lm_`tag')

    display as text "============================================"
    display as text "矩阵：`label' (`tag')"
    display as text "LM / Robust LM 检验"
    display as text "============================================"

    quietly tabulate pid, generate(pid_d_)
    quietly tabulate year, generate(year_d_)

    regress eff lntl ind urb rd open es pid_d_2-pid_d_${N_CROSS} year_d_2-year_d_${T_PERIOD}

    noisily spatdiag, weights(`WLM')
    return list

    capture confirm matrix r(stats)
    if !_rc {
        matrix list r(stats)
    }

    capture confirm matrix r(stats)
    if !_rc {
        tempname LMSTAT
        matrix `LMSTAT' = r(stats)
        post lm_handle ("`tag'") ("LM Error") (`LMSTAT'[2,1]) (`LMSTAT'[2,2]) (`LMSTAT'[2,3])
        post lm_handle ("`tag'") ("Robust LM Error") (`LMSTAT'[3,1]) (`LMSTAT'[3,2]) (`LMSTAT'[3,3])
        post lm_handle ("`tag'") ("LM Lag") (`LMSTAT'[4,1]) (`LMSTAT'[4,2]) (`LMSTAT'[4,3])
        post lm_handle ("`tag'") ("Robust LM Lag") (`LMSTAT'[5,1]) (`LMSTAT'[5,2]) (`LMSTAT'[5,3])
    }

    log close lm_`tag'

    * ----------------------------------------
    * B. LR：个体 / 时间 / 双固定 SDM
    * ----------------------------------------
    capture log close sdm_`tag'
    log using "${STATA_DIR}/模型结果_`tag'.log", text replace name(sdm_`tag')

    display as text "============================================"
    display as text "矩阵：`label' (`tag')"
    display as text "SDM 个体 / 时间 / 双固定估计"
    display as text "============================================"

    quietly xsmle eff lntl ind urb rd open es, ///
        wmat(`WNAME') model(sdm) fe type(ind) nolog noeffects
    estimates store ind_`tag'
    estimates restore ind_`tag'
    ereturn display

    quietly xsmle eff lntl ind urb rd open es, ///
        wmat(`WNAME') model(sdm) fe type(time) nolog noeffects
    estimates store time_`tag'
    estimates restore time_`tag'
    ereturn display

    quietly xsmle eff lntl ind urb rd open es, ///
        wmat(`WNAME') model(sdm) fe type(both) nolog noeffects
    estimates store both_`tag'
    estimates restore both_`tag'
    ereturn display

    display as text "--------------------------------------------"
    display as text "LR 检验"
    display as text "--------------------------------------------"

    quietly lrtest both_`tag' ind_`tag', df(`df_time')
    post lr_handle ("`tag'") ("LR: both vs ind") (r(chi2)) (`df_time') (r(p))
    noisily lrtest both_`tag' ind_`tag', df(`df_time')

    quietly lrtest both_`tag' time_`tag', df(`df_ind')
    post lr_handle ("`tag'") ("LR: both vs time") (r(chi2)) (`df_ind') (r(p))
    noisily lrtest both_`tag' time_`tag', df(`df_ind')

    * ----------------------------------------
    * C. Wald：SDM -> SAR / SDM -> SEM
    * ----------------------------------------
    display as text "--------------------------------------------"
    display as text "Wald 检验"
    display as text "--------------------------------------------"

    quietly estimates restore both_`tag'

    quietly test ///
        ([Wx]lntl = 0) ///
        ([Wx]ind  = 0) ///
        ([Wx]urb  = 0) ///
        ([Wx]rd   = 0) ///
        ([Wx]open = 0) ///
        ([Wx]es   = 0)
    post wald_handle ("`tag'") ("Wald: SDM -> SAR") (r(chi2)) (r(df)) (r(p))
    noisily test ///
        ([Wx]lntl = 0) ///
        ([Wx]ind  = 0) ///
        ([Wx]urb  = 0) ///
        ([Wx]rd   = 0) ///
        ([Wx]open = 0) ///
        ([Wx]es   = 0)

    quietly testnl ///
        ([Wx]lntl = -[Spatial]rho*[Main]lntl) ///
        ([Wx]ind  = -[Spatial]rho*[Main]ind) ///
        ([Wx]urb  = -[Spatial]rho*[Main]urb) ///
        ([Wx]rd   = -[Spatial]rho*[Main]rd) ///
        ([Wx]open = -[Spatial]rho*[Main]open) ///
        ([Wx]es   = -[Spatial]rho*[Main]es)
    post wald_handle ("`tag'") ("Wald: SDM -> SEM") (r(chi2)) (r(df)) (r(p))
    noisily testnl ///
        ([Wx]lntl = -[Spatial]rho*[Main]lntl) ///
        ([Wx]ind  = -[Spatial]rho*[Main]ind) ///
        ([Wx]urb  = -[Spatial]rho*[Main]urb) ///
        ([Wx]rd   = -[Spatial]rho*[Main]rd) ///
        ([Wx]open = -[Spatial]rho*[Main]open) ///
        ([Wx]es   = -[Spatial]rho*[Main]es)

    log close sdm_`tag'
end

* ------------------------------
* 7. 运行四类矩阵
* ------------------------------
run_one_matrix, tag(adjacency_01) label("0-1邻接矩阵") wfile("${W_ADJ_FILE}")
run_one_matrix, tag(economic_inv) label("经济倒数权重矩阵") wfile("${W_ECO_FILE}")
run_one_matrix, tag(geographic_inv) label("地理距离倒数矩阵（省会版）") wfile("${W_GEO_INV_FILE}")
run_one_matrix, tag(economic_geo_nested) label("经济地理嵌套矩阵（省会版）") wfile("${W_ECO_GEO_NEST_FILE}")

postclose lm_handle
postclose lr_handle
postclose wald_handle

use "`lm_results'", clear
sort weight_type test_name
export delimited using "${OUT_DIR}/LM与RobustLM检验结果.csv", replace
save "${STATA_DIR}/LM与RobustLM检验结果.dta", replace

use "`lr_results'", clear
sort weight_type test_name
export delimited using "${OUT_DIR}/LR检验结果.csv", replace
save "${STATA_DIR}/LR检验结果.dta", replace

use "`wald_results'", clear
sort weight_type test_name
export delimited using "${OUT_DIR}/Wald检验结果.csv", replace
save "${STATA_DIR}/Wald检验结果.dta", replace

display as text "============================================"
display as text "结果文件已输出："
display as text "${OUT_DIR}/LM与RobustLM检验结果.csv"
display as text "${OUT_DIR}/LR检验结果.csv"
display as text "${OUT_DIR}/Wald检验结果.csv"
display as text "${STATA_DIR}/LM_*.log"
display as text "${STATA_DIR}/模型结果_*.log"
display as text "============================================"

log close
