import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 50)
y = np.exp(-0.1 * x) * np.sin(x)

fig, ax = plt.subplots(facecolor='white') # 深色背景效果更佳
ax.set_facecolor('white')

# 核心：循环绘制多层背景线，线宽逐渐增大，透明度逐渐降低
n_lines = 10
diff_linewidth = 1.05
alpha_value = 0.03

for i in range(1, n_lines + 1):
    ax.plot(x, y, linewidth=2 + (diff_linewidth * i),
            alpha=alpha_value, color='blue', zorder=i)

# 绘制最亮的主中心线
ax.plot(x, y, color='#FFFFFF', linewidth=1.5, zorder=n_lines+1)

plt.show()