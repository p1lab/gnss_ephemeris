项目任务：
根据导航电文解算卫星瞬时位置的程序。
具体的算法比如解析文件和解算数据都应该根据官方文档或者标准实现来完成.

相关信息：
**一、RINEX 格式**

**定义**
Receiver Independent Exchange Format，由 IGS 与 RTCM-SC104 联合维护。它是 GNSS 后处理环节的**标准化数据交换容器**，不是接收机实时输出的原生格式。

**核心特征**
- **接收机无关**：统一不同厂商接收机的数据表达
- **版本演进**：2.10 / 2.11 → 3.02 / 3.04 / 4.00 / 4.02（3.x 起支持多系统标识，4.x 支持多频多模扩展）
- **文件类型**（扩展名标识）：
  - `N` / `.n` / `.c` / `.g` / `.r` / `.l` / `.q`：导航电文（广播星历、钟差、电离层参数）
  - `O` / `.o`：观测数据（伪距、载波相位、多普勒、信噪比）
  - `M` / `.m`：气象数据（气压、温度、湿度）
- **物理结构**：固定 80 字符/行的文本格式，分为 **Header**（元数据）与 **Data**（主体数据）
- **职能边界**：RINEX 规范只定义**字段语义、位置、单位、比例因子**，不定义解算算法

**官方规范地址**
- 总入口：`https://igs.org/formats-and-standards/`
- RINEX 2.11：`https://files.igs.org/pub/data/format/rinex211.txt`
- RINEX 3.04：`ftp://igs.org/pub/data/format/rinex304.pdf`
- RINEX 4.02：`https://files.igs.org/pub/data/format/rinex_4.02.pdf`

---

**二、各 GNSS 系统官方解算方法（ICD）**

广播星历参数到卫星瞬时位置/钟差的**完整公式链**由各系统官方 ICD 定义，而非 RINEX。

| 系统 | 官方文档 | 网址 |
|---|---|---|
| **GPS** | IS-GPS-200 | `https://www.gps.gov/technical/icwg/` |
| **北斗（BDS）** | 北斗卫星导航系统空间信号接口控制文件 | `http://en.beidou.gov.cn/SYSTEMS/Officialdocument/` |
| **GLONASS** | ICD GLONASS | `http://russianspacesystems.ru/wp-content/uploads/2016/08/ICD_GLONASS_eng_v5.1.pdf` |
| **Galileo** | Galileo OS SIS ICD | `https://www.gsc-europa.eu/electronic-library/programme-reference-documents` |
| **汇总** | UNOOSA 官方索引 | `https://www.unoosa.org/res/oosadoc/data/documents/2021/stspace/stspace75rev_1_0_html/st_space_75rev01E.pdf` |

---

**三、RTKLib：工程实现模板**

RTKLib 由 Tomoji Takasu 开发，是 GNSS 领域**事实标准的开源处理库**，其源码可直接作为官方 ICD 算法的工程映射。

- **仓库**：`https://github.com/tomojitakasu/RTKLIB`
- **核心文件**：`src/ephemeris.c`
- **关键函数**：
  - `eph2pos()` — GPS / Galileo / 北斗 / QZSS 广播星历 → 卫星位置
  - `geph2pos()` — GLONASS 星历 → 卫星位置（GLONASS 采用状态向量而非开普勒根数）
  - `eph2clk()` — 广播星历 → 卫星钟差
- **手册**：`https://rtkexplorer.com/pdfs/manual_demo5.pdf`（附录含数学公式描述）

**逻辑关系**
```
RINEX 文件 ──► 提取参数 ──► 按 ICD 公式链计算 ──► 卫星位置/钟差
     │                              │
     └──────── 格式定义 ────────────┘      └──── 算法定义
              (IGS)                          (各系统官方)
                                    └──── 工程实现
                                          (RTKLib)
```


