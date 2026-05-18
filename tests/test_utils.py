"""公共工具模块单元测试."""

import math
import pytest

from gnss_ephemeris.utils.constants import CLIGHT, RTOL_KEPLER, MAX_ITER_KEPLER
from gnss_ephemeris.utils.fortran import fortran_d_to_float
from gnss_ephemeris.utils.kepler import solve_kepler
from gnss_ephemeris.utils.time import normalize_sow, HALF_WEEK, FULL_WEEK


# ===========================================================================
# fortran_d_to_float
# ===========================================================================

class TestFortranDToFloat:
    """Fortran D 格式转换测试."""

    def test_uppercase_d(self):
        assert fortran_d_to_float("-3.809658810496D-04") == pytest.approx(-3.809658810496e-04)

    def test_lowercase_d(self):
        assert fortran_d_to_float("0.123456789012d+03") == pytest.approx(0.123456789012e+03)

    def test_uppercase_e(self):
        assert fortran_d_to_float("1.234E+02") == pytest.approx(123.4)

    def test_lowercase_e(self):
        assert fortran_d_to_float("5.678e-01") == pytest.approx(0.5678)

    def test_plain_float(self):
        assert fortran_d_to_float("42.0") == pytest.approx(42.0)

    def test_integer(self):
        assert fortran_d_to_float("7") == pytest.approx(7.0)

    def test_blank_field_returns_zero(self):
        """空白 spare 字段应返回 0.0 而非报错."""
        assert fortran_d_to_float("") == 0.0
        assert fortran_d_to_float("   ") == 0.0

    def test_negative_exponent(self):
        assert fortran_d_to_float("1.0D-12") == pytest.approx(1e-12)

    def test_positive_exponent(self):
        assert fortran_d_to_float("1.0D+12") == pytest.approx(1e12)

    def test_leading_trailing_spaces(self):
        assert fortran_d_to_float("  -3.14D+00  ") == pytest.approx(-3.14)


# ===========================================================================
# solve_kepler
# ===========================================================================

class TestSolveKepler:
    """开普勒方程求解测试."""

    def test_circular_orbit(self):
        """圆轨道 (e=0): Ek = Mk."""
        for Mk in [0.0, 1.0, 3.0, -2.0]:
            Ek, n = solve_kepler(Mk, e=0.0)
            assert Ek == pytest.approx(Mk, abs=1e-15)
            assert n == 1

    def test_low_eccentricity(self):
        """低偏心率 GPS 典型值 (e ≈ 0.01)."""
        Mk = 1.0
        Ek, n = solve_kepler(Mk, e=0.01)
        # 验证满足开普勒方程
        assert Ek - 0.01 * math.sin(Ek) == pytest.approx(Mk, abs=1e-14)

    def test_moderate_eccentricity(self):
        """中等偏心率 (e ≈ 0.1)."""
        Mk = 2.0
        Ek, n = solve_kepler(Mk, e=0.1)
        assert Ek - 0.1 * math.sin(Ek) == pytest.approx(Mk, abs=1e-14)

    def test_high_eccentricity(self):
        """高偏心率 (e ≈ 0.5)."""
        Mk = 0.5
        Ek, n = solve_kepler(Mk, e=0.5)
        assert Ek - 0.5 * math.sin(Ek) == pytest.approx(Mk, abs=1e-14)

    def test_zero_anomaly(self):
        """Mk=0: 无论偏心率如何，Ek=0 是精确解."""
        Ek, n = solve_kepler(0.0, e=0.3)
        assert Ek == pytest.approx(0.0, abs=1e-15)

    def test_convergence_with_custom_tolerance(self):
        """自定义收敛容差."""
        Mk = 1.0
        Ek, n = solve_kepler(Mk, e=0.1, rtol=1e-10)
        assert Ek - 0.1 * math.sin(Ek) == pytest.approx(Mk, abs=1e-10)

    def test_returns_iteration_count(self):
        """返回实际迭代次数."""
        _, n = solve_kepler(1.0, e=0.0)
        assert n == 1  # 圆轨道一次迭代即收敛

    def test_gps_realistic_values(self):
        """使用 GPS MVP 中的真实参数验证.

        GPS PRN 2 (来自 000A0070.20n):
          Mk ≈ 1.9166 rad, e ≈ 0.0087
        """
        Mk = 1.9166
        e = 0.0087
        Ek, n = solve_kepler(Mk, e)
        # 残差必须极小
        residual = abs(Ek - e * math.sin(Ek) - Mk)
        assert residual < 1e-14


# ===========================================================================
# normalize_sow
# ===========================================================================

class TestNormalizeSow:
    """周内秒归一化测试."""

    def test_within_range(self):
        """正常范围内不需要归一化."""
        assert normalize_sow(0.0) == 0.0
        assert normalize_sow(100000.0) == 100000.0
        assert normalize_sow(-100000.0) == -100000.0
        assert normalize_sow(302399.9) == 302399.9

    def test_positive_half_week_crossing(self):
        """超过半周 (+302400) 应减去一周."""
        assert normalize_sow(400000.0) == pytest.approx(400000.0 - 604800.0)

    def test_negative_half_week_crossing(self):
        """低于负半周 (-302400) 应加上一周."""
        assert normalize_sow(-400000.0) == pytest.approx(-400000.0 + 604800.0)

    def test_exact_half_week(self):
        """恰好等于半周不触发归一化."""
        assert normalize_sow(302400.0) == 302400.0

    def test_just_over_half_week(self):
        """刚超过半周."""
        assert normalize_sow(302400.1) == pytest.approx(302400.1 - 604800.0)

    def test_just_under_neg_half_week(self):
        """刚低于负半周."""
        assert normalize_sow(-302400.1) == pytest.approx(-302400.1 + 604800.0)

    def test_full_week_offset(self):
        """整整一周偏移."""
        assert normalize_sow(604800.0) == pytest.approx(0.0)

    def test_gps_tk_scenario(self):
        """模拟 GPS 星历解算中的 tk 计算.

        t_obs = 504000, toe = 201600  →  tk = 302400 (恰好半周边界)
        """
        tk = normalize_sow(504000.0 - 201600.0)
        assert tk == 302400.0  # 恰好等于半周，不归一化


# ===========================================================================
# 常量值验证
# ===========================================================================

class TestConstants:
    """常量值正确性验证."""

    def test_clight(self):
        assert CLIGHT == 299792458.0

    def test_rtol_kepler(self):
        assert RTOL_KEPLER == 1e-14

    def test_max_iter_kepler(self):
        assert MAX_ITER_KEPLER == 30
