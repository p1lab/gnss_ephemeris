"""星历解算统一入口.

根据 Ephemeris 子类型自动分派到对应解算函数。
使用注册表模式：新增系统时只需调用 register_eph2pos，无需修改本文件。
"""

from __future__ import annotations

import logging
from typing import Callable

from gnss_ephemeris.rinex.models import Ephemeris, GPSEphemeris, BDSEphemeris
from gnss_ephemeris.ephemeris.gps import gps_eph2pos
from gnss_ephemeris.ephemeris.bds import bds_eph2pos

logger = logging.getLogger(__name__)

# Ephemeris 子类型 → 解算函数
_EPH2POS_REGISTRY: dict[type[Ephemeris], Callable] = {}


def register_eph2pos(
    eph_cls: type[Ephemeris],
    compute_fn: Callable[[float, Ephemeris], tuple],
) -> None:
    """注册星历解算函数.

    Args:
        eph_cls: Ephemeris 子类
        compute_fn: 解算函数，签名为 (t_obs, eph) -> ((X,Y,Z), dts, intermediates)
    """
    if eph_cls in _EPH2POS_REGISTRY:
        logger.warning("覆盖已注册的解算器: %s", eph_cls.__name__)
    _EPH2POS_REGISTRY[eph_cls] = compute_fn


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
    for cls, fn in _EPH2POS_REGISTRY.items():
        if isinstance(eph, cls):
            return fn(t_obs, eph)

    registered = [c.__name__ for c in _EPH2POS_REGISTRY]
    raise TypeError(
        f"不支持的星历类型: {type(eph).__name__}，已注册: {registered}"
    )


# ---------------------------------------------------------------------------
# 自注册：内置解算器
# ---------------------------------------------------------------------------

register_eph2pos(GPSEphemeris, gps_eph2pos)
register_eph2pos(BDSEphemeris, bds_eph2pos)
