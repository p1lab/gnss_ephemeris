# AGENTS.md — GNSS 卫星瞬时位置解算项目

> 本文档面向 AI 编码助手。阅读本文档前，默认你对本项目一无所知。

---

## 项目概览

本项目目标为：**根据 GNSS 导航电文（广播星历）解算卫星瞬时位置与钟差**。

- **当前状态**：Phase 1（RINEX 解析 MVP）已完成并验证通过；Phase 2（GPS 星历解算 MVP）与 Phase 3（BDS 星历解算 MVP）已完成，与 RTKLib C 原生输出比对：位置差 < 0.6 μm，钟差差 = 0 ns。
- **核心任务**：
  1. 读取并解析 RINEX 格式的导航电文文件；
  2. 按各系统官方 ICD（接口控制文件）定义的公式链，由星历参数计算卫星在地心地固（ECEF）坐标系下的瞬时位置与钟差；
  3. 输出结果供后续定位解算或分析使用。

---

## 技术栈与架构现状

- **编程语言**：**Python**（纯标准库，不引入 NumPy）。理由：RINEX 为固定列宽文本格式，Python 字符串处理效率高；星历解算仅涉及单颗卫星的数十次双精度浮点运算，计算量极小，纯 `float` 即可满足性能与精度要求；零外部依赖可保证代码逐行严格对应 ICD 公式，避免 NumPy 广播等带来的隐蔽行为差异。
- **交互形态**：**CLI（命令行）**。核心任务为文件进、计算、结果出，CLI 便于自动化测试与批量验证。输出格式优先支持 CSV / JSON，便于与 RTKLib 等参考结果做差异比对。
- **测试框架**：**pytest**。以 RTKLib 输出作为 golden reference，对 RINEX 解析与星历解算做单元测试与集成测试。
- **项目构建**：极简配置，使用 `pyproject.toml` 管理项目元数据即可，无需复杂构建系统。

### 目标代码组织（验证后建立）

待核心算法在 MVP 中验证通过后，再抽象为正式模块：
- `src/rinex/` — RINEX 文件解析（支持多版本、多系统）
- `src/ephemeris/` — 星历参数结构与 ICD 解算算法
- `src/utils/` — 时间系统转换、坐标转换等通用工具
- `src/cli.py` — 命令行入口
- `tests/` — pytest 单元测试与集成测试

---

## 已有资产

### 数据文件（`data/`）

| 文件名 | 格式 | 内容说明 |
|--------|------|----------|
| `000A0070.20n` | RINEX 2.10 | GPS 导航电文，2020-01-06 观测，含多颗卫星星历 |
| `gths135a.18f` | RINEX 3.02 | 北斗（BDS）导航电文，2018-05-14 观测，含 IONOSPHERIC CORR 与 TIME SYSTEM CORR |
| `pt.16c` | RINEX 2.11 | BDS 导航电文，2016-11-08 观测，含 TIME SYSTEM CORR |

> 注意：`.n` / `.f` / `.c` 均为 RINEX 导航电文扩展名，分别对应不同系统与版本。文件采用固定 80 字符/行的文本格式，由 Header（元数据）和 Data（星历参数主体）两部分组成。

### 报告（`reports/`）

| 本地文件名 | 内容说明 |
|------------|----------|
| `phase1_rinex_parser_spec.md` | **Phase 1 任务目标与 RINEX 格式规范提取**。记录当前 MVP 阶段的目标边界、从官方文档提取的 2.x/3.x 导航电文字段定义、列位置切片规则、单位与比例因子说明，供 `rinex_parser_mvp.py` 实现时直接对照。 |
| `phase2_gps_eph2pos_spec.md` | **Phase 2 任务目标与 GPS 星历解算规范提取**。记录 IS-GPS-200N 公式链、常量定义、算法步骤，供 `gps_eph2pos_mvp.py` 实现时直接对照。 |
| `phase3_bds_eph2pos_spec.md` | **Phase 3 任务目标与 BDS 星历解算规范提取**。记录北斗 B1I ICD v3.0 公式链、常量定义、GEO/MEO/IGSO 分支算法步骤，供 `bds_eph2pos_mvp.py` 实现时直接对照。 |

### MVP 代码（`tests/mvps/`）

| 文件名 | 状态 | 内容说明 |
|--------|------|----------|
| `rinex_parser_mvp.py` | ✅ 已验证通过 | RINEX 2.x/3.x 导航电文解析，支持自动版本识别、首条星历提取、Fortran D 格式转换。三个样例文件逐字段核对正确。 |
| `gps_eph2pos_mvp.py` | ✅ 已验证通过 | GPS 广播星历 → ECEF 位置/钟差解算，按 IS-GPS-200N 公式链。与 RTKLib C 原生比对：位置差 0.47 μm，钟差差 0 ns |
| `bds_eph2pos_mvp.py` | ✅ 已验证通过 | BDS 广播星历 → ECEF 位置/钟差解算，按北斗 B1I ICD v3.0 公式链。含 GEO(PRN 1-5)/MEO/IGSO 分支。与 RTKLib C 原生比对：位置差 0.38 μm，钟差差 0 ns |

### 文档（`doc/`）

已下载的关键参考文档：

| 本地文件名 | 对应官方文档 | 备注 |
|------------|--------------|------|
| `rinex210.txt` | RINEX 2.10 格式规范 | 解析 `000A0070.20n` |
| `rinex211.txt` | RINEX 2.11 格式规范 | 解析 `pt.16c` |
| `BeiDou Navigation Satellite System .pdf` | 北斗 B1I ICD v3.0（2018-06） | BDS 星历解算公式链与常量 |
| `IS-GPS-200N.pdf` | IS-GPS-200N（2025-07） | GPS 星历解算公式链与常量 |
| `UNOOSA_ICD_index.pdf` | UNOOSA 官方 ICD 汇总索引 | 多系统文档总览 |
| `rinex304.pdf` | RINEX 3.04 格式规范 | 解析 `gths135a.18f`（3.02 向后兼容） |
| `rtklib_manual.pdf.pdf` | RTKLib 手册 | 工程实现参考（附录含公式） |

### 正式模块（`src/gnss_ephemeris/`，Phase 4 已完成）

| 路径 | 状态 | 内容说明 |
|------|------|----------|
| `src/gnss_ephemeris/utils/constants.py` | ✅ 已实现 | 物理常数与算法参数 |
| `src/gnss_ephemeris/utils/fortran.py` | ✅ 已实现 | Fortran D→float 转换 |
| `src/gnss_ephemeris/utils/kepler.py` | ✅ 已实现 | 开普勒方程求解器（公共） |
| `src/gnss_ephemeris/utils/time.py` | ✅ 已实现 | 周内秒归一化 |
| `src/gnss_ephemeris/rinex/models.py` | ✅ 已实现 | 数据契约层：`Ephemeris` / `GPSEphemeris` / `BDSEphemeris` |
| `src/gnss_ephemeris/rinex/parser.py` | ✅ 已实现 | RINEX 2.x/3.x 全量解析 + 自动版本识别 |
| `src/gnss_ephemeris/ephemeris/gps.py` | ✅ 已实现 | GPS 广播星历 → ECEF 位置/钟差 |
| `src/gnss_ephemeris/ephemeris/bds.py` | ✅ 已实现 | BDS 广播星历 → ECEF 位置/钟差（含 GEO/MEO/IGSO） |
| `src/gnss_ephemeris/ephemeris/__init__.py` | ✅ 已实现 | 统一入口 `eph2pos()`，自动分派 |
| `src/gnss_ephemeris/cli.py` | ✅ 已实现 | CLI 入口：`parse` / `compute` 子命令 |
| `tests/test_utils.py` | ✅ 36 用例 | Fortran 转换、开普勒求解、时间归一化、常量验证 |
| `tests/test_rinex.py` | ✅ 26 用例 | 契约层类型测试 + GPS/BDS R2/R3 解析回归 |
| `tests/test_ephemeris.py` | ✅ 15 用例 | 分派测试 + GPS/BDS 解算 + 一致性验证 |

> 注意：`pyproject.toml` 的 `[project.scripts]` 入口为 `gnss-eph = "gnss_ephemeris.cli:main"`。

---

## 实现规范与参考标准

本项目**不依赖假设**，所有解析逻辑与解算算法必须严格对应官方规范。关键参考文献如下：

### 1. RINEX 格式规范（负责“读取参数”）
- **总入口**：`https://igs.org/formats-and-standards/`
- **RINEX 2.11**：`https://files.igs.org/pub/data/format/rinex211.txt`
- **RINEX 3.04**：`ftp://igs.org/pub/data/format/rinex304.pdf`
- **RINEX 4.02**：`https://files.igs.org/pub/data/format/rinex_4.02.pdf`

> RINEX 只定义字段语义、位置、单位与比例因子，**不定义**卫星位置解算算法。

### 2. 各 GNSS 系统 ICD（负责“解算算法”）

| 系统 | 官方文档 | 参考网址 |
|------|----------|----------|
| GPS | IS-GPS-200N（2025-07 版） | `https://www.gps.gov/interface-control-documents-icds-interface-specifications-iss`<br>直接 PDF：`https://www.gps.gov/sites/default/files/2025-07/IS-GPS-200N.pdf` |
| 北斗（BDS） | 北斗卫星导航系统空间信号接口控制文件 | `http://en.beidou.gov.cn/SYSTEMS/Officialdocument/` |
| GLONASS | ICD GLONASS | `http://russianspacesystems.ru/wp-content/uploads/2016/08/ICD_GLONASS_eng_v5.1.pdf` |
| Galileo | Galileo OS SIS ICD | `https://www.gsc-europa.eu/electronic-library/programme-reference-documents` |
| 汇总 | UNOOSA 官方索引 | `https://www.unoosa.org/res/oosadoc/data/documents/2021/stspace/stspace75rev_1_0_html/st_space_75rev01E.pdf` |

### 3. 工程实现模板：RTKLib

- **仓库**：`https://github.com/tomojitakasu/RTKLIB`
- **核心参考文件**：`src/ephemeris.c`
- **关键函数**：
  - `eph2pos()` — GPS / Galileo / 北斗 / QZSS 广播星历 → 卫星位置
  - `geph2pos()` — GLONASS 星历 → 卫星位置（GLONASS 采用状态向量而非开普勒根数）
  - `eph2clk()` — 广播星历 → 卫星钟差
- **手册**：`https://rtkexplorer.com/pdfs/manual_demo5.pdf`（附录含数学公式描述）

### 数据流逻辑

```
RINEX 文件 ──► 提取参数 ──► 按 ICD 公式链计算 ──► 卫星位置/钟差
     │                              │
     └──────── 格式定义 ────────────┘      └──── 算法定义
              (IGS)                          (各系统官方)
                                    └──── 工程实现
                                          (RTKLib)
```

### 模块间数据契约：继承式 dataclass

解析模块（`rinex`）与解算模块（`ephemeris`）之间是**生产者-消费者**关系，需要一个显式契约来约束接口。当前 MVP 使用隐式的 `dict`，正式模块改用**继承式 dataclass**。

#### 架构

```
                 ┌───────────────────────┐
                 │  rinex/models.py       │  ← 契约层（两个模块的共同依赖）
                 │  Ephemeris (基类)       │
                 │  GPSEphemeris(子类)     │
                 │  BDSEphemeris(子类)     │
                 └──────┬─────────┬────────┘
                        │         │
            ┌───────────┘         └───────────┐
            ▼                                 ▼
  ┌──────────────────┐             ┌──────────────────┐
  │  rinex/parser    │             │  ephemeris/       │
  │  产出 Ephemeris   │             │  消费 Ephemeris   │
  │  (GPS/BDS子类)    │             │  gps_eph2pos()    │
  └──────────────────┘             │  bds_eph2pos()    │
                                   │  eph2pos() 分派   │
                                   └──────────────────┘
```

- **`rinex` 不依赖 `ephemeris`**，**`ephemeris` 不依赖 `rinex`**，两者共同依赖 `rinex/models.py` 中的 dataclass 定义。
- `models.py` 放在 `rinex/` 下而非独立的 `models/` 包中，因为星历数据结构的字段语义由 RINEX 规范定义，与解析模块天然同源。

#### 类设计

```python
@dataclass
class Ephemeris:
    """广播星历基类：GPS/BDS/Galileo 共享的开普勒根数字段."""
    system: str          # "GPS" / "BDS" / ...
    prn: int             # 卫星号
    epoch: tuple         # (year, month, day, hour, minute, second)
    toe: float           # 星历参考时间 (sow)
    af0: float; af1: float; af2: float          # 钟差多项式系数
    sqrt_a: float; e: float; m0: float         # 轨道根数
    delta_n: float                               # 平运动校正
    omega: float; omega0: float; omega_dot: float  # 近地点幅角 / 升交点赤经 / 变率
    i0: float; idot: float                       # 轨道倾角 / 变率
    cuc: float; cus: float                       # 纬度幅角摄动
    crc: float; crs: float                       # 轨道半径摄动
    cic: float; cis: float                       # 轨道倾角摄动

@dataclass
class GPSEphemeris(Ephemeris):
    """GPS 专有字段."""
    iode: float; iodc: float; tgd: float
    gps_week: float; codes_on_l2: float; l2_p_flag: float
    sv_accuracy: float; sv_health: float
    trans_time: float; fit_interval: float

@dataclass
class BDSEphemeris(Ephemeris):
    """BDS 专有字段."""
    aode: float; aodc: float
    tgd1: float; tgd2: float; sath1: float
    bdt_week: float; sv_accuracy: float
    trans_time: float
```

#### 设计决策：为什么选继承式 dataclass 而非 Protocol / ABC？

| 方案 | 适用场景 | 本项目评估 |
|------|----------|-----------|
| `Protocol`（结构化子类型） | 跨库边界松耦合，隐式接口 | GPS/BDS 共享 20+ 同名字段，`Protocol` 无法表达"基类字段+专有字段"的继承关系；适合单库内 |
| `ABC`（抽象基类） | 有行为的接口，需强制子类实现方法 | 星历是**纯数据载体**（全是 `float` 字段，无行为），`ABC` 增加复杂度但无收益 |
| **继承式 `dataclass`** | 单库内数据结构，字段继承自然表达 | ✅ 基类含共享字段、子类追加专有字段，`isinstance` 分派直观，类型检查器友好 |

#### 分派策略

`ephemeris/` 的统一入口 `eph2pos(t_obs, eph)` 根据 `eph` 的类型分派：

```python
def eph2pos(t_obs: float, eph: Ephemeris) -> tuple:
    if isinstance(eph, GPSEphemeris):
        return gps_eph2pos(t_obs, eph)
    elif isinstance(eph, BDSEphemeris):
        return bds_eph2pos(t_obs, eph)
    raise TypeError(f"不支持的星历类型: {type(eph)}")
```

未来扩展 Galileo 时：新增 `GalileoEphemeris(Ephemeris)` + `galileo_eph2pos()` + 在 `eph2pos` 中增加分支即可。

---

## 代码风格与开发约定（建议）

- **注释与文档**：优先使用**中文**撰写注释与文档，与现有 `task.md` 保持一致。
- **变量命名**：涉及 RINEX 字段时，建议保留标准中的符号名（如 `M0`, `Delta-n`, `e`, `Cuc`, `Cus`, `Crc`, `Crs`, `Cic`, `Cis`, `i0`, `OMEGA`, `omega`, `OMEGA-DOT`, `IDOT` 等），或建立明确的映射表。
- **数值精度**：星历解算涉及大量双精度浮点运算，注意保持与 ICD 一致的常量精度（如地球引力常数 `GM`、地球自转角速度 `Omega-e` 等）。
- **时间系统**：注意区分 GPS 时、北斗时（BDT）、GLONASS 时、UTC 与 TAI 的转换关系，尤其在处理跨系统数据时。
- **版本兼容**：RINEX 2.x 与 3.x/4.x 的 Header 字段、卫星标识方式、行格式均有差异，解析层需做好版本适配。

---

## 测试策略（建议）

- **单元测试**：针对 RINEX 解析器，使用已有样例文件做回归测试，确保 Header 字段与每条星历参数解析值正确。
- **集成测试**：使用已知历元的参考星历，对比 `eph2pos()` / `eph2clk()` 输出与 RTKLib 或官方工具的结果，验证位置与钟差误差在厘米/毫米级以内。
- **边界测试**：处理闰秒、跨天、不同卫星系统混排、缺失可选 Header 字段等边界情况。

---

## 安全与注意事项

- **输入校验**：RINEX 文件来自外部数据源，解析时必须校验文件类型标识、版本号、行长度与字段范围，防止非法输入导致数值溢出或数组越界。
- **常量来源**：所有物理常数与算法系数必须从对应系统 ICD 中获取，禁止随意近似或混用不同系统的常量。
- **GLONASS 特殊处理**：GLONASS 采用状态向量（位置、速度、加速度）而非开普勒根数，需单独实现 `geph2pos()` 类算法，不可与 GPS/BDS/Galileo 共用同一套根数传播流程。
- **RINEX 字段粘连**：部分 RINEX 生成器在行1中，当 af0 为负数时，F5.1 秒字段的尾部空格会被 af0 的负号"吞没"（如 ` 0.0-3.809...D-04`），导致固定列切片 `l1[18:23]` 错误。解决方案：从行尾倒推 3×D19.12 字段提取 af0/af1/af2，秒取剩余部分 `l1[18:-57]`。
- **空白 spare 字段**：RINEX 3.x BDS 星历的 spare 字段可能为全空格，`fortran_d_to_float("")` 需返回 0.0 而非报错。

---

## 开发策略：MVP 先行，验证后再抽象

本项目采用 **"先写 MVP（最小可行验证），后建正式模块"** 的迭代策略：

1. **在 `tests/mvps/` 中逐个验证核心功能**：
   - `rinex_parser_mvp.py` — ✅ **已验证通过**。快速解析样例文件的第一条星历，逐字段打印，肉眼对照 RINEX 规范；
   - `gps_eph2pos_mvp.py` — ✅ **已验证通过**。用解析出的 GPS 星历参数，严格按 IS-GPS-200N 手算卫星位置与钟差，与 RTKLib C 原生输出比对：位置差 0.47 μm，钟差差 0 ns。实现中发现并修复了 ECEF Y 分量公式错误（第二项应使用 cos(Ωk) 而非 sin(Ωk)）。
   - `bds_eph2pos_mvp.py` — ✅ **已验证通过**。用解析出的 BDS 星历参数，严格按北斗 B1I ICD v3.0 计算卫星位置与钟差，与 RTKLib C 原生输出比对：位置差 0.38 μm，钟差差 0 ns。实现了 GEO(PRN 1-5)专用 Step 10/11（5° 旋转矩阵）和 MEO/IGSO 分支。

2. **MVP 通过标准**：
   - 位置误差相对 RTKLib 在 **厘米级以内**；
   - 钟差误差在 **亚纳秒或纳秒级以内**；
   - 所有常量与公式编号能在代码注释中一一对应到 ICD / RINEX 规范。

3. **验证通过后抽象到 `src/`**：
   - 将 MVP 中经检验正确的逻辑封装为正式模块（`rinex/`、`ephemeris/`、`utils/`）；
   - 保留 MVP 作为回归测试与文档参考，但不作为生产代码依赖。

> 该策略避免过早抽象，确保每一处数值计算都在真实数据上得到验证后再固化接口。

---

## 下一步行动建议

1. ~~确定技术栈~~ — **已完成**：Python + CLI + pytest。
2. ~~初始化项目骨架~~ — **已完成**：`pyproject.toml`、`tests/mvps/`、`src/`（先留空，待 MVP 验证后填充）。
3. ~~编写第一个 MVP~~ — **已完成**：`tests/mvps/rinex_parser_mvp.py`，解析三个样例文件的第一条星历，逐字段与原始数据核对通过。
4. ~~编写第二个 MVP~~ — **已完成**：`tests/mvps/gps_eph2pos_mvp.py`，按 IS-GPS-200N 计算卫星 ECEF 位置与钟差，与 RTKLib 风格 Python 复现比对一致。
5. ~~编写第三个 MVP~~ — **已完成**：`tests/mvps/bds_eph2pos_mvp.py`，按北斗 B1I ICD v3.0 计算卫星 ECEF 位置与钟差，含 GEO/MEO/IGSO 分支，与 RTKLib 风格 Python 复现比对一致。

---

### Phase 4：抽象正式模块 — ✅ 已完成

> **总体思路**：自底向上迁移——先提取公共工具（无依赖），再迁移 RINEX 解析器（依赖 utils），再迁移星历解算（依赖 utils），最后实现 CLI（依赖全部模块）。每个子步骤完成后立即编写对应单元测试，用 MVP 相同的样例数据 + RTKLib 参考结果做回归验证。

#### 4.1 `src/utils/` — 公共工具模块

| 迁移来源 | 目标 | 说明 |
|----------|------|------|
| `rinex_parser_mvp.fortran_d_to_float` | `utils/fortran.py` | Fortran D→float 转换，含空字段返回 0.0 的处理 |
| GPS/BDS MVP 中的开普勒方程迭代 | `utils/kepler.py` | 提取公共 `_solve_kepler(Mk, e, rtol, max_iter)` 函数，消除 GPS 与 BDS 之间的重复代码 |
| GPS/BDS MVP 中的共享常量 | `utils/constants.py` | `CLIGHT`, `RTOL_KEPLER`, `MAX_ITER_KEPLER`；GPS/BDS 各自的 `MU`/`OMGE` 留在 ephemeris 模块中（系统相关） |
| — | `utils/time.py` | 预留：周内秒归一化（`tk` 半周处理）目前内联在 eph2pos 中，可提取为 `normalize_sow(t, half_week=302400)` 供复用 |

**测试**：`tests/test_utils.py`
- `fortran_d_to_float`：正常 E/D 格式、大小写混合、空白字段、极值
- `solve_kepler`：低/中/高偏心率，验证收敛性与迭代次数
- `normalize_sow`：正/负半周跨越

#### 4.2 `src/rinex/` — RINEX 解析器模块 + 数据契约层

本步骤包含两部分：**数据契约**（`models.py`）和**解析逻辑**（`parser.py`）。契约层必须先于解析逻辑完成，因为 4.3 星历解算模块依赖它。

##### 4.2a 数据契约：`rinex/models.py`

定义 `Ephemeris` 基类及其子类（详见上方"模块间数据契约"章节），替代 MVP 中的隐式 `dict`。这是 `rinex` 与 `ephemeris` 两个模块的**共同依赖**。

| 内容 | 说明 |
|------|------|
| `Ephemeris` 基类 | GPS/BDS/Galileo 共享的 ~20 个开普勒根数字段 + `system` + `prn` + `epoch` |
| `GPSEphemeris(Ephemeris)` | 追加 `iode`, `iodc`, `tgd`, `gps_week` 等 GPS 专有字段 |
| `BDSEphemeris(Ephemeris)` | 追加 `aode`, `aodc`, `tgd1`, `tgd2`, `sath1` 等 BDS 专有字段 |

**为什么放在 `rinex/` 而非独立包？** 星历数据结构的字段语义由 RINEX 规范定义，与解析模块天然同源。`ephemeris/` 仅消费这些 dataclass，不依赖 `rinex/parser.py`。

##### 4.2b 解析逻辑：`rinex/parser.py`

| 迁移来源 | 目标 | 说明 |
|----------|------|------|
| `rinex_parser_mvp._find_end_of_header` | `rinex/parser.py` | 内部函数 |
| `rinex_parser_mvp._parse_clock_line_r2` | `rinex/parser.py` | RINEX 2.x 行 1 解析（含 af0 负号粘连修复） |
| `rinex_parser_mvp._parse_clock_line_r3` | `rinex/parser.py` | RINEX 3.x 行 1 解析 |
| `rinex_parser_mvp.parse_rinex2_first_eph` | `rinex/parser.py` | 升级为 `parse_rinex2(lines) -> list[GPSEphemeris]`，支持解析**全部**星历记录 |
| `rinex_parser_mvp.parse_rinex3_first_eph` | `rinex/parser.py` | 升级为 `parse_rinex3(lines) -> list[BDSEphemeris]`，支持解析**全部**星历记录 |
| — | `rinex/parser.py` | 新增 `parse_nav_file(path) -> list[Ephemeris]`，根据首行版本号自动分派 2.x/3.x 解析 |
| `rinex_parser_mvp.print_*` | 不迁移 | 打印函数仅用于 MVP 调试，正式模块用 `__repr__` / `logging` 替代 |

**关键设计决策**：
- **dict → dataclass**：MVP 使用 `dict` 是为了快速迭代，正式模块需用 `@dataclass` 提供类型安全与字段文档
- **单条 → 全量解析**：MVP 仅解析第一条星历，正式版需遍历全文件返回 `list[Ephemeris]`
- **版本自动识别**：`parse_nav_file(path)` 根据首行版本号 + 卫星系统标识自动分派，返回对应子类的列表

**测试**：`tests/test_rinex.py`
- 用 `data/` 三个样例文件逐字段回归比对（断言每个参数值与 MVP 输出完全一致）
- 全量解析：验证解析出的星历条数与文件中实际条数一致
- 边界：空文件、缺 END OF HEADER、行数不足 8 行
- **契约测试**：验证 `parse_nav_file` 返回的对象类型正确（`GPSEphemeris` / `BDSEphemeris`），`isinstance` 断言

#### 4.3 `src/ephemeris/` — 星历解算模块

| 迁移来源 | 目标 | 说明 |
|----------|------|------|
| `gps_eph2pos_mvp.gps_eph2pos` | `ephemeris/gps.py` | 函数签名改为 `(t_obs, eph: GPSEphemeris)`，内部调用 `utils.kepler.solve_kepler` 和 `utils.time.normalize_sow` |
| `gps_eph2pos_mvp` 中的 GPS 常量 | `ephemeris/gps.py` | `MU_GPS`, `OMGE` 作为模块级常量 |
| `bds_eph2pos_mvp.bds_eph2pos` | `ephemeris/bds.py` | 函数签名改为 `(t_obs, eph: BDSEphemeris)` |
| `bds_eph2pos_mvp` 中的 BDS 常量 + GEO 旋转 | `ephemeris/bds.py` | `MU_CMP`, `OMGE_CMP`, `SIN_5`, `COS_5`, `_is_geo` |
| — | `ephemeris/__init__.py` | 统一入口 `eph2pos(t_obs, eph)`，根据 `eph` 类型自动分派 GPS/BDS |

**关键设计决策**：
- **返回值**：保留 `(xyz, dts, intermediates)` 三元组，`intermediates` 对调试至关重要
- **BDS GEO 判定**：从 `Ephemeris` dataclass 的 `system` + `prn` 推断（`eph.system == "BDS" and 1 <= eph.prn <= 5`），而非硬编码范围
- **仅依赖契约层**：`ephemeris/` 仅 import `rinex/models.py` 中的 dataclass，**不 import `rinex/parser.py`**——解算模块不知道星历数据从何而来（文件解析 / 手动构造 / 网络获取），只关心数据结构

**测试**：`tests/test_ephemeris.py`
- GPS/BDS 各用 MVP 同样的 (t_obs=Toe) 测试用例，断言位置差 < 1 μm、钟差差 < 1 ns（与 RTKLib C 原生比对）
- 增加 t_obs = Toe ± 3600 的外推测试
- BDS GEO vs MEO/IGSO 两条路径分别覆盖

#### 4.4 `src/cli.py` — 命令行入口

实现 `gnss-eph` 命令，支持以下用法：

```bash
# 解析 RINEX 文件，输出所有星历参数
gnss-eph parse data/000A0070.20n

# 计算指定卫星在指定历元的 ECEF 位置与钟差
gnss-eph compute data/000A0070.20n --system GPS --prn 2 --epoch "2020-01-06T22:00:00"

# 输出中间变量（调试用）
gnss-eph compute ... --verbose
```

- 纯标准库 `argparse` 实现，不引入第三方 CLI 框架
- 输出格式：默认 JSON，`--format csv` 可选

**测试**：`tests/test_cli.py`（ subprocess 调用验证）

#### 4.5 集成验证

- 端到端流水线：`RINEX 文件 → parse_nav_file → eph2pos → 输出`
- 用三个样例文件 + RTKLib C 原生输出做全链路对比
- 确认 `pip install -e .` 后 `gnss-eph` 命令可正常执行

---

### 执行顺序与依赖关系

```
4.1 utils ─────────────┬──────────────┬──────────→ 4.4 cli
                       │              │
4.2a rinex/models.py ──┤              │
  (契约层，4.2b/4.3    │              │
   共同依赖)            │              │
                       ▼              │
4.2b rinex/parser.py ──┘              │
  (依赖 4.1 + 4.2a)                   │
                                       │
4.3 ephemeris/ ────────────────────────┘
  (依赖 4.1 + 4.2a，不依赖 4.2b)
```

- 4.1 无依赖，优先实现
- 4.2a（契约层）仅依赖标准库 `dataclasses`，可紧随 4.1 完成
- 4.2b 依赖 4.1（`fortran_d_to_float`）+ 4.2a（产出 `Ephemeris` 对象）
- 4.3 依赖 4.1（`solve_kepler`, `normalize_sow`）+ **4.2a**（`Ephemeris` dataclass 类型签名），**不依赖 4.2b**（解算模块不知道数据来源）
- 4.4 依赖 4.1~4.3 全部模块
- 每个子步骤完成后立即编写对应单元测试，**测试通过后再进入下一步**
