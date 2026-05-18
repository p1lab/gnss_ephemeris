"""Fortran 格式数值转换工具.

RINEX 规范允许 E/e/D/d 作为指数分隔符，如：
    -3.809658810496D-04  ->  -3.809658810496e-04
     0.123456789012D+03  ->   0.123456789012e+03
"""


def fortran_d_to_float(s: str) -> float:
    """将 Fortran D 格式字符串转为 Python float.

    Args:
        s: RINEX 字段字符串，可能含 D/d/E/e 指数分隔符。

    Returns:
        对应的浮点数。空白字段（spare）返回 0.0。
    """
    s = s.strip()
    if not s:
        return 0.0
    return float(s.replace("D", "E").replace("d", "e"))
