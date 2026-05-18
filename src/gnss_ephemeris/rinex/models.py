"""广播星历数据契约层.

定义 `Ephemeris` 基类及其子类，作为 RINEX 解析模块（生产者）与
星历解算模块（消费者）之间的显式接口契约。

两个模块的共同依赖关系：
    rinex/parser  ──产出──►  Ephemeris 子类  ──消费──►  ephemeris/gps, bds
                                         ▲
                                    rinex/models.py
                                    （契约层，独立于 parser）

字段命名遵循各系统 ICD 与 RINEX 规范的符号名。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ephemeris:
    """广播星历基类：GPS/BDS/Galileo 共享的开普勒根数字段.

    所有子类共享的字段按 ICD/RINEX 规范命名。
    """

    # ---- 卫星标识 ----
    system: str          # 卫星系统标识: "GPS" / "BDS" / ...
    prn: int             # 卫星 PRN 号
    epoch: tuple         # 钟差参考历元 (year, month, day, hour, minute, second)

    # ---- 钟差多项式系数 ----
    af0: float           # 钟偏差 (s)
    af1: float           # 钟漂移 (s/s)
    af2: float           # 钟漂移率 (s/s^2)

    # ---- 开普勒轨道根数 ----
    toe: float           # 星历参考时间 (sow)
    sqrt_a: float        # 轨道半长轴平方根 (sqrt(m))
    e: float             # 轨道偏心率
    m0: float            # 参考时刻平近点角 (rad)
    delta_n: float       # 平运动校正 (rad/s)

    # ---- 轨道面摄动 ----
    omega: float         # 近地点幅角 (rad)
    omega0: float        # 升交点赤经 (rad)
    omega_dot: float     # 升交点赤经变率 (rad/s)
    i0: float            # 参考时刻轨道倾角 (rad)
    idot: float          # 轨道倾角变率 (rad/s)

    # ---- 谐波摄动 ----
    cuc: float           # 纬度幅角余弦摄动 (rad)
    cus: float           # 纬度幅角正弦摄动 (rad)
    crc: float           # 轨道半径余弦摄动 (m)
    crs: float           # 轨道半径正弦摄动 (m)
    cic: float           # 轨道倾角余弦摄动 (rad)
    cis: float           # 轨道倾角正弦摄动 (rad)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(system={self.system!r}, prn={self.prn}, "
            f"epoch={self.epoch}, toe={self.toe:.3f})"
        )


@dataclass
class GPSEphemeris(Ephemeris):
    """GPS 广播星历专有字段.

    字段来源：IS-GPS-200N / RINEX 2.x & 3.x GPS 导航电文。
    """

    iode: float           # 星历数据龄期
    iodc: float           # 时钟数据龄期
    tgd: float            # 群延迟校正 (s)
    gps_week: float       # GPS 周
    codes_on_l2: float    # L2 码标志
    l2_p_flag: float      # L2 P 数据标志
    sv_accuracy: float    # 卫星精度 (m)
    sv_health: float      # 卫星健康状态
    trans_time: float     # 传输时间 (sow)
    fit_interval: float   # 拟合区间 (h)


@dataclass
class BDSEphemeris(Ephemeris):
    """BDS 广播星历专有字段.

    字段来源：北斗 B1I ICD v3.0 / RINEX 2.x & 3.x BDS 导航电文。
    """

    aode: float           # 星历数据龄期
    aodc: float           # 时钟数据龄期
    tgd1: float           # B1/B3 群延迟校正 (s)
    tgd2: float           # B2/B3 群延迟校正 (s)
    sath1: float          # 卫星健康状态
    bdt_week: float       # BDT 周
    sv_accuracy: float    # 卫星精度 (m)
    trans_time: float     # 传输时间 (sow)
