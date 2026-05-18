"""命令行入口：GNSS 广播星历解析与卫星位置/钟差解算.

用法:
    gnss-eph parse <file>              解析 RINEX 文件，输出所有星历参数
    gnss-eph compute <file> [options]  计算指定卫星在指定历元的 ECEF 位置与钟差
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gnss_ephemeris.rinex.parser import parse_nav_file
from gnss_ephemeris.rinex.models import GPSEphemeris, BDSEphemeris
from gnss_ephemeris.ephemeris import eph2pos


def cmd_parse(args: argparse.Namespace) -> None:
    """解析 RINEX 文件，输出所有星历参数."""
    try:
        eph_list = parse_nav_file(args.file)
    except Exception as e:
        print(f"[ERROR] 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    output = []
    for eph in eph_list:
        import dataclasses
        d = {}
        for f in dataclasses.fields(eph):
            v = getattr(eph, f.name)
            if isinstance(v, tuple):
                v = list(v)
            d[f.name] = v
        output.append(d)

    _output_result(output, args.format)


def cmd_compute(args: argparse.Namespace) -> None:
    """计算指定卫星在指定历元的 ECEF 位置与钟差."""
    try:
        eph_list = parse_nav_file(args.file)
    except Exception as e:
        print(f"[ERROR] 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 筛选卫星
    target_system = args.system.upper() if args.system else None
    target_prn = args.prn

    candidates = []
    for eph in eph_list:
        if target_system and eph.system != target_system:
            continue
        if target_prn is not None and eph.prn != target_prn:
            continue
        candidates.append(eph)

    if not candidates:
        print("[ERROR] 未找到匹配的卫星", file=sys.stderr)
        sys.exit(1)

    # 确定观测历元
    if args.epoch:
        # 解析 ISO 格式历元
        t_obs = _parse_epoch(args.epoch, candidates[0])
    else:
        # 默认使用第一条星历的 Toe
        t_obs = candidates[0].toe

    # 计算所有候选卫星
    results = []
    for eph in candidates:
        (X, Y, Z), dts, mid = eph2pos(t_obs, eph)
        entry = {
            "system": eph.system,
            "prn": eph.prn,
            "t_obs": t_obs,
            "X": X,
            "Y": Y,
            "Z": Z,
            "dts": dts,
        }
        if args.verbose:
            entry["intermediates"] = {k: v for k, v in mid.items()}
        results.append(entry)

    _output_result(results, args.format)


def _parse_epoch(epoch_str: str, eph: GPSEphemeris | BDSEphemeris) -> float:
    """解析 ISO 格式历元字符串为 seconds of week.

    简化实现：仅支持 --epoch sow 数值（周内秒）。
    """
    try:
        return float(epoch_str)
    except ValueError:
        pass

    # 尝试解析 ISO 格式
    # TODO: 完整的日期时间 → sow 转换
    print(f"[ERROR] 暂不支持 ISO 历元格式，请使用周内秒数值", file=sys.stderr)
    sys.exit(1)


def _output_result(data: list | dict, fmt: str) -> None:
    """输出结果."""
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    elif fmt == "csv":
        if not data:
            return
        if isinstance(data, dict):
            data = [data]
        # 简单 CSV 输出（展平嵌套 dict）
        keys = list(data[0].keys())
        print(",".join(keys))
        for row in data:
            vals = []
            for k in keys:
                v = row.get(k, "")
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, default=str)
                vals.append(str(v))
            print(",".join(vals))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def main() -> None:
    """CLI 主函数."""
    parser = argparse.ArgumentParser(
        prog="gnss-eph",
        description="GNSS 广播星历解析与卫星位置/钟差解算",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # parse 子命令
    parse_cmd = subparsers.add_parser("parse", help="解析 RINEX 文件")
    parse_cmd.add_argument("file", type=str, help="RINEX 导航电文文件路径")
    parse_cmd.add_argument("--format", choices=["json", "csv"], default="json",
                           help="输出格式 (默认 json)")
    parse_cmd.set_defaults(func=cmd_parse)

    # compute 子命令
    compute_cmd = subparsers.add_parser("compute", help="计算卫星位置与钟差")
    compute_cmd.add_argument("file", type=str, help="RINEX 导航电文文件路径")
    compute_cmd.add_argument("--system", type=str, default=None,
                             help="卫星系统 (GPS/BDS)")
    compute_cmd.add_argument("--prn", type=int, default=None,
                             help="卫星 PRN 号")
    compute_cmd.add_argument("--epoch", type=str, default=None,
                             help="观测历元 (周内秒数值)")
    compute_cmd.add_argument("--verbose", action="store_true",
                             help="输出中间变量")
    compute_cmd.add_argument("--format", choices=["json", "csv"], default="json",
                             help="输出格式 (默认 json)")
    compute_cmd.set_defaults(func=cmd_compute)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
