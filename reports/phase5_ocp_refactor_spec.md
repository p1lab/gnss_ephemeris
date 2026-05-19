# Phase 5 规划：开闭原则重构——注册表模式

> **目标**：消除解析器与解算器中的 `if/elif` 硬编码分派，使新增 GNSS 系统或 RINEX 版本时只需**添加代码**，无需**修改**已有代码。

---

## 1. 问题诊断

### 1.1 当前违反 OCP 的位置

| 位置 | 代码模式 | 扩展时需要做什么 |
|------|----------|-----------------|
| `parser.py` L172-189 | `if system == "GPS": ... elif system == "BDS": ...` | **修改** `parse_rinex2`，增加 `elif system == "Galileo"` |
| `parser.py` L262-281 | 同上，`parse_rinex3` 中重复的 `if/elif` | **修改** `parse_rinex3` |
| `parser.py` L310-318 | `if version_str.startswith("2."): ... elif "3.": ...` | **修改** `parse_nav_file`，增加 `elif "4."` |
| `ephemeris/__init__.py` L32-36 | `if isinstance(eph, GPSEphemeris): ... elif BDSEphemeris: ...` | **修改** `eph2pos`，增加 `elif GalileoEphemeris` |
| `cli.py` L94 | 类型注解 `GPSEphemeris \| BDSEphemeris` | **修改** 类型注解 |

**共同特征**：每新增一个系统/版本，必须打开已有文件插入分支——这正是开闭原则所禁止的。

### 1.2 根因

解析器中的 `if/elif` 本质上做了两件事的耦合：
1. **识别系统**（`system == "GPS"`）
2. **构造对应类型的对象**（`GPSEphemeris(...)`）

解算器中的 `isinstance` 链也是同理：
1. **识别类型**（`isinstance(eph, GPSEphemeris)`）
2. **调用对应算法**（`gps_eph2pos(t_obs, eph)`）

当"识别"与"执行"写在一起时，新增分支必须修改代码。

---

## 2. 解决方案：注册表模式（Registry Pattern）

核心思想：用**数据结构**（dict）替代**控制流**（if/elif），通过 `register` 函数在模块加载时填入映射关系。新增系统时只需在新文件中调用 `register`，无需触碰已有代码。

### 2.1 三个注册表

| 注册表 | 所在模块 | 键 | 值 | 用途 |
|--------|---------|-----|-----|------|
| **版本解析器注册表** | `rinex/parser.py` | 版本前缀 (`"2."`, `"3."`, `"4."`) | `parse_fn(lines, **kwargs) -> list[Ephemeris]` | RINEX 版本 → 解析函数 |
| **星历构造器注册表** | `rinex/parser.py` | 系统标识 (`"GPS"`, `"BDS"`, `"Galileo"`) | `(Ephemeris子类, builder_fn) -> Ephemeris` | 卫星系统 → dataclass 类型 + 行数据→对象构造函数 |
| **解算器注册表** | `ephemeris/__init__.py` | `Ephemeris` 子类型 | `eph2pos_fn(t_obs, eph) -> (xyz, dts, mid)` | 星历类型 → 解算函数 |

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────┐
│                     注册表层                              │
│                                                         │
│  _VERSION_PARSERS = {"2.": parse_rinex2, "3.": ...}     │
│  _EPH_BUILDERS    = {"GPS": (GPSEph, build_gps), ...}   │
│  _EPH2POS_REGISTRY = {GPSEph: gps_eph2pos, ...}         │
│                                                         │
│  register_version_parser(version_prefix, fn)             │
│  register_eph_builder(system, cls, builder)              │
│  register_eph2pos(eph_cls, fn)                           │
└─────────────────────────────────────────────────────────┘
          ▲                ▲                ▲
          │ register       │ register       │ register
          │                │                │
┌─────────┴──────┐  ┌─────┴──────┐  ┌──────┴───────────┐
│ rinex/parser   │  │ 新系统模块  │  │ ephemeris/gps    │
│ (自注册 2.x    │  │ (如        │  │ ephemeris/bds    │
│  3.x + GPS/BDS)│  │  galileo)  │  │ (各自注册)       │
└────────────────┘  └────────────┘  └──────────────────┘
```

---

## 3. 详细设计

### 3.1 版本解析器注册表

**改造前**（`parse_nav_file`）：
```python
if version_str.startswith("2."):
    return parse_rinex2(lines, system=system)
elif version_str.startswith("3."):
    return parse_rinex3(lines)
else:
    raise ValueError(f"不支持的 RINEX 版本: {version_str}")
```

**改造后**：
```python
# 注册表
_VERSION_PARSERS: dict[str, Callable] = {}

def register_version_parser(version_prefix: str, parser_fn: Callable) -> None:
    """注册 RINEX 版本解析器.
    
    Args:
        version_prefix: 版本前缀，如 "2.", "3.", "4."
        parser_fn: 解析函数，签名为 (lines, **kwargs) -> list[Ephemeris]
    """
    _VERSION_PARSERS[version_prefix] = parser_fn

def parse_nav_file(path: str | Path) -> list[Ephemeris]:
    path = Path(path)
    with open(path, "r") as f:
        lines = f.readlines()

    version_str = lines[0][0:9].strip()

    for prefix, parser_fn in _VERSION_PARSERS.items():
        if version_str.startswith(prefix):
            # RINEX 2.x 需要额外 system 参数
            if prefix.startswith("2."):
                system = _infer_system_from_path(path)
                return parser_fn(lines, system=system)
            return parser_fn(lines)

    raise ValueError(f"不支持的 RINEX 版本: {version_str}，已注册: {list(_VERSION_PARSERS.keys())}")

# 模块加载时自注册
register_version_parser("2.", parse_rinex2)
register_version_parser("3.", parse_rinex3)
```

**新增 RINEX 4.x 时**（在 `rinex/parser_v4.py` 中）：
```python
from gnss_ephemeris.rinex.parser import register_version_parser

def parse_rinex4(lines, **kwargs):
    ...

register_version_parser("4.", parse_rinex4)
```

### 3.2 星历构造器注册表

**改造前**（`parse_rinex2` 中）：
```python
if system == "GPS":
    eph = GPSEphemeris(**common, iode=row2[0], iodc=row7[3], tgd=row7[2], ...)
elif system == "BDS":
    eph = BDSEphemeris(**common, aode=row2[0], aodc=row8[1], tgd1=row7[2], ...)
else:
    raise ValueError(f"RINEX 2.x 不支持系统: {system}")
```

**改造后**：
```python
# 注册表：system → (Ephemeris子类, builder函数)
_EPH_BUILDERS: dict[str, tuple[type[Ephemeris], Callable]] = {}

def register_eph_builder(
    system: str,
    eph_cls: type[Ephemeris],
    builder: Callable[[dict, list[list[float]]], Ephemeris],
) -> None:
    """注册星历构造器.
    
    Args:
        system: 卫星系统标识，如 "GPS", "BDS", "Galileo"
        eph_cls: 对应的 Ephemeris 子类（用于 isinstance 检查和类型推断）
        builder: 构造函数，签名为 (common_fields, rows) -> Ephemeris实例
                 common_fields: 共享字段的 dict
                 rows: [row2, row3, row4, row5, row6, row7, row8]
    """
    _EPH_BUILDERS[system] = (eph_cls, builder)
```

GPS/BDS 的 builder 函数：
```python
def _build_gps_eph(common: dict, rows: list[list[float]]) -> GPSEphemeris:
    row2, row3, row4, row5, row6, row7, row8 = rows
    return GPSEphemeris(
        **common,
        iode=row2[0], iodc=row7[3], tgd=row7[2],
        gps_week=row6[2], codes_on_l2=row6[1], l2_p_flag=row6[3],
        sv_accuracy=row7[0], sv_health=row7[1],
        trans_time=row8[0], fit_interval=row8[1],
    )

def _build_bds_eph(common: dict, rows: list[list[float]]) -> BDSEphemeris:
    row2, row3, row4, row5, row6, row7, row8 = rows
    return BDSEphemeris(
        **common,
        aode=row2[0], aodc=row8[1],
        tgd1=row7[2], tgd2=row7[3], sath1=row7[1],
        bdt_week=row6[2], sv_accuracy=row7[0],
        trans_time=row8[0],
    )

# 自注册
register_eph_builder("GPS", GPSEphemeris, _build_gps_eph)
register_eph_builder("BDS", BDSEphemeris, _build_bds_eph)
```

`parse_rinex2` / `parse_rinex3` 中的分派变为：
```python
if system not in _EPH_BUILDERS:
    # 跳过不支持的系统（而非 raise，因为 RINEX 3.x 可能混排多系统）
    i += 8
    continue

eph_cls, builder = _EPH_BUILDERS[system]
eph = builder(common, [row2, row3, row4, row5, row6, row7, row8])
results.append(eph)
```

### 3.3 解算器注册表

**改造前**（`ephemeris/__init__.py`）：
```python
if isinstance(eph, GPSEphemeris):
    return gps_eph2pos(t_obs, eph)
elif isinstance(eph, BDSEphemeris):
    return bds_eph2pos(t_obs, eph)
raise TypeError(f"不支持的星历类型: {type(eph).__name__}")
```

**改造后**：
```python
_EPH2POS_REGISTRY: dict[type[Ephemeris], Callable] = {}

def register_eph2pos(
    eph_cls: type[Ephemeris],
    compute_fn: Callable[[float, Ephemeris], tuple],
) -> None:
    """注册星历解算函数.
    
    Args:
        eph_cls: Ephemeris 子类
        compute_fn: 解算函数，签名为 (t_obs, eph) -> ((X,Y,Z), dts, intermediates)
    """
    _EPH2POS_REGISTRY[eph_cls] = compute_fn

def eph2pos(t_obs: float, eph: Ephemeris) -> tuple:
    for cls, fn in _EPH2POS_REGISTRY.items():
        if isinstance(eph, cls):
            return fn(t_obs, eph)
    raise TypeError(
        f"不支持的星历类型: {type(eph).__name__}，"
        f"已注册: {[c.__name__ for c in _EPH2POS_REGISTRY]}"
    )

# 自注册
register_eph2pos(GPSEphemeris, gps_eph2pos)
register_eph2pos(BDSEphemeris, bds_eph2pos)
```

**新增 Galileo 时**（在 `ephemeris/galileo.py` 中）：
```python
from gnss_ephemeris.ephemeris import register_eph2pos
from gnss_ephemeris.rinex.models import GalileoEphemeris

def galileo_eph2pos(t_obs, eph):
    ...

register_eph2pos(GalileoEphemeris, galileo_eph2pos)
```

### 3.4 CLI 的 `--system` 选项

当前 CLI 的 `--system` 是自由文本，但帮助只写 `GPS/BDS`。改造后可动态生成：

```python
from gnss_ephemeris.rinex.parser import _EPH_BUILDERS

compute_cmd.add_argument(
    "--system", type=str, default=None,
    help=f"卫星系统 ({'/'.join(_EPH_BUILDERS.keys())})"
)
```

---

## 4. 新增 Galileo 的完整流程（验证 OCP）

以下步骤中，**没有任何一步需要修改已有文件**：

### 4.1 新增数据契约（`rinex/models.py` 末尾追加）

```python
@dataclass
class GalileoEphemeris(Ephemeris):
    """Galileo 专有字段."""
    iode: float
    iodc: float
    bgd_e1e5a: float    # E1/E5a 群延迟
    bgd_e1e5b: float    # E1/E5b 群延迟
    gal_week: float
    sv_health: float
    trans_time: float
```

> **说明**：`models.py` 是契约层，所有系统的 dataclass 定义都在这里。新增子类是**追加**，不修改已有类。

### 4.2 新增解析器构造函数（新文件 `rinex/builders/galileo.py`）

```python
from gnss_ephemeris.rinex.models import GalileoEphemeris
from gnss_ephemeris.rinex.parser import register_eph_builder

def _build_galileo_eph(common: dict, rows: list[list[float]]) -> GalileoEphemeris:
    row2, row3, row4, row5, row6, row7, row8 = rows
    return GalileoEphemeris(
        **common,
        iode=row2[0], iodc=row7[3],
        bgd_e1e5a=row7[2], bgd_e1e5b=row7[3],
        gal_week=row6[2], sv_health=row7[1],
        trans_time=row8[0],
    )

register_eph_builder("Galileo", GalileoEphemeris, _build_galileo_eph)
```

### 4.3 新增解算函数（新文件 `ephemeris/galileo.py`）

```python
from gnss_ephemeris.ephemeris import register_eph2pos
from gnss_ephemeris.rinex.models import GalileoEphemeris

def galileo_eph2pos(t_obs, eph):
    # Galileo F/NAV ICD 算法
    ...

register_eph2pos(GalileoEphemeris, galileo_eph2pos)
```

### 4.4 确保模块被导入

在 `rinex/__init__.py` 或 `ephemeris/__init__.py` 中添加：
```python
import gnss_ephemeris.rinex.builders.galileo  # 触发 register
import gnss_ephemeris.ephemeris.galileo        # 触发 register
```

> 也可以用 `__all__` 或 `importlib` 动态扫描，但初期显式 import 更清晰。

**总计修改已有文件的行数：0**（`models.py` 是追加，`__init__.py` 是追加 import）。

---

## 5. 实施步骤

### 5.1 文件变更清单

| 步骤 | 文件 | 变更类型 | 说明 |
|------|------|---------|------|
| 1 | `rinex/parser.py` | 修改 | 提取 `_EPH_BUILDERS` + `register_eph_builder`；提取 `_VERSION_PARSERS` + `register_version_parser`；`parse_rinex2/3` 中 `if/elif` → 查表 |
| 2 | `ephemeris/__init__.py` | 修改 | 提取 `_EPH2POS_REGISTRY` + `register_eph2pos`；`isinstance` 链 → 查表 |
| 3 | `tests/test_registry.py` | 新增 | 注册表单元测试：注册/查询/重复注册/未注册类型报错 |
| 4 | `tests/test_rinex.py` | 修改 | 回归测试不变，增加注册表断言 |
| 5 | `tests/test_ephemeris.py` | 修改 | 回归测试不变，增加注册表断言 |
| 6 | `cli.py` | 微调 | `--system` 帮助文本动态化 |

### 5.2 安全保障

- **回归测试**：现有 77 个用例全部保留，重构后必须全部通过
- **注册时机**：所有 `register` 调用在模块顶层执行（import 时），保证 `parse_nav_file` / `eph2pos` 被调用时注册表已就绪
- **重复注册**：`register_*` 函数允许覆盖（同名键后者覆盖前者），并输出 `logging.warning`
- **未注册类型**：查表失败时抛出清晰的错误信息，列出所有已注册的键

### 5.3 执行顺序

```
步骤1 (parser注册表) ──┐
                       ├──→ 步骤3 (测试) ──→ 步骤4/5 (回归) ──→ 步骤6 (CLI)
步骤2 (ephemeris注册表)┘
```

步骤1和2互不依赖，可并行。

---

## 6. 不做的事

| 方案 | 不采用理由 |
|------|-----------|
| **Plugin 动态发现**（`entry_points` / `importlib` 扫描） | 当前系统数量少（GPS/BDS），过度工程化。`import` 即注册够用 |
| **`Protocol` 替代 `dataclass` 继承** | 之前已分析：GPS/BDS 共享 20+ 同名字段，`Protocol` 无法表达继承关系 |
| **Builder 抽象基类** | builder 函数签名简单，`Callable` 类型注解足够，无需额外 ABC |
| **将 `models.py` 拆为独立包** | 星历字段语义由 RINEX 规范定义，与解析模块天然同源，无独立包必要 |

---

## 7. 验收标准

1. **零回归**：77 个现有测试全部通过
2. **OCP 验证**：新增一个 `DummyEphemeris(Ephemeris)` + `_build_dummy_eph` + `dummy_eph2pos`，仅通过 `register` 调用注册，不修改任何已有文件，即可被 `parse_nav_file` 和 `eph2pos` 正确分派
3. **错误信息友好**：传入未注册的系统/类型时，错误信息包含已注册的键列表
