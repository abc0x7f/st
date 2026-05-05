import pandas as pd
import matplotlib.pyplot as plt

# 1. 设置中文字体（防止图表中的中文显示为方块）
# Windows系统一般使用SimHei，Mac系统可以使用Arial Unicode MS或Heiti TC
plt.rcParams['font.sans-serif'] = ['SimHei']  
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号

# 2. 读取你的 Excel 数据
# 请将 'your_data.xlsx' 替换为你实际的文件名
file_path = '结果_超效率SBM Malmquist 指数 -全局参比_规模报酬可变VRS_0\结果_超效率SBM Malmquist 指数 -全局参比_规模报酬可变VRS_0.xlsx'
df = pd.read_excel(file_path)

# 3. 找出平均静态生产率最高和最低的省份
# 这里使用 e-g-t 列来计算 7 个时期的平均值
mean_efficiency = df.groupby('Province')['e-g-t'].mean()
best_prov = mean_efficiency.idxmax()
worst_prov = mean_efficiency.idxmin()

print(f"平均静态效率最高的省份是: {best_prov} (平均得分: {mean_efficiency[best_prov]:.4f})")
print(f"平均静态效率最低的省份是: {worst_prov} (平均得分: {mean_efficiency[worst_prov]:.4f})")

# 4. 定义一个函数：将跨期数据(2015-2016)还原为连续的单年时序数据(2015~2022)
def extract_time_series(province_name):
    # 筛选该省份数据并按年份排序，确保时间顺序正确
    prov_df = df[df['Province'] == province_name].sort_values('Year')
    
    years = []
    efficiencies = []
    
    # 遍历前7个时期，提取 t 年的年份和 e-g-t 的值
    for index, row in prov_df.iterrows():
        t_year = row['Year'].split('-')[0]  # 切分出前面的年份，比如 "2015"
        years.append(t_year)
        efficiencies.append(row['e-g-t'])
        
    # 单独处理最后一行，提取 t+1 年的年份和 e-g-t+1 的值，凑齐第8年（2022年）
    last_row = prov_df.iloc[-1]
    last_year = last_row['Year'].split('-')[1] # 切分出后面的年份，比如 "2022"
    years.append(last_year)
    efficiencies.append(last_row['e-g-t+1'])
    
    return years, efficiencies

# 获取最高和最低省份的时序数据
years_best, eff_best = extract_time_series(best_prov)
years_worst, eff_worst = extract_time_series(worst_prov)

# 5. 绘制折线图
plt.figure(figsize=(10, 6), dpi=120)

# 画最高省份的线（红色，带圆点标记）
plt.plot(years_best, eff_best, marker='o', color='#d62728', linewidth=2, 
         label=f'最高省份：{best_prov}')

# 画最低省份的线（蓝色，带方块标记）
plt.plot(years_worst, eff_worst, marker='s', color='#1f77b4', linewidth=2, 
         label=f'最低省份：{worst_prov}')

# 6. 图表美化与细节设置
plt.title('平均静态生产率最高与最低省份的演进趋势 (全局参比)', fontsize=15, pad=15)
plt.xlabel('年份', fontsize=12)
plt.ylabel('静态综合技术效率 (e-g-t 系列)', fontsize=12)

# 添加参考线（效率值为 1.0 的前沿面基准线）
plt.axhline(y=1.0, color='gray', linestyle='--', alpha=0.7, label='有效前沿面基准线 (1.0)')

plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(fontsize=11)
plt.tight_layout()

# 显示图表（或替换为 plt.savefig('trend_chart.png') 保存图片）
plt.show()