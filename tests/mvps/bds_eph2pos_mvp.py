#!/usr/bin/env python3
"""MVP: BDS broadcast ephemeris -> satellite ECEF position & clock bias.

Algorithm source: 北斗 B1I ICD v3.0, Section 5.2.4 (position) & Section 5.2.3 (clock).
Engineering reference: RTKLib src/ephemeris.c eph2pos().

Key differences from GPS:
  1. Different constants: mu = 3.986004418e14, Omega_e = 7.292115e-5
  2. GEO satellites (PRN 1-5): Step 10 omits -Omega_e*tk; Step 11 applies R_z(Omega_e*tk)*R_x(-5deg)
  3. MEO/IGSO satellites: same formula as GPS but with BDS constants
"""

from __future__ import annotations
from math import sqrt, sin, cos, atan2
import sys

# ---------------------------------------------------------------------------
# Constants (北斗 B1I ICD v3.0 Section 5.2.4 / RTKLib rtklib.h)
# ---------------------------------------------------------------------------
MU_CMP = 3.986004418e14     # CGCS2000 gravitational constant (m^3/s^2)
OMGE_CMP = 7.292115e-5      # CGCS2000 earth rotation rate (rad/s)
CLIGHT = 299792458.0        # speed of light (m/s)

# GEO 5-degree rotation constants (RTKLib SIN_5 / COS_5)
SIN_5 = -0.0871557427476582   # sin(-5 deg)
COS_5 = 0.9961946980917456    # cos(-5 deg) = cos(5 deg)

# Kepler equation solver parameters (aligned with RTKLib)
RTOL_KEPLER = 1e-14
MAX_ITER_KEPLER = 30

# GEO satellite PRN range
GEO_PRN_MIN = 1
GEO_PRN_MAX = 5


def _is_geo(prn: int) -> bool:
    """判断是否为 GEO 卫星 (PRN 1-5)."""
    return GEO_PRN_MIN <= prn <= GEO_PRN_MAX


def _extract_prn(eph: dict) -> int:
    """从星历字典中提取 PRN 整数值.

    RINEX 2.x: eph['prn'] = int (如 1)
    RINEX 3.x: eph['sv'] = str (如 'C01')
    """
    if "prn" in eph:
        return int(eph["prn"])
    if "sv" in eph:
        sv = eph["sv"]
        # 取数字部分, 如 'C01' -> 1, 'C10' -> 10
        return int(sv[1:])
    raise ValueError(f"Cannot extract PRN from ephemeris dict: {eph}")


def bds_eph2pos(t_obs: float, eph: dict, prn: int | None = None) -> tuple[tuple[float, float, float], float, dict]:
    """BDS broadcast ephemeris -> ECEF position & clock bias.

    Args:
        t_obs: observation epoch (BDT seconds of week)
        eph: dict of ephemeris parameters from rinex_parser_mvp
        prn: satellite PRN number (1-5 = GEO, 6+ = MEO/IGSO).
             If None, auto-extracted from eph dict.

    Returns:
        ((X, Y, Z), dts, intermediates)
        - X, Y, Z: satellite ECEF coordinates in CGCS2000 (m)
        - dts: satellite clock bias including relativity correction (s)
        - intermediates: dict of all intermediate variables for debugging
    """
    if prn is None:
        prn = _extract_prn(eph)

    geo = _is_geo(prn)

    # Extract ephemeris parameters
    sqrt_a = eph["sqrt_a"]          # sqrt(A) (sqrt(m))
    e = eph["e"]                    # eccentricity
    m0 = eph["m0"]                  # mean anomaly at Toe (rad)
    delta_n = eph["delta_n"]        # mean motion correction (rad/s)
    toe = eph["toe"]                # ephemeris reference time (BDT sow)
    toc = eph["toe"]                # for BDS: use Toe as Toc (same record)
    omega = eph["omega"]            # argument of perigee (rad)
    omega0 = eph["omega0"]          # right ascension of ascending node (rad)
    omega_dot = eph["omega_dot"]    # rate of right ascension (rad/s)
    i0 = eph["i0"]                  # inclination at Toe (rad)
    idot = eph["idot"]              # rate of inclination (rad/s)
    cuc = eph["cuc"]                # cos harmonic correction to argument of latitude (rad)
    cus = eph["cus"]                # sin harmonic correction to argument of latitude (rad)
    crc = eph["crc"]                # cos harmonic correction to orbit radius (m)
    crs = eph["crs"]                # sin harmonic correction to orbit radius (m)
    cic = eph["cic"]                # cos harmonic correction to inclination (rad)
    cis = eph["cis"]                # sin harmonic correction to inclination (rad)
    af0 = eph["af0"]                # clock bias (s)
    af1 = eph["af1"]                # clock drift (s/s)
    af2 = eph["af2"]                # clock drift rate (s/s^2)

    mu = MU_CMP
    omge = OMGE_CMP

    # =========================================================================
    # Step 1-9: 公共部分 (与 GPS 结构相同, 常量不同)
    # 北斗 ICD v3.0 Section 5.2.4 Step 1-9
    # =========================================================================

    # Step 1: Time from ephemeris reference epoch
    # ICD Section 5.2.4 Step 1
    tk = t_obs - toe
    if tk > 302400.0:
        tk -= 604800.0
    elif tk < -302400.0:
        tk += 604800.0

    # Step 2: Computed mean motion (rad/s)
    # n0 = sqrt(mu / A^3)
    A = sqrt_a * sqrt_a
    n0 = sqrt(mu / (A * A * A))

    # Step 3: Corrected mean motion
    # n = n0 + delta_n
    n = n0 + delta_n

    # Step 4: Mean anomaly
    # Mk = M0 + n * tk
    Mk = m0 + n * tk

    # Step 5: Solve Kepler equation for Ek
    # Mk = Ek - e * sin(Ek)
    # Newton iteration: Ek+1 = Ek - (Ek - e*sin(Ek) - Mk) / (1 - e*cos(Ek))
    Ek = Mk
    for iteration_count in range(MAX_ITER_KEPLER):
        Ek_old = Ek
        Ek = Ek_old - (Ek_old - e * sin(Ek_old) - Mk) / (1.0 - e * cos(Ek_old))
        if abs(Ek - Ek_old) < RTOL_KEPLER:
            break
    else:
        print(f"[WARNING] Kepler equation did not converge after {MAX_ITER_KEPLER} iterations", file=sys.stderr)

    sinEk = sin(Ek)
    cosEk = cos(Ek)

    # Step 6: True anomaly
    # vk = atan2(sqrt(1-e^2)*sin(Ek), cos(Ek)-e)
    vk = atan2(sqrt(1.0 - e * e) * sinEk, cosEk - e)

    # Step 7: Argument of latitude
    # uk = vk + omega
    uk = vk + omega

    # Step 8: Perturbation corrections
    sin2uk = sin(2.0 * uk)
    cos2uk = cos(2.0 * uk)

    delta_uk = cus * sin2uk + cuc * cos2uk
    delta_rk = crs * sin2uk + crc * cos2uk
    delta_ik = cis * sin2uk + cic * cos2uk

    # Corrected argument of latitude, radius, and inclination
    uk += delta_uk
    rk = A * (1.0 - e * cosEk) + delta_rk
    ik = i0 + delta_ik + idot * tk

    # Step 9: Positions in orbital plane
    xk_orb = rk * cos(uk)
    yk_orb = rk * sin(uk)

    # =========================================================================
    # Step 10-11: 分支部分 (GEO vs MEO/IGSO)
    # 北斗 ICD v3.0 Section 5.2.4 Step 10-11
    # =========================================================================

    cos_ik = cos(ik)

    if geo:
        # -----------------------------------------------------------------
        # GEO 卫星 (PRN 1-5)
        # -----------------------------------------------------------------

        # Step 10 (GEO): 计算惯性系中的升交点经度
        # ICD: Omega_k = Omega_0 + Omega_dot * tk - Omega_e * toe
        # 注意: 没有 -Omega_e * tk 项！
        Omegak = omega0 + omega_dot * tk - omge * toe

        sinO = sin(Omegak)
        cosO = cos(Omegak)

        # Step 11a: 惯性系坐标 (x_G, y_G, z_G)
        xG = xk_orb * cosO - yk_orb * cos_ik * sinO
        yG = xk_orb * sinO + yk_orb * cos_ik * cosO
        zG = yk_orb * sin(ik)

        # Step 11b: 旋转到 CGCS2000 地固系
        # R_z(Omega_e * tk) * R_x(-5 deg)
        # RTKLib: sino=sin(omge*tk), coso=cos(omge*tk)
        sino = sin(omge * tk)
        coso = cos(omge * tk)

        X = xG * coso + yG * sino * COS_5 + zG * sino * SIN_5
        Y = -xG * sino + yG * coso * COS_5 + zG * coso * SIN_5
        Z = -yG * SIN_5 + zG * COS_5

    else:
        # -----------------------------------------------------------------
        # MEO/IGSO 卫星 (PRN 6+)
        # 公式与 GPS 相同, 仅常量不同
        # -----------------------------------------------------------------

        # Step 10 (MEO/IGSO): Omega_k = Omega_0 + (Omega_dot - Omega_e) * tk - Omega_e * toe
        Omegak = omega0 + (omega_dot - omge) * tk - omge * toe

        sinO = sin(Omegak)
        cosO = cos(Omegak)

        # Step 11 (MEO/IGSO): ECEF coordinates
        X = xk_orb * cosO - yk_orb * cos_ik * sinO
        Y = xk_orb * sinO + yk_orb * cos_ik * cosO
        Z = yk_orb * sin(ik)

        # MEO/IGSO 不需要 GEO 特有变量, 设为 0
        xG = yG = zG = 0.0
        sino = coso = 0.0

    # =========================================================================
    # 卫星钟差计算
    # 北斗 ICD v3.0 Section 5.2.3
    # =========================================================================

    # Time from clock reference epoch
    t_toc = t_obs - toc
    if t_toc > 302400.0:
        t_toc -= 604800.0
    elif t_toc < -302400.0:
        t_toc += 604800.0

    # Polynomial clock correction
    dts = af0 + af1 * t_toc + af2 * t_toc * t_toc

    # Relativity correction (注意: mu 使用 BDS 值)
    # dtr = -2 * sqrt(mu * A) * e * sin(Ek) / c^2
    dtr = -2.0 * sqrt(mu * A) * e * sinEk / (CLIGHT * CLIGHT)

    # Total clock bias
    dts += dtr

    # Collect intermediates for debugging
    intermediates = {
        "prn": prn,
        "sat_type": "GEO" if geo else "MEO/IGSO",
        "tk": tk,
        "A": A,
        "n0": n0,
        "n": n,
        "Mk": Mk,
        "Ek": Ek,
        "sinEk": sinEk,
        "cosEk": cosEk,
        "vk": vk,
        "uk_before_corr": vk + omega,
        "sin2uk": sin2uk,
        "cos2uk": cos2uk,
        "delta_uk": delta_uk,
        "delta_rk": delta_rk,
        "delta_ik": delta_ik,
        "uk": uk,
        "rk": rk,
        "ik": ik,
        "xk_orb": xk_orb,
        "yk_orb": yk_orb,
        "Omegak": Omegak,
        "sinO": sinO,
        "cosO": cosO,
        "cos_ik": cos_ik,
        # GEO-specific
        "xG": xG,
        "yG": yG,
        "zG": zG,
        "sino": sino,
        "coso": coso,
        # Clock
        "t_toc": t_toc,
        "dts_poly": af0 + af1 * t_toc + af2 * t_toc * t_toc,
        "dtr": dtr,
        "dts": dts,
        "kepler_iters": iteration_count + 1,
    }

    return (X, Y, Z), dts, intermediates


def main():
    """MVP 入口: 解析 BDS 星历, 计算 Toe 时刻位置与钟差, 打印所有中间变量."""
    sys.path.insert(0, ".")
    from tests.mvps.rinex_parser_mvp import parse_rinex2_first_eph, parse_rinex3_first_eph
    from pathlib import Path

    # =========================================================================
    # 样例 1: data/pt.16c (RINEX 2.11, BDS PRN 1 — GEO)
    # =========================================================================
    filepath1 = Path("data/pt.16c")
    if filepath1.exists():
        with open(filepath1, "r") as f:
            lines1 = f.readlines()
        eph1 = parse_rinex2_first_eph(lines1)
        prn1 = eph1["prn"]
        t_obs1 = eph1["toe"]

        print("=" * 70)
        print(f"BDS Ephemeris -> ECEF Position & Clock Bias (MVP)")
        print(f"File: {filepath1}  (RINEX 2.11, PRN {prn1})")
        print("=" * 70)

        # Print input ephemeris
        _print_eph(eph1, prn1)

        # Compute at Toe
        (X1, Y1, Z1), dts1, mid1 = bds_eph2pos(t_obs1, eph1, prn1)

        _print_intermediates(mid1)
        _print_results(X1, Y1, Z1, dts1, mid1)

        # Cross-check at Toe + 3600
        _print_crosscheck(eph1, prn1, 3600.0)
    else:
        print(f"[跳过] 文件不存在: {filepath1}")

    # =========================================================================
    # 样例 2: data/gths135a.18f (RINEX 3.02, BDS C01 — GEO)
    # =========================================================================
    filepath2 = Path("data/gths135a.18f")
    if filepath2.exists():
        with open(filepath2, "r") as f:
            lines2 = f.readlines()
        eph2 = parse_rinex3_first_eph(lines2)
        prn2 = int(eph2["sv"][1:])  # 'C01' -> 1
        t_obs2 = eph2["toe"]

        print(f"\n{'=' * 70}")
        print(f"BDS Ephemeris -> ECEF Position & Clock Bias (MVP)")
        print(f"File: {filepath2}  (RINEX 3.02, SV {eph2['sv']})")
        print("=" * 70)

        _print_eph(eph2, prn2)

        (X2, Y2, Z2), dts2, mid2 = bds_eph2pos(t_obs2, eph2, prn2)

        _print_intermediates(mid2)
        _print_results(X2, Y2, Z2, dts2, mid2)

        _print_crosscheck(eph2, prn2, 3600.0)
    else:
        print(f"[跳过] 文件不存在: {filepath2}")


def _print_eph(eph: dict, prn: int):
    """打印输入星历参数."""
    epoch = eph["epoch"]
    y, m, d, h, mi, s = epoch
    sat_type = "GEO" if _is_geo(prn) else "MEO/IGSO"

    print(f"\n--- Input Ephemeris (PRN {prn}, {sat_type}) ---")
    print(f"  Epoch (Toc): {y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}:{s:04.1f}")
    print(f"  Toe (sow)  : {eph['toe']:.3f}")
    print(f"  sqrt(A)    : {eph['sqrt_a']:.12e} sqrt(m)")
    print(f"  e          : {eph['e']:.12e}")
    print(f"  M0         : {eph['m0']:.12e} rad")
    print(f"  Delta-n    : {eph['delta_n']:.12e} rad/s")
    print(f"  omega      : {eph['omega']:.12e} rad")
    print(f"  OMEGA0     : {eph['omega0']:.12e} rad")
    print(f"  OMEGA DOT  : {eph['omega_dot']:.12e} rad/s")
    print(f"  i0         : {eph['i0']:.12e} rad")
    print(f"  IDOT       : {eph['idot']:.12e} rad/s")
    print(f"  Cuc        : {eph['cuc']:.12e} rad")
    print(f"  Cus        : {eph['cus']:.12e} rad")
    print(f"  Crc        : {eph['crc']:.12e} m")
    print(f"  Crs        : {eph['crs']:.12e} m")
    print(f"  Cic        : {eph['cic']:.12e} rad")
    print(f"  Cis        : {eph['cis']:.12e} rad")
    print(f"  af0        : {eph['af0']:.12e} s")
    print(f"  af1        : {eph['af1']:.12e} s/s")
    print(f"  af2        : {eph['af2']:.12e} s/s^2")


def _print_intermediates(mid: dict):
    """打印所有中间变量."""
    print(f"\n--- Intermediate Variables (PRN {mid['prn']}, {mid['sat_type']}) ---")
    print(f"  Step 1: tk              : {mid['tk']:.6e} s")
    print(f"  Step 2: A               : {mid['A']:.6f} m")
    print(f"  Step 2: n0              : {mid['n0']:.12e} rad/s")
    print(f"  Step 3: n               : {mid['n']:.12e} rad/s")
    print(f"  Step 4: Mk              : {mid['Mk']:.15e} rad")
    print(f"  Step 5: Ek              : {mid['Ek']:.15e} rad  ({mid['kepler_iters']} iterations)")
    print(f"  Step 5: sin(Ek)         : {mid['sinEk']:.15e}")
    print(f"  Step 5: cos(Ek)         : {mid['cosEk']:.15e}")
    print(f"  Step 6: vk              : {mid['vk']:.15e} rad")
    print(f"  Step 7: uk (before corr): {mid['uk_before_corr']:.15e} rad")
    print(f"  Step 8: sin(2*uk)       : {mid['sin2uk']:.15e}")
    print(f"  Step 8: cos(2*uk)       : {mid['cos2uk']:.15e}")
    print(f"  Step 8: delta_uk        : {mid['delta_uk']:.15e} rad")
    print(f"  Step 8: delta_rk        : {mid['delta_rk']:.15e} m")
    print(f"  Step 8: delta_ik        : {mid['delta_ik']:.15e} rad")
    print(f"  Step 8: uk (corrected)  : {mid['uk']:.15e} rad")
    print(f"  Step 8: rk              : {mid['rk']:.6f} m")
    print(f"  Step 8: ik              : {mid['ik']:.15e} rad")
    print(f"  Step 9: xk_orb          : {mid['xk_orb']:.6f} m")
    print(f"  Step 9: yk_orb          : {mid['yk_orb']:.6f} m")
    print(f"  Step 10: Omegak         : {mid['Omegak']:.15e} rad")
    print(f"  Step 10: sin(Omegak)    : {mid['sinO']:.15e}")
    print(f"  Step 10: cos(Omegak)    : {mid['cosO']:.15e}")
    print(f"  Step 10: cos(ik)        : {mid['cos_ik']:.15e}")

    if mid["sat_type"] == "GEO":
        print(f"  Step 11a: xG            : {mid['xG']:.6f} m")
        print(f"  Step 11a: yG            : {mid['yG']:.6f} m")
        print(f"  Step 11a: zG            : {mid['zG']:.6f} m")
        print(f"  Step 11b: sin(Omega_e*tk): {mid['sino']:.15e}")
        print(f"  Step 11b: cos(Omega_e*tk): {mid['coso']:.15e}")
        print(f"  Step 11b: SIN_5          : {SIN_5:.16f}")
        print(f"  Step 11b: COS_5          : {COS_5:.16f}")


def _print_results(X: float, Y: float, Z: float, dts: float, mid: dict):
    """打印最终结果."""
    print(f"\n--- Final Results (PRN {mid['prn']}, {mid['sat_type']}) ---")
    print(f"  X          : {X:.6f} m")
    print(f"  Y          : {Y:.6f} m")
    print(f"  Z          : {Z:.6f} m")
    print(f"  dts (total): {dts:.15e} s")
    print(f"  dts (poly) : {mid['dts_poly']:.15e} s")
    print(f"  dtr (rel)  : {mid['dtr']:.15e} s")


def _print_crosscheck(eph: dict, prn: int, dt: float):
    """打印 t = Toe + dt 时的交叉验证结果."""
    t_obs = eph["toe"] + dt
    (X, Y, Z), dts, mid = bds_eph2pos(t_obs, eph, prn)

    print(f"\n  {'='*60}")
    print(f"  Cross-check: t_obs = Toe + {dt:.0f} s")
    print(f"  {'='*60}")
    print(f"  tk         : {mid['tk']:.6e} s")
    print(f"  X          : {X:.6f} m")
    print(f"  Y          : {Y:.6f} m")
    print(f"  Z          : {Z:.6f} m")
    print(f"  dts (total): {dts:.15e} s")


if __name__ == "__main__":
    main()
