# Phase 2: GPS 广播星历解算 MVP — 任务目标与算法规范

> 本文档面向 AI 编码助手，记录 Phase 2 的任务边界、算法来源、公式链与验证策略。

---

## 1. 当前阶段任务目标

**目标**：实现 `tests/mvps/gps_eph2pos_mvp.py`，使用 Phase 1 已验证的 GPS 星历参数，计算指定历元下卫星的 ECEF 坐标 (X, Y, Z) 与钟差 (dt_sv)，并与 RTKLib 输出比对。

### 1.1 功能边界

| 做 | 不做 |
|---|---|
| 计算 GPS 卫星 ECEF 位置 (X, Y, Z) | 不计算 BDS/Galileo/GLONASS（留给 Phase 3） |
| 计算卫星钟差（含相对论改正） | 不做电离层/对流层延迟改正 |
| 与 RTKLib `eph2pos()`/`eph2clk()` 输出比对 | 不做实时定位，仅单颗卫星单历元 |
| 输出中间变量供调试（E, v, u, r 等） | 不封装为类，纯函数式 MVP |

### 1.2 输入

来自 Phase 1 `rinex_parser_mvp.py` 解析 `data/000A0070.20n` 第一条星历（GPS PRN 2）的参数：

| 参数 | 解析值 | 单位 | ICD 符号 |
|------|--------|------|----------|
| PRN | 2 | — | — |
| epoch (Toc) | 2020-01-06 22:00:00.0 | — | $t_{oc}$ |
| af0 | -3.809658810496e-04 | s | $a_{f0}$ |
| af1 | -7.275957614183e-12 | s/s | $a_{f1}$ |
| af2 | 0.000000000000e+00 | s/s^2 | $a_{f2}$ |
| IODE | 7.0 | — | IODE |
| Crs | -6.968750000000e+01 | m | $C_{rs}$ |
| Delta-n | 4.274106605125e-09 | rad/s | $\Delta n$ |
| M0 | -2.027194694510e+00 | rad | $M_0$ |
| Cuc | -3.527849912643e-06 | rad | $C_{uc}$ |
| e | 1.967201998923e-02 | — | $e$ |
| Cus | 9.125098586082e-06 | rad | $C_{us}$ |
| sqrt(A) | 5.153611560822e+03 | sqrt(m) | $\sqrt{A}$ |
| Toe | 1.656000000000e+05 | s (GPS周内秒) | $t_{oe}$ |
| Cic | 3.967434167862e-07 | rad | $C_{ic}$ |
| OMEGA0 | -7.764644518439e-01 | rad | $\Omega_0$ |
| Cis | 1.098960638046e-07 | rad | $C_{is}$ |
| i0 | 9.576194394134e-01 | rad | $i_0$ |
| Crc | 1.986562500000e+02 | m | $C_{rc}$ |
| omega | -1.679951801284e+00 | rad | $\omega$ |
| OMEGA DOT | -7.642818354062e-09 | rad/s | $\dot{\Omega}$ |
| IDOT | 4.535903224290e-11 | rad/s | $\dot{i}$ |
| GPS Week | 2.087000000000e+03 | — | WN |
| TGD | -1.769512891769e-08 | s | $T_{GD}$ |
| IODC | 7.0 | — | IODC |
| Transmission time | 1.583400000000e+05 | s | $t_{tm}$ |

### 1.3 输出

| 量 | 符号 | 单位 | 说明 |
|----|------|------|------|
| 卫星 ECEF X | X | m | 地心地固坐标系 |
| 卫星 ECEF Y | Y | m | 地心地固坐标系 |
| 卫星 ECEF Z | Z | m | 地心地固坐标系 |
| 卫星钟差 | dt_sv | s | 含相对论改正 |

### 1.4 通过标准

- 位置 (X, Y, Z) 相对 RTKLib 输出误差 < 1 mm；
- 钟差 dt_sv 相对 RTKLib 输出误差 < 0.1 ns；
- 代码注释中标注每一步对应的 IS-GPS-200N 章节/公式编号。

---

## 2. 算法来源与参考策略

### 2.1 核心原则：以 ICD 为主，RTKLib 为辅

本项目坚持**算法来源于官方标准文档，工程实现仅作验证参考**的原则：

| 角色 | 文档 | 用途 |
|------|------|------|
| **主参考（算法来源）** | IS-GPS-200N | 公式链、常量定义、算法步骤的唯一权威来源 |
| **辅参考（工程对照）** | RTKLib `src/ephemeris.c` | 理解工程实现细节、验证输出数值 |

具体策略：
1. **按 IS-GPS-200N 公式链逐步实现**，代码注释标注对应章节号；
2. **遇到 ICD 描述模糊处**（如迭代初值、收敛判据），参考 RTKLib 的工程选择；
3. **最终以 RTKLib 的数值输出作为 golden reference** 比对验证。

### 2.2 为什么不能仅参考 RTKLib

- RTKLib 是工程实现，存在简化、合并步骤、变量复用等优化，可能掩盖 ICD 中明确的分步逻辑；
- RTKLib 在一个函数内处理 GPS/Galileo/BDS/QZSS 多系统，通过 switch 分支选择常量，我们的 MVP 只需 GPS；
- ICD 的公式编号和变量命名是我们代码注释和文档的锚点，RTKLib 无此信息。

---

## 3. GPS 星历解算公式链

> 来源：IS-GPS-200N, Table 20-IV (Satellite Antenna Phase Center Position) 及 Table 20-V (Clock Correction)。

### 3.1 常量（IS-GPS-200N, §30.3.3）

| 常量 | 值 | 符号 | 说明 |
|------|-----|------|------|
| 地球引力常数 | 3.9860050e14 m^3/s^2 | $\mu$ | WGS84 值 |
| 地球自转角速度 | 7.2921151467e-5 rad/s | $\dot{\Omega}_e$ | WGS84 值 |
| 光速 | 2.99792458e8 m/s | $c$ | 精确值 |

> 注：RTKLib 中 `MU_GPS = 3.9860050E14`，`OMGE = 7.2921151467E-5`，`CLIGHT = 299792458.0`，与 ICD 一致。

### 3.2 卫星位置计算（eph2pos）

以下公式编号对应 IS-GPS-200N Table 20-IV：

```
输入: t (观测时刻, GPST), 星历参数
输出: 卫星 ECEF 坐标 (X, Y, Z)
```

**Step 1: 计算观测时刻与星历参考时刻之差**

$$t_k = t - t_{oe}$$

其中 $t_{oe}$ 为 Toe（星历参考时间，GPS 周内秒）。若 $t_k > 302400$，则 $t_k \leftarrow t_k - 604800$；若 $t_k < -302400$，则 $t_k \leftarrow t_k + 604800$。

> 注：RTKLib 使用 `timediff()` 函数处理半周跳变，效果相同。

**Step 2: 计算卫星平均运动角速度**

$$n_0 = \sqrt{\mu / A^3}$$

其中 $A = (\sqrt{A})^2$（从 RINEX 读取的 `sqrt(A)` 需要平方）。

**Step 3: 计算改正后的平均运动角速度**

$$n = n_0 + \Delta n$$

**Step 4: 计算平近点角**

$$M_k = M_0 + n \cdot t_k$$

> RTKLib 合并为一步：`M = M0 + (sqrt(mu/A^3) + deln) * tk`

**Step 5: 求解开普勒方程得偏近点角 E_k**

$$M_k = E_k - e \cdot \sin E_k$$

采用牛顿迭代法：

$$E_{k,i+1} = E_{k,i} - \frac{E_{k,i} - e \cdot \sin E_{k,i} - M_k}{1 - e \cdot \cos E_{k,i}}$$

- 初值：$E_{k,0} = M_k$
- 收敛判据：$|E_{k,i+1} - E_{k,i}| < \epsilon$（RTKLib 取 $\epsilon = 10^{-14}$）
- 最大迭代次数：30（RTKLib 取 `MAX_ITER_KEPLER = 30`）

**Step 6: 计算真近点角 v_k**

$$v_k = \text{atan2}(\sqrt{1 - e^2} \cdot \sin E_k,\ \cos E_k - e)$$

**Step 7: 计算升交点角距 u_k**

$$u_k = v_k + \omega$$

> RTKLib 合并为：`u = atan2(sqrt(1-e^2)*sinE, cosE-e) + omg`

**Step 8: 摄动改正**

$$\delta u_k = C_{us} \cdot \sin 2u_k + C_{uc} \cdot \cos 2u_k$$
$$\delta r_k = C_{rs} \cdot \sin 2u_k + C_{rc} \cdot \cos 2u_k$$
$$\delta i_k = C_{is} \cdot \sin 2u_k + C_{ic} \cdot \cos 2u_k$$

改正后：

$$u_k \leftarrow u_k + \delta u_k$$
$$r_k \leftarrow A(1 - e \cdot \cos E_k) + \delta r_k$$
$$i_k \leftarrow i_0 + \delta i_k + \text{IDOT} \cdot t_k$$

> RTKLib 的实现顺序略有不同：先算 `r = A*(1-e*cosE)`，再分别加改正，等效。

**Step 9: 轨道平面内坐标**

$$x_k' = r_k \cdot \cos u_k$$
$$y_k' = r_k \cdot \sin u_k$$

**Step 10: 计算改正后的升交点经度**

$$\Omega_k = \Omega_0 + (\dot{\Omega} - \dot{\Omega}_e) \cdot t_k - \dot{\Omega}_e \cdot t_{oe}$$

> 注意：对于 GPS 卫星，使用此公式。BDS GEO 卫星有特殊处理（Phase 3 会涉及）。

**Step 11: ECEF 坐标**

$$X_k = x_k' \cdot \cos \Omega_k - y_k' \cdot \cos i_k \cdot \sin \Omega_k$$
$$Y_k = x_k' \cdot \sin \Omega_k + y_k' \cdot \cos i_k \cdot \sin \Omega_k$$
$$Z_k = y_k' \cdot \sin i_k$$

### 3.3 卫星钟差计算（eph2clk）

以下公式对应 IS-GPS-200N §20.3.3.3.3.1：

**Step 1: 计算时间差**

$$t = t_{recv} - t_{oc}$$

同样需要处理半周跳变（同 Step 1 的 $t_k$ 处理）。

**Step 2: 钟差多项式**

$$\Delta t_{sv} = a_{f0} + a_{f1} \cdot t + a_{f2} \cdot t^2$$

**Step 3: 相对论改正**

$$\Delta t_r = -\frac{2\sqrt{\mu A} \cdot e \cdot \sin E_k}{c^2}$$

**Step 4: 总钟差**

$$\Delta t_{sv} \leftarrow \Delta t_{sv} + \Delta t_r$$

> 注：RTKLib 的 `eph2clk()` 先迭代修正 t（两次不动点迭代），然后 `eph2pos()` 中再单独加相对论改正。我们的 MVP 中钟差计算直接在位置计算后一并完成即可，与 RTKLib `eph2pos()` 返回的 `dts` 比对。

---

## 4. 验证策略

### 4.1 Golden Reference 获取

需要用 RTKLib 对相同输入（PRN 2, epoch = Toe）计算参考输出。两种途径：

1. **编译 RTKLib 并运行**：使用 `RTKLIB-master/src/` 中的源码，编写小型 C 程序调用 `eph2pos()` 输出结果；
2. **用 RTKLib 的 Python 绑定或 RNX2RTKP 工具**：将星历参数写入 RINEX 文件，用 RTKLib 工具计算。

> 建议：直接用 C 语言编写小型验证程序，避免工具链复杂性。若编译不便，可先用手工验算作为中间验证。

### 4.2 验证步骤

1. 用 MVP 计算观测时刻 = Toe（星历参考时刻）的卫星位置与钟差；
2. 在 MVP 中打印所有中间变量（$t_k$, $n_0$, $n$, $M_k$, $E_k$, $v_k$, $u_k$, $r_k$, $i_k$, $\Omega_k$, $x_k'$, $y_k'$, $\Delta t_{sv}$, $\Delta t_r$）；
3. 与 RTKLib 输出逐项比对；
4. 误差超过阈值则逐步回溯中间变量定位偏差源。

### 4.3 选择 Toe 时刻的理由

观测时刻取 $t = t_{oe}$ 时，$t_k = 0$，此时：
- $M_k = M_0$（平近点角等于星历参考值）
- 摄动改正中的 $t_k$ 项为零
- 卫星位置仅由星历参考时刻的轨道参数决定
- 最容易手工验算，也是 RTKLib 最基本的测试场景

---

## 5. 与 RTKLib 实现的差异对照

以下是 RTKLib 实现中需要注意的工程细节：

| 对照项 | IS-GPS-200N | RTKLib 实现 | MVP 处理 |
|--------|-------------|-------------|----------|
| 半周跳变 | "若 $t_k$ 超过 302400" | `timediff()` 函数处理 | 自行实现 $t_k$ 归化 |
| 开普勒迭代初值 | 未指定 | $E_0 = M_k$ | 同 RTKLib |
| 收敛判据 | 未指定 | $|E_{i+1} - E_i| < 10^{-14}$ | 同 RTKLib |
| 最大迭代次数 | 未指定 | 30 | 同 RTKLib |
| 钟差迭代 | 未提及对 t 的迭代 | `eph2clk()` 迭代 2 次修正 t | MVP 中钟差在位置计算后一次性算出，不单独迭代 |
| 相对论改正 | 位置计算后单独加 | 在 `eph2pos()` 中最后一步加 | 同 RTKLib |
| TGD 改正 | ICD 有定义 | `eph2pos()` 不含 TGD | MVP 不含 TGD（钟差不含群延迟） |

---

## 6. 参考文档索引

| 文档 | 本地路径 | 对应内容 |
|------|---------|---------|
| IS-GPS-200N | `doc/IS-GPS-200N.pdf` | §20.3.3.4 Table 20-IV (位置), §20.3.3.3.3.1 (钟差) |
| RTKLib ephemeris.c | `RTKLIB-master/src/ephemeris.c` | `eph2pos()` (L181-250), `eph2clk()` (L154-167) |
| RTKLib rtklib.h | `RTKLIB-master/src/rtklib.h` | 常量 CLIGHT, OMGE, RE_WGS84 |
| RTKLib 手册 | `doc/rtklib_manual.pdf.pdf` | 附录 E 公式描述 |
