import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

# 1. 设置中文字体与负号显示
plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows用黑体，Mac用户可改为 'Arial Unicode MS'
plt.rcParams['axes.unicode_minus'] = False 

# 2. 读取数据 (注意替换为你实际的文件名和路径)
# 强烈建议像上次一样，使用 r'绝对路径' 防止报错
file_path = r'结果_SBM超效率模型_规模报酬可变VRS_0\结果_SBM超效率模型_规模报酬可变VRS_0.xlsx'
df = pd.read_excel(file_path)

# 确保 Year 字段被识别为整数，防止X轴出现小数年份(如2015.5)
df['Year'] = df['Year'].astype(int)

# 3. 初始化画布 (设置得宽一点，给右侧图例留出空间)
plt.figure(figsize=(14, 7), dpi=120)

# 获取所有省份的唯一列表
provinces = df['Province'].unique()

# 生成一组颜色映射（为30个省份分配不同颜色）
colors = cm.get_cmap('tab20', len(provinces))

# 4. 循环绘制每个省份的折线
for i, province in enumerate(provinces):
    # 筛选出当前省份的数据，并按年份排序确保连线正确
    prov_data = df[df['Province'] == province].sort_values('Year')
    
    # 画线
    plt.plot(prov_data['Year'], 
             prov_data['超效率'], 
             marker='.',          # 加个小圆点标示具体年份
             linewidth=1.5,       # 线条稍微细一点，防止30条线太拥挤
             alpha=0.8,           # 稍微加一点透明度
             color=colors(i), 
             label=province)

# 5. 图表美化与细节设置
plt.title('2015-2022年全国30个省份超效率演进趋势', fontsize=16, pad=15)
plt.xlabel('年份', fontsize=12)
plt.ylabel('超效率得分', fontsize=12)

# 添加有效前沿面基准线 (y=1.0)
plt.axhline(y=1.0, color='black', linestyle='--', linewidth=2, alpha=0.7, zorder=0, label='有效前沿面基准 (1.0)')

# 限制X轴只显示整数年份
plt.xticks(np.arange(df['Year'].min(), df['Year'].max() + 1, 1))

# 添加网格线，方便对齐看数据
plt.grid(True, linestyle=':', alpha=0.6)

# 6. 处理极其庞大的图例 (将其移到绘图区域的右侧外部，分为两列)
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0., ncol=2, fontsize=10)

# 自动调整布局，防止右侧图例被切掉
plt.tight_layout()

# 7. 显示图表 (如果想保存为图片，将下面这行替换为 plt.savefig('超效率折线图.png', bbox_inches='tight') )
plt.show()