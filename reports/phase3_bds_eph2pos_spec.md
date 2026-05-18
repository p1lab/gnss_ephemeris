# Phase 3: BDS 广播星历解算 MVP — 任务目标与算法规范

> 本文档面向 AI 编码助手，记录 Phase 3 的任务边界、算法来源、公式链与验证策略。

---

## 1. 当前阶段任务目标

**目标**：实现 `tests/mvps/bds_eph2pos_mvp.py`，使用 Phase 1 已验证的 BDS 星历参数，计算指定历元下北斗卫星的 ECEF 坐标 (X, Y, Z) 与钟差 (dt_sv)，并与 RTKLib 输出比对。

### 1.1 功能边界

| 做 | 不做 |
|---|---|
| 计算 BDS 卫星 ECEF 位置 (X, Y, Z) | 不计算 GPS/Galileo/GLONASS（Phase 2 已完成 GPS） |
| 区分 GEO（PRN 1-5）与 MEO/IGSO 的不同算法路径 | 不做电离层/对流层延迟改正 |
| 计算卫星钟差（含相对论改正） | 不做实时定位，仅单颗卫星单历元 |
| 与 RTKLib `eph2pos()` 输出比对 | 不封装为类，纯函数式 MVP |
| 输出中间变量供调试 | 不处理 BDS-3 新信号（仅 B1I） |

### 1.2 输入

来自 Phase 1 `rinex_parser_mvp.py` 解析的两个 BDS 样例文件的第一条星历：

**文件 1：`data/pt.16c`（RINEX 2.11，BDS PRN 1 — GEO 卫星）**

| 参数 | 解析值 | 单位 | ICD 符号 |
|------|--------|------|----------|
| PRN | 1 | — | — |
| epoch (Toc) | 2016-11-08 07:00:00.0 | BDT | $t_{oc}$ |
| af0 | -1.898203045130e-04 | s | $a_{f0}$ |
| af1 | 3.908251500210e-11 | s/s | $a_{f1}$ |
| af2 | 0.000000000000e+00 | s/s^2 | $a_{f2}$ |
| AODE | 1.0 | — | AODE |
| Crs | 1.560468750000e+02 | m | $C_{rs}$ |
| Delta-n | -7.211014653420e-10 | rad/s | $\Delta n$ |
| M0 | 1.191720520490e+00 | rad | $M_0$ |
| Cuc | 5.036592483520e-06 | rad | $C_{uc}$ |
| e | 5.832343595100e-04 | — | $e$ |
| Cus | 1.651281490920e-05 | rad | $C_{us}$ |
| sqrt(A) | 6.493327470780e+03 | sqrt(m) | $\sqrt{A}$ |
| Toe | 1.980000000000e+05 | s (BDT周内秒) | $t_{oe}$ |
| Cic | -1.476146280770e-07 | rad | $C_{ic}$ |
| OMEGA0 | -1.137305421700e+00 | rad | $\Omega_0$ |
| Cis | 8.381903171540e-09 | rad | $C_{is}$ |
| i0 | 1.105566501110e-01 | rad | $i_0$ |
| Crc | -5.110781250000e+02 | m | $C_{rc}$ |
| omega | -2.021807533790e+00 | rad | $\omega$ |
| OMEGA DOT | 1.716857228280e-09 | rad/s | $\dot{\Omega}$ |
| IDOT | -2.292952653540e-10 | rad/s | $\dot{i}$ |
| BDT Week | 566 | — | WN |
| TGD1 | 1.420000028670e-08 | s | $T_{GD1}$ |
| Transmission time | 1.980000000000e+05 | s | $t_{tm}$ |

**文件 2：`data/gths135a.18f`（RINEX 3.02，BDS PRN C01 — GEO 卫星）**

| 参数 | 解析值 | 单位 | ICD 符号 |
|------|--------|------|----------|
| SV | C01 | — | — |
| epoch (Toc) | 2018-05-14 23:00:00 | BDT | $t_{oc}$ |
| af0 | -2.979293931276e-04 | s | $a_{f0}$ |
| af1 | 4.932498853805e-11 | s/s | $a_{f1}$ |
| af2 | 0.000000000000e+00 | s/s^2 | $a_{f2}$ |
| AODE | 1.0 | — | AODE |
| Crs | -7.770468750000e+02 | m | $C_{rs}$ |
| Delta-n | -8.368205572928e-10 | rad/s | $\Delta n$ |
| M0 | -2.627930186309e+00 | rad | $M_0$ |
| Cuc | -2.512754872441e-05 | rad | $C_{uc}$ |
| e | 3.243593964726e-04 | — | $e$ |
| Cus | 2.640578895807e-05 | rad | $C_{us}$ |
| sqrt(A) | 6.493487777710e+03 | sqrt(m) | $\sqrt{A}$ |
| Toe | 1.692000000000e+05 | s (BDT周内秒) | $t_{oe}$ |
| Cic | -1.634471118450e-07 | rad | $C_{ic}$ |
| OMEGA0 | 2.764664389083e+00 | rad | $\Omega_0$ |
| Cis | 2.002343535423e-08 | rad | $C_{is}$ |
| i0 | 1.089695785632e-01 | rad | $i_0$ |
| Crc | -8.080156250000e+02 | m | $C_{rc}$ |
| omega | 2.078861131150e+00 | rad | $\omega$ |
| OMEGA DOT | 1.692213369431e-09 | rad/s | $\dot{\Omega}$ |
| IDOT | 6.814569464275e-10 | rad/s | $\dot{i}$ |
| BDT Week | 645 | — | WN |
| TGD1 | 1.420000028673e-08 | s | $T_{GD1}$ |
| TGD2 | -1.039999997232e-08 | s | $T_{GD2}$ |
| Transmission time | 1.692004000000e+05 | s | $t_{tm}$ |

> **重要**：两个样例文件的第一条星历均为 **GEO 卫星**（PRN 1/C01，i0 ~ 0.11 rad ≈ 6.3°，sqrt(A) ~ 6493 → A ~ 42164 km）。这意味着 MVP 必须实现 GEO 专用算法路径，而不仅仅是 GPS 公式的常量替换。

### 1.3 输出

| 量 | 符号 | 单位 | 说明 |
|----|------|------|------|
| 卫星 ECEF X | X | m | CGCS2000 地心地固坐标系 |
| 卫星 ECEF Y | Y | m | CGCS2000 地心地固坐标系 |
| 卫星 ECEF Z | Z | m | CGCS2000 地心地固坐标系 |
| 卫星钟差 | dt_sv | s | 含相对论改正 |

### 1.4 通过标准

- 位置 (X, Y, Z) 相对 RTKLib 输出误差 < 1 mm；
- 钟差 dt_sv 相对 RTKLib 输出误差 < 0.1 ns；
- 代码注释中标注每一步对应的北斗 ICD 章节/公式编号。

---

## 2. 算法来源与参考策略

### 2.1 核心原则：以 ICD 为主，RTKLib 为辅

与 Phase 2 相同，本项目坚持**算法来源于官方标准文档，工程实现仅作验证参考**：

| 角色 | 文档 | 用途 |
|------|------|------|
| **主参考（算法来源）** | 北斗 B1I ICD v3.0（2018-06） | 公式链、常量定义、GEO/MEO/IGSO 分支的权威来源 |
| **辅参考（工程对照）** | RTKLib `src/ephemeris.c` | 理解 GEO 旋转矩阵的工程实现、验证输出数值 |

### 2.2 BDS 与 GPS 的关键差异

BDS 星历解算**并非简单替换常量**，存在本质性的算法差异：

| 差异点 | GPS | BDS |
|--------|-----|-----|
| 地球引力常数 $\mu$ | 3.9860050 × 10^14 m³/s² | 3.986004418 × 10^14 m³/s² |
| 地球自转角速度 $\dot{\Omega}_e$ | 7.2921151467 × 10⁻⁵ rad/s | 7.292115 × 10⁻⁵ rad/s |
| 坐标系 | WGS84 | CGCS2000 |
| 时间系统 | GPST | BDT（= GPST - 14 s） |
| GEO 卫星处理 | 无 | 需要 5° 旋转矩阵（Step 10/11 不同） |
| 卫星类型 | 仅 MEO | GEO（PRN 1-5）、MEO（PRN 6-39ish）、IGSO |

### 2.3 为什么 GEO 卫星需要特殊处理

北斗 GEO 卫星静止在赤道上空约 36000 km 处，倾角接近零（~0.1 rad ≈ 6°，受摄动影响非严格为零）。若直接使用 GPS 的标准公式，升交点经度 $\Omega_k$ 中的 $-\dot{\Omega}_e \cdot t_k$ 项会导致坐标随时间快速旋转（因为 GEO 的 $\dot{\Omega}$ 极小，而 $\dot{\Omega}_e$ 很大），结果不正确。

ICD 的解决方案：GEO 卫星先在**惯性系**中计算位置（$\Omega_k$ 不含 $-\dot{\Omega}_e \cdot t_k$），然后通过 $R_z(\dot{\Omega}_e \cdot t_k) \cdot R_x(-5°)$ 旋转矩阵转到地固系。这里的 $-5°$ 旋转是 CGCS2000 坐标系定义的一部分，用于消除 GEO 轨道倾角偏置的影响。

---

## 3. BDS 星历解算公式链

> 来源：北斗 B1I ICD v3.0，Section 5.2.4（卫星位置计算）及 Section 5.2.3（卫星钟差计算）。

### 3.1 常量（北斗 ICD Section 5.2.4）

| 常量 | 值 | 符号 | 说明 |
|------|-----|------|------|
| 地球引力常数 | 3.986004418 × 10^14 m³/s² | $\mu$ | CGCS2000 值 |
| 地球自转角速度 | 7.292115 × 10⁻⁵ rad/s | $\dot{\Omega}_e$ | CGCS2000 值 |
| 光速 | 2.99792458 × 10⁸ m/s | $c$ | 精确值 |
| 5° 旋转（GEO 用） | sin(-5°) = -0.0871557427476582 | $S_{-5}$ | RTKLib 常量 SIN_5 |
| | cos(-5°) = 0.9961946980917456 | $C_{-5}$ | RTKLib 常量 COS_5 |

> **常量精度差异对照**：
>
> | 常量 | GPS ICD | BDS ICD | RTKLib (GPS) | RTKLib (BDS) |
> |------|---------|---------|-------------|-------------|
> | $\mu$ | 3.9860050e14 | 3.986004418e14 | MU_GPS=3.9860050E14 | MU_CMP=3.986004418E14 |
> | $\dot{\Omega}_e$ | 7.2921151467e-5 | 7.292115e-5 | OMGE=7.2921151467E-5 | OMGE_CMP=7.292115E-5 |
>
> 注意：BDS 的 $\dot{\Omega}_e$ 精度较低（6 位有效数字 vs GPS 的 10 位），这是 ICD 定义差异，**必须使用 BDS ICD 的值**，不可混用。

### 3.2 卫星位置计算 — 公共部分（Step 1-9）

BDS MEO/IGSO 与 GEO 在 Step 1-9 完全相同：

```
输入: t (观测时刻, BDT), 星历参数, 卫星类型 (GEO / MEO-IGSO)
输出: 卫星 ECEF 坐标 (X, Y, Z)
```

**Step 1: 计算观测时刻与星历参考时刻之差**

$$t_k = t - t_{oe}$$

若 $t_k > 302400$，则 $t_k \leftarrow t_k - 604800$；若 $t_k < -302400$，则 $t_k \leftarrow t_k + 604800$。

> 注：此处的 $t_{oe}$ 是 BDT 周内秒。

**Step 2: 计算卫星平均运动角速度**

$$n_0 = \sqrt{\mu / A^3}$$

**Step 3: 计算改正后的平均运动角速度**

$$n = n_0 + \Delta n$$

**Step 4: 计算平近点角**

$$M_k = M_0 + n \cdot t_k$$

**Step 5: 求解开普勒方程得偏近点角 E_k**

$$M_k = E_k - e \cdot \sin E_k$$

牛顿迭代法，同 GPS：
- 初值：$E_{k,0} = M_k$
- 收敛判据：$|E_{k,i+1} - E_{k,i}| < 10^{-14}$
- 最大迭代次数：30

**Step 6: 计算真近点角 v_k**

$$v_k = \text{atan2}(\sqrt{1 - e^2} \cdot \sin E_k,\ \cos E_k - e)$$

**Step 7: 计算升交点角距 u_k**

$$u_k = v_k + \omega$$

**Step 8: 摄动改正**

$$\delta u_k = C_{us} \cdot \sin 2u_k + C_{uc} \cdot \cos 2u_k$$
$$\delta r_k = C_{rs} \cdot \sin 2u_k + C_{rc} \cdot \cos 2u_k$$
$$\delta i_k = C_{is} \cdot \sin 2u_k + C_{ic} \cdot \cos 2u_k$$

改正后：

$$u_k \leftarrow u_k + \delta u_k$$
$$r_k \leftarrow A(1 - e \cdot \cos E_k) + \delta r_k$$
$$i_k \leftarrow i_0 + \delta i_k + \text{IDOT} \cdot t_k$$

**Step 9: 轨道平面内坐标**

$$x_k' = r_k \cdot \cos u_k$$
$$y_k' = r_k \cdot \sin u_k$$

### 3.3 卫星位置计算 — 分支部分（Step 10-11）

#### 3.3.1 MEO/IGSO 卫星（PRN 6+）

与 GPS 公式完全相同，仅常量不同：

**Step 10:**

$$\Omega_k = \Omega_0 + (\dot{\Omega} - \dot{\Omega}_e) \cdot t_k - \dot{\Omega}_e \cdot t_{oe}$$

**Step 11:**

$$X_k = x_k' \cdot \cos \Omega_k - y_k' \cdot \cos i_k \cdot \sin \Omega_k$$
$$Y_k = x_k' \cdot \sin \Omega_k + y_k' \cdot \cos i_k \cdot \cos \Omega_k$$
$$Z_k = y_k' \cdot \sin i_k$$

#### 3.3.2 GEO 卫星（PRN 1-5）— 关键差异

GEO 卫星的 Step 10-11 与 MEO/IGSO **本质不同**：

**Step 10（GEO）: 计算惯性系中的升交点经度**

$$\Omega_k = \Omega_0 + \dot{\Omega} \cdot t_k - \dot{\Omega}_e \cdot t_{oe}$$

> **注意**：GEO 的 $\Omega_k$ 公式中**没有** $-\dot{\Omega}_e \cdot t_k$ 项！这是因为 GEO 的位置在惯性系中计算，地球自转效应在后续旋转矩阵中显式处理。

**Step 11（GEO）: 先算惯性系坐标，再旋转到 CGCS2000**

**11a. 惯性系坐标**（以 $\Omega_k$ 为升交点经度）：

$$x_G = x_k' \cdot \cos \Omega_k - y_k' \cdot \cos i_k \cdot \sin \Omega_k$$
$$y_G = x_k' \cdot \sin \Omega_k + y_k' \cdot \cos i_k \cdot \cos \Omega_k$$
$$z_G = y_k' \cdot \sin i_k$$

**11b. 旋转到 CGCS2000 地固系**：

应用旋转矩阵 $R_z(\dot{\Omega}_e \cdot t_k) \cdot R_x(-5°)$：

$$\begin{bmatrix} X_k \\ Y_k \\ Z_k \end{bmatrix} = R_z(\dot{\Omega}_e \cdot t_k) \cdot R_x(-5°) \cdot \begin{bmatrix} x_G \\ y_G \\ z_G \end{bmatrix}$$

展开为：

$$X_k = x_G \cdot \cos(\dot{\Omega}_e \cdot t_k) + y_G \cdot \sin(\dot{\Omega}_e \cdot t_k) \cdot \cos 5° + z_G \cdot \sin(\dot{\Omega}_e \cdot t_k) \cdot \sin(-5°)$$

$$Y_k = -x_G \cdot \sin(\dot{\Omega}_e \cdot t_k) + y_G \cdot \cos(\dot{\Omega}_e \cdot t_k) \cdot \cos 5° + z_G \cdot \cos(\dot{\Omega}_e \cdot t_k) \cdot \sin(-5°)$$

$$Z_k = -y_G \cdot \sin(-5°) + z_G \cdot \cos(-5°)$$

使用 RTKLib 的预计算常量：

$$\sin(-5°) = S_{-5} = -0.0871557427476582$$
$$\cos(-5°) = C_{-5} = 0.9961946980917456$$

> RTKLib 实现（`ephemeris.c` L223-234）：
> ```c
> if (sys==SYS_CMP && prn<=5) {
>     O = eph->OMG0 + eph->OMGd*tk - omge*eph->toes;    // Step 10 GEO
>     sinO=sin(O); cosO=cos(O);
>     xg = x*cosO - y*cosi*sinO;                          // Step 11a
>     yg = x*sinO + y*cosi*cosO;
>     zg = y*sin(i);
>     sino = sin(omge*tk); coso = cos(omge*tk);           // Step 11b
>     rs[0] =  xg*coso + yg*sino*COS_5 + zg*sino*SIN_5;
>     rs[1] = -xg*sino + yg*coso*COS_5 + zg*coso*SIN_5;
>     rs[2] = -yg*SIN_5   + zg*COS_5;
> }
> ```

### 3.4 卫星钟差计算

与 GPS 钟差公式相同，仅使用 BDS 的 $\mu$：

**Step 1: 计算时间差**

$$t = t_{recv} - t_{oc}$$

处理半周跳变。

**Step 2: 钟差多项式**

$$\Delta t_{sv} = a_{f0} + a_{f1} \cdot t + a_{f2} \cdot t^2$$

**Step 3: 相对论改正**

$$\Delta t_r = -\frac{2\sqrt{\mu \cdot A} \cdot e \cdot \sin E_k}{c^2}$$

> 注意：此处 $\mu$ 使用 BDS 值 3.986004418e14，而非 GPS 值。

**Step 4: 总钟差**

$$\Delta t_{sv} \leftarrow \Delta t_{sv} + \Delta t_r$$

---

## 4. 验证策略

### 4.1 验证数据

两个 BDS 样例文件均包含 GEO 卫星（PRN 1 / C01），可充分验证 GEO 分支：

| 文件 | PRN | 类型 | 说明 |
|------|-----|------|------|
| `data/pt.16c` | 1 | GEO | RINEX 2.11 格式 |
| `data/gths135a.18f` | C01 | GEO | RINEX 3.02 格式 |

> **局限**：当前数据集不包含 MEO/IGSO 卫星的星历，因此 MEO/IGSO 分支无法用实际数据验证。但该分支公式与 GPS 完全一致（仅常量不同），Phase 2 已验证逻辑正确性，MVP 中仅替换常量即可。

### 4.2 验证步骤

1. 用 MVP 计算观测时刻 = Toe 的 GEO 卫星位置与钟差；
2. 在 MVP 中打印所有中间变量（$t_k$, $n_0$, $n$, $M_k$, $E_k$, $v_k$, $u_k$, $r_k$, $i_k$, $\Omega_k$, $x_G$, $y_G$, $z_G$, $X_k$, $Y_k$, $Z_k$, $\Delta t_{sv}$, $\Delta t_r$）；
3. 与 RTKLib 风格 Python 复现逐项比对；
4. 误差超过阈值则逐步回溯中间变量定位偏差源。

### 4.3 GEO 卫星在 t = Toe 时的特殊行为

观测时刻取 $t = t_{oe}$ 时：
- $t_k = 0$，因此 $\sin(\dot{\Omega}_e \cdot t_k) = 0$，$\cos(\dot{\Omega}_e \cdot t_k) = 1$
- GEO 旋转矩阵简化为 $R_z(0) \cdot R_x(-5°) = R_x(-5°)$
- 此时 ECEF 坐标为：$X = x_G$，$Y = y_G \cdot C_{-5} + z_G \cdot S_{-5}$，$Z = -y_G \cdot S_{-5} + z_G \cdot C_{-5}$
- 这意味着即使是 Toe 时刻，GEO 的 Z 坐标也不等于 $z_G$，而是受到 5° 旋转的影响

---

## 5. 与 RTKLib 实现的差异对照

| 对照项 | 北斗 ICD | RTKLib 实现 | MVP 处理 |
|--------|---------|-------------|----------|
| 半周跳变 | "若 $t_k$ 超过 302400" | `timediff()` 函数处理 | 自行实现 $t_k$ 归化 |
| 开普勒迭代初值 | 未指定 | $E_0 = M_k$ | 同 RTKLib |
| 收敛判据 | 未指定 | $|E_{i+1} - E_i| < 10^{-14}$ | 同 RTKLib |
| GEO 判定 | PRN 1-5 | `sys==SYS_CMP && prn<=5` | PRN 1-5 为 GEO |
| GEO Step 10 | $\Omega_k = \Omega_0 + \dot{\Omega} \cdot t_k - \dot{\Omega}_e \cdot t_{oe}$ | `O=OMG0+OMGd*tk-omge*toes` | 同 ICD/RTKLib |
| GEO 旋转矩阵 | $R_z(\dot{\Omega}_e \cdot t_k) \cdot R_x(-5°)$ | 预计算 SIN_5/COS_5 | 同 RTKLib |
| MEO/IGSO Step 10 | $\Omega_k = \Omega_0 + (\dot{\Omega} - \dot{\Omega}_e) \cdot t_k - \dot{\Omega}_e \cdot t_{oe}$ | `O=OMG0+(OMGd-omge)*tk-omge*toes` | 同 ICD/RTKLib |
| 钟差迭代 | 未提及 | `eph2clk()` 迭代 2 次修正 t | 钟差在位置计算后一次性算出 |
| TGD 改正 | ICD 定义 TGD1/TGD2 | `eph2pos()` 不含 TGD | MVP 不含 TGD |
| $\dot{\Omega}_e$ 精度 | 7.292115e-5（6 位） | `OMGE_CMP=7.292115E-5` | 使用 BDS ICD 值 |

---

## 6. BDS ICD 公式中的关键注意事项

### 6.1 时间系统：BDT vs GPST

- BDT 起始历元为 2006-01-01 00:00:00 UTC，GPST 起始历元为 1980-01-06 00:00:00 UTC
- BDT = GPST - 14 s（且随闰秒累积差异不变，因为两者都不插闰秒）
- RINEX 文件中的 epoch 已经是 BDT，Toe 也是 BDT 周内秒
- **RTKLib 内部统一使用 GPST**，在读取 BDS RINEX 时会自动将 BDT 转换为 GPST（+14 s）
- **MVP 中**：由于我们直接使用 RINEX 解析的 Toe 作为观测时刻，$t_k = t_{obs} - t_{oe}$ 中的 BDT 偏移被抵消，不影响计算结果

### 6.2 GEO 旋转矩阵的物理含义

$R_x(-5°)$ 旋转不是物理意义上的坐标旋转，而是 CGCS2000 坐标系定义的一部分。北斗 GEO 卫星的参考轨道面与赤道面有约 1.5° 的偏差，加上坐标系定义的约 3.5° 偏置，总共约 5°。ICD 通过 $R_x(-5°)$ 将惯性系坐标转到 CGCS2000 地固系。

### 6.3 为什么 RTKLib 用 sin(-5°) 而不是 sin(5°)

RTKLib 的 `SIN_5 = sin(-5°)` 和 `COS_5 = cos(-5°)` 对应的是 $R_x(-5°)$ 旋转矩阵。展开 $R_x(\theta)$：

$$R_x(\theta) = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \cos\theta & -\sin\theta \\ 0 & \sin\theta & \cos\theta \end{bmatrix}$$

当 $\theta = -5°$ 时，$\sin(-5°) = -\sin(5°)$。RTKLib 直接使用 $S_{-5}$ 和 $C_{-5}$ 避免运行时计算三角函数。

---

## 7. 参考文档索引

| 文档 | 本地路径 | 对应内容 |
|------|---------|---------|
| 北斗 B1I ICD v3.0 | `doc/BeiDou Navigation Satellite System .pdf` | Section 5.2.4 (位置), Section 5.2.3 (钟差) |
| RTKLib ephemeris.c | `RTKLIB-master/src/ephemeris.c` | `eph2pos()` L181-250 (含 GEO 分支 L223-234) |
| RTKLib rtklib.h | `RTKLIB-master/src/rtklib.h` | 常量 CLIGHT, OMGE_CMP, MU_CMP, SIN_5, COS_5 |
| RTKLib 手册 | `doc/rtklib_manual.pdf.pdf` | 附录 E 公式描述 |
| IS-GPS-200N | `doc/IS-GPS-200N.pdf` | GPS 对比参考（Phase 2） |
