# gnss-ephemeris

GNSS 广播星历解析与卫星瞬时位置/钟差解算工具。

根据 RINEX 导航电文文件中的广播星历参数，按各系统官方 ICD 定义的公式链，计算卫星在地心地固（ECEF）坐标系下的瞬时位置与钟差。

## 特性

- **零外部依赖**：纯 Python 标准库实现，`pip install` 即可用
- **多系统支持**：GPS（IS-GPS-200N）、北斗 BDS（B1I ICD v3.0）
- **多版本 RINEX**：自动识别 RINEX 2.x / 3.x 格式
- **高精度验证**：与 RTKLib C 原生输出比对，位置差 < 1 μm，钟差差 = 0 ns

## 安装

```bash
git clone <repo-url>
cd GNSS_data
pip install -e .
```

安装后即可使用 `gnss-eph` 命令，或通过 Python 模块方式调用：

```bash
gnss-eph --help
# 等价于
python -m gnss_ephemeris.cli --help
```

> **注意**：不要直接 `python cli.py` 运行，这会导致包导入失败。请使用上述两种方式。

## 快速开始

### 解析 RINEX 文件

```bash
# 输出文件中所有星历参数（JSON 格式）
gnss-eph parse data/000A0070.20n

# CSV 格式输出
gnss-eph parse data/gths135a.18f --format csv
```

### 计算卫星位置与钟差

```bash
# 计算 GPS PRN 2 在 toe 时刻的位置（默认使用星历参考时间）
gnss-eph compute data/000A0070.20n --system GPS --prn 2

# 指定观测历元（周内秒）
gnss-eph compute data/000A0070.20n --system GPS --prn 2 --epoch 504000

# 输出中间变量（开普勒方程迭代值、偏近点角等）
gnss-eph compute data/000A0070.20n --system GPS --prn 2 --verbose

# 计算 BDS 卫星
gnss-eph compute data/pt.16c --system BDS --prn 1
```

## 命令参考

```
gnss-eph [-h] {parse,compute} ...

子命令:
  parse          解析 RINEX 导航电文文件
  compute        计算卫星 ECEF 位置与钟差

通用选项:
  -h, --help     显示帮助信息
```

### `parse` — 解析 RINEX 文件

```
gnss-eph parse <file> [--format {json,csv}]
```

| 参数 | 说明 |
|------|------|
| `file` | RINEX 导航电文文件路径 |
| `--format` | 输出格式：`json`（默认）或 `csv` |

输出包含文件中所有星历记录的完整参数（轨道根数、摄动改正、钟差系数等）。

### `compute` — 计算卫星位置与钟差

```
gnss-eph compute <file> [--system SYS] [--prn N] [--epoch SOW] [--verbose] [--format FMT]
```

| 参数 | 说明 |
|------|------|
| `file` | RINEX 导航电文文件路径 |
| `--system` | 卫星系统：`GPS` 或 `BDS`（不指定则输出所有卫星） |
| `--prn` | 卫星 PRN 号（不指定则输出该系统所有卫星） |
| `--epoch` | 观测历元，周内秒数值（不指定则使用各星历的 `toe`） |
| `--verbose` | 输出中间变量（平近点角、偏近点角、升交点赤经等） |
| `--format` | 输出格式：`json`（默认）或 `csv` |

输出字段：

| 字段 | 说明 |
|------|------|
| `system` | 卫星系统 |
| `prn` | 卫星号 |
| `t_obs` | 观测历元（周内秒） |
| `X`, `Y`, `Z` | ECEF 坐标（m） |
| `dts` | 卫星钟差（s） |

加 `--verbose` 时额外输出 `intermediates` 对象，包含解算过程中的所有中间变量。

## Python API

除 CLI 外，也可在 Python 中直接调用各模块：

```python
from gnss_ephemeris.rinex.parser import parse_nav_file
from gnss_ephemeris.ephemeris import eph2pos

# 解析 RINEX 文件
eph_list = parse_nav_file("data/000A0070.20n")

# 筛选 GPS PRN 2
gps_prn2 = [e for e in eph_list if e.system == "GPS" and e.prn == 2]

# 计算卫星位置与钟差
(X, Y, Z), dts, intermediates = eph2pos(gps_prn2[0].toe, gps_prn2[0])
print(f"X = {X:.3f} m, Y = {Y:.3f} m, Z = {Z:.3f} m")
print(f"钟差 = {dts:.12e} s")
```

### 数据契约

解析模块与解算模块通过 `Ephemeris` dataclass 系列连接：

```python
from gnss_ephemeris.rinex.models import Ephemeris, GPSEphemeris, BDSEphemeris

# isinstance 分派
if isinstance(eph, GPSEphemeris):
    ...  # GPS 专有字段：iode, iodc, tgd, gps_week, ...
elif isinstance(eph, BDSEphemeris):
    ...  # BDS 专有字段：aode, aodc, tgd1, tgd2, ...
```

## 支持的文件格式

| 扩展名 | RINEX 版本 | 卫星系统 | 示例 |
|--------|-----------|---------|------|
| `.n`, `.YYn` | 2.x | GPS | `000A0070.20n` |
| `.c`, `.YYc` | 2.x | BDS | `pt.16c` |
| `.gnn`, `.f` | 3.x | 多系统 | `gths135a.18f` |

系统识别优先级：RINEX 3.x 首行卫星标识 → 文件扩展名约定。

## 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

当前测试覆盖：77 个用例，涵盖工具函数、RINEX 解析、星历解算全链路。

## 项目结构

```
src/gnss_ephemeris/
├── __init__.py
├── cli.py                  # CLI 入口
├── rinex/
│   ├── __init__.py
│   ├── models.py           # 数据契约层（Ephemeris 基类及子类）
│   └── parser.py           # RINEX 2.x/3.x 解析器
├── ephemeris/
│   ├── __init__.py         # 统一入口 eph2pos()
│   ├── gps.py              # GPS 星历解算（IS-GPS-200N）
│   └── bds.py              # BDS 星历解算（B1I ICD v3.0）
└── utils/
    ├── __init__.py
    ├── constants.py         # 物理常数
    ├── fortran.py           # Fortran D 格式转换
    ├── kepler.py            # 开普勒方程求解器
    └── time.py              # 周内秒归一化
```

## 参考标准

- [IS-GPS-200N](https://www.gps.gov/interface-control-documents-icds-interface-specifications-iss) — GPS 星历解算公式链
- [北斗 B1I ICD v3.0](http://en.beidou.gov.cn/SYSTEMS/Officialdocument/) — BDS 星历解算公式链
- [RINEX 2.11](https://files.igs.org/pub/data/format/rinex211.txt) / [3.04](ftp://igs.org/pub/data/format/rinex304.pdf) — 导航电文格式规范
- [RTKLib](https://github.com/tomojitakasu/RTKLIB) — 工程实现参考

## License

MIT
