clear all
set more off
cd "C:/Users/abc0x7f/Desktop/PRO/统计建模"

import delimited using "data/最终数据/省际经济距离矩阵.csv", clear varnames(1) encoding(utf8) stringcols(1)
drop province
mkmat _all, matrix(Wraw)

mata:
real matrix row_normalize(real matrix W)
{
    real scalar i, s
    real matrix R
    R = W
    for (i=1; i<=rows(R); i++) {
        s = sum(R[i,])
        if (s != 0) R[i,] = R[i,] :/ s
    }
    return(R)
}
end

mata: st_matrix("W", row_normalize(st_matrix("Wraw")))
matrix drop Wraw

import delimited using "data/最终数据/第二阶段_基础.csv", clear varnames(1) encoding(utf8)
keep province year eff lntl ind urb rd open es
drop if missing(province, year, eff, lntl, ind, urb, rd, open, es)
replace province = trim(province)
destring year eff lntl ind urb rd open es, replace force
encode province, gen(pid)
xtset pid year

xsmle eff lntl ind urb rd open es, wmat(W) model(sdm) fe type(both) effect nolog
return list
ereturn list
matrix list e(b)
