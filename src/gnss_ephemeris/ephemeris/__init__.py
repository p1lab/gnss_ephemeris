"""星历解算统一入口.

根据 Ephemeris 子类型自动分派到 GPS/BDS 解算函数。
"""

from __future__ import annotations

from gnss_ephemeris.rinex.models import Ephemeris, GPSEphemeris, BDSEphemeris
from gnss_ephemeris.ephemeris.gps import gps_eph2pos
from gnss_ephemeris.ephemeris.bds import bds_eph2pos


def eph2pos(
    t_obs: float,
    eph: Ephemeris,
) -> tuple[tuple[float, float, float], float, dict]:
    """广播星历 → ECEF 位置与钟差（自动分派）.

    Args:
        t_obs: 观测历元 (seconds of week)
        eph: 星历参数（GPSEphemeris 或 BDSEphemeris）

    Returns:
        ((X, Y, Z), dts, intermediates)
        - X, Y, Z: 卫星 ECEF 坐标 (m)
        - dts: 卫星钟差（含相对论校正）(s)
        - intermediates: 中间变量字典

    Raises:
        TypeError: 不支持的星历类型
    """
    if isinstance(eph, GPSEphemeris):
        return gps_eph2pos(t_obs, eph)
    elif isinstance(eph, BDSEphemeris):
        return bds_eph2pos(t_obs, eph)
    raise TypeError(f"不支持的星历类型: {type(eph).__name__}")
