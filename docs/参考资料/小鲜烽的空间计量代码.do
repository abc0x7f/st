***前言***
**stata15及以上使用

keep 年份 地区代码 lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad
order 年份 地区代码  lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad

**被解释变量:lnRGDP
**解释变量:rateir
**控制变量：lnRpop lnScon lnK lnRopen fispower lnroad

//两种下载命令方式  command spatwmat is unrecognized
ssc install xtmoran,replace
ssc install shp2dta,replace
ssc install spatwmat,replace

findit spmat
findit spatwmat

//手动更改工作目录

//利用行政区划矢量数据获取经纬度 GCS
shp2dta using "中国_市-MULTIPOLYGON.shp" ,data(data_db) coor(data_xy) genid(id) gence(stub) replace
use data_db, clear
***去excel使用vlookup合并坐标和人均GDP***
//清空数据
clear
//导入Excel文件
xtset id 年份
//计算n年的年平均“人均GDP"
bys id:egen meamGDP=mean(人均GDP)

//保存面板数据

//保存截面数据
keep if 年份==2020

//记录路径：
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
use "E:\空间计量\空间计量演示数据\空间截面数据.dta",clear
xtset id 年份

//记录区：反距离矩阵W01  反距离平方矩阵W02 经济距离矩阵W03  嵌套矩阵W04  0-1矩阵W05   行标准化后的反距离SWO1


//地理距离矩阵-反距离
spwmatrix gecon y_stub x_stub, wname(W01) wtype(inv) alpha(1) xport(W01,txt) replace
clear
svmat W01
save W01,replace

//地理距离矩阵-反距离平方
spwmatrix gecon y_stub x_stub, wname(W02) wtype(inv) alpha(2) xport(W02,txt) replace
clear
svmat W02
save W02,replace

//经济距离矩阵   不要用spwmatrix！！！

tomata meamGDP
mata 
      W = J(284,284,0)  
	  id = 1::284
      for (k=1; k<=length(meamGDP);k++) {
  	     for (j=1; j<=length(meamGDP);j++) {
		
	    vk=meamGDP[k]	;vj=meamGDP[j]
		if (k!=j)
        W[k,j]=1/abs(vk-vj) 
      }
     }
   end  
   
spmatrix spfrommata W03 = W id, normalize(none)
spmatrix dir
spmatrix export W03 using W03.txt,replace
clear
getmata (x*)=W
save W03.dta, replace

//经济地理嵌套矩阵（各0.5权重）
spmatrix import W01 using W01.txt ,replace
spmatrix import W03 using W03.txt ,replace
spmatrix matafromsp Wx id = W01
spmatrix matafromsp Wy id = W03

mata
      Wxy = 0.5*Wx + 0.5*Wy
end

spmatrix spfrommata W04 = Wxy id, normalize(none)
spmatrix export W04 using W04.txt,replace
clear
spmat import W04 using "W04.txt",replace
spmat getmatrix W04 W
getmata (x*)=W
save W04.dta, replace

//0-1邻接矩阵---使用spmat
use "E:\空间计量\空间计量演示数据\空间截面数据.dta",clear
xtset id 年份
spmat contiguity W05 using data_xy ,id(id) replace     
spmat summarize W05 
spmat export W05 using W05.txt,replace 
clear
cap spmat drop W05
spmat import W05 using W05.txt
spmat getmatrix W05 M
getmata(x*) = M
save W05,replace

///莫兰指数---此步骤会自动标准化矩阵
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
//全局莫兰
xtset id 年份
xtmoran lnRGDP, wname(W01.dta)
//局部莫兰
xtmoran lnRGDP, wname(W01.dta) morani(2011 2015 2019) graph symbol()
//莫兰指数导出
asdoc xtmoran lnRGDP, wname(W01.dta)
//局部莫兰加上名字---建议省级层面数据用
xtmoran lnRGDP, wname(W01.dta) morani(2020) graph symbol(name)

//LM检验---扩大矩阵   help memory
clear all
set maxvar 10000    
use W01
spcs2xt W011-W01284, matrix(aaa) time(19)
spatwmat using aaaxt, name(WLM) standardize
clear
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
xtset id 年份
reg lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad
spatdiag, weights(WLM)

//hausman检验
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
xtset id 年份
spatwmat using W01.dta, name(SW01) standardize
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, hausman model(sdm) wmat(SW01)

//LR检验
spatwmat using W01.dta, name(SW01) standardize
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, fe model(sdm) wmat(SW01) type(ind)
est store ind
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, fe model(sdm) wmat(SW01) type(time)
est store time
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, fe model(sdm) wmat(SW01) type(both)
est store both
lrtest both ind, df(10)
lrtest both time, df(10)

//Wald检验
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, wmat(SW01) model(sdm) fe type(both)
//Wald检验---SAR
test [Wx]rateir=[Wx]lnRpop=[Wx]lnScon=[Wx]lnK=[Wx]lnRopen=[Wx]fispower=[Wx]lnroad=0
//Wald检验---SEM
testnl ([Wx]rateir=-[Spatial]rho*[Main]rateir)([Wx]lnRpop=-[Spatial]rho*[Main]lnRpop)([Wx]lnScon=-[Spatial]rho*[Main]lnScon)([Wx]lnK=-[Spatial]rho*[Main]lnK)([Wx]lnRopen=-[Spatial]rho*[Main]lnRopen)([Wx]fispower=-[Spatial]rho*[Main]fispower)([Wx]lnroad=-[Spatial]rho*[Main]lnroad)

//双固定空间杜宾模型
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad, wmat(SW01) model(sdm) fe type(both) vce(r) from(0.03 0.15 0.042 0.233 0.008 -0.852 0.004 0.274 -0.004 -0.324 0.175 0.055 1.976 0.222 0.902 0.0125, copy)
//结果导出t值版
outreg2 using result.doc,replace tstat bdec(4) tdec(4) ctitle(aaa)
//结果导出标准误版
outreg2 using result.doc,replace bdec(4) tdec(4) ctitle(aaa)

///空间异质性分析（思路介绍）
//生成东部地区的矩阵：W东部
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
keep if 是否东部==1
keep if 年份==2020
**省略生成矩阵命令

//生成东部地区的矩阵：W非东部
use "E:\空间计量\空间计量演示数据\空间面板数据.dta",clear
keep if 是否东部==0
keep if 年份==2020
**省略生成矩阵命令

//异质性分析命令
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad if 东部地区==1, wmat(SW东部) model(sdm) effect fe type(both) vce(cluster id)
xsmle lnRGDP rateir lnRpop lnScon lnK lnRopen fispower lnroad if 东部地区==0, wmat(SW非东部) model(sdm) effect fe type(both) vce(cluster id)

///空间中介效应
//第一步：解释变量影响被解释变量
xsmle 被解释 解释 控制变量, wmat(SW01) model(sdm) effect fe type(both) vce(cluster id)
//第二步：解释变量影响中介变量
xsmle 中介变量 解释 控制变量, wmat(SW01) model(sdm) effect fe type(both) vce(cluster id)
//第三步：解释变量通过中介变量影响被解释
xsmle 被解释 中介变量 解释 控制变量, wmat(SW01) model(sdm) effect fe type(both) vce(cluster id)

