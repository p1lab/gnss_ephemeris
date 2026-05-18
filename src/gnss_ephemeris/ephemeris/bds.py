"""BDS 广播星历 → ECEF 位置与钟差解算.

算法来源：北斗 B1I ICD v3.0, Section 5.2.4 (位置) & Section 5.2.3 (钟差).

与 GPS 的关键差异：
  1. 不同常量: mu = 3.986004418e14, Omega_e = 7.292115e-5
  2. GEO 卫星 (PRN 1-5): Step 10 无 -Omega_e*tk; Step 11 应用 R_z(Omega_e*tk)*R_x(-5deg)
  3. MEO/IGSO 卫星: 公式与 GPS 相同，但使用 BDS 常量
"""

from __future__ import annotations

from math import sqrt, sin, cos, atan2

from gnss_ephemeris.rinex.models import BDSEphemeris
from gnss_ephemeris.utils.constants import CLIGHT
from gnss_ephemeris.utils.kepler import solve_kepler
from gnss_ephemeris.utils.time import normalize_sow


# ---------------------------------------------------------------------------
# BDS 常量（北斗 B1I ICD v3.0 Section 5.2.4 / RTKLib rtklib.h）
# ---------------------------------------------------------------------------
MU_CMP = 3.986004418e14     # CGCS2000 地球引力常数 (m^3/s^2)
OMGE_CMP = 7.292115e-5      # CGCS2000 地球自转角速度 (rad/s)

# GEO 5° 旋转常量（RTKLib SIN_5 / COS_5）
SIN_5 = -0.0871557427476582   # sin(-5 deg)
COS_5 = 0.9961946980917456    # cos(-5 deg) = cos(5 deg)

# GEO 卫星 PRN 范围
GEO_PRN_MIN = 1
GEO_PRN_MAX = 5


def _is_geo(eph: BDSEphemeris) -> bool:
    """判断是否为 GEO 卫星 (PRN 1-5)."""
    return GEO_PRN_MIN <= eph.prn <= GEO_PRN_MAX


def bds_eph2pos(
    t_obs: float,
    eph: BDSEphemeris,
) -> tuple[tuple[float, float, float], float, dict]:
    """BDS broadcast ephemeris -> ECEF position & clock bias.

    Args:
        t_obs: 观测历元 (BDT seconds of week)
        eph: BDS 星历参数

    Returns:
        ((X, Y, Z), dts, intermediates)
        - X, Y, Z: 卫星 ECEF 坐标 (CGCS2000, m)
        - dts: 卫星钟差（含相对论校正）(s)
        - intermediates: 中间变量字典，供调试
    """
    geo = _is_geo(eph)

    # =========================================================================
    # Step 1-9: 公共部分 (与 GPS 结构相同，常量不同)
    # 北斗 ICD v3.0 Section 5.2.4 Step 1-9
    # =========================================================================

    # Step 1: 星历参考历元起算的时间差
    tk = normalize_sow(t_obs - eph.toe)

    # Step 2: 计算平均角速度 n0 = sqrt(mu / A^3)
    A = eph.sqrt_a * eph.sqrt_a
    n0 = sqrt(MU_CMP / (A * A * A))

    # Step 3: 校正平均角速度 n = n0 + delta_n
    n = n0 + eph.delta_n

    # Step 4: 平近点角 Mk = M0 + n * tk
    Mk = eph.m0 + n * tk

    # Step 5: 求解开普勒方程
    Ek, kepler_iters = solve_kepler(Mk, eph.e)
    sinEk = sin(Ek)
    cosEk = cos(Ek)

    # Step 6: 真近点角
    vk = atan2(sqrt(1.0 - eph.e * eph.e) * sinEk, cosEk - eph.e)

    # Step 7: 纬度幅角
    uk = vk + eph.omega

    # Step 8: 摄动校正
    sin2uk = sin(2.0 * uk)
    cos2uk = cos(2.0 * uk)

    delta_uk = eph.cus * sin2uk + eph.cuc * cos2uk
    delta_rk = eph.crs * sin2uk + eph.crc * cos2uk
    delta_ik = eph.cis * sin2uk + eph.cic * cos2uk

    uk += delta_uk
    rk = A * (1.0 - eph.e * cosEk) + delta_rk
    ik = eph.i0 + delta_ik + eph.idot * tk

    # Step 9: 轨道平面坐标
    xk_orb = rk * cos(uk)
    yk_orb = rk * sin(uk)

    # =========================================================================
    # Step 10-11: 分支 (GEO vs MEO/IGSO)
    # =========================================================================

    cos_ik = cos(ik)

    if geo:
        # GEO 卫星 (PRN 1-5)

        # Step 10 (GEO): 惯性系升交点经度
        # ICD: Omega_k = Omega_0 + Omega_dot * tk - Omega_e * toe
        # 注意: 没有 -Omega_e * tk 项！
        Omegak = eph.omega0 + eph.omega_dot * tk - OMGE_CMP * eph.toe

        sinO = sin(Omegak)
        cosO = cos(Omegak)

        # Step 11a: 惯性系坐标 (x_G, y_G, z_G)
        xG = xk_orb * cosO - yk_orb * cos_ik * sinO
        yG = xk_orb * sinO + yk_orb * cos_ik * cosO
        zG = yk_orb * sin(ik)

        # Step 11b: 旋转到 CGCS2000 地固系
        # R_z(Omega_e * tk) * R_x(-5 deg)
        sino = sin(OMGE_CMP * tk)
        coso = cos(OMGE_CMP * tk)

        X = xG * coso + yG * sino * COS_5 + zG * sino * SIN_5
        Y = -xG * sino + yG * coso * COS_5 + zG * coso * SIN_5
        Z = -yG * SIN_5 + zG * COS_5

    else:
        # MEO/IGSO 卫星 (PRN 6+)
        # 公式与 GPS 相同，仅常量不同

        # Step 10 (MEO/IGSO): Omega_k = Omega_0 + (Omega_dot - Omega_e) * tk - Omega_e * toe
        Omegak = eph.omega0 + (eph.omega_dot - OMGE_CMP) * tk - OMGE_CMP * eph.toe

        sinO = sin(Omegak)
        cosO = cos(Omegak)

        # Step 11 (MEO/IGSO): ECEF coordinates
        X = xk_orb * cosO - yk_orb * cos_ik * sinO
        Y = xk_orb * sinO + yk_orb * cos_ik * cosO
        Z = yk_orb * sin(ik)

        # MEO/IGSO 不需要 GEO 特有变量
        xG = yG = zG = 0.0
        sino = coso = 0.0

    # =========================================================================
    # 卫星钟差计算
    # 北斗 ICD v3.0 Section 5.2.3
    # =========================================================================

    toc = eph.toe  # BDS: 使用 Toe 作为 Toc
    t_toc = normalize_sow(t_obs - toc)

    # 多项式钟差校正
    dts_poly = eph.af0 + eph.af1 * t_toc + eph.af2 * t_toc * t_toc

    # 相对论校正（注意: mu 使用 BDS 值）
    dtr = -2.0 * sqrt(MU_CMP * A) * eph.e * sinEk / (CLIGHT * CLIGHT)

    # 总钟差
    dts = dts_poly + dtr

    # 收集中间变量
    intermediates = {
        "prn": eph.prn, "sat_type": "GEO" if geo else "MEO/IGSO",
        "tk": tk, "A": A, "n0": n0, "n": n, "Mk": Mk,
        "Ek": Ek, "sinEk": sinEk, "cosEk": cosEk, "vk": vk,
        "uk_before_corr": vk + eph.omega,
        "sin2uk": sin2uk, "cos2uk": cos2uk,
        "delta_uk": delta_uk, "delta_rk": delta_rk, "delta_ik": delta_ik,
        "uk": uk, "rk": rk, "ik": ik,
        "xk_orb": xk_orb, "yk_orb": yk_orb,
        "Omegak": Omegak, "sinO": sinO, "cosO": cosO, "cos_ik": cos_ik,
        "xG": xG, "yG": yG, "zG": zG, "sino": sino, "coso": coso,
        "t_toc": t_toc, "dts_poly": dts_poly, "dtr": dtr, "dts": dts,
        "kepler_iters": kepler_iters,
    }

    return (X, Y, Z), dts, intermediates
