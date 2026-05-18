#!/usr/bin/env python3
"""MVP: GPS broadcast ephemeris -> satellite ECEF position & clock bias.

Algorithm source: IS-GPS-200N, Table 20-IV (position) & Section 20.3.3.3.3.1 (clock).
Engineering reference: RTKLib src/ephemeris.c eph2pos().

Strategy: ICD primary, RTKLib supplementary (iteration initial value, convergence criteria, etc.)
"""

from __future__ import annotations
from math import sqrt, sin, cos, atan2
import sys

# ---------------------------------------------------------------------------
# Constants (IS-GPS-200N Section 30.3.3 / RTKLib rtklib.h)
# ---------------------------------------------------------------------------
MU_GPS = 3.9860050e14       # WGS84 gravitational constant (m^3/s^2)
OMGE = 7.2921151467e-5      # WGS84 earth rotation rate (rad/s)
CLIGHT = 299792458.0        # speed of light (m/s)

# Kepler equation solver parameters (aligned with RTKLib)
RTOL_KEPLER = 1e-14         # convergence tolerance
MAX_ITER_KEPLER = 30        # max iterations


def gps_eph2pos(t_obs: float, eph: dict) -> tuple[tuple[float, float, float], float, dict]:
    """GPS broadcast ephemeris -> ECEF position & clock bias.

    Args:
        t_obs: observation epoch (GPS seconds of week)
        eph: dict of ephemeris parameters from rinex_parser_mvp

    Returns:
        ((X, Y, Z), dts, intermediates)
        - X, Y, Z: satellite ECEF coordinates (m)
        - dts: satellite clock bias including relativity correction (s)
        - intermediates: dict of all intermediate variables for debugging
    """
    # Extract ephemeris parameters
    sqrt_a = eph["sqrt_a"]          # sqrt(A) (sqrt(m))
    e = eph["e"]                    # eccentricity
    m0 = eph["m0"]                  # mean anomaly at Toe (rad)
    delta_n = eph["delta_n"]        # mean motion correction (rad/s)
    toe = eph["toe"]                # ephemeris reference time (sow)
    toc = eph["toe"]                # for GPS: Toe == Toc in same record (sow)
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

    mu = MU_GPS
    omge = OMGE

    # Step 1: Time from ephemeris reference epoch
    # IS-GPS-200N Table 20-IV
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
    # Initial value: Ek = Mk (same as RTKLib)
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

    # Step 10: Corrected longitude of ascending node
    # Omegak = Omega0 + (Omega_dot - omge) * tk - omge * toe
    Omegak = omega0 + (omega_dot - omge) * tk - omge * toe

    # Step 11: ECEF coordinates
    sinO = sin(Omegak)
    cosO = cos(Omegak)
    cos_ik = cos(ik)

    X = xk_orb * cosO - yk_orb * cos_ik * sinO
    Y = xk_orb * sinO + yk_orb * cos_ik * cosO
    Z = yk_orb * sin(ik)

    # --- Clock bias calculation ---
    # IS-GPS-200N Section 20.3.3.3.3.1

    # Time from clock reference epoch
    t_toc = t_obs - toc
    if t_toc > 302400.0:
        t_toc -= 604800.0
    elif t_toc < -302400.0:
        t_toc += 604800.0

    # Polynomial clock correction
    dts = af0 + af1 * t_toc + af2 * t_toc * t_toc

    # Relativity correction
    # dtr = -2 * sqrt(mu * A) * e * sin(Ek) / c^2
    dtr = -2.0 * sqrt(mu * A) * e * sinEk / (CLIGHT * CLIGHT)

    # Total clock bias (same as RTKLib eph2pos)
    dts += dtr

    # Collect intermediates for debugging
    intermediates = {
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
        "t_toc": t_toc,
        "dts_poly": af0 + af1 * t_toc + af2 * t_toc * t_toc,
        "dtr": dtr,
        "dts": dts,
        "kepler_iters": iteration_count + 1,
    }

    return (X, Y, Z), dts, intermediates


def main():
    """MVP entry: parse GPS ephemeris, compute position & clock at Toe, print all intermediates."""
    # Import Phase 1 parser
    sys.path.insert(0, ".")
    from tests.mvps.rinex_parser_mvp import parse_rinex2_first_eph
    from pathlib import Path

    # Parse GPS ephemeris from RINEX 2.10 file
    filepath = Path("data/000A0070.20n")
    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r") as f:
        lines = f.readlines()

    eph = parse_rinex2_first_eph(lines)

    # Use Toe as observation epoch (tk = 0, easiest to verify)
    t_obs = eph["toe"]

    print("=" * 70)
    print("GPS Ephemeris -> ECEF Position & Clock Bias (MVP)")
    print("=" * 70)

    # Print input ephemeris
    print(f"\n--- Input Ephemeris (PRN {eph['prn']}) ---")
    print(f"  Epoch (Toc): {eph['epoch']}")
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

    # Compute
    (X, Y, Z), dts, mid = gps_eph2pos(t_obs, eph)

    # Print all intermediate variables
    print(f"\n--- Intermediate Variables ---")
    print(f"  Observation epoch t_obs : {t_obs:.3f} sow")
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

    # Print final results
    print(f"\n--- Final Results ---")
    print(f"  X          : {X:.6f} m")
    print(f"  Y          : {Y:.6f} m")
    print(f"  Z          : {Z:.6f} m")
    print(f"  dts (total): {dts:.15e} s")
    print(f"  dts (poly) : {mid['dts_poly']:.15e} s")
    print(f"  dtr (rel)  : {mid['dtr']:.15e} s")

    # Also compute at t_obs = Toe + 3600 (1 hour later) for cross-check
    print(f"\n{'='*70}")
    print("Cross-check: t_obs = Toe + 3600 (1 hour later)")
    print(f"{'='*70}")
    t_obs2 = eph["toe"] + 3600.0
    (X2, Y2, Z2), dts2, mid2 = gps_eph2pos(t_obs2, eph)
    print(f"  tk         : {mid2['tk']:.6e} s")
    print(f"  X          : {X2:.6f} m")
    print(f"  Y          : {Y2:.6f} m")
    print(f"  Z          : {Z2:.6f} m")
    print(f"  dts (total): {dts2:.15e} s")


if __name__ == "__main__":
    main()
