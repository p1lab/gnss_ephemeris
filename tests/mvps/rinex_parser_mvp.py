#!/usr/bin/env python3
"""MVP：RINEX 导航电文解析验证.

目标：
    1. 读取 data/ 下的三个样例文件；
    2. 自动识别 RINEX 2.x / 3.x；
    3. 跳过 Header，提取第一条星历的 8 行数据；
    4. 按官方规范定义的固定列位置切片，逐字段解析；
    5. 将 Fortran D 格式转为 Python float，打印输出供人工核对.

通过标准：
    - 解析出的各参数值与手动按规范读取的数值一致；
    - 能区分 2.x（PRN 为纯数字）与 3.x（SV 为系统字母+PRN）的格式差异.
"""

from __future__ import annotations
from pathlib import Path


def fortran_d_to_float(s: str) -> float:
    """将 Fortran D 格式字符串转为 Python float.

    RINEX 规范允许 E/e/D/d 作为指数分隔符，如::

        -3.809658810496D-04  ->  -3.809658810496e-04
        0.123456789012D+03   ->   0.123456789012e+03

    空白字段（spare）返回 0.0.
    """
    s = s.strip()
    if not s:
        return 0.0
    return float(s.replace("D", "E").replace("d", "e"))


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
    # 先去除行尾换行符，否则从右倒推时偏移量错误
    l1 = l1.rstrip("\n").rstrip("\r")

    prn = int(l1[0:2].strip())
    year_2dig = int(l1[3:5].strip())
    # 2 位年份转换：00-79 -> 2000-2079, 80-99 -> 1980-1999
    year = 2000 + year_2dig if year_2dig < 80 else 1900 + year_2dig
    month = int(l1[6:8].strip())
    day = int(l1[9:11].strip())
    hour = int(l1[12:14].strip())
    minute = int(l1[15:17].strip())

    # 从行尾倒推 3×D19.12 = 57 字符提取 af0/af1/af2
    # 这避免了秒字段与 af0 负号粘连导致的切片错位
    af2_str = l1[-19:]
    af1_str = l1[-38:-19]
    af0_str = l1[-57:-38]
    # 秒字段：从 index 18 到 af0 起始位置（l1[:-57] 的尾部）
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
    # 先去除行尾换行符
    l1 = l1.rstrip("\n").rstrip("\r")

    sv = l1[0:3].strip()          # 如 C01, G02
    year = int(l1[4:8].strip())
    month = int(l1[9:11].strip())
    day = int(l1[12:14].strip())
    hour = int(l1[15:17].strip())
    minute = int(l1[18:20].strip())

    # 从行尾倒推 3×D19.12
    af2_str = l1[-19:]
    af1_str = l1[-38:-19]
    af0_str = l1[-57:-38]
    # 秒字段：RINEX 3.x 秒为 I2.2（2位整数），位于 index 21-22
    second_str = l1[21:-57].strip()

    second = int(second_str) if second_str else 0
    af0 = fortran_d_to_float(af0_str)
    af1 = fortran_d_to_float(af1_str)
    af2 = fortran_d_to_float(af2_str)

    return sv, (year, month, day, hour, minute, second), af0, af1, af2


def parse_rinex2_first_eph(lines: list[str]) -> dict:
    """解析 RINEX 2.x 第一条星历.

    数据记录共 8 行，每行长度约 79 字符（末行可能截断）.
    行2~8 字段按固定列位置切片提取（3X + 4D19.12），行1 采用从右倒推策略.
    """
    start = _find_end_of_header(lines)
    eph = lines[start : start + 8]
    if len(eph) < 8:
        raise ValueError("星历记录不足 8 行")

    # ---------- 第 1 行：PRN / EPOCH / SV CLK ----------
    prn, epoch, af0, af1, af2 = _parse_clock_line_r2(eph[0])

    # ---------- 第 2~8 行：BROADCAST ORBIT ----------
    # 2.x 行 2~8 的格式为 3X,4D19.12
    # 字段起始于 index 3, 22, 41, 60（0-based）.
    def _slice4(line: str):
        """从一行中提取 4 个 D19.12 字段，最后一个取到行尾."""
        line = line.rstrip("\n").rstrip("\r")
        return [
            fortran_d_to_float(line[3:22]),
            fortran_d_to_float(line[22:41]),
            fortran_d_to_float(line[41:60]),
            fortran_d_to_float(line[60:]),
        ]

    iode, crs, delta_n, m0 = _slice4(eph[1])
    cuc, e, cus, sqrt_a = _slice4(eph[2])
    toe, cic, omega0, cis = _slice4(eph[3])
    i0, crc, omega, omega_dot = _slice4(eph[4])
    idot, codes_on_l2, gps_week, l2_p_flag = _slice4(eph[5])
    sv_accuracy, sv_health, tgd, iodc = _slice4(eph[6])
    trans_time, fit_interval, spare1, spare2 = _slice4(eph[7])

    return {
        "prn": prn,
        "epoch": epoch,
        "af0": af0,
        "af1": af1,
        "af2": af2,
        "iode": iode,
        "crs": crs,
        "delta_n": delta_n,
        "m0": m0,
        "cuc": cuc,
        "e": e,
        "cus": cus,
        "sqrt_a": sqrt_a,
        "toe": toe,
        "cic": cic,
        "omega0": omega0,
        "cis": cis,
        "i0": i0,
        "crc": crc,
        "omega": omega,
        "omega_dot": omega_dot,
        "idot": idot,
        "codes_on_l2": codes_on_l2,
        "gps_week": gps_week,
        "l2_p_flag": l2_p_flag,
        "sv_accuracy": sv_accuracy,
        "sv_health": sv_health,
        "tgd": tgd,
        "iodc": iodc,
        "trans_time": trans_time,
        "fit_interval": fit_interval,
    }


def parse_rinex3_first_eph(lines: list[str]) -> dict:
    """解析 RINEX 3.x 第一条星历.

    数据记录共 8 行，每行长度约 80 字符（末行或中间行可能截断）.
    与 2.x 的核心差异：
      - SV 标识为系统字母+2 位 PRN（如 G02, C01）；
      - 年份为 4 位；秒为 I2.2（2 位整数）；
      - 行 2~8 前导空白为 4X，字段起始于 index 4.
    """
    start = _find_end_of_header(lines)
    eph = lines[start : start + 8]
    if len(eph) < 8:
        raise ValueError("星历记录不足 8 行")

    # ---------- 第 1 行：SV / EPOCH / SV CLK ----------
    sv, epoch, af0, af1, af2 = _parse_clock_line_r3(eph[0])

    # ---------- 第 2~8 行：BROADCAST ORBIT ----------
    # 3.x 行 2~8 的格式为 4X,4D19.12，字段起始于 index 4.
    def _slice4(line: str):
        """从一行中提取 4 个 D19.12 字段，最后一个取到行尾."""
        line = line.rstrip("\n").rstrip("\r")
        return [
            fortran_d_to_float(line[4:23]),
            fortran_d_to_float(line[23:42]),
            fortran_d_to_float(line[42:61]),
            fortran_d_to_float(line[61:]),
        ]

    aode, crs, delta_n, m0 = _slice4(eph[1])
    cuc, e, cus, sqrt_a = _slice4(eph[2])
    toe, cic, omega0, cis = _slice4(eph[3])
    i0, crc, omega, omega_dot = _slice4(eph[4])
    idot, spare1, bdt_week, spare2 = _slice4(eph[5])
    sv_accuracy, sath1, tgd1, tgd2 = _slice4(eph[6])
    trans_time, aodc, spare3, spare4 = _slice4(eph[7])

    return {
        "sv": sv,
        "epoch": epoch,
        "af0": af0,
        "af1": af1,
        "af2": af2,
        "aode": aode,
        "crs": crs,
        "delta_n": delta_n,
        "m0": m0,
        "cuc": cuc,
        "e": e,
        "cus": cus,
        "sqrt_a": sqrt_a,
        "toe": toe,
        "cic": cic,
        "omega0": omega0,
        "cis": cis,
        "i0": i0,
        "crc": crc,
        "omega": omega,
        "omega_dot": omega_dot,
        "idot": idot,
        "bdt_week": bdt_week,
        "sv_accuracy": sv_accuracy,
        "sath1": sath1,
        "tgd1": tgd1,
        "tgd2": tgd2,
        "trans_time": trans_time,
        "aodc": aodc,
    }


def print_rinex2_eph(result: dict, filename: str, system: str):
    """以可读格式打印 RINEX 2.x 星历解析结果."""
    y, m, d, h, mi, s = result["epoch"]
    print(f"\n{'='*60}")
    print(f"文件: {filename}  (RINEX 2.x, {system})")
    print(f"{'='*60}")
    print(f"{'PRN':<20s}: {result['prn']}")
    print(f"{'历元 (Toc)':<20s}: {y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}:{s:04.1f}")
    print(f"{'af0 (s)':<20s}: {result['af0']:.12e}")
    print(f"{'af1 (s/s)':<20s}: {result['af1']:.12e}")
    print(f"{'af2 (s/s^2)':<20s}: {result['af2']:.12e}")
    print("-" * 40)
    print(f"{'IODE':<20s}: {result['iode']:.12e}")
    print(f"{'Crs (m)':<20s}: {result['crs']:.12e}")
    print(f"{'Delta-n (rad/s)':<20s}: {result['delta_n']:.12e}")
    print(f"{'M0 (rad)':<20s}: {result['m0']:.12e}")
    print(f"{'Cuc (rad)':<20s}: {result['cuc']:.12e}")
    print(f"{'e (Eccentricity)':<20s}: {result['e']:.12e}")
    print(f"{'Cus (rad)':<20s}: {result['cus']:.12e}")
    print(f"{'sqrt(A) (sqrt(m))':<20s}: {result['sqrt_a']:.12e}")
    print(f"{'Toe (s of week)':<20s}: {result['toe']:.12e}")
    print(f"{'Cic (rad)':<20s}: {result['cic']:.12e}")
    print(f"{'OMEGA0 (rad)':<20s}: {result['omega0']:.12e}")
    print(f"{'Cis (rad)':<20s}: {result['cis']:.12e}")
    print(f"{'i0 (rad)':<20s}: {result['i0']:.12e}")
    print(f"{'Crc (m)':<20s}: {result['crc']:.12e}")
    print(f"{'omega (rad)':<20s}: {result['omega']:.12e}")
    print(f"{'OMEGA DOT (rad/s)':<20s}: {result['omega_dot']:.12e}")
    print(f"{'IDOT (rad/s)':<20s}: {result['idot']:.12e}")
    print(f"{'Codes on L2':<20s}: {result['codes_on_l2']:.12e}")
    print(f"{'GPS/BDS Week #':<20s}: {result['gps_week']:.12e}")
    print(f"{'L2 P data flag':<20s}: {result['l2_p_flag']:.12e}")
    print(f"{'SV accuracy (m)':<20s}: {result['sv_accuracy']:.12e}")
    print(f"{'SV health':<20s}: {result['sv_health']:.12e}")
    print(f"{'TGD (s)':<20s}: {result['tgd']:.12e}")
    print(f"{'IODC':<20s}: {result['iodc']:.12e}")
    print(f"{'Transmission time':<20s}: {result['trans_time']:.12e}")
    print(f"{'Fit interval (h)':<20s}: {result['fit_interval']:.12e}")


def print_rinex3_eph(result: dict, filename: str, system: str):
    """以可读格式打印 RINEX 3.x 星历解析结果."""
    y, m, d, h, mi, s = result["epoch"]
    print(f"\n{'='*60}")
    print(f"文件: {filename}  (RINEX 3.x, {system})")
    print(f"{'='*60}")
    print(f"{'SV':<20s}: {result['sv']}")
    print(f"{'历元 (Toc)':<20s}: {y:04d}-{m:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}")
    print(f"{'af0 (s)':<20s}: {result['af0']:.12e}")
    print(f"{'af1 (s/s)':<20s}: {result['af1']:.12e}")
    print(f"{'af2 (s/s^2)':<20s}: {result['af2']:.12e}")
    print("-" * 40)
    print(f"{'AODE':<20s}: {result['aode']:.12e}")
    print(f"{'Crs (m)':<20s}: {result['crs']:.12e}")
    print(f"{'Delta-n (rad/s)':<20s}: {result['delta_n']:.12e}")
    print(f"{'M0 (rad)':<20s}: {result['m0']:.12e}")
    print(f"{'Cuc (rad)':<20s}: {result['cuc']:.12e}")
    print(f"{'e (Eccentricity)':<20s}: {result['e']:.12e}")
    print(f"{'Cus (rad)':<20s}: {result['cus']:.12e}")
    print(f"{'sqrt(A) (sqrt(m))':<20s}: {result['sqrt_a']:.12e}")
    print(f"{'Toe (s of week)':<20s}: {result['toe']:.12e}")
    print(f"{'Cic (rad)':<20s}: {result['cic']:.12e}")
    print(f"{'OMEGA0 (rad)':<20s}: {result['omega0']:.12e}")
    print(f"{'Cis (rad)':<20s}: {result['cis']:.12e}")
    print(f"{'i0 (rad)':<20s}: {result['i0']:.12e}")
    print(f"{'Crc (m)':<20s}: {result['crc']:.12e}")
    print(f"{'omega (rad)':<20s}: {result['omega']:.12e}")
    print(f"{'OMEGA DOT (rad/s)':<20s}: {result['omega_dot']:.12e}")
    print(f"{'IDOT (rad/s)':<20s}: {result['idot']:.12e}")
    print(f"{'BDT Week #':<20s}: {result['bdt_week']:.12e}")
    print(f"{'SV accuracy (m)':<20s}: {result['sv_accuracy']:.12e}")
    print(f"{'SatH1':<20s}: {result['sath1']:.12e}")
    print(f"{'TGD1 B1/B3 (s)':<20s}: {result['tgd1']:.12e}")
    print(f"{'TGD2 B2/B3 (s)':<20s}: {result['tgd2']:.12e}")
    print(f"{'Transmission time':<20s}: {result['trans_time']:.12e}")
    print(f"{'AODC':<20s}: {result['aodc']:.12e}")


def main():
    """MVP 入口：遍历三个样例文件并打印第一条星历."""
    files = [
        ("../../data/000A0070.20n", "GPS"),
        ("../../data/pt.16c", "BDS"),
        ("../../data/gths135a.18f", "BDS"),
    ]

    for filepath, system in files:
        path = Path(filepath)
        if not path.exists():
            print(f"[跳过] 文件不存在: {filepath}")
            continue

        with open(path, "r") as f:
            lines = f.readlines()

        # 自动识别版本
        version_line = lines[0]
        version_str = version_line[0:9].strip()

        if version_str.startswith("2."):
            result = parse_rinex2_first_eph(lines)
            print_rinex2_eph(result, filepath, system)
        elif version_str.startswith("3."):
            result = parse_rinex3_first_eph(lines)
            print_rinex3_eph(result, filepath, system)
        else:
            raise ValueError(f"不支持的 RINEX 版本: {version_str}")


if __name__ == "__main__":
    main()
