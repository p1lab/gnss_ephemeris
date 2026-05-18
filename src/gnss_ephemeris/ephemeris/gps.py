"""GPS 广播星历 → ECEF 位置与钟差解算.

算法来源：IS-GPS-200N, Table 20-IV (位置) & Section 20.3.3.3.3.1 (钟差).
工程参考：RTKLib src/ephemeris.c eph2pos().
"""

from __future__ import annotations

from math import sqrt, sin, cos, atan2

from gnss_ephemeris.rinex.models import GPSEphemeris
from gnss_ephemeris.utils.constants import CLIGHT
from gnss_ephemeris.utils.kepler import solve_kepler
from gnss_ephemeris.utils.time import normalize_sow


# ---------------------------------------------------------------------------
# GPS 常量（IS-GPS-200N Section 30.3.3 / RTKLib rtklib.h）
# ---------------------------------------------------------------------------
MU_GPS = 3.9860050e14       # WGS84 地球引力常数 (m^3/s^2)
OMGE = 7.2921151467e-5      # WGS84 地球自转角速度 (rad/s)


def gps_eph2pos(
    t_obs: float,
    eph: GPSEphemeris,
) -> tuple[tuple[float, float, float], float, dict]:
    """GPS broadcast ephemeris -> ECEF position & clock bias.

    Args:
        t_obs: 观测历元 (GPS seconds of week)
        eph: GPS 星历参数

    Returns:
        ((X, Y, Z), dts, intermediates)
        - X, Y, Z: 卫星 ECEF 坐标 (m)
        - dts: 卫星钟差（含相对论校正）(s)
        - intermediates: 中间变量字典，供调试
    """
    # Step 1: 星历参考历元起算的时间差
    # IS-GPS-200N Table 20-IV
    tk = normalize_sow(t_obs - eph.toe)

    # Step 2: 计算平均角速度 n0 = sqrt(mu / A^3)
    A = eph.sqrt_a * eph.sqrt_a
    n0 = sqrt(MU_GPS / (A * A * A))

    # Step 3: 校正平均角速度 n = n0 + delta_n
    n = n0 + eph.delta_n

    # Step 4: 平近点角 Mk = M0 + n * tk
    Mk = eph.m0 + n * tk

    # Step 5: 求解开普勒方程 Mk = Ek - e*sin(Ek)
    Ek, kepler_iters = solve_kepler(Mk, eph.e)
    sinEk = sin(Ek)
    cosEk = cos(Ek)

    # Step 6: 真近点角 vk = atan2(sqrt(1-e^2)*sin(Ek), cos(Ek)-e)
    vk = atan2(sqrt(1.0 - eph.e * eph.e) * sinEk, cosEk - eph.e)

    # Step 7: 纬度幅角 uk = vk + omega
    uk = vk + eph.omega

    # Step 8: 摄动校正
    sin2uk = sin(2.0 * uk)
    cos2uk = cos(2.0 * uk)

    delta_uk = eph.cus * sin2uk + eph.cuc * cos2uk
    delta_rk = eph.crs * sin2uk + eph.crc * cos2uk
    delta_ik = eph.cis * sin2uk + eph.cic * cos2uk

    # 校正后的纬度幅角、轨道半径、倾角
    uk += delta_uk
    rk = A * (1.0 - eph.e * cosEk) + delta_rk
    ik = eph.i0 + delta_ik + eph.idot * tk

    # Step 9: 轨道平面坐标
    xk_orb = rk * cos(uk)
    yk_orb = rk * sin(uk)

    # Step 10: 校正升交点经度
    # Omegak = Omega0 + (Omega_dot - omge) * tk - omge * toe
    Omegak = eph.omega0 + (eph.omega_dot - OMGE) * tk - OMGE * eph.toe

    # Step 11: ECEF 坐标
    sinO = sin(Omegak)
    cosO = cos(Omegak)
    cos_ik = cos(ik)

    X = xk_orb * cosO - yk_orb * cos_ik * sinO
    Y = xk_orb * sinO + yk_orb * cos_ik * cosO
    Z = yk_orb * sin(ik)

    # ---- 钟差计算 ----
    # IS-GPS-200N Section 20.3.3.3.3.1

    # 钟差参考历元起算的时间差
    toc = eph.toe  # GPS: Toe == Toc in same record
    t_toc = normalize_sow(t_obs - toc)

    # 多项式钟差校正
    dts_poly = eph.af0 + eph.af1 * t_toc + eph.af2 * t_toc * t_toc

    # 相对论校正 dtr = -2 * sqrt(mu * A) * e * sin(Ek) / c^2
    dtr = -2.0 * sqrt(MU_GPS * A) * eph.e * sinEk / (CLIGHT * CLIGHT)

    # 总钟差
    dts = dts_poly + dtr

    # 收集中间变量
    intermediates = {
        "tk": tk, "A": A, "n0": n0, "n": n, "Mk": Mk,
        "Ek": Ek, "sinEk": sinEk, "cosEk": cosEk, "vk": vk,
        "uk_before_corr": vk + eph.omega,
        "sin2uk": sin2uk, "cos2uk": cos2uk,
        "delta_uk": delta_uk, "delta_rk": delta_rk, "delta_ik": delta_ik,
        "uk": uk, "rk": rk, "ik": ik,
        "xk_orb": xk_orb, "yk_orb": yk_orb,
        "Omegak": Omegak, "sinO": sinO, "cosO": cosO, "cos_ik": cos_ik,
        "t_toc": t_toc, "dts_poly": dts_poly, "dtr": dtr, "dts": dts,
        "kepler_iters": kepler_iters,
    }

    return (X, Y, Z), dts, intermediates
