"""RINEX 导航电文解析器.

支持 RINEX 2.x 和 3.x 广播星历文件的解析，返回对应的
GPSEphemeris / BDSEphemeris dataclass 对象列表。

关键特性：
  - 自动识别 RINEX 版本（2.x / 3.x）
  - 从行尾倒推 D19.12 字段，解决 af0 负号粘连问题
  - 空白 spare 字段返回 0.0
  - 全量解析（非仅第一条）
  - 注册表模式：新增系统/版本时无需修改本文件
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from gnss_ephemeris.rinex.models import Ephemeris, GPSEphemeris, BDSEphemeris
from gnss_ephemeris.utils.fortran import fortran_d_to_float

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 注册表：版本解析器 & 星历构造器
# ---------------------------------------------------------------------------

# 版本前缀 → 解析函数 (lines, **kwargs) -> list[Ephemeris]
_VERSION_PARSERS: dict[str, Callable] = {}

# 系统标识 → (Ephemeris 子类, builder 函数)
# builder 签名: (common: dict, rows: list[list[float]]) -> Ephemeris
_EPH_BUILDERS: dict[str, tuple[type[Ephemeris], Callable]] = {}


def register_version_parser(version_prefix: str, parser_fn: Callable) -> None:
    """注册 RINEX 版本解析器.

    Args:
        version_prefix: 版本前缀，如 "2.", "3.", "4."
        parser_fn: 解析函数，签名为 (lines, **kwargs) -> list[Ephemeris]
    """
    if version_prefix in _VERSION_PARSERS:
        logger.warning("覆盖已注册的版本解析器: %s", version_prefix)
    _VERSION_PARSERS[version_prefix] = parser_fn


def register_eph_builder(
    system: str,
    eph_cls: type[Ephemeris],
    builder: Callable[[dict, list[list[float]]], Ephemeris],
) -> None:
    """注册星历构造器.

    Args:
        system: 卫星系统标识，如 "GPS", "BDS", "Galileo"
        eph_cls: 对应的 Ephemeris 子类
        builder: 构造函数，签名为 (common_fields, rows) -> Ephemeris实例
                 common_fields: 共享字段的 dict
                 rows: [row2, row3, row4, row5, row6, row7, row8]
    """
    if system in _EPH_BUILDERS:
        logger.warning("覆盖已注册的星历构造器: %s", system)
    _EPH_BUILDERS[system] = (eph_cls, builder)


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _find_end_of_header(lines: list[str]) -> int:
    """返回 'END OF HEADER' 所在行的下一行索引."""
    for i, line in enumerate(lines):
        if "END OF HEADER" in line:
            return i + 1
    raise ValueError("未找到 END OF HEADER")


def _parse_clock_line_r2(l1: str) -> tuple[int, tuple, float, float, float]:
    """解析 RINEX 2.x 行1（PRN / EPOCH / SV CLK）.

    格式: I2,1X,I2.2,5(1X,I2),F5.1,3D19.12

    关键问题：部分 RINEX 生成器在 af0 为负数时，F5.1 秒字段的尾部空格
    会被 af0 的负号"吞没"，导致 l1[18:23] 切到 ' 0.0-' 而非 ' 0.0 '.
    解决方案：从行尾倒推 3 个 D19.12 字段（每个 19 字符），秒取剩余部分.
    """
    l1 = l1.rstrip("\n").rstrip("\r")

    prn = int(l1[0:2].strip())
    year_2dig = int(l1[3:5].strip())
    year = 2000 + year_2dig if year_2dig < 80 else 1900 + year_2dig
    month = int(l1[6:8].strip())
    day = int(l1[9:11].strip())
    hour = int(l1[12:14].strip())
    minute = int(l1[15:17].strip())

    # 从行尾倒推 3×D19.12 = 57 字符提取 af0/af1/af2
    af2_str = l1[-19:]
    af1_str = l1[-38:-19]
    af0_str = l1[-57:-38]
    second_str = l1[18:-57].strip()

    second = float(second_str) if second_str else 0.0
    af0 = fortran_d_to_float(af0_str)
    af1 = fortran_d_to_float(af1_str)
    af2 = fortran_d_to_float(af2_str)

    return prn, (year, month, day, hour, minute, second), af0, af1, af2


def _parse_clock_line_r3(l1: str) -> tuple[str, tuple, float, float, float]:
    """解析 RINEX 3.x 行1（SV / EPOCH / SV CLK）.

    格式: A1,I2.2,1X,I4,5(1X,I2.2),3D19.12
    同样采用从行尾倒推 D19.12 的策略以防粘连.
    """
    l1 = l1.rstrip("\n").rstrip("\r")

    sv = l1[0:3].strip()
    year = int(l1[4:8].strip())
    month = int(l1[9:11].strip())
    day = int(l1[12:14].strip())
    hour = int(l1[15:17].strip())
    minute = int(l1[18:20].strip())

    af2_str = l1[-19:]
    af1_str = l1[-38:-19]
    af0_str = l1[-57:-38]
    second_str = l1[21:-57].strip()

    second = int(second_str) if second_str else 0
    af0 = fortran_d_to_float(af0_str)
    af1 = fortran_d_to_float(af1_str)
    af2 = fortran_d_to_float(af2_str)

    return sv, (year, month, day, hour, minute, second), af0, af1, af2


def _slice4_r2(line: str) -> list[float]:
    """从 RINEX 2.x 数据行中提取 4 个 D19.12 字段.

    格式: 3X,4D19.12，字段起始于 index 3, 22, 41, 60.
    """
    line = line.rstrip("\n").rstrip("\r")
    return [
        fortran_d_to_float(line[3:22]),
        fortran_d_to_float(line[22:41]),
        fortran_d_to_float(line[41:60]),
        fortran_d_to_float(line[60:]),
    ]


def _slice4_r3(line: str) -> list[float]:
    """从 RINEX 3.x 数据行中提取 4 个 D19.12 字段.

    格式: 4X,4D19.12，字段起始于 index 4, 23, 42, 61.
    """
    line = line.rstrip("\n").rstrip("\r")
    return [
        fortran_d_to_float(line[4:23]),
        fortran_d_to_float(line[23:42]),
        fortran_d_to_float(line[42:61]),
        fortran_d_to_float(line[61:]),
    ]


def _build_common_fields(
    system: str, prn: int, epoch: tuple,
    af0: float, af1: float, af2: float,
    rows: list[list[float]],
) -> dict:
    """从解析行数据构造共享字段 dict."""
    row2, row3, row4, row5, row6, row7, row8 = rows
    return dict(
        system=system, prn=prn, epoch=epoch,
        af0=af0, af1=af1, af2=af2,
        toe=row4[0],
        sqrt_a=row3[3], e=row3[1], m0=row2[3],
        delta_n=row2[2],
        omega=row5[2], omega0=row4[2], omega_dot=row5[3],
        i0=row5[0], idot=row6[0],
        cuc=row3[0], cus=row3[2],
        crc=row5[1], crs=row2[1],
        cic=row4[1], cis=row4[3],
    )


# ---------------------------------------------------------------------------
# 内置星历构造函数
# ---------------------------------------------------------------------------

def _build_gps_eph(common: dict, rows: list[list[float]]) -> GPSEphemeris:
    """构造 GPSEphemeris 对象."""
    row2, row3, row4, row5, row6, row7, row8 = rows
    return GPSEphemeris(
        **common,
        iode=row2[0], iodc=row7[3], tgd=row7[2],
        gps_week=row6[2], codes_on_l2=row6[1], l2_p_flag=row6[3],
        sv_accuracy=row7[0], sv_health=row7[1],
        trans_time=row8[0], fit_interval=row8[1],
    )


def _build_bds_eph(common: dict, rows: list[list[float]]) -> BDSEphemeris:
    """构造 BDSEphemeris 对象."""
    row2, row3, row4, row5, row6, row7, row8 = rows
    return BDSEphemeris(
        **common,
        aode=row2[0], aodc=row8[1],
        tgd1=row7[2], tgd2=row7[3], sath1=row7[1],
        bdt_week=row6[2], sv_accuracy=row7[0],
        trans_time=row8[0],
    )


# ---------------------------------------------------------------------------
# RINEX 2.x 解析
# ---------------------------------------------------------------------------

def parse_rinex2(lines: list[str], system: str = "GPS") -> list[Ephemeris]:
    """解析 RINEX 2.x 导航电文文件，返回全部星历记录.

    Args:
        lines: 文件全部行
        system: 卫星系统 ("GPS" 或 "BDS")

    Returns:
        GPSEphemeris 或 BDSEphemeris 对象列表

    Raises:
        ValueError: 系统未在注册表中注册
    """
    start = _find_end_of_header(lines)
    results: list[Ephemeris] = []

    i = start
    while i + 7 < len(lines):
        # 检查行1是否为空行（文件末尾可能有空行）
        if not lines[i].strip():
            i += 1
            continue

        # 解析行1
        prn, epoch, af0, af1, af2 = _parse_clock_line_r2(lines[i])

        # 解析行2~8
        rows = [_slice4_r2(lines[i + k]) for k in range(1, 8)]

        # 查表构造星历对象
        if system not in _EPH_BUILDERS:
            raise ValueError(
                f"RINEX 2.x 不支持系统: {system}，"
                f"已注册: {list(_EPH_BUILDERS.keys())}"
            )

        common = _build_common_fields(system, prn, epoch, af0, af1, af2, rows)
        _cls, builder = _EPH_BUILDERS[system]
        eph = builder(common, rows)

        results.append(eph)
        i += 8

    return results


# ---------------------------------------------------------------------------
# RINEX 3.x 解析
# ---------------------------------------------------------------------------

# RINEX 3.x 卫星系统字母标识
_RINEX3_SYSTEM_MAP = {
    "G": "GPS",
    "C": "BDS",
    "E": "Galileo",
    "R": "GLONASS",
    "J": "QZSS",
}


def parse_rinex3(lines: list[str]) -> list[Ephemeris]:
    """解析 RINEX 3.x 导航电文文件，返回全部星历记录.

    自动根据 SV 标识（如 G02, C01）识别卫星系统。
    未在注册表中注册的系统将被跳过。

    Args:
        lines: 文件全部行

    Returns:
        GPSEphemeris 或 BDSEphemeris 对象列表
    """
    start = _find_end_of_header(lines)
    results: list[Ephemeris] = []

    i = start
    while i + 7 < len(lines):
        if not lines[i].strip():
            i += 1
            continue

        # 解析行1
        sv, epoch, af0, af1, af2 = _parse_clock_line_r3(lines[i])

        # 识别卫星系统
        sys_char = sv[0] if sv else "G"
        system = _RINEX3_SYSTEM_MAP.get(sys_char, "Unknown")
        prn = int(sv[1:]) if sv else 0

        # 解析行2~8
        rows = [_slice4_r3(lines[i + k]) for k in range(1, 8)]

        # 查表构造星历对象（未注册的系统跳过）
        if system not in _EPH_BUILDERS:
            i += 8
            continue

        common = _build_common_fields(system, prn, epoch, af0, af1, af2, rows)
        _cls, builder = _EPH_BUILDERS[system]
        eph = builder(common, rows)

        results.append(eph)
        i += 8

    return results


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def parse_nav_file(path: str | Path) -> list[Ephemeris]:
    """解析 RINEX 导航电文文件，自动识别版本与卫星系统.

    Args:
        path: RINEX 导航电文文件路径

    Returns:
        GPSEphemeris / BDSEphemeris 对象列表

    Raises:
        ValueError: 不支持的 RINEX 版本
    """
    path = Path(path)
    with open(path, "r") as f:
        lines = f.readlines()

    # 自动识别版本
    version_str = lines[0][0:9].strip()

    for prefix, parser_fn in _VERSION_PARSERS.items():
        if version_str.startswith(prefix):
            # RINEX 2.x 需要额外 system 参数
            if prefix.startswith("2."):
                system = _infer_system_from_path(path)
                return parser_fn(lines, system=system)
            return parser_fn(lines)

    raise ValueError(
        f"不支持的 RINEX 版本: {version_str}，"
        f"已注册: {list(_VERSION_PARSERS.keys())}"
    )


def _infer_system_from_path(path: Path) -> str:
    """从文件扩展名推断卫星系统.

    约定：
      - .c, .nnnc → BDS（如 .16c）
      - 其他（.n, .20n, .gnn 等）→ GPS
    """
    suffix = path.suffix.lower()
    # RINEX 2.x BDS 文件扩展名以 c 结尾（如 .16c）
    if suffix.endswith("c") and len(suffix) > 1:
        return "BDS"
    # 默认 GPS（.n, .20n 等）
    return "GPS"


# ---------------------------------------------------------------------------
# 自注册：内置版本解析器与星历构造器
# ---------------------------------------------------------------------------

register_version_parser("2.", parse_rinex2)
register_version_parser("3.", parse_rinex3)

register_eph_builder("GPS", GPSEphemeris, _build_gps_eph)
register_eph_builder("BDS", BDSEphemeris, _build_bds_eph)
