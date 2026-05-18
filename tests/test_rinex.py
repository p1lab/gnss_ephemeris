"""RINEX 解析器与数据契约测试."""

from pathlib import Path
import dataclasses

import pytest

from gnss_ephemeris.rinex.models import Ephemeris, GPSEphemeris, BDSEphemeris
from gnss_ephemeris.rinex.parser import parse_nav_file, parse_rinex2, parse_rinex3


# ---------------------------------------------------------------------------
# 样例文件路径
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GPS_R2_FILE = DATA_DIR / "000A0070.20n"     # RINEX 2.10 GPS
BDS_R2_FILE = DATA_DIR / "pt.16c"           # RINEX 2.11 BDS
BDS_R3_FILE = DATA_DIR / "gths135a.18f"     # RINEX 3.02 BDS


# ===========================================================================
# 数据契约：Ephemeris dataclass 构造与类型
# ===========================================================================

class TestEphemerisContract:
    """验证 Ephemeris 基类与子类的基本契约."""

    @staticmethod
    def _make_base_kwargs():
        """构造 Ephemeris 基类所需的全部参数."""
        return dict(
            system="GPS", prn=2,
            epoch=(2020, 1, 6, 22, 0, 0.0),
            af0=-3.809658810496e-04, af1=-3.809658810496e-12, af2=0.0,
            toe=504000.0,
            sqrt_a=5153.65503750, e=8.743295434763e-03, m0=1.916624857486e+00,
            delta_n=4.598822594290e-09,
            omega=-2.725990600538e+00, omega0=2.129233489985e+00,
            omega_dot=-7.686441304055e-09,
            i0=9.565298360394e-01, idot=-6.385530557634e-11,
            cuc=1.088738441467e-06, cus=7.451385259628e-06,
            crc=2.187500000000e+02, crs=1.218750000000e+01,
            cic=-3.725290298462e-08, cis=-1.862645149231e-09,
        )

    def test_base_ephemeris_construction(self):
        """Ephemeris 基类可直接构造."""
        eph = Ephemeris(**self._make_base_kwargs())
        assert eph.system == "GPS"
        assert eph.prn == 2
        assert eph.toe == 504000.0

    def test_gps_ephemeris_inherits_base(self):
        """GPSEphemeris 继承 Ephemeris 基类."""
        kwargs = self._make_base_kwargs()
        kwargs.update(
            iode=1.0, iodc=1.0, tgd=-1.117587089539e-08,
            gps_week=2086.0, codes_on_l2=1.0, l2_p_flag=0.0,
            sv_accuracy=0.0, sv_health=0.0,
            trans_time=504000.0, fit_interval=0.0,
        )
        eph = GPSEphemeris(**kwargs)
        assert isinstance(eph, Ephemeris)
        assert isinstance(eph, GPSEphemeris)
        assert eph.iode == 1.0
        assert eph.tgd == pytest.approx(-1.117587089539e-08)

    def test_bds_ephemeris_inherits_base(self):
        """BDSEphemeris 继承 Ephemeris 基类."""
        kwargs = self._make_base_kwargs()
        kwargs.update(
            system="BDS", prn=1,
            aode=1.0, aodc=1.0,
            tgd1=-1.0e-08, tgd2=0.0, sath1=0.0,
            bdt_week=520.0, sv_accuracy=0.0, trans_time=345600.0,
        )
        eph = BDSEphemeris(**kwargs)
        assert isinstance(eph, Ephemeris)
        assert isinstance(eph, BDSEphemeris)
        assert eph.aode == 1.0
        assert eph.tgd1 == pytest.approx(-1.0e-08)

    def test_isinstance_dispatch(self):
        """isinstance 分派：GPS/BDS 子类可被区分."""
        kwargs = self._make_base_kwargs()
        gps = GPSEphemeris(**kwargs, iode=1, iodc=1, tgd=0, gps_week=1,
                          codes_on_l2=0, l2_p_flag=0, sv_accuracy=0,
                          sv_health=0, trans_time=0, fit_interval=0)
        bds = BDSEphemeris(**{**kwargs, "system": "BDS", "prn": 1},
                           aode=1, aodc=1, tgd1=0, tgd2=0, sath1=0,
                           bdt_week=1, sv_accuracy=0, trans_time=0)

        assert isinstance(gps, GPSEphemeris)
        assert not isinstance(gps, BDSEphemeris)
        assert isinstance(bds, BDSEphemeris)
        assert not isinstance(bds, GPSEphemeris)

    def test_repr(self):
        """repr 输出包含类名、系统、PRN 和 toe."""
        kwargs = self._make_base_kwargs()
        kwargs.update(
            iode=1.0, iodc=1.0, tgd=0, gps_week=1.0,
            codes_on_l2=0, l2_p_flag=0, sv_accuracy=0,
            sv_health=0, trans_time=0, fit_interval=0,
        )
        eph = GPSEphemeris(**kwargs)
        r = repr(eph)
        assert "GPSEphemeris" in r
        assert "GPS" in r
        assert "prn=2" in r

    def test_field_count_gps(self):
        """GPSEphemeris 字段数 = 基类 22 + 专有 10 = 32."""
        assert len(dataclasses.fields(GPSEphemeris)) == 32

    def test_field_count_bds(self):
        """BDSEphemeris 字段数 = 基类 22 + 专有 8 = 30."""
        assert len(dataclasses.fields(BDSEphemeris)) == 30


# ===========================================================================
# RINEX 解析器回归测试
# ===========================================================================

class TestParseRinex2GPS:
    """RINEX 2.x GPS 解析回归测试.

    与 MVP rinex_parser_mvp.py 的输出逐字段核对。
    """

    @pytest.fixture(scope="class")
    def gps_eph_list(self):
        """解析 GPS RINEX 2.10 文件."""
        if not GPS_R2_FILE.exists():
            pytest.skip(f"数据文件不存在: {GPS_R2_FILE}")
        return parse_nav_file(GPS_R2_FILE)

    def test_returns_list_of_gps_ephemeris(self, gps_eph_list):
        """返回值类型正确."""
        assert len(gps_eph_list) > 0
        for eph in gps_eph_list:
            assert isinstance(eph, GPSEphemeris)

    def test_first_eph_prn(self, gps_eph_list):
        """第一条星历的 PRN."""
        assert gps_eph_list[0].prn == 2

    def test_first_eph_system(self, gps_eph_list):
        """第一条星历的系统."""
        assert gps_eph_list[0].system == "GPS"

    def test_first_eph_epoch(self, gps_eph_list):
        """第一条星历的历元."""
        assert gps_eph_list[0].epoch == (2020, 1, 6, 22, 0, 0.0)

    def test_first_eph_clock_coefficients(self, gps_eph_list):
        """第一条星历的钟差系数."""
        eph = gps_eph_list[0]
        assert eph.af0 == pytest.approx(-3.809658810496e-04)
        assert eph.af1 == pytest.approx(-7.275957614183e-12)
        assert eph.af2 == pytest.approx(0.0)

    def test_first_eph_keplerian_elements(self, gps_eph_list):
        """第一条星历的开普勒根数（关键参数抽样）."""
        eph = gps_eph_list[0]
        assert eph.sqrt_a == pytest.approx(5153.611560822)
        assert eph.e == pytest.approx(0.01967201998923)
        assert eph.m0 == pytest.approx(-2.02719469451)
        assert eph.delta_n == pytest.approx(4.274106605125e-09)

    def test_first_eph_harmonic_perturbations(self, gps_eph_list):
        """第一条星历的谐波摄动."""
        eph = gps_eph_list[0]
        assert eph.cuc == pytest.approx(-3.527849912643e-06)
        assert eph.cus == pytest.approx(9.125098586082e-06)
        assert eph.crc == pytest.approx(198.65625)
        assert eph.crs == pytest.approx(-69.6875)
        assert eph.cic == pytest.approx(3.967434167862e-07)
        assert eph.cis == pytest.approx(1.098960638046e-07)

    def test_first_eph_gps_specific(self, gps_eph_list):
        """第一条星历的 GPS 专有字段."""
        eph = gps_eph_list[0]
        assert eph.iode == pytest.approx(7.0)
        assert eph.iodc == pytest.approx(7.0)
        assert eph.tgd == pytest.approx(-1.769512891769e-08)
        assert eph.gps_week == pytest.approx(2087.0)

    def test_total_record_count(self, gps_eph_list):
        """解析出的总记录数应大于 0（文件含多颗卫星多历元）."""
        assert len(gps_eph_list) > 1


class TestParseRinex2BDS:
    """RINEX 2.x BDS 解析回归测试."""

    @pytest.fixture(scope="class")
    def bds_eph_list(self):
        if not BDS_R2_FILE.exists():
            pytest.skip(f"数据文件不存在: {BDS_R2_FILE}")
        return parse_nav_file(BDS_R2_FILE)

    def test_returns_list_of_bds_ephemeris(self, bds_eph_list):
        assert len(bds_eph_list) > 0
        for eph in bds_eph_list:
            assert isinstance(eph, BDSEphemeris)

    def test_first_eph_system_and_prn(self, bds_eph_list):
        """第一条星历的系统与 PRN（BDS GEO PRN 1）."""
        eph = bds_eph_list[0]
        assert eph.system == "BDS"
        assert eph.prn == 1

    def test_first_eph_bds_specific(self, bds_eph_list):
        """第一条星历的 BDS 专有字段."""
        eph = bds_eph_list[0]
        assert eph.aode == pytest.approx(1.0)
        assert eph.tgd1 == pytest.approx(1.42000002867e-08)


class TestParseRinex3BDS:
    """RINEX 3.x BDS 解析回归测试."""

    @pytest.fixture(scope="class")
    def bds_eph_list(self):
        if not BDS_R3_FILE.exists():
            pytest.skip(f"数据文件不存在: {BDS_R3_FILE}")
        return parse_nav_file(BDS_R3_FILE)

    def test_returns_list_of_bds_ephemeris(self, bds_eph_list):
        assert len(bds_eph_list) > 0
        for eph in bds_eph_list:
            assert isinstance(eph, BDSEphemeris)

    def test_first_eph_sv(self, bds_eph_list):
        """第一条星历的 PRN（从 C01 提取 → PRN 1）."""
        assert bds_eph_list[0].prn == 1

    def test_first_eph_system(self, bds_eph_list):
        assert bds_eph_list[0].system == "BDS"

    def test_first_eph_epoch_year_4digit(self, bds_eph_list):
        """RINEX 3.x 使用 4 位年份."""
        assert bds_eph_list[0].epoch[0] == 2018


class TestParseNavFileAutoVersion:
    """parse_nav_file 自动版本识别."""

    def test_gps_r2_auto(self):
        if not GPS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        eph_list = parse_nav_file(GPS_R2_FILE)
        assert all(isinstance(eph, GPSEphemeris) for eph in eph_list)

    def test_bds_r2_auto(self):
        if not BDS_R2_FILE.exists():
            pytest.skip("数据文件不存在")
        eph_list = parse_nav_file(BDS_R2_FILE)
        assert all(isinstance(eph, BDSEphemeris) for eph in eph_list)

    def test_bds_r3_auto(self):
        if not BDS_R3_FILE.exists():
            pytest.skip("数据文件不存在")
        eph_list = parse_nav_file(BDS_R3_FILE)
        assert all(isinstance(eph, BDSEphemeris) for eph in eph_list)
