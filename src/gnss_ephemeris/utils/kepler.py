"""开普勒方程求解器.

Mk = Ek - e * sin(Ek)

采用 Newton 迭代法，与 RTKLib src/ephemeris.c eph2pos() 一致：
  - 初始值 Ek = Mk
  - Ek+1 = Ek - (Ek - e*sin(Ek) - Mk) / (1 - e*cos(Ek))
"""

from __future__ import annotations

import sys
from gnss_ephemeris.utils.constants import RTOL_KEPLER, MAX_ITER_KEPLER


def solve_kepler(
    Mk: float,
    e: float,
    rtol: float = RTOL_KEPLER,
    max_iter: int = MAX_ITER_KEPLER,
) -> tuple[float, int]:
    """求解开普勒方程 Mk = Ek - e*sin(Ek).

    Args:
        Mk: 平近点角 (rad)
        e: 轨道偏心率
        rtol: 收敛容差 (rad)，默认 RTOL_KEPLER
        max_iter: 最大迭代次数，默认 MAX_ITER_KEPLER

    Returns:
        (Ek, n_iter): 偏近点角与实际迭代次数
    """
    from math import sin, cos

    Ek = Mk
    n_iter = max_iter
    for i in range(max_iter):
        Ek_old = Ek
        Ek = Ek_old - (Ek_old - e * sin(Ek_old) - Mk) / (1.0 - e * cos(Ek_old))
        if abs(Ek - Ek_old) < rtol:
            n_iter = i + 1
            break
    else:
        print(
            f"[WARNING] 开普勒方程未收敛：Mk={Mk}, e={e}, "
            f"迭代 {max_iter} 次后残差={abs(Ek - Ek_old):.2e}",
            file=sys.stderr,
        )
        n_iter = max_iter

    return Ek, n_iter
