/*
 * verify_rtklib.c — 最小化 RTKLib eph2pos 验证程序
 *
 * 直接硬编码星历参数，调用 RTKLib eph2pos() 核心算法，
 * 输出卫星 ECEF 位置与钟差，与 Python MVP 比对。
 *
 * 编译: gcc -O2 -o verify_rtklib verify_rtklib.c -lm
 * 运行: ./verify_rtklib
 */

#include <stdio.h>
#include <math.h>

/* RTKLib 常量 (ephemeris.c / rtklib.h) */
#define MU_GPS   3.9860050E14
#define MU_CMP   3.986004418E14
#define OMGE     7.2921151467E-5
#define OMGE_CMP 7.292115E-5
#define CLIGHT   299792458.0
#define SIN_5   -0.0871557427476582
#define COS_5    0.9961946980917456
#define RTOL_KEPLER 1E-14
#define MAX_ITER_KEPLER 30
#define SQR(x) ((x)*(x))

/* 星历参数结构 (仅包含 eph2pos 所需字段) */
typedef struct {
    double A;        /* semi-major axis (m) */
    double e;        /* eccentricity */
    double i0;       /* inclination at Toe (rad) */
    double idot;     /* rate of inclination (rad/s) */
    double OMG0;     /* right ascension of ascending node (rad) */
    double OMGd;     /* rate of right ascension (rad/s) */
    double omg;      /* argument of perigee (rad) */
    double M0;       /* mean anomaly at Toe (rad) */
    double deln;     /* mean motion correction (rad/s) */
    double cuc, cus; /* harmonic correction to argument of latitude (rad) */
    double crc, crs; /* harmonic correction to orbit radius (m) */
    double cic, cis; /* harmonic correction to inclination (rad) */
    double f0, f1, f2; /* clock bias, drift, drift rate */
    double toe;      /* ephemeris reference time (sow) */
    double toes;     /* same as toe for our purpose */
    double toc;      /* clock reference time (sow) */
} eph_t;

/* RTKLib eph2pos 核心算法 (摘自 RTKLIB-master/src/ephemeris.c L181-250)
 * sys: 0=GPS, 1=BDS
 * prn: satellite PRN number
 */
static void eph2pos_rtklib(double time_sow, const eph_t *eph, int sys, int prn,
                            double *rs, double *dts)
{
    double tk, M, E, Ek, sinE, cosE, u, r, i, O, sin2u, cos2u;
    double x, y, sinO, cosO, cosi, mu, omge;
    double xg, yg, zg, sino, coso;
    int n;

    tk = time_sow - eph->toe;
    if (tk > 302400.0) tk -= 604800.0;
    else if (tk < -302400.0) tk += 604800.0;

    if (sys == 1) { /* BDS */
        mu = MU_CMP; omge = OMGE_CMP;
    } else { /* GPS */
        mu = MU_GPS; omge = OMGE;
    }

    /* RTKLib merges Step 2-4 into one line */
    M = eph->M0 + (sqrt(mu / (eph->A * eph->A * eph->A)) + eph->deln) * tk;

    for (n = 0, E = M, Ek = 0.0; fabs(E - Ek) > RTOL_KEPLER && n < MAX_ITER_KEPLER; n++) {
        Ek = E;
        E -= (E - eph->e * sin(E) - M) / (1.0 - eph->e * cos(E));
    }
    sinE = sin(E); cosE = cos(E);

    u = atan2(sqrt(1.0 - eph->e * eph->e) * sinE, cosE - eph->e) + eph->omg;
    r = eph->A * (1.0 - eph->e * cosE);
    i = eph->i0 + eph->idot * tk;
    sin2u = sin(2.0 * u); cos2u = cos(2.0 * u);
    u += eph->cus * sin2u + eph->cuc * cos2u;
    r += eph->crs * sin2u + eph->crc * cos2u;
    i += eph->cis * sin2u + eph->cic * cos2u;
    x = r * cos(u); y = r * sin(u); cosi = cos(i);

    /* BDS GEO satellite */
    if (sys == 1 && prn <= 5) {
        O = eph->OMG0 + eph->OMGd * tk - omge * eph->toes;
        sinO = sin(O); cosO = cos(O);
        xg = x * cosO - y * cosi * sinO;
        yg = x * sinO + y * cosi * cosO;
        zg = y * sin(i);
        sino = sin(omge * tk); coso = cos(omge * tk);
        rs[0] =  xg * coso + yg * sino * COS_5 + zg * sino * SIN_5;
        rs[1] = -xg * sino + yg * coso * COS_5 + zg * coso * SIN_5;
        rs[2] = -yg * SIN_5 + zg * COS_5;
    } else {
        O = eph->OMG0 + (eph->OMGd - omge) * tk - omge * eph->toes;
        sinO = sin(O); cosO = cos(O);
        rs[0] = x * cosO - y * cosi * sinO;
        rs[1] = x * sinO + y * cosi * cosO;
        rs[2] = y * sin(i);
    }

    /* Clock */
    tk = time_sow - eph->toc;
    if (tk > 302400.0) tk -= 604800.0;
    else if (tk < -302400.0) tk += 604800.0;
    *dts = eph->f0 + eph->f1 * tk + eph->f2 * tk * tk;

    /* Relativity correction */
    *dts -= 2.0 * sqrt(mu * eph->A) * eph->e * sinE / SQR(CLIGHT);
}

int main(void)
{
    double rs[3], dts;
    eph_t eph;

    /* ====================================================================
     * GPS PRN 2 (from 000A0070.20n)
     * ==================================================================== */
    eph.A = SQR(5153.611560822);
    eph.e = 1.967201998923e-02;
    eph.M0 = -2.027194694510e+00;
    eph.deln = 4.274106605125e-09;
    eph.omg = -1.679951801284e+00;
    eph.OMG0 = -7.764644518439e-01;
    eph.OMGd = -7.642818354062e-09;
    eph.i0 = 9.576194394134e-01;
    eph.idot = 4.535903224290e-11;
    eph.cuc = -3.527849912643e-06;
    eph.cus = 9.125098586082e-06;
    eph.crc = 1.986562500000e+02;
    eph.crs = -6.968750000000e+01;
    eph.cic = 3.967434167862e-07;
    eph.cis = 1.098960638046e-07;
    eph.f0 = -3.809658810496e-04;
    eph.f1 = -7.275957614183e-12;
    eph.f2 = 0.0;
    eph.toe = 1.656000000000e+05;
    eph.toes = eph.toe;
    eph.toc = eph.toe;

    printf("=== GPS PRN 2 (from 000A0070.20n) ===\n");

    /* At Toe */
    eph2pos_rtklib(eph.toe, &eph, 0, 2, rs, &dts);
    printf("t=Toe:     X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    /* At Toe+3600 */
    eph2pos_rtklib(eph.toe + 3600.0, &eph, 0, 2, rs, &dts);
    printf("t=Toe+3600: X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    /* ====================================================================
     * BDS PRN 1 GEO (from pt.16c, RINEX 2.11)
     * ==================================================================== */
    eph.A = SQR(6.493327470780e+03);
    eph.e = 5.832343595100e-04;
    eph.M0 = 1.191720520490e+00;
    eph.deln = -7.211014653420e-10;
    eph.omg = -2.021807533790e+00;
    eph.OMG0 = -1.137305421700e+00;
    eph.OMGd = 1.716857228280e-09;
    eph.i0 = 1.105566501110e-01;
    eph.idot = -2.292952653540e-10;
    eph.cuc = 5.036592483520e-06;
    eph.cus = 1.651281490920e-05;
    eph.crc = -5.110781250000e+02;
    eph.crs = 1.560468750000e+02;
    eph.cic = -1.476146280770e-07;
    eph.cis = 8.381903171540e-09;
    eph.f0 = -1.898203045130e-04;
    eph.f1 = 3.908251500210e-11;
    eph.f2 = 0.0;
    eph.toe = 1.980000000000e+05;
    eph.toes = eph.toe;
    eph.toc = eph.toe;

    printf("\n=== BDS PRN 1 GEO (from pt.16c) ===\n");

    eph2pos_rtklib(eph.toe, &eph, 1, 1, rs, &dts);
    printf("t=Toe:     X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    eph2pos_rtklib(eph.toe + 3600.0, &eph, 1, 1, rs, &dts);
    printf("t=Toe+3600: X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    /* ====================================================================
     * BDS PRN 1 GEO (from gths135a.18f, RINEX 3.02)
     * ==================================================================== */
    eph.A = SQR(6.493487777710e+03);
    eph.e = 3.243593964726e-04;
    eph.M0 = -2.627930186309e+00;
    eph.deln = -8.368205572928e-10;
    eph.omg = 2.078861131150e+00;
    eph.OMG0 = 2.764664389083e+00;
    eph.OMGd = 1.692213369431e-09;
    eph.i0 = 1.089695785632e-01;
    eph.idot = 6.814569464275e-10;
    eph.cuc = -2.512754872441e-05;
    eph.cus = 2.640578895807e-05;
    eph.crc = -8.080156250000e+02;
    eph.crs = -7.770468750000e+02;
    eph.cic = -1.634471118450e-07;
    eph.cis = 2.002343535423e-08;
    eph.f0 = -2.979293931276e-04;
    eph.f1 = 4.932498853805e-11;
    eph.f2 = 0.0;
    eph.toe = 1.692000000000e+05;
    eph.toes = eph.toe;
    eph.toc = eph.toe;

    printf("\n=== BDS PRN 1 GEO (from gths135a.18f) ===\n");

    eph2pos_rtklib(eph.toe, &eph, 1, 1, rs, &dts);
    printf("t=Toe:     X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    eph2pos_rtklib(eph.toe + 3600.0, &eph, 1, 1, rs, &dts);
    printf("t=Toe+3600: X=%15.6f  Y=%15.6f  Z=%15.6f  dts=%.15e\n",
           rs[0], rs[1], rs[2], dts);

    return 0;
}
