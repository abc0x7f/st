version 17.0
clear all
set more off

* ============================================================
* 空间 SDM 主模型估计与效应分解
* 主模型：经济倒数权重矩阵 + 双固定效应 SDM
* 对照模型：0-1 邻接矩阵 + 双固定效应 SDM
* 输出：
* 1. 主模型系数表
* 2. 空间效应分解表
* 3. Stata 日志
* ============================================================

global PROJECT_ROOT "C:/Users/abc0x7f/Desktop/PRO/统计建模"
cd "${PROJECT_ROOT}"

global DATA_FILE   "data/最终数据/第二阶段_基础.csv"
global W_ADJ_FILE  "data/最终数据/省际01邻接矩阵.csv"
global W_ECO_FILE  "data/最终数据/省际经济距离矩阵.csv"
global W_GEO_INV_FILE "data/最终数据/省际地理距离倒数矩阵_省会版.csv"
global W_ECO_GEO_NEST_FILE "data/最终数据/省际经济地理嵌套矩阵_省会版.csv"
global OUT_DIR     "outputs/回归分析/80_空间SDM主模型"
global STATA_DIR   "${OUT_DIR}/stata"

cap mkdir "${OUT_DIR}"
cap mkdir "${STATA_DIR}"
cap log close _all
log using "${STATA_DIR}/空间SDM主模型总日志.log", text replace

cap which xsmle
if _rc {
    display as error "未检测到 xsmle。请先执行：ssc install xsmle, replace"
    exit 499
}

* ------------------------------
* 1. Mata 辅助函数
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
end

* ------------------------------
* 2. 读取空间矩阵
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
* 3. 主面板数据
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

* ------------------------------
* 4. 结果收集表
* ------------------------------
tempfile coef_results effect_results
postfile coef_handle str32 weight_type str20 section str20 variable ///
    double coef double se double zstat double pvalue double ll double ul ///
    using "`coef_results'", replace
postfile effect_handle str32 weight_type str20 effect_type str20 variable ///
    double coef double se double zstat double pvalue double ll double ul ///
    using "`effect_results'", replace

* ------------------------------
* 5. 单个矩阵的模型估计
* ------------------------------
capture program drop run_sdm_model
program define run_sdm_model
    syntax , TAG(string) LABEL(string) WFILE(string)

    tempname W RTAB
    local k = 0

    quietly build_w_matrix, wfile("`wfile'") wname(`W')
    local WNAME "`r(wname)'"

    use "${TMP_PANEL_RAW}", clear
    encode province, gen(pid)
    xtset pid year

    capture log close sdm_`tag'
    log using "${STATA_DIR}/SDM主模型_`tag'.log", text replace name(sdm_`tag')

    display as text "============================================"
    display as text "矩阵：`label' (`tag')"
    display as text "双固定效应 SDM 主模型"
    display as text "============================================"

    quietly xsmle eff lntl ind urb rd open es, ///
        wmat(`WNAME') model(sdm) fe type(both) effect nolog

    ereturn display
    return list
    matrix `RTAB' = r(table)

    local cnames : colfullnames e(b)
    local k = colsof(`RTAB')

    forvalues j = 1/`k' {
        local token : word `j' of `cnames'
        local clean = subinstr("`token'", ":", " ", .)
        local section : word 1 of `clean'
        local variable : word 2 of `clean'

        scalar b  = `RTAB'[1,`j']
        scalar se = `RTAB'[2,`j']
        scalar zz = `RTAB'[3,`j']
        scalar pp = `RTAB'[4,`j']
        scalar ll = `RTAB'[5,`j']
        scalar ul = `RTAB'[6,`j']

        if inlist("`section'", "Main", "Wx", "Spatial", "Variance") {
            post coef_handle ("`tag'") ("`section'") ("`variable'") ///
                (b) (se) (zz) (pp) (ll) (ul)
        }
        else if inlist("`section'", "LR_Direct", "LR_Indirect", "LR_Total") {
            post effect_handle ("`tag'") ("`section'") ("`variable'") ///
                (b) (se) (zz) (pp) (ll) (ul)
        }
    }

    log close sdm_`tag'
end

* ------------------------------
* 6. 运行四类矩阵模型
* ------------------------------
run_sdm_model, tag(economic_inv) label("经济倒数权重矩阵") wfile("${W_ECO_FILE}")
run_sdm_model, tag(adjacency_01) label("0-1邻接矩阵") wfile("${W_ADJ_FILE}")
run_sdm_model, tag(geographic_inv) label("地理距离倒数矩阵（省会版）") wfile("${W_GEO_INV_FILE}")
run_sdm_model, tag(economic_geo_nested) label("经济地理嵌套矩阵（省会版）") wfile("${W_ECO_GEO_NEST_FILE}")

postclose coef_handle
postclose effect_handle

use "`coef_results'", clear
sort weight_type section variable
export delimited using "${OUT_DIR}/主模型系数表.csv", replace
save "${STATA_DIR}/主模型系数表.dta", replace

use "`effect_results'", clear
sort weight_type effect_type variable
export delimited using "${OUT_DIR}/空间效应分解表.csv", replace
save "${STATA_DIR}/空间效应分解表.dta", replace

display as text "============================================"
display as text "结果文件已输出："
display as text "${OUT_DIR}/主模型系数表.csv"
display as text "${OUT_DIR}/空间效应分解表.csv"
display as text "${STATA_DIR}/SDM主模型_*.log"
display as text "============================================"

log close
