"""物理常数与算法参数.

所有常量来源：
  - CLIGHT: CODATA 2017 / IS-GPS-200N
  - RTOL_KEPLER / MAX_ITER_KEPLER: RTKLib rtklib.h
"""

CLIGHT = 299792458.0        # 真空光速 (m/s)

# 开普勒方程求解器参数（与 RTKLib 对齐）
RTOL_KEPLER = 1e-14         # 收敛容差 (rad)
MAX_ITER_KEPLER = 30         # 最大迭代次数
