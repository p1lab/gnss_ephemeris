# Phase 1: RINEX 导航电文解析 MVP — 任务目标与格式规范

> 本文档面向 AI 编码助手，记录当前阶段的任务目标，以及从官方 RINEX 规范中提取的、**实现 MVP 所必需的最小格式定义**。

---

## 1. 当前阶段任务目标

**目标**：实现 `tests/mvps/rinex_parser_mvp.py`，使其能够读取 `data/` 下三个样例文件，提取**第一条完整星历**的全部字段，按规范应用比例因子后打印输出，供人工对照官方文档验证。

### 1.1 功能边界

| 做 | 不做 |
|---|---|
| 自动识别文件是 RINEX 2.x 还是 3.x | 不解析 Header 中的 ION ALPHA / ION BETA / DELTA-UTC 等可选记录 |
| 跳过 Header（顺序读到 `END OF HEADER`） | 不遍历所有星历（仅读第一条） |
| 按版本对应的列格式提取第一条星历的 8 行数据 | 不做异常处理（假设文件格式正确） |
| 将 Fortran D 格式（`1.234D+03`）转为 Python float | 不用面向对象（不定义 `RinexParser` 类） |
| 打印字段名、原始值、物理值、单位 | 不写 pytest（这是正式 `tests/test_rinex.py` 的事） |

### 1.2 输入文件

| 文件 | 版本 | 系统 | 说明 |
|------|------|------|------|
| `data/000A0070.20n` | RINEX 2.10 | GPS | 纯 GPS，PRN 用 1~2 位数字 |
| `data/pt.16c` | RINEX 2.11 | BDS | BDS-2，PRN 用 1~2 位数字，文件名 `.c` 标识系统 |
| `data/gths135a.18f` | RINEX 3.02 | BDS | BDS-2/BDS-3 混合，PRN 用 `Cxx` 格式 |

### 1.3 预期输出示例

```
=== 文件: data/000A0070.20n (RINEX 2.10, GPS) ===
PRN / SV ID        : 2
历元 (Toc)         : 2020-01-06 22:00:00.0
SV clock bias  af0 : -3.809658810496e-04  s
SV clock drift af1 : -7.275957614183e-12  s/s
SV clock rate  af2 : 0.000000000000e+00   s/s²
IODE               : 7.000000000000e+00
Crs                : -6.968750000000e+01  m
Delta-n            : 4.274106605125e-09  rad/s
M0                 : -2.027194694510e+00  rad
Cuc                : -3.527849912643e-06  rad
e (Eccentricity)   : 1.967201998923e-02
Cus                : 9.125098586082e-06  rad
sqrt(A)            : 7.178864983578e+03  sqrt(m)
Toe                : 1.656000000000e+05  s (of GPS week)
...（其余字段同理）
```

### 1.4 通过标准
- 每个字段的数值能与手动按规范切片读出的结果一致；
- 对 `000A0070.20n` 和 `pt.16c`，能使用同一套 RINEX 2.x 逻辑解析（仅文件名/Header 中的系统标识不同）；
- 对 `gths135a.18f`，能使用 RINEX 3.x 逻辑解析，卫星标识为 `C01`、`C02` 等；
- 所有角度类参数（Delta-n、M0、Cuc、e、Cus、OMEGA0、Cis、i0、omega、OMEGA DOT、IDOT）的单位在输出中明确标注为 rad 或 rad/s。

---

## 2. RINEX 2.x 导航电文数据记录格式

> 来源：`doc/rinex210.txt` Table A4、`doc/rinex211.txt` Table A4。RINEX 2.10 与 2.11 的导航电文数据记录在格式上完全一致，仅 Header 中版本号不同。

### 2.1 通用特征
- 每行固定 **80 字符**；
- 数值采用 **Fortran D 格式**（如 `0.123456789012D+03`），字段宽 **19 字符**，指数占 12 位；
- 允许 `E/e/D/d` 作为指数分隔符；
- 2.x 导航电文中，**GPS 与 BDS 的数据记录格式相同**，系统区别体现在：
  - 文件名后缀（`.n` = GPS，`.c` = BDS）；
  - Header 中的 `RINEX VERSION / TYPE` 行；
  - 具体常量含义（如 BDS 的 Toe 是 BDT 周秒，而非 GPS 周秒），但 RINEX 格式层面字段位置完全一致。

### 2.2 数据记录 8 行结构

| 行号 | 记录标签 | 字段内容（按顺序） | 格式 |
|:---:|---------|-------------------|------|
| 1 | `PRN / EPOCH / SV CLK` | PRN(1~2位), 年(2位), 月, 日, 时, 分, 秒(5.1), af0, af1, af2 | `I2,1X,I2.2,5(1X,I2),F5.1,3D19.12` |
| 2 | `BROADCAST ORBIT - 1` | IODE, Crs(m), Delta-n(rad/s), M0(rad) | `3X,4D19.12` |
| 3 | `BROADCAST ORBIT - 2` | Cuc(rad), e, Cus(rad), sqrt(A)(√m) | `3X,4D19.12` |
| 4 | `BROADCAST ORBIT - 3` | Toe(s of week), Cic(rad), OMEGA0(rad), Cis(rad) | `3X,4D19.12` |
| 5 | `BROADCAST ORBIT - 4` | i0(rad), Crc(m), omega(rad), OMEGA DOT(rad/s) | `3X,4D19.12` |
| 6 | `BROADCAST ORBIT - 5` | IDOT(rad/s), Codes on L2, GPS/BDS Week #, L2 P data flag | `3X,4D19.12` |
| 7 | `BROADCAST ORBIT - 6` | SV accuracy(m), SV health, TGD(s), IODC | `3X,4D19.12` |
| 8 | `BROADCAST ORBIT - 7` | Transmission time(s of week), Fit interval(h), spare, spare | `3X,4D19.12` |

### 2.3 字段详解（行 1）

```
 cols: 1- 2  I2     PRN / satellite number
       3- 3  1X     blank
       4- 5  I2.2   year (2 digits, 00-79→2000-2079, 80-99→1980-1999)
       6- 6  1X     blank
       7- 8  I2     month
       9- 9  1X     blank
      10-11  I2     day
      12-12  1X     blank
      13-14  I2     hour
      15-15  1X     blank
      16-17  I2     minute
      18-18  1X     blank
      19-23  F5.1   second
      24-42  D19.12 SV clock bias      af0  (seconds)
      43-61  D19.12 SV clock drift      af1  (sec/sec)
      62-80  D19.12 SV clock drift rate af2  (sec/sec²)
```

### 2.4 字段详解（行 2~8）

每行均为：`3X`（前导3空格）+ `4D19.12`（4个19.12字段），即列位置固定为：
- 列 4~22：第 1 个字段
- 列 23~41：第 2 个字段
- 列 42~60：第 3 个字段
- 列 61~79：第 4 个字段

> 注：列号从 1 开始计数。某些 Fortran 格式描述中 3X 表示跳过 3 列，实际数据从第 4 列开始。

### 2.5 单位与比例因子

RINEX 2.x 导航电文文件中，**所有星历参数在文件中已经是以实际物理单位存储**，解析时**无需额外乘比例因子**（这与观测文件不同）。但需特别注意：
- 角度参数（Delta-n, M0, Cuc, Cus, Cic, Cis, i0, omega, OMEGA0, OMEGA DOT, IDOT）的单位在 ICD 解算时使用的是 **radians**，RINEX 文件中存储的已是 radians（或 radians/sec），可直接使用；
- 但部分 ICD 文档中原始广播电文的单位是 **semi-circles**，RINEX 生成器已在写入时完成了 `× π` 的转换。因此从 RINEX 读出的值可直接代入 ICD 公式。

---

## 3. RINEX 3.x 导航电文数据记录格式

> 来源：`doc/rinex304.pdf` Appendix Table A6（GPS）、Table A14（BDS）。RINEX 3.02 与 3.04 的导航电文数据记录格式一致。

### 3.1 通用特征
- 每行仍接近 80 字符，但 3.x 不再严格限制 80 列（允许稍长）；
- 第一行以 **系统标识符 + PRN** 开头（如 `G02`、`C01`），替代了 2.x 的纯数字 PRN；
- 年份为 **4 位**；
- 秒为 **2 位整数**（`I2.2`），而非 2.x 的 `F5.1`；
- 浮点格式仍为 `D19.12`。

### 3.2 GPS 数据记录 8 行结构（Table A6）

| 行号 | 记录标签 | 字段内容（按顺序） | 格式 |
|:---:|---------|-------------------|------|
| 1 | `SV / EPOCH / SV CLK` | G+PRN, 年(4), 月, 日, 时, 分, 秒, af0, af1, af2 | `A1,I2.2,1X,I4,5(1X,I2.2),3D19.12` |
| 2 | `BROADCAST ORBIT - 1` | IODE, Crs(m), Delta-n(rad/s), M0(rad) | `4X,4D19.12` |
| 3 | `BROADCAST ORBIT - 2` | Cuc(rad), e, Cus(rad), sqrt(A)(√m) | `4X,4D19.12` |
| 4 | `BROADCAST ORBIT - 3` | Toe(s of GPS week), Cic(rad), OMEGA0(rad), Cis(rad) | `4X,4D19.12` |
| 5 | `BROADCAST ORBIT - 4` | i0(rad), Crc(m), omega(rad), OMEGA DOT(rad/s) | `4X,4D19.12` |
| 6 | `BROADCAST ORBIT - 5` | IDOT(rad/s), Codes on L2, GPS Week #, L2 P data flag | `4X,4D19.12` |
| 7 | `BROADCAST ORBIT - 6` | SV accuracy(m), SV health, TGD(s), IODC | `4X,4D19.12` |
| 8 | `BROADCAST ORBIT - 7` | Transmission time(s of GPS week), Fit interval(h), spare, spare | `4X,4D19.12` |

### 3.3 BDS 数据记录 8 行结构（Table A14）

BDS 与 GPS 的 3.x 格式**高度相似**，差异仅在于：
1. 系统标识符为 `C`（如 `C01`）；
2. 时间为 **BDT（北斗时）**；
3. 部分字段名称和含义有 BDS 特有定义。

| 行号 | 记录标签 | 字段内容（按顺序） | 格式 |
|:---:|---------|-------------------|------|
| 1 | `SV / EPOCH / SV CLK` | C+PRN, 年(4), 月, 日, 时, 分, 秒, af0, af1, af2 | `A1,I2.2,1X,I4,5(1X,I2.2),3D19.12` |
| 2 | `BROADCAST ORBIT - 1` | **AODE**, Crs(m), Delta-n(rad/s), M0(rad) | `4X,4D19.12` |
| 3 | `BROADCAST ORBIT - 2` | Cuc(rad), e, Cus(rad), sqrt(A)(√m) | `4X,4D19.12` |
| 4 | `BROADCAST ORBIT - 3` | Toe(s of **BDT** week), Cic(rad), OMEGA0(rad), Cis(rad) | `4X,4D19.12` |
| 5 | `BROADCAST ORBIT - 4` | i0(rad), Crc(m), omega(rad), OMEGA DOT(rad/s) | `4X,4D19.12` |
| 6 | `BROADCAST ORBIT - 5` | IDOT(rad/s), **Spare**, **BDT Week #**, **Spare** | `4X,4D19.12` |
| 7 | `BROADCAST ORBIT - 6` | SV accuracy(m), **SatH1**, **TGD1** B1/B3(s), **TGD2** B2/B3(s) | `4X,4D19.12` |
| 8 | `BROADCAST ORBIT - 7` | Transmission time(s of **BDT** week), **AODC**, spare, spare | `4X,4D19.12` |

### 3.4 2.x 与 3.x 的关键格式差异对比

| 对比项 | RINEX 2.x | RINEX 3.x |
|--------|-----------|-----------|
| 卫星标识 | `2`（纯数字） | `G02` / `C01`（系统字母+2位数字） |
| 年份 | 2 位（`20`） | 4 位（`2020`） |
| 秒 | `F5.1`（如 ` 0.0`） | `I2.2`（如 `00`） |
| 行首空白 | 行 2~8 前导 **3 空格**（`3X`） | 行 2~8 前导 **4 空格**（`4X`） |
| 星历主体字段 | GPS 与 BDS 格式相同 | GPS 与 BDS 格式基本相同，仅个别字段名不同 |
| Header 系统标识 | 由文件名后缀/空白隐含 | 明确写在第一行 `N: GNSS NAV DATA C: BEIDOU` |

### 3.5 对 `gths135a.18f` 的字段对照（实际数据验证）

```
C01 2018 05 14 23 00 00-2.979293931276D-04 4.932498853805D-11 0.000000000000D+00
     1.000000000000D+00-7.770468750000D+02-8.368205572928D-10-2.627930186309D+00
```

第一行解析：
- `C01` — 系统 C，PRN 01
- `2018` — 年
- `05` `14` `23` `00` `00` — 月日时分秒
- `-2.979293931276D-04` — af0 (s)
- `4.932498853805D-11` — af1 (s/s)
- `0.000000000000D+00` — af2 (s/s²)

第二行（`BROADCAST ORBIT - 1`）解析：
- 前导 1 空格（实际 `4X` 中因为该文件格式问题，可能是 1 空格而非 4，需按实际列位置调整）
- `1.000000000000D+00` — AODE
- `-7.770468750000D+02` — Crs (m)
- `-8.368205572928D-10` — Delta-n (rad/s)
- `-2.627930186309D+00` — M0 (rad)

> ⚠️ **注意**：RINEX 3.x 的 `4X` 前导空白在实际文件中可能因为字段对齐问题并不严格是 4 个空格（如第二行实际为 `     1.000...` 即 5 空格开头）。MVP 实现时，**建议按固定列位置切片**（而非按空格 split），以兼容各种对齐情况。

---

## 4. MVP 实现提示

### 4.1 读取策略
```python
# 伪代码
with open(path) as f:
    lines = f.readlines()

# 1. 识别版本
version_line = lines[0]
version = float(version_line[0:9].strip())  # e.g. "2.10" or "3.02"

# 2. 找到 END OF HEADER 的索引
for i, line in enumerate(lines):
    if "END OF HEADER" in line:
        header_end = i
        break

# 3. 读取第一条星历（8 行）
eph_lines = lines[header_end+1 : header_end+9]
```

### 4.2 切片策略
- **RINEX 2.x**：严格按 80 字符/行处理，字段位置固定（见 2.3、2.4 节）；
- **RINEX 3.x**：同样按固定列位置切片，但注意第一行中秒字段为 `I2.2`（占 2 列），其后紧跟 `D19.12`（无空格），与 2.x 的 `F5.1` 不同。

### 4.3 Fortran D → Python float
```python
def fortran_d_to_float(s: str) -> float:
    """将 Fortran D 格式字符串转为 Python float.
    例如: '0.123456789012D+03' -> 0.123456789012e+03
    """
    s = s.strip().replace('D', 'E').replace('d', 'e')
    return float(s)
```

---

## 5. 参考文档索引

| 文档 | 本地路径 | 对应内容 |
|------|---------|---------|
| RINEX 2.10 | `doc/rinex210.txt` | Table A3 (Header), Table A4 (Data Record) |
| RINEX 2.11 | `doc/rinex211.txt` | Table A3 (Header), Table A4 (Data Record) |
| RINEX 3.04 | `doc/rinex304.pdf` | Appendix Table A5 (Header), Table A6 (GPS Data), Table A14 (BDS Data) |
