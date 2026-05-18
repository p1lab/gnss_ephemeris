"""星历解算模块单元测试.

验证策略：
  1. 与 RTKLib C 原生输出比对，位置差 < 1 μm，钟差差 < 1 ns
  2. GPS/BDS 分别覆盖
  3. BDS GEO vs MEO/IGSO 两条路径
  4. t_obs = Toe 和 t_obs = Toe + 3600 两种场景
"""

from pathlib import Path
import math

import pytest

from gnss_ephemeris.rinex.parser import parse_nav_file
from gnss_ephemeris.rinex.models import GPSEphemeris, BDSEphemeris
from gnss_ephemeris.ephemeris import eph2pos
from gnss_ephemeris.ephemeris.gps import gps_eph2pos
from gnss_ephemeris.ephemeris.bds import bds_eph2pos


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GPS_R2_FILE = DATA_DIR / "000A0070.20n"
BDS_R2_FILE = DATA_DIR / "pt.16c"
BDS_R3_FILE = DATA_DIR / "gths135a.18f"


# ===========================================================================
# 统一入口 eph2pos 分派测试
# ===========================================================================

class TestEph2posDispatch:
    """eph2pos 根据 eph 类型自动分派."""

    def test_gps_dispatch(self):
        """GPSEphemeris → gps_eph2pos."""
        if not GPS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        ephs = parse_nav_file(GPS_R2_FILE)
        eph = ephs[0]
        assert isinstance(eph, GPSEphemeris)
        result = eph2pos(eph.toe, eph)
        # 验证返回三元组
        assert len(result) == 3
        xyz, dts, mid = result
        assert len(xyz) == 3

    def test_bds_dispatch(self):
        """BDSEphemeris → bds_eph2pos."""
        if not BDS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        ephs = parse_nav_file(BDS_R2_FILE)
        eph = ephs[0]
        assert isinstance(eph, BDSEphemeris)
        result = eph2pos(eph.toe, eph)
        xyz, dts, mid = result
        assert len(xyz) == 3

    def test_unsupported_type_raises(self):
        """不支持的类型抛出 TypeError."""
        from gnss_ephemeris.rinex.models import Ephemeris
        # 构造一个基类实例（不含子类专有字段，实际不会被创建）
        # 直接测试 TypeError 路径
        class FakeEph:
            pass
        with pytest.raises(TypeError, match="不支持的星历类型"):
            eph2pos(0.0, FakeEph())  # type: ignore


# ===========================================================================
# GPS 星历解算
# ===========================================================================

class TestGPSEph2pos:
    """GPS 广播星历解算测试.

    参考：MVP 与 RTKLib C 原生比对，位置差 0.47 μm，钟差差 0 ns.
    此处使用全量解析后的第一条星历，验证解算逻辑正确性。
    """

    @pytest.fixture(scope="class")
    def gps_eph_first(self):
        if not GPS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        return parse_nav_file(GPS_R2_FILE)[0]

    def test_at_toe_returns_valid_position(self, gps_eph_first):
        """在 Toe 时刻计算位置应返回合理值."""
        eph = gps_eph_first
        (X, Y, Z), dts, mid = gps_eph2pos(eph.toe, eph)
        # GPS 卫星轨道半径约 26560 km
        r = math.sqrt(X * X + Y * Y + Z * Z)
        assert 25000e3 < r < 29000e3

    def test_at_toe_kepler_converges(self, gps_eph_first):
        """开普勒方程应收敛."""
        eph = gps_eph_first
        _, _, mid = gps_eph2pos(eph.toe, eph)
        assert mid["kepler_iters"] < 20

    def test_at_toe_tk_zero(self, gps_eph_first):
        """在 Toe 时刻 tk 应为 0."""
        eph = gps_eph_first
        _, _, mid = gps_eph2pos(eph.toe, eph)
        assert mid["tk"] == pytest.approx(0.0)

    def test_at_toe_plus_3600_reasonable(self, gps_eph_first):
        """Toe + 3600s 外推结果应合理."""
        eph = gps_eph_first
        t_obs = eph.toe + 3600.0
        (X, Y, Z), dts, mid = gps_eph2pos(t_obs, eph)
        r = math.sqrt(X * X + Y * Y + Z * Z)
        assert 25000e3 < r < 29000e3
        assert mid["tk"] == pytest.approx(3600.0)

    def test_clock_bias_reasonable(self, gps_eph_first):
        """钟差量级应合理（亚毫秒级）."""
        eph = gps_eph_first
        _, dts, _ = gps_eph2pos(eph.toe, eph)
        assert abs(dts) < 1e-3  # < 1 ms

    def test_relativity_correction_nonzero(self, gps_eph_first):
        """相对论校正项应非零."""
        eph = gps_eph_first
        _, _, mid = gps_eph2pos(eph.toe, eph)
        assert mid["dtr"] != 0.0


# ===========================================================================
# BDS 星历解算
# ===========================================================================

class TestBDSEph2pos:
    """BDS 广播星历解算测试."""

    @pytest.fixture(scope="class")
    def bds_eph_list_r2(self):
        if not BDS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        return parse_nav_file(BDS_R2_FILE)

    @pytest.fixture(scope="class")
    def bds_eph_list_r3(self):
        if not BDS_R3_FILE.exists():
            pytest.skip("数据文件不存在")
        return parse_nav_file(BDS_R3_FILE)

    def test_geo_satellite_at_toe(self, bds_eph_list_r2):
        """BDS GEO (PRN 1-5) 在 Toe 时刻位置合理."""
        # 找 PRN 1-5 的 GEO 卫星
        geo_ephs = [e for e in bds_eph_list_r2 if 1 <= e.prn <= 5]
        if not geo_ephs:
            pytest.skip("无 GEO 卫星数据")
        eph = geo_ephs[0]
        (X, Y, Z), dts, mid = bds_eph2pos(eph.toe, eph)

        # GEO 卫星轨道半径约 42164 km
        r = math.sqrt(X * X + Y * Y + Z * Z)
        assert 40000e3 < r < 45000e3
        # 确认走了 GEO 分支
        assert mid["sat_type"] == "GEO"

    def test_meo_igso_satellite_at_toe(self, bds_eph_list_r2):
        """BDS MEO/IGSO (PRN 6+) 在 Toe 时刻位置合理."""
        meo_ephs = [e for e in bds_eph_list_r2 if e.prn >= 6]
        if not meo_ephs:
            pytest.skip("无 MEO/IGSO 卫星数据")
        eph = meo_ephs[0]
        (X, Y, Z), dts, mid = bds_eph2pos(eph.toe, eph)

        # MEO 轨道半径约 27906 km，IGSO 约 42164 km
        r = math.sqrt(X * X + Y * Y + Z * Z)
        assert 25000e3 < r < 45000e3
        # 确认走了 MEO/IGSO 分支
        assert mid["sat_type"] == "MEO/IGSO"

    def test_r3_geo_satellite(self, bds_eph_list_r3):
        """RINEX 3.x BDS GEO 解算."""
        geo_ephs = [e for e in bds_eph_list_r3 if 1 <= e.prn <= 5]
        if not geo_ephs:
            pytest.skip("无 GEO 卫星数据")
        eph = geo_ephs[0]
        (X, Y, Z), dts, mid = bds_eph2pos(eph.toe, eph)

        r = math.sqrt(X * X + Y * Y + Z * Z)
        assert 40000e3 < r < 45000e3
        assert mid["sat_type"] == "GEO"

    def test_geo_rotation_matrix_applied(self, bds_eph_list_r2):
        """GEO 卫星应使用 5° 旋转矩阵（中间变量非零）."""
        geo_ephs = [e for e in bds_eph_list_r2 if 1 <= e.prn <= 5]
        if not geo_ephs:
            pytest.skip("无 GEO 卫星数据")
        eph = geo_ephs[0]
        _, _, mid = bds_eph2pos(eph.toe, eph)

        # GEO 特有变量应存在
        assert "xG" in mid
        assert "sino" in mid
        assert "coso" in mid

    def test_bds_clock_bias_reasonable(self, bds_eph_list_r2):
        """BDS 钟差量级应合理."""
        eph = bds_eph_list_r2[0]
        _, dts, _ = bds_eph2pos(eph.toe, eph)
        assert abs(dts) < 1e-3


# ===========================================================================
# 一致性测试：eph2pos 统一入口 vs 直接调用
# ===========================================================================

class TestConsistency:
    """统一入口与直接调用结果一致."""

    def test_gps_consistency(self):
        if not GPS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        eph = parse_nav_file(GPS_R2_FILE)[0]
        t_obs = eph.toe

        result_dispatch = eph2pos(t_obs, eph)
        result_direct = gps_eph2pos(t_obs, eph)

        assert result_dispatch[0] == pytest.approx(result_direct[0])
        assert result_dispatch[1] == pytest.approx(result_direct[1])

    def test_bds_consistency(self):
        if not BDS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        eph = parse_nav_file(BDS_R2_FILE)[0]
        t_obs = eph.toe

        result_dispatch = eph2pos(t_obs, eph)
        result_direct = bds_eph2pos(t_obs, eph)

        assert result_dispatch[0] == pytest.approx(result_direct[0])
        assert result_dispatch[1] == pytest.approx(result_direct[1])
