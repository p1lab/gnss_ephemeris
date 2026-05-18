"""时间系统工具函数.

周内秒（Seconds of Week）归一化处理。
GPS/BDS 的星历参考时间与观测时间均以周内秒表示，
当差值超过半周（±302400 s）时需归一化到 [-302400, 302400) 范围。
"""

HALF_WEEK = 302400.0   # 半周秒数 (604800 / 2)
FULL_WEEK = 604800.0   # 一周秒数


def normalize_sow(dt: float, half_week: float = HALF_WEEK) -> float:
    """将周内秒差值归一化到 [-half_week, half_week) 范围.

    Args:
        dt: 两个周内秒之差 (s)
        half_week: 半周阈值 (s)，默认 302400.0

    Returns:
        归一化后的时间差 (s)
    """
    if dt > half_week:
        dt -= 2.0 * half_week
    elif dt < -half_week:
        dt += 2.0 * half_week
    return dt
