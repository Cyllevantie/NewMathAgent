# 文献定向与机理锚定（LITERATURE_DIRECTION）

> 阶段：`literature` / skill `1Literature-orientation`（链上第 2 步；上游＝读题阶段的
> `runtime/quality/intake/INTAKE_REPORT.md`，人工确认于 **2026-09-29T11:18:24**，run_id `a1093483`）。
> 产出用途：仅作 `analysis`（建模设计）的方向参照与 `review`（机理评审）的外部锚点。
> **本报告不建正式模型、不写代码、不写论文**（阶段边界见 §6）。
> 检索方式：WebSearch（主题发现）+ CrossRef 公开 API `api.crossref.org`（逐条元数据核验）
> + 维普/知网/期刊官网（中文核心刊题录，见 §5.1）。
> 全部引用条目的 DOI / 题录已逐条回查核实（核验留痕见 §5）。
>
> **本轮（2026-09-29 重跑）性质＝内容复用 + 全量复核**：本工作区此前已在**同一道题**上产出过本报告
> （上一版 sha256 `46ba2bede972e0c6…`，归档副本见 `tmp/fr6/iso/reports/LITERATURE_DIRECTION.md`）。
> 本轮属"同题重跑"，故按 `skills/_references/stage_discipline.md` 一·1.1 **复用上一版的结论与文献台账**，
> 并对**每一个数字、每一条 DOI、每一处题面常量在本轮重新取证**（清单见 §6.2）；
> 本轮发现的偏差已就地更正（见 §6.3）。**未复用任何与本题无关的内容**。

---

## 0. 总括

本赛题可归为**机理/动力学类（分布参数 PDE 正问题 + 事件定位）**：四问实质都是"给定烘房环境驱动与物性经验式，求圆柱形药材内部温度场 $T(r,t)$ 与**干基**含水率场 $C(r,t)$ 的时空演化"，Q3 是在解之上求**全场达标时间**（等价于"最坏点约束下的事件定位/根查找"而非平均量最优化），Q4 再叠加**尺寸变化**（动边界问题）。因此各问宜统一以「**一维径向耦合传热-传质 PDE + 第三类（Robin）对流边界 + 隐式/收敛可控的数值解**」为骨架：Q1 用该骨架的短时版本（≈ 预热平衡段），Q2 把物性换成附录 3 的强非线性变物性版本，Q3 在 Q2 的解上做"$\max_r C(r,t)<0.15$"的达标时间定位，Q4 把半径 $R(t)$ 换成附件 2 给定的运动学输入并用动边界/坐标变换处理收缩。文献上的分野很清楚：**薄层干燥经验模型（Page/Midilli/Weibull 等）只回答"整块平均含水率随时间"，不能回答本题"到中心距离 0–2 cm 的分布"与"各处均低于 0.15"**，只能作对照校核，不能作主模型。

---

## 1. 赛题主题与领域关键词

| 项 | 内容 |
|---|---|
| 赛题 | 2026 高教社杯 A 题「药材的烘干问题」——圆柱形中药材热风烘干（预热平衡段 + 恒温干燥段） |
| 领域 | 多孔介质/生物质**对流干燥**（convective drying of porous media）；中药材加工（中药材热风干燥） |
| 物理过程 | 烘房对流加热（$h$）与对流除湿（$h_m$）→ 体内导热 + 湿分扩散（Fick 型有效扩散系数 $D$）→ 干燥后期收缩致尺寸变化 |
| 中文关键词 | 热风干燥；预热平衡阶段；干基含水率；有效水分扩散系数；对流传质系数；第三类边界条件；降速干燥阶段；收缩/动边界；烘干时间；有限差分/有限体积/有限元 |
| English keywords | hot-air convective drying；preheating (warm-up) period；dry-basis moisture content；effective moisture diffusivity；convective mass transfer coefficient；Robin boundary condition；falling-rate period；coupled heat and mass transfer (CHMT)；shrinkage / moving boundary / ALE；drying time；moisture distribution uniformity |
| 补充检索词 | 圆柱 / cylindrical coordinate；无限长圆柱 / infinite cylinder；变物性 / variable properties；Arrhenius 型扩散系数 / temperature-dependent diffusivity；反问题 / inverse problem |
| 题型辨析 | **不是**"薄层干燥动力学曲线拟合"型，也不是"数据驱动预测"型（题面只给烘房环境与半径序列，未给药材内部实测含水率剖面，纯数据驱动无法给出要求的内部分布）；**是**机理 PDE 正问题 + 达标时间定位 |

---

## 2. 题面参数集与数据：量级锚点（本阶段只做核对，不建模型）

下列数字均由题面附录 2/3/4 与附件 1/2 按定义式直接算出（**复算脚本，非模型结果**），用途是给建模与评审一个**可复算的机理标尺**。

> **本轮复核方式（2026-09-29）**：常量**不是**从上一版报告抄的 ——
> `_tmp/lit_problem_verbatim.py` 从 `request/problem.md` 原文正则抠出附录 2/3/4 的
> 全部系数（`820/2600/0.36/25/8×10⁻⁷`、`7×10⁻⁹`、`0.89`、`650/128`、`1450/2736`、`0.21/0.38`、
> `2.4×10⁻³`、`0.45/3850`、`4.2×10⁻⁴`、`0.30/3850`），再由这些常量重算下表锚点；
> 附件侧的规模/步长/极值/平台/收缩反算由 `_tmp/lit_mech_probe.py` + `_tmp/lit_shrink_probe.py` 原样重跑。
> 三支探针的输出见 §6.2，**下表每个数字都与本轮输出逐位对上**（唯一一处措辞更正见 §6.3）。

| 锚点 | 数值 | 来源/算式 | 机理含义 |
|---|---|---|---|
| 热扩散率 $\alpha$ | $1.6886\times10^{-7}\ \mathrm{m^2/s}$ | $\alpha=k/(\rho c_p)=0.36/(820\times2600)$ | 温度场响应速度 |
| 热特征时间 $\tau_{\rm heat}=R^2/\alpha$ | **2368.9 s ≈ 39.5 min** | $R=0.02$ m | 温度场达到平衡的量级 |
| 质特征时间 $\tau_{\rm mass}=R^2/D$（Q1，$C_0=2.55$） | **81010 s ≈ 22.5 h** | $D=7\times10^{-9}e^{-0.89/C}=4.9377\times10^{-9}$ | 水分场达到平衡的量级 |
| 时间尺度分离 | $\tau_{\rm mass}/\tau_{\rm heat}=\mathbf{34.2}$ | — | 温度远快于水分 |
| 1800 s 的相对位置 | $0.76\,\tau_{\rm heat}$；$0.022\,\tau_{\rm mass}$ | — | **Q1 时段内温度变化显著、水分浓度变化极小** |
| 外膜传质时间 $R/h_m$ | 25000 s ≈ 6.9 h | $h_m=8\times10^{-7}$ m/s | 表面传质阻力亦远慢于 1800 s |
| 热 Biot 数 | $\mathrm{Bi}_h=hR/k=\mathbf{1.389}$ | $h=25$ W/(m²·K) | $\gg0.1$ ⇒ **不能集总** |
| 质 Biot 数（初始） | $\mathrm{Bi}_m=h_mR/D=\mathbf{3.240}$ | — | $\gg0.1$ ⇒ **不能集总**；内/外阻力同量级 |
| 质 Biot 数（干燥后期，$C=0.15$） | $\mathrm{Bi}_m\approx\mathbf{863}$ | $D=1.85\times10^{-11}$（Q1 式外推） | 后期**内扩散绝对控制**，表面近似与环境平衡 |
| 附录 3 的 $D$ 变化（分解） | **纯 $C$ 效应**（固定 $T$）$C{:}2.55\to0.15$：$D$ 降 **16.84 倍**；**纯 $T$ 效应**（固定 $C$）$30\to50°\mathrm{C}$：$D$ 升 **2.20 倍**；**净效应** $2.55@30°\mathrm{C}\to0.15@50°\mathrm{C}$：降 **7.67 倍**（$6.138\times10^{-9}\to8.001\times10^{-10}$） | 附录 3 指数分解 | $e^{-0.45/C}$ 是**主因**（$C$ 的指数衰减），$e^{-3850/T}$ 只部分回补 ⇒ 长时程由 $C$ 主导 |
| 附录 4 与附录 3 的 $D$ 之比 | $0.203$（同 $C=1.0,T=50°\mathrm{C}$） | 附录 4/附录 3 | Q4 的传质比 Q2/Q3 慢约 5 倍 |
| 附件 2 收缩 | $R:2.000\to1.198$ cm，$V/V_0=0.2149$，$t\approx2.7\text{–}2.8$ d 后稳定 | 附件 2 | 收缩在**烘干后段停止**（$R$ 平台 1.198–1.200 cm） |
| 附件 1 环境 | 4 h 内 $T_\infty:28\to50.246\,°\mathrm{C}$；$C_\infty:0.01963\to0.05025$ | 附件 1（241 点，60 s 步长） | 环境**4 h 内未达平台**：末段每分钟 $T_\infty$ 变幅仍在 $\pm0.4\,°\mathrm{C}$ 量级（未衰减到 0），$C_\infty$ 每 60 s 变化 $\approx1\times10^{-4}$ kg/kg |

**三条可直接当判据用的结论**：

1. **Q1 的主导变化量是温度，不是水分**：1800 s 只走完温度尺度的 0.76、水分尺度的 0.022 ⇒ 表 1 应显著变化、表 2 应近乎不起伏。若某解法给出 1800 s 内水分浓度出现大幅下降（或中心与表面拉开很大差距），其 $D$ 口径或单位必有一处错（判据化，供 `review` 用）。
2. **集总（Lumped）模型在本例不成立**：$\mathrm{Bi}_h=1.39$、$\mathrm{Bi}_m=3.24$ 均远大于 0.1 的集总适用线（Biot 数在干燥中的标准用法见 L6）⇒ 必须解分布参数方程，中心点必然滞后于表面。
3. **干燥后期由内部扩散控制**（$\mathrm{Bi}_m$ 增至 $10^2\text{–}10^3$）⇒ **Q3 的达标时间由中心点决定**，判据必须是 $\max_r C(r,t)$ 而非平均或表面值。

---

## 3. 逐子问题推荐建模方向

### 3.0 总表

| 子问题 | 主流模型族 / 算法（含近 3–5 年进展） | 领域机理基线（主变量 / 因果方向 / 主导效应） | 真实文献（标题—作者/年—期刊或 DOI—为何相关） | 可检索关键词 |
|---|---|---|---|---|
| **问题 1**（0–1800 s 预热平衡段） | ① 一维径向耦合传热-传质 PDE（Fick + Fourier）+ Robin 边界，隐式差分/有限体积；② 无限圆柱解析级数解作独立校核；③ 反对集总模型（$Bi\gg0.1$） | 主变量＝局部温度 $T(r,t)$ 与**干基**含水率 $C(r,t)$；因果方向＝**表面先响应、中心滞后**（$\mathrm{Bi}_h{=}1.39$）；主导效应＝对流加热（$\tau_{\rm heat}{=}39.5$ min）远快于水分迁移（$\tau_{\rm mass}{=}22.5$ h，相差 34 倍）；$D=D(C)$ 只单向依赖 $C$（附录 2 无温度项、无潜热项）⇒ 本问不宜引入无法由题面确定的强热-质耦合 | ① Koukouch 等 2020，*Heat and Mass Transfer* 56(6):1971–1983，doi:10.1007/s00231-020-02817-w——生物质对流干燥**耦合传热传质方程解析解并实验验证**，可作级数解校核范式；② Nylen 等 2024，*Drying Technology* 42(13):2044–2055，doi:10.1080/07373937.2024.2407959——给出**内部与表面温度剖面的瞬态差异**（预热段的核心特征）；③ López-Ortiz 等 2018，*Food and Bioproducts Processing* 111:83–92，doi:10.1016/j.fbp.2018.06.005——非等温干燥中**初始温度/升温方式**对过程的影响；④ Górnicki 等 2019，*Energies* 12(14):2822，doi:10.3390/en12142822——干燥过程中 **Biot 数的估计与用法**（集总适用性的量化依据） | 预热带/预热平衡期（preheating period, warm-up period）；耦合传热传质（coupled heat and mass transfer）；无限圆柱（infinite cylinder）；第三类边界条件（Robin / convective boundary condition）；对流换热系数（convective heat transfer coefficient）；Biot 数（Biot number） |
| **问题 2**（全流程 2–3 d，附录 3 变物性） | ① 强非线性变物性 PDE（$\rho(C),c_p(C),k(C),D(C,T)$）+ 隐式时间推进（牛顿/算子分裂）；② 控制体积法处理 $r=0$ 对称奇异性；③ 谱/小波配点等高精度空间离散；④ 薄层经验模型仅作**平均含水率的对照曲线** | 主变量＝$T(r,t)$ 与 $C(r,t)$，但**耦合升级为双向**：$D$ 依赖 $T$ 与 $C$，物性依赖 $C$；主导效应＝$D(C,T)=2.4\times10^{-3}e^{-0.45/C}e^{-3850/T}$ 的**指数非线性**（固定 $T$ 时 $C{:}2.55\to0.15$ 使 $D$ 降 **16.84 倍**；升温 $30\to50\,°\mathrm{C}$ 只回补 **2.20 倍**）⇒ 过程很快进入**降速段**，长时程由 $C$ 的指数项主导；因果方向＝温度升高加速传质（$T$ 是显著的加速因子而非独立目标） | ① Li 等 2023，*Drying Technology* 41(12):2027–2041，doi:10.1080/07373937.2023.2213767——谷物干燥**耦合热湿传递数值仿真**（离散元+有限元），多场耦合实现范式；② Martínez Vera & Vizcarra Mendoza 2022，*Biosystems Engineering* 218:256–273，doi:10.1016/j.biosystemseng.2022.04.016——**浓度依赖的扩散系数**估计（含收缩），正是附录 3 里 $D(C)$ 的处理方式；③ Ol'shanskii & Gusarov 2020，*J. Eng. Phys. Thermophys.* 93(2):364–368，doi:10.1007/s10891-020-02129-0——**降速段**物料温度的解析讨论（本题 2–3 d 全程处于降速段的依据）；④ Vu & Tsotsas 2018，*Int. J. Chem. Eng.* 2018:9456418，doi:10.1155/2018/9456418——干燥多孔介质各类传热传质模型（Luikov/Whitaker/扩散理论/退行前沿）**综述与数值实现** | 热风干燥（hot-air drying）；降速干燥阶段（falling-rate period）；变物性/有效扩散系数（variable properties, effective moisture diffusivity）；Arrhenius 温度依赖（Arrhenius temperature dependence）；强非线性扩散方程（nonlinear diffusion equation）；长时程干燥（long-time drying 2–3 days） |
| **问题 3**（烘干时长：各处 $C<0.15$） | ① 在 Q2 解上做**最坏点约束下的事件定位**：求 $g(t)=\max_{r}C(r,t)-0.15$ 的首个零点（$g$ 单调，用 Brent/二分，配合时间插值）；② 每步判据用全场极值而非平均；③ 敏感性分析（环境外推方式、阈值附近的数值分辨率） | 主变量仍是 $C(r,t)$，但**判据量是场的最坏点**：表面先干、中心最后达标（$\mathrm{Bi}_m$ 后期达 $10^2$–$10^3$，内扩散控制）；因果方向＝环境 $T_\infty\!-\!C_\infty$ 驱动表面，内部靠扩散传导"干燥前沿"；主导效应＝中心点滞后 + $D$ 随 $C$ 指数衰减 ⇒ 达标时间对**环境条件在 4 h 之后的外推方式**高度敏感（附件 1 只覆盖 4 h，本题却要跑到 2–3 d） | ① Ostanek & Ileleji 2019，*Drying Technology* 38(5-6):775–792，doi:10.1080/07373937.2019.1590394——**共轭传热传质模型预测干燥均匀性**，最差点/均匀性表征范式；② Lin 等 2020，*Drying Technology* 39(8):1044–1058，doi:10.1080/07373937.2020.1741006——热风与其它方式干燥的**水分均匀性**对比；③ Lv 等 2018，*Drying Technology* 36(13):1592–1602，doi:10.1080/07373937.2017.1418751——**内部含水率分布**的在线测量（说明"平均含水率"不等于"各处达标"）；④ Bai 等 2023，*Heliyon* 9(5):e15554，doi:10.1016/j.heliyon.2023.e15554——**中药材（枳壳）热风薄层干燥**在不同温度下的干燥特性与品质（领域内"温度↑、干燥时间↓"的实证基线） | 干燥时间/达标签（drying time, time to reach target moisture content）；最坏点/均匀性（worst case, drying uniformity）；水分分布（moisture distribution）；降速段（falling-rate period）；阈值达标（threshold, attainment time）；中药材热风干燥（hot-air drying of Chinese medicinal materials） |
| **问题 4**（尺寸变化 + 附录 4） | ① **动边界**模型：域 $r\in[0,R(t)]$，$R(t)$ 由附件 2 **直接插值给定**（不必也不应由 $C$ 反推）；② 坐标变换到固定参考域（$\xi=r/R(t)$，会引入网格速度对流项）或 ALE 有限元；③ 与固壁固定域解法对比，量化收缩对结果的影响 | 主变量＝$C(r,t)$ 与**运动边界 $R(t)$**；因果方向＝水分流失 → 体积收缩/孔隙塌陷（**收缩幅度大于水分体积的减少**，见下）；主导效应＝收缩同时改变**扩散距离**与**通量面积**（$2/R$ 增大 ⇒ 表观干燥加速），故忽略收缩与"理想收缩"两种简化都会系统性偏离；数据方面 $R(t)$ 是**给定的运动学输入**，不是待求的力学响应 | ① Adrover 等 2019，*J. Food Eng.* 244:178–191，doi:10.1016/j.jfoodeng.2018.09.018——食品等温干燥与收缩的**动边界模型（一般设定）**；② Lentzou 等 2019，*J. Food Eng.* 263:299–310，doi:10.1016/j.jfoodeng.2019.07.010——动边界模型中**水分扩散系数与收缩的联合反演优化**；③ Azhdari & Emami 2019，*Math. Comput. Simul.* 166:253–265，doi:10.1016/j.matcom.2019.05.013——番茄干燥**"含收缩"与"不含收缩"模型**的解析/数值对照（忽略收缩偏差的直接依据）；④ Das 等 2025，*Thermochimica Acta* 749:180024，doi:10.1016/j.tca.2025.180024——香蕉片对流干燥的**ALE 等向收缩**有限元建模（工程实现范式） | 收缩（shrinkage）；动边界/移动边界（moving boundary）；任意拉格朗日-欧拉（ALE）；坐标变换（coordinate transformation / Landau transform）；体积收缩系数（volumetric shrinkage coefficient）；尺寸变化（dimensional change）；移动网格有限元（moving-mesh FEM） |

---

### 3.1 问题 1：预热平衡阶段的温度与水分浓度场

**机理基线（供 `review` 逐条判 PASS/FAIL）**

- **真正的主变量**：局部温度 $T(r,t)$ 与**干基**含水率 $C(r,t)$。二者都是**场量**，题目要求的输出正是"到中心距离 0/0.5/1/1.5/2 cm 处"的剖面 ⇒ 分布参数模型是题面硬约束。
- **因果方向**：烘房环境（$T_\infty(t)$、$C_\infty(t)$，附件 1）→ 通过第三类边界（$h=25$ W/(m²·K)、$h_m=8\times10^{-7}$ m/s）驱动**表面**；体内由导热与湿分扩散把扰动传向中心。$\mathrm{Bi}_h=1.39$、$\mathrm{Bi}_m=3.24$ ⇒ **表面与中心必然有明显落差，中心必滞后**。
- **主导效应/时间尺度**：$\tau_{\rm heat}=2368.9$ s、$\tau_{\rm mass}=81010$ s、比值 34.2 ⇒ 1800 s 内"温度显著变化、水分几乎不变"。**这是本问最容易被做错的地方**（见 §4 错误清单 E1/E3）。
- **可测代理 vs 衍生量**：$C$ 与 $T$ 是可直接定义的状态量；$\rho,c_p,k,D$ 均为**由经验式或常数给出的物性**（附录 2 里 $k=0.36$、$\rho=820$、$c_p=2600$ 为常数，$D=D(C)$）——**物性不是主变量**，把物性当自变量、把状态量当因变量的写法（如"以 $D$ 的分布为主变量"）在本问没有机理意义。
- **口径分叉（须由 `analysis` 显式决策并披露）**：附录 2 未给汽化潜热或蒸发吸热项。物理上干燥必然伴随吸热，但**题面参数集不足以确定该耦合强度**。建议主档采用**题面闭合的参数集**（温度场由对流加热 + 导热主导，水分迁移对温度场的反向影响按题面不建模），若另行引入潜热项，则必须（i）写明其参数取值来源，（ii）作为口径/敏感性单独披露，且不得让结论依赖未给定参数。
- **预判风险点**：烘房 $C_\infty=0.0196\text{–}0.0503$ 相对药材初始 $C_0=2.55$ 很小，但**不为零**——表面传质驱动势应取 $(C_s-C_\infty)$，不能把 $C_\infty$ 当 0（差异虽小，却是"是否读懂了边界条件"的判别点）。

**候选算法族与取舍**

1. **一维径向 PDE + 隐式差分/有限体积（推荐主档）**。理由是本题 $L/R=25/2=12.5$，轴向梯度可忽略，"无限长圆柱"是标准理想化（一维 vs 二维取舍的文献依据见 L13）；局限是忽略两端效应，须在假设中写明。
2. **无限圆柱解析级数解（校核档）**——$D$ 依赖 $C$ 时严格解析解不存在，但可对**冻结系数**（取 $D(C)$ 在某代表值）求级数解，用来校核数值解的量级与边界响应（文献 L1 即为"解析解 + 实验验证"范式，经典理论见 L31）。**解析解不得直接当作交付结果**（因为 $D$ 随 $C$ 变，冻结系数解在长时段有系统偏差）。
3. **不应采用**：集总参数（$Bi\gg0.1$，见 L6）、把温度或浓度在空间上取单点/单值的"平均"模型、纯数据拟合（题面无内部实测剖面可训）。

**文献（4 条，含近 5 年 2 条）**

| 编号 | 条目 | 相关性 |
|---|---|---|
| L1 | Koukouch A., Bakhattar I., Asbik M., Idlimam A. (2020). Analytical solution of coupled heat and mass transfer equations during convective drying of biomass: experimental validation. *Heat and Mass Transfer* 56(6): 1971–1983. doi:10.1007/s00231-020-02817-w | 对流干燥**耦合传热传质**方程的解析解构造 + 实验验证：校核档的方法学来源 |
| L2 | Nylen J., Sheehan M., Whelan A., Antunes E. (2024). Internal and surface temperature profiles of spherical biosolids particles during convective drying. *Drying Technology* 42(13): 2044–2055. doi:10.1080/07373937.2024.2407959 | **内部与表面温度剖面**的瞬态演化：预热段"表面先升、中心滞后"的直接证据 |
| L3 | López-Ortiz A., Rodríguez-Ramírez J., Méndez-Lagunas L.L., Martynenko A. (2018). Non-isothermal drying of garlic slices (*Allium sativum*, L.): Wave period and initial temperature of the heating/cooling. *Food and Bioproducts Processing* 111: 83–92. doi:10.1016/j.fbp.2018.06.005 | **非等温**干燥与初始温度/升温方式的影响：本题"预热平衡段"独立成问的领域依据 |
| L6 | Górnicki K., Winiczenko R., Kaleta A. (2019). Estimation of the Biot Number Using Genetic Algorithms: Application for the Drying Process. *Energies* 12(14): 2822. doi:10.3390/en12142822 | 干燥中 **Biot 数**的用途与估计：支撑"$\mathrm{Bi}=1.39/3.24\Rightarrow$ 不可集总"这一判据 |

（另见 §5 的共用池：L5 综述、L30 连续介质模型、L31/L32 经典专著。）

**可检索关键词**：见 §3.0 总表末列（Q1 行）。

---

### 3.2 问题 2：整个烘干过程（2–3 d，附录 3 变物性）

**机理基线**

- **主变量**：仍为 $T(r,t)$、$C(r,t)$；但物性成为状态量的函数：$\rho=650+128C$、$c_p=1450+2736\frac{C}{C+1}$、$k=0.21+0.38\frac{C}{C+1}$、$D=2.4\times10^{-3}e^{-0.45/C}e^{-3850/T}$。
- **因果方向（双向）**：$T\uparrow\Rightarrow D\uparrow\Rightarrow$ 水分迁移加快；$C\downarrow\Rightarrow D$ 指数衰减、同时 $\rho,c_p,k$ 变化 ⇒ **过程自然进入并停留在降速段**（L7 提供降速段物料温度的解析讨论）。温度因此既是驱动力也是被调制的量。
- **主导效应**：$e^{-0.45/C}$ 项。**指数分解**（同一附录 3 式）：固定 $T$ 时 $C{:}2.55\to0.15$ 使 $D$ 降 **16.84 倍**；固定 $C$ 时 $T{:}30\to50\,°\mathrm{C}$ 只使 $D$ 升 **2.20 倍**；两者合成的净效应为降 **7.67 倍**（$6.138\times10^{-9}\to8.001\times10^{-10}$ m²/s）。⇒ **$C$ 的指数衰减是长时程的主因，升温只部分回补**；这也解释了"2–3 天"这一时长量级（$\tau_{\rm mass}=R^2/D$ 由 $C{=}2.55$ 时的 0.34–0.75 d 增长到 $C{=}0.15$ 时的 5.79–12.70 d）。
- **口径分叉 1（环境外推）**：附件 1 只覆盖 0–4 h，且 4 h 末 $T_\infty$ **尚未达平台**（末段每分钟变幅仍为 $\pm0.4\,°\mathrm{C}$ 量级），$C_\infty$ 每 60 s 变化 $\approx1\times10^{-4}$ kg/kg。Q2/Q3 要跑 2–3 d，必须显式声明 4 h 之后的 $T_\infty(t),C_\infty(t)$ 处理方式，并对其做敏感性。**不得默默把 4 h 的线性趋势外推到 72 h**（那不是数据支持的结论）。
- **口径分叉 2（潜热/汽化吸热）**：附录 3 同样未给潜热项，同上按题面闭合参数集处理并披露。
- **可测代理 vs 衍生量**：附录 3 的 $c_p,k$ 中的 $\frac{C}{C+1}$ **本身就是干基→湿基质量分数的换算**（$C/(1+C)$ 是湿基含水率）。这是"口径已内置"的信号：不要再做第二次换算，也不要把它写成"$C$ 的某种修正"。
- **判据（供 `review`）**：任何"以整块平均含水率的经验曲线（Page/Midilli/Weibull）为主模型"的做法都无法产出题面要求的径向分布，属方向性错误（经验模型只可作对照，领域现状见 L24/L25）。

**候选算法族与取舍**

1. **变物性非线性 PDE + 隐式时间推进（推荐主档）**：显式格式在初期（$D$ 大、$T$ 跳变）受稳定性限制最严，后期（$D$ 小时）反而宽松；隐式（或牛顿线性化 + 自适应步长）能用一个步长穿越 2–3 d 且不牺牲精度。
2. **空间离散用控制体积/有限体积**：$r=0$ 处 $\frac1r\frac{\partial}{\partial r}\left(rD\frac{\partial C}{\partial r}\right)$ 在网格上直接展开会产生奇异性；用围绕中心节点的**控制体积（对称条件 $\partial C/\partial r|_{r=0}=0$ 自动满足）**是标准且不引入人为条件的做法。
3. **高精度替代方案**：小波配点/谱方法（L23 为干燥传热传质的小波配点实例），可在细网格上做**收敛性交叉校核**；但工程上隐式有限体积通常足够，且更易维护一致的干基口径。
4. **不应采用**：把 $D$ 取为常数或初始值的平均（后期系统性高估干燥速率）；把 $T$ 固定在烘房温度而把能量方程省掉（$T$ 影响 $D$，是本题耦合链的一环；不过 $T$ 的时间尺度远快于 $C$，"准稳态温度"可作为**一次性校核档**而不作主档）。

**文献（4 条）**

| 编号 | 条目 | 相关性 |
|---|---|---|
| L8 | Li X., Yang K., Wang Y., Du X. (2023). Simulation study on coupled heat and moisture transfer in grain drying process based on discrete element and finite element method. *Drying Technology* 41(12): 2027–2041. doi:10.1080/07373937.2023.2213767 | 近年**耦合热湿传递数值仿真**的完整实现（多场耦合、长时程） |
| L9 | Martínez Vera C., Vizcarra Mendoza M.G. (2022). Concentration-dependent moisture diffusion coefficient estimation in peas drying considering shrinkage: An observer approach. *Biosystems Engineering* 218: 256–273. doi:10.1016/j.biosystemseng.2022.04.016 | **浓度依赖的扩散系数**（$D(C)$）的识别与使用：直接对应附录 3 的核心非线性 |
| L7 | Ol'shanskii A.I., Gusarov A.M. (2020). Temperature of Material in the Process of Convective Drying of Thin Materials in the Falling Rate Period of Drying. *Journal of Engineering Physics and Thermophysics* 93(2): 364–368. doi:10.1007/s10891-020-02129-0 | **降速段**的物料温度行为：本题 2–3 d 全程处于降速段的机理依据 |
| L5 | Vu H.T., Tsotsas E. (2018). Mass and Heat Transport Models for Analysis of the Drying Process in Porous Media: A Review and Numerical Implementation. *International Journal of Chemical Engineering* 2018: 9456418, 1–13. doi:10.1155/2018/9456418 | 模型族**综述 + 数值实现**：说明扩散理论在这类问题中的定位与局限（系数难确定） |

**可检索关键词**：见 §3.0 总表末列（Q2 行）。

---

### 3.3 问题 3：烘干所需时间（各处水分浓度 < 0.15 kg/kg）

**机理基线**

- **判据量是"场的最坏点"，不是平均值**：$t_{\rm dry}=\min\{t:\max_{0\le r\le R}C(r,t)\le0.15\}$。表面先干、**中心最后达标**（后期 $\mathrm{Bi}_m$ 达 $10^2$–$10^3$，内扩散控制），因此取平均或取表面值都会**低估**烘干时间。
- **因果方向**：环境驱动表面 → 干燥前沿向内推进；中心点的时间滞后由 $R^2/D$ 决定，而 $D$ 在 $C\to0.15$ 段指数衰减 ⇒ 达标时间由**最后 5% 的水分**决定，对数值方法的时间分辨率与阈值附近的行为特别敏感。
- **主导效应**：$D(C,T)$ 的指数衰减 + 环境条件在 4 h 后的外推方式（附件 1 只有 4 h）。这两点是 Q3 结论不确定性的主要来源，应作为敏感性分析的两个主因子。
- **可测代理 vs 衍生量**：本题**没有任何药材内部含水率实测**（附件 1/2 只给环境与半径），因此"烘干时间"完全是**模型导出的量**，其可信度完全取决于 PDE 口径与参数——这也是必须做网格/时间步收敛与口径敏感性、而不能"报一个漂亮数字"的原因。
- **与文献的关系（诚实说明）**：检索到的干燥时间类文献绝大多数是**薄层/整块平均含水率**口径（L24、L25）或**均匀性/最差点**的表征（L10、L11、L12），**没有**"圆柱形中药材、以全场最坏点达标定义烘干时长"的直接对口文献。故本问的机理依据主要来自 §2 的时间尺度分析与 PDE 本身，文献提供的是"最差点必须显式表征"的方法论支持。**不应为了凑引用而把薄层模型文献说成支持"最坏点达标"口径**。

**候选算法族与取舍**

1. **在 Q2 解上做事件定位（推荐主档）**：把解写成可插值的 $C(r,t)$（时间步内插值），令 $g(t)=\max_r C(r,t)-0.15$，用二分/Brent 求首个零点；因 $g$ 单调递减（干燥单调失水），根唯一。
2. **等价的最优化表述（备选措辞）**：$\min t$ s.t. $\max_r C(r,t)\le0.15$——即"最坏点/覆盖式约束下的最小化"，与把"平均风险"当唯一目标的口径明确区分（这正是本阶段要给下游的**方向性提示**）。
3. **不应采用**：以平均含水率 0.15 为判据；以表面浓度 0.15 为判据；把 result3.xlsx 的时间轴截到"表面达标"时刻。

**文献（4 条）**

| 编号 | 条目 | 相关性 |
|---|---|---|
| L10 | Ostanek J., Ileleji K. (2019). Conjugate heat and mass transfer model for predicting thin-layer drying uniformity in a compact, crossflow dehydrator. *Drying Technology* 38(5-6): 775–792. doi:10.1080/07373937.2019.1590394 | 用共轭传热传质模型**预测干燥均匀性/最差点**：Q3 判据口径的方法论支持 |
| L11 | Lin X., Xu J.-L., Sun D.-W. (2020). Comparison of moisture uniformity between microwave-vacuum and hot-air dried ginger slices using hyperspectral information. *Drying Technology* 39(8): 1044–1058. doi:10.1080/07373937.2020.1741006 | 热风干燥的**水分均匀性**实证：平均达标 ≠ 各处达标 |
| L12 | Lv W., Zhang M., Wang Y., Adhikari B. (2018). Online measurement of moisture content, moisture distribution, and state of water in corn kernels during microwave drying. *Drying Technology* 36(13): 1592–1602. doi:10.1080/07373937.2017.1418751 | **内部含水率分布**的测量与解释：中心滞后于表面的直接证据 |
| L25 | Bai T., Wan Q., Liu X., Ke R., et al. (2023). Drying kinetics and attributes of fructus aurantii processed by hot air thin-layer drying at different temperatures. *Heliyon* 9(5): e15554. doi:10.1016/j.heliyon.2023.e15554 | **中药材（枳壳）热风干燥**的干燥特性与时间—温度关系：领域实证基线 |

**可检索关键词**：见 §3.0 总表末列（Q3 行）。

---

### 3.4 问题 4：考虑尺寸变化的烘干时长

**机理基线**

- **主变量**：$C(r,t)$（附录 4 物性）与**运动边界 $R(t)$**。$R(t)$ **由附件 2 直接给出**（145 点、1800 s 步长，$2.000\to1.198$ cm，$t\approx2.7\text{–}2.8$ d 后稳定）。
- **因果方向**：水分流失 → 体积收缩/孔隙塌陷 → 扩散距离与通量面积改变（表面通量面积随 $R$ 减小，而曲面散度项 $2/R$ 随 $R$ 减小而增大 ⇒ 单位体积物料的外交换面积**上升**，表观干燥被加速）⇒ 收缩不是可忽略的几何细节，它同时改**距离**和**面积**。
- **关键机理观测（本阶段可核验，供 `analysis` 复用）**：把附件 2 的 $R(t)$ 代入**理想收缩**（干物质体积不变、总体积 = 干物质体积 + 水分体积；用题面 $\rho=820$ kg/m³ 作初始湿态密度）反算含水率，会得到**物理上不可能的负值**：$t=12$ h 处 $V/V_0=0.2430$ 反算 $C=-0.727$ kg/kg，终态 $V/V_0=0.2149$ 反算 $C=-0.849$ kg/kg（对比：若终态 $C=0.15$，理想收缩预测 $V/V_0=0.4456$，实测仅 $0.2149$ —— 三种说法要分开讲，**别混用**：① 实测**终态体积**是理想收缩预测的 **0.48 倍**（反过来，理想预测是实测的 **2.08 倍**）；② 按"**收缩掉的体积占比**"算，实测 $1-0.2149=0.785$、理想 $1-0.4456=0.554$，实测是理想的 **1.42 倍**；③ 反算含水率 $-0.849$ kg/kg 是**物理不可能值**，这才是"不自洽"的直接判据）。⇒ **附件 2 的半径序列与"含水率线性/体积守恒"关系不自洽**，本问必须把 $R(t)$ 当作**给定的运动学输入**（插值使用），**不得由 $C$ 反推 $R$**，也不得用"$R^3\propto$ 含水体积"这类关系去互相校核。
  该结论只依赖题面 $\rho$ 与附件 2 两个来源，属可直接复核的量级判断；其物理解释（收缩大于水分体积减少 = 结构塌陷/孔隙闭合）与文献中"收缩对水分迁移有实质影响、且需专门建模"的结论一致（L17 给出含/不含收缩模型的对照范式，L22 给出圆柱试样的收缩实测方法）。
- **主导效应**：收缩在烘干后段停止（$R$ 平台），提示**收缩本身可作为"接近平衡"的经验指示**，但最终"烘干时长"仍须以 $\max_r C\le0.15$ 的模型判据为准（两者若不一致，须在论文中说明差异来源，不得相互替代）。
- **可测代理 vs 衍生量**：$R(t)$ 是**给定输入**（附件 2），不是待求量；$D$ 由附录 4 给出，同 $C,T$ 下只有附录 3 的 **0.203 倍**。
- **跨问一致性粗判据（供跨问一致性审查 `cross`，含陷阱预警）**：简单地把 $D$ 之比当时间之比会得到"Q4 比 Q3 慢 5 倍"——**这是错的**，因为收缩同时把扩散长度缩短：$R^2$ 由 $2.000^2$ 降到 $1.198^2$ = **0.359 倍**。末态两效应部分抵消，特征时间之比 $\tau_4/\tau_3\approx0.359/0.203\approx\mathbf{1.8}$。⇒ 可用于跨问审查的判据只有**方向性**一条：Q4 的烘干时长应**略长于** Q3（同量级、约 1–2 倍量级），若解出的 Q4 时长短于 Q3、或长出 4–5 倍，都应先查 $R(t)$ 插值、坐标变换的网格速度对流项与附录 4 的 $D$ 温标，而不是去调阈值。

**候选算法族与取舍**

1. **坐标变换到固定参考域（推荐主档，实现最简）**：令 $\xi=r/R(t)\in[0,1]$，方程变为含**网格速度对流项**的形式；优点是网格固定、可用与 Q2 相同的离散框架；代价是必须正确写出该对流项（漏掉它 = 隐性丢失收缩效应）。
2. **ALE 有限元/动网格（备选，工程主流的文献做法）**：L19（ALE 等向收缩）、L20（动边界 FEM + 变扩散系数反演）、L14/L15/L16（食品等温干燥动边界模型族）提供成熟范式；代价是网格畸变与收敛问题（文献亦自述其计算代价）。
3. **不应采用**：把 $R$ 固定为 2 cm（忽略收缩——文献 L17 的对照即为此设计）；在固定网格上直接模拟收缩体而不做任何变换（网格与物质点不再重合，方程形式不再成立）；用 $C$ 反推 $R$（见上，与附件 2 不自洽）。

**文献（4 条）**

| 编号 | 条目 | 相关性 |
|---|---|---|
| L14 | Adrover A., Brasiello A., Ponso G. (2019). A moving boundary model for food isothermal drying and shrinkage: General setting. *Journal of Food Engineering* 244: 178–191. doi:10.1016/j.jfoodeng.2018.09.018 | **动边界 + 收缩**干燥模型的一般设定：Q4 骨架的原始文献 |
| L16 | Lentzou D., Boudouvis A.G., Karathanos V.T., Xanthopoulos G. (2019). A moving boundary model for fruit isothermal drying and shrinkage: An optimization method for water diffusivity and shrinkage. *Journal of Food Engineering* 263: 299–310. doi:10.1016/j.jfoodeng.2019.07.010 | 动边界模型中**扩散系数与收缩的联合处理**：口径参照 |
| L17 | Azhdari E., Emami A. (2019). Analytical and numerical study of drying of tomato in non-shrinkage and shrinkage model. *Mathematics and Computers in Simulation* 166: 253–265. doi:10.1016/j.matcom.2019.05.013 | **含/不含收缩模型的对照**：支撑"忽略收缩会系统性偏离"这一判据 |
| L19 | Das R., Islam M., Saini P., Kaduji G.R. (2025). Finite element modeling of banana slices in convective drying, studies on isotropic shrinkage kinetics using Arbitrary Lagrangian Eulerian approach. *Thermochimica Acta* 749: 180024. doi:10.1016/j.tca.2025.180024 | 近 2 年**对流干燥 + ALE 收缩**的实现范式（含收敛/计算代价讨论） |

**可检索关键词**：见 §3.0 总表末列（Q4 行）。

---

## 4. 应规避的常见错误清单

> 每条给出「错误 → 为什么错 → 依据（文献号 / §2 中的可复算数字）」。这批条目是 `review` 判"机理/方向性错误"时的检查表。

| # | 应规避的错误 | 为什么错 | 依据 |
|---|---|---|---|
| **E1** | 把 Q1 的 1800 s 当成"水分显著变化的时段"，因而用平均含水率降幅去标定 $D$ 或强行让浓度场出现大变化 | $\tau_{\rm mass}=81010$ s，1800 s 只占 2.2% ⇒ 水分浓度变化量级极小；温度才是主导变化量 | §2（$\tau$ 表）；L2 |
| **E2** | 用集总参数（lumped）模型：整块一个温度/一个含水率 | $\mathrm{Bi}_h=1.389$、$\mathrm{Bi}_m=3.240$，均 $\gg0.1$；且题面要求"到中心距离 0–2 cm"的剖面 | §2；L6 |
| **E3** | 温度场与含水率场**解耦成两个独立问题**（各算各的），或反过来在 Q1 里强行引入无法由题面确定的强耦合（如把蒸发吸热当作主导项） | Q1 的 $D$ 只依赖 $C$（无温度项）、题面未给潜热 ⇒ 附录 2 的参数集下耦合是"物性单向"的；但 Q2–Q4 的 $D(C,T)$ 是真耦合，不能沿用 Q1 的解耦写法 | 附录 2 与附录 3 的 $D$ 式对比；L4 |
| **E4** | 把 $D$ 取为常数或取静态平均值 | 附录 3 中固定 $T$ 时 $C:2.55\to0.15$ 使 $D$ 降 **16.84 倍**（含升温净效应仍降 7.67 倍）；附录 4 在 $C=0.15,T=50°\mathrm{C}$ 时 $D=3.81\times10^{-10}$（$\tau_{\rm mass}\approx12.2$ d）⇒ 常数 $D$ 会系统性高估后段速率 | §2；L9 |
| **E5** | 边界条件用第一类（把表面温度固定为 $T_\infty$、表面含水率固定为 0 或 $C_\infty$） | 题面给了 $h=25$ W/(m²·K) 与 $h_m=8\times10^{-7}$ m/s，本意就是第三类（Robin）对流边界；固定值会抹掉"表面—环境"的有限交换速率 | 附录 2；L1、L5 |
| **E6** | 把 $C_\infty$ 当作 0（忽略烘房本身的水分浓度） | 附件 1 给 $C_\infty=0.0196\text{–}0.0503$ kg/kg，与阈值 0.15 同量级；末期驱动势被显著削弱 | 附件 1 |
| **E7** | 单位/温标混用：$e^{-3850/T}$ 里的 $T$ 用 °C；$R$ 用 cm 代入 SI 公式；$D$ 的 m²/s 与 $h_m$ 的 m/s 混算 | 用 °C 时 $e^{-3850/50}=e^{-77}\approx0$，结果会"看起来合理但完全错"；这是无法通过数值稳健性检查发现的硬错 | 附录 3/4 明确 $T$ 为 K；附录 2 明确 $D$ 为 m²/s |
| **E8** | 干基/湿基混淆（把 $C=2.55$ kg/kg 当湿基；或把 $c_p$、$k$ 里的 $\frac{C}{C+1}$ 再做一次换算） | 湿基含水率不可能 $>1$；而 $\frac{C}{C+1}$ **本身就是干基→湿基的质量分数换算**，重复换算会破坏物性口径 | 题面"（即干基含水率）"；附录 3/4 的 $\frac{C}{C+1}$ |
| **E9** | Q3 用平均含水率或表面含水率判"是否烘干" | 表面先干、中心最后达标；后期 $\mathrm{Bi}_m=10^2\text{–}10^3$（内扩散控制）⇒ 用平均/表面值会**低估**烘干时间 | §2；L10、L11、L12 |
| **E10** | Q3/Q2 把附件 1 的 4 h 环境趋势线性外推到 72 h 而不加说明 | 附件 1 只到 4 h，且末尾 $T_\infty$ 尚未达平台、$C_\infty$ 仍在漂移 ⇒ 外推方式直接决定达标时间，必须显式声明并做敏感性 | 附件 1；§3.2 口径分叉 1 |
| **E11** | Q4 忽略收缩（$R$ 固定 2 cm），或用"理想收缩/体积守恒"从 $C$ 反推 $R$ | 忽略收缩会系统性偏离（含/不含收缩模型的对照见 L17）；而附件 2 的 $R(t)$ 与理想收缩**不自洽**（反算 $C$ 为负：$t=12$ h 处 $-0.73$ kg/kg）⇒ $R(t)$ 只能当给定输入 | §3.4 可核验观测；附件 2；L17、L22 |
| **E12** | Q4 在固定网格上直接模拟收缩体（不做坐标变换/ALE），或做了变换却漏掉网格速度带来的对流项 | 收缩后网格点与物质点分离，纯扩散形式的方程不再成立；漏掉对流项等于隐性丢弃收缩效应 | L14、L15、L16、L19、L20 |
| **E13** | 用纯数据驱动模型（回归/树模型/LSTM）替代机理 PDE 作主模型 | 题面**没有**药材内部含水率/温度的实测剖面（附件 1 是环境、附件 2 是半径），数据驱动无法给出题目要求的"内部空间分布"，也无法保证外推到 2–3 d | 附件 1/2 的数据范围；§1 题型辨析 |
| **E14** | 不做网格/时间步收敛就输出"四位小数"结果 | 题面要求 4 位小数与 0.1 cm×1 s 的密集输出；非线性 + 动边界下，离散误差很容易落在第 3–4 位小数上 | 附录 3/4 的强非线性；L23（高精度离散的必要性讨论） |
| **E15** | 把附件 1 的"烘房水分浓度"与药材的"水分浓度"当成同一个量混用 | 二者同名不同物：一个是环境条件（$C_\infty$），一个是被求的场量（$C$）；混用会直接写错边界条件 | 附录 1 说明与题面第 1 问表述 |
| **E16** | 用干燥前沿/退行前沿（receding front）等更复杂的多相模型取代题面给定的单相扩散参数集 | 题面用附录 2/3/4 的 $D$ 经验式**完全指定**了传质闭式；引入多相模型会引入题面未给的参数，且与"统一采用附录 3 公式"的要求冲突 | 题面问题 2 的"（为简化问题，相关经验公式统一采用附录 3 中的公式）"；L5（多相模型的系数难确定） |
| **E17** | 把"收缩停止"（附件 2 后段 $R$ 平台）直接等同于"烘干结束"，而不做 $C\le0.15$ 的场判据 | 二者机理不同：收缩停止反映结构/体积不再变化（可能只是达到某含水率区间），题面的烘干判据是**处处 $C<0.15$**；两者若不同必须说明差异来源 | 附件 2；题面问题 3/4 表述 |

---

## 5. 文献台账（已逐条核验）

核验方式：以 **CrossRef 公开 API** `https://api.crossref.org/works/<DOI>` 逐条回查标题/作者/年份/期刊/卷期页（核验脚本见 §6 留痕）。除 L29 外全部为 CrossRef 已注册 DOI。

> **本轮（2026-09-29）逐条重核结果**（`_tmp/lit_verify_ledger.py`：把**本表声称的**年/刊/卷/期/页
> 与 CrossRef 返回值**逐字段自动比对**，不再靠肉眼）：
> **30 条中 27 条全字段一致（OK）**；`L1` 首轮因 SSL 握手超时误报 MISS，单独重取后一致
> （2020, *Heat and Mass Transfer* 56(6): 1971–1983）；`L5` 是**假阳**——本表写的是
> "2018: 9456418, 1–13"（文章号 + 页码并列），CrossRef 的 `page` 字段只存 `1-13`；
> `L29` 为中文 DOI，CrossRef 返回 404（其独立核验见 §5.1）。
> 结论：**台账内 30 条 DOI 在本轮全部仍然存在、且题录与 CrossRef 一致**。

| 编号 | 条目（作者. 年份. 标题. 期刊 卷(期): 页. DOI） | 用于 |
|---|---|---|
| L1 | Koukouch A., Bakhattar I., Asbik M., Idlimam A. 2020. Analytical solution of coupled heat and mass transfer equations during convective drying of biomass: experimental validation. *Heat and Mass Transfer* 56(6): 1971–1983. doi:10.1007/s00231-020-02817-w | Q1 |
| L2 | Nylen J., Sheehan M., Whelan A., Antunes E. 2024. Internal and surface temperature profiles of spherical biosolids particles during convective drying. *Drying Technology* 42(13): 2044–2055. doi:10.1080/07373937.2024.2407959 | Q1 |
| L3 | López-Ortiz A., Rodríguez-Ramírez J., Méndez-Lagunas L.L., Martynenko A. 2018. Non-isothermal drying of garlic slices (*Allium sativum*, L.): Wave period and initial temperature of the heating/cooling. *Food and Bioproducts Processing* 111: 83–92. doi:10.1016/j.fbp.2018.06.005 | Q1 |
| L4 | Zhu Y., Wang P., Sun D., Qu Z. 2021. Multiphase porous media model with thermo-hydro and mechanical bidirectional coupling for food convective drying. *International Journal of Heat and Mass Transfer* 175: 121356. doi:10.1016/j.ijheatmasstransfer.2021.121356 | 机理（共用） |
| L5 | Vu H.T., Tsotsas E. 2018. Mass and Heat Transport Models for Analysis of the Drying Process in Porous Media: A Review and Numerical Implementation. *International Journal of Chemical Engineering* 2018: 9456418, 1–13. doi:10.1155/2018/9456418 | Q2（+共用） |
| L6 | Górnicki K., Winiczenko R., Kaleta A. 2019. Estimation of the Biot Number Using Genetic Algorithms: Application for the Drying Process. *Energies* 12(14): 2822. doi:10.3390/en12142822 | Q1（集总判据） |
| L7 | Ol'shanskii A.I., Gusarov A.M. 2020. Temperature of Material in the Process of Convective Drying of Thin Materials in the Falling Rate Period of Drying. *Journal of Engineering Physics and Thermophysics* 93(2): 364–368. doi:10.1007/s10891-020-02129-0 | Q2/Q3 |
| L8 | Li X., Yang K., Wang Y., Du X. 2023. Simulation study on coupled heat and moisture transfer in grain drying process based on discrete element and finite element method. *Drying Technology* 41(12): 2027–2041. doi:10.1080/07373937.2023.2213767 | Q2 |
| L9 | Martínez Vera C., Vizcarra Mendoza M.G. 2022. Concentration-dependent moisture diffusion coefficient estimation in peas drying considering shrinkage: An observer approach. *Biosystems Engineering* 218: 256–273. doi:10.1016/j.biosystemseng.2022.04.016 | Q2/Q4 |
| L10 | Ostanek J., Ileleji K. 2019. Conjugate heat and mass transfer model for predicting thin-layer drying uniformity in a compact, crossflow dehydrator. *Drying Technology* 38(5-6): 775–792. doi:10.1080/07373937.2019.1590394 | Q3 |
| L11 | Lin X., Xu J.-L., Sun D.-W. 2020. Comparison of moisture uniformity between microwave-vacuum and hot-air dried ginger slices using hyperspectral information. *Drying Technology* 39(8): 1044–1058. doi:10.1080/07373937.2020.1741006 | Q3 |
| L12 | Lv W., Zhang M., Wang Y., Adhikari B. 2018. Online measurement of moisture content, moisture distribution, and state of water in corn kernels during microwave drying. *Drying Technology* 36(13): 1592–1602. doi:10.1080/07373937.2017.1418751 | Q3 |
| L13 | Adrover A., Brasiello A. 2019. A moving boundary model for food isothermal drying and shrinkage: One-dimensional versus two-dimensional approaches. *Journal of Food Process Engineering* 42(6): e13178. doi:10.1111/jfpe.13178 | Q1/Q2（1D 径向取舍） |
| L14 | Adrover A., Brasiello A., Ponso G. 2019. A moving boundary model for food isothermal drying and shrinkage: General setting. *Journal of Food Engineering* 244: 178–191. doi:10.1016/j.jfoodeng.2018.09.018 | Q4 |
| L15 | Adrover A., Brasiello A., Ponso G. 2019. A moving boundary model for food isothermal drying and shrinkage: A shortcut numerical method for estimating the shrinkage. *Journal of Food Engineering* 244: 212–219. doi:10.1016/j.jfoodeng.2018.09.030 | Q4 |
| L16 | Lentzou D., Boudouvis A.G., Karathanos V.T., Xanthopoulos G. 2019. A moving boundary model for fruit isothermal drying and shrinkage: An optimization method for water diffusivity and shrinkage. *Journal of Food Engineering* 263: 299–310. doi:10.1016/j.jfoodeng.2019.07.010 | Q4 |
| L17 | Azhdari E., Emami A. 2019. Analytical and numerical study of drying of tomato in non-shrinkage and shrinkage model. *Mathematics and Computers in Simulation* 166: 253–265. doi:10.1016/j.matcom.2019.05.013 | Q4（收缩对照） |
| L18 | Guilherme G.L., Nicolin D.J. 2020. Soybean drying as a moving boundary problem: Shrinkage and moisture kinetics prediction. *Journal of Food Process Engineering* 43(10): e13497. doi:10.1111/jfpe.13497 | Q4（备用） |
| L19 | Das R., Islam M., Saini P., Kaduji G.R. 2025. Finite element modeling of banana slices in convective drying, studies on isotropic shrinkage kinetics using Arbitrary Lagrangian Eulerian approach. *Thermochimica Acta* 749: 180024. doi:10.1016/j.tca.2025.180024 | Q4 |
| L20 | Xanthopoulos G., Lentzou D., Papadakis S. 2026. Moving-boundary finite element modeling and inverse identification of moisture-dependent diffusivity in convective drying. *Drying Technology* 44(12): 1804–1820. doi:10.1080/07373937.2026.2686407 | Q4（备用，含变 $D$） |
| L21 | Ning Z., Khir R., Niederholzer F., Pan Z. 2026. Modeling of heat and moisture transfer during convective drying of in-hull almonds considering non-isotropic shrinkage. *International Journal of Heat and Mass Transfer* 258: 128286. doi:10.1016/j.ijheatmasstransfer.2025.128286 | Q4（备用，各向异性收缩） |
| L22 | Singh P., Talukdar P. 2019. Determination of shrinkage characteristics of cylindrical potato during convective drying using novel image processing. *Heat and Mass Transfer* 56(4): 1223–1235. doi:10.1007/s00231-019-02771-2 | Q4（**圆柱**试样收缩实测） |
| L23 | Upadhyay S., Singh V.K., Rai K.N. 2019. Finite difference Legendre wavelet collocation method applied to the study of heat mass transfer during food drying. *Heat Transfer—Asian Research* 48(7): 3079–3100. doi:10.1002/htj.21531 | Q2（高精度离散） |
| L24 | Yue Y., Zhang Q., Wan F., Ma G., Zang Z., Xu Y., Jiang C., Huang X. 2023. Effects of Different Drying Methods on the Drying Characteristics and Quality of *Codonopsis pilosulae* Slices. *Foods* 12(6): 1323. doi:10.3390/foods12061323 | 领域（中药材） |
| L25 | Bai T., Wan Q., Liu X., Ke R., et al. 2023. Drying kinetics and attributes of fructus aurantii processed by hot air thin-layer drying at different temperatures. *Heliyon* 9(5): e15554. doi:10.1016/j.heliyon.2023.e15554 | Q3（领域） |
| L26 | Zhu L., Xie Y., Li M., Zhang X., et al. 2024. Design and optimization of heat pump with infrared drying for *Glycyrrhiza uralensis* (Licorice) processing. *Frontiers in Nutrition* 11: 1382296. doi:10.3389/fnut.2024.1382296 | 领域（中药材，备用） |
| L27 | Wang X., Zhong J., Han M., Li F. 2023. Drying characteristics and moisture migration of ultrasound enhanced heat pump drying on carrot. *Heat and Mass Transfer* 59(12): 2255–2266. doi:10.1007/s00231-023-03412-5 | 领域（**圆柱形**物料，备用） |
| L28 | Gu Y., Zhen L., Jiang H. 2019. Mathematical analysis of temperature distribution uniformity of banana dried by vacuum radio frequency treatment. *Drying Technology* 38(15): 2027–2038. doi:10.1080/07373937.2019.1611595 | Q3（温度均匀性，备用） |
| L29 | 商涛, 袁越锦, 赵哲, 徐英英. 2023. 黄芩微波热风联合干燥动力学及品质研究. *中草药* 54(14): 4501–4510. DOI: 10.7501/j.issn.0253-2670.2023.14.010 | 领域（中药材，中文文献） |
| L30 | Le K.H., Tsotsas E., Kharaghani A. 2018. Continuum-scale modeling of superheated steam drying of cellular plant porous media. *International Journal of Heat and Mass Transfer* 124: 1033–1044. doi:10.1016/j.ijheatmasstransfer.2018.04.032 | 机理（连续介质建模，备用） |
| L31 | Crank J. 1975. *The Mathematics of Diffusion*, 2nd ed. Oxford University Press.（经典专著） | Q1/Q3 级数解与特征时间 |
| L32 | Luikov A.V. 1966. *Heat and Mass Transfer in Capillary-Porous Bodies*. Pergamon Press, Oxford.（经典专著） | 耦合传热传质奠基（Q1/Q2） |

**L29 的核验说明（诚实登记）**：`10.7501/j.issn.0253-2670.2023.14.010` **未在 CrossRef 注册**（该前缀由国内机构注册，CrossRef 返回 404）。其题录信息经**三个独立来源**核对一致：期刊官网 `tiprpress.com/zcy/article/abstract/20231410`、知网条目 `ZCYO202314010`、万方条目 `zcy202314011`（题名/作者/54 卷 14 期/4501–4510 页/2023 年）。若写作阶段需要更保守，可改用 L24/L25/L26 这三条 CrossRef 可核验的中药材文献。

### 5.1 中文核心刊文献（本轮新补 4 条 + 上一版 1 条，共 5 条）

> 阶段 SKILL 要求：题面与领域在国内的，除英文文献外**再补 2–3 篇近年中文核心刊**。
> 本表 5 条**全部为北大核心 / CSCD 刊**，且**逐条给出可复核的题录来源**（中文刊多数不在 CrossRef，
> 故按 SKILL 给的三条入口核验：维普结果页（`cqvip.com`，未登录可读题录）/ 知网（手机版/知网空间）
> / 期刊官网）。**没有为"看起来有中文"而编造任何条目。**

| 编号 | 条目 | 与本赛题的关系 | 核验来源（本轮实测） |
|---|---|---|---|
| **C1** | 王晓辉, 王学成, 唐培渝, 伍志成, 伍振峰, 王雅琪, 刘振峰, 杨明. 2023. 数值模拟仿真研究现状及其在中药干燥领域应用展望. *中国中药杂志* 48(13): 3440–3447. DOI: 10.19540/j.cnki.cjcmm.20230331.301 | **领域综述**：中药干燥的传热传质理论与数值模拟流程（建模—边界条件—求解—试验对比），并指出"模型精确性不高、缺少定量化指标"——正是本题 Q1–Q4 要落到具体口径的地方 | ① 维普结果页题录（北大核心·CSCD，2023 年 13 期，3440–3447，共 8 页）；② 知网手机版 `ZGZY202313003`（刊名《中国中药杂志》2023 年 13 期 + 关键词 + 摘要）；③ **PubMed E-utilities `esummary`（PMID 37474981）直接取回**：vol 48 / iss 13 / p 3440–3447 / 2023 Jul，8 位作者姓名与中文一致，`articleids` 含 `doi:10.19540/j.cnki.cjcmm.20230331.301`。三源一致 |
| **C2** | 刘格含, 王鹏, 吴小华, 山强, 范芃佐. 2020. 农产品热风干燥传热传质数值模拟研究进展. *食品工业科技* 41(22): 342–350, 357. DOI: 10.13386/j.issn1002-0306.2020010245 | **方法族综述**：把"干燥动力学模型 / 连续介质假设模型 / 孔道网络模型"三条路线并列评述——对应本报告 §3.2 里"薄层经验模型只作对照、主档用连续介质 PDE"的取舍依据 | ① 期刊官网 `spgykj.com` 的 `citation_*` 元标签（直取）：DOI 同上、卷 41、期 22、页 `342`–`350,357`、作者 5 人、出版日 2020-11-15；② 知网手机版 `SPKJ202022052`（《食品工业科技》2020 年 22 期 + 关键词）；③ 维普结果页（北大核心，2020 年 22 期，342–350，共 10 页）。三源一致 |
| **C3** | 张继凯, 郑霞, 肖红伟, 单春会, 李义璨, 杨涛庆. 2024. 山药片红外联合热风干燥热质传递收缩模拟与品质. *农业工程学报* 40(6): 134–145. DOI: 10.11975/j.issn.1002-6819.202308074 | **Q4 的直接工程范式**：COMSOL 有限元建"温度场–湿度场"耦合模型并**显式含收缩变形**，给出体积比随温度的变化——即"收缩必须进模型、且要单独验证"的中文实证 | ① 期刊官网 `tcsae.org/article/doi/10.11975/j.issn.1002-6819.202308074` 的 `citation_*` 元标签（直取）：DOI 同上、卷 40、期 6、页 134–145、作者 6 人；② 知网手机版 `NYGU202406013`（《农业工程学报》2024 年 06 期）；③ 知网空间同条目页（作者六人与①一致）。三源一致 |
| **C4** | 谢好, 齐娅汝, 万娜, 伍振峰, 王学成, 李远辉, 杨明. 2022. 中药材干燥过程中的皱缩机制、影响因素与调控策略. *中草药* 53(9): 2872–2881. DOI: 10.7501/j.issn.0253-2670.2022.09.031 | **Q4 的机理侧依据**：中药材干燥皱缩的**成因与影响因素**（物料特性/微观结构/机械性能/工艺条件），并指出皱缩会"降低水分扩散速率、延长干燥时间"——支撑本报告 §3.4 的因果链 | ① 期刊官网 `tiprpress.com` 的 `citation_*` / `DC.Contributor` 元标签（直取）：刊 中草药、卷 53、期 9、页 `2872`–`2881`、DOI 同上、作者 7 人逐字一致；② 检索快照另见维普 `7107351227`、万方 `zcy202209031`（题名一致，未直取）。①②一致 |
| **C5**（原 L29） | 商涛, 袁越锦, 赵哲, 徐英英. 2023. 黄芩微波热风联合干燥动力学及品质研究. *中草药* 54(14): 4501–4510. DOI: 10.7501/j.issn.0253-2670.2023.14.010 | **领域实证基线**：同一"中药材 + 热风（联合）干燥"场景下的干燥特性与品质研究 | 同 L29 注（该 DOI 未在 CrossRef 注册、本轮复取仍返回 404；题录经期刊官网/知网/万方三方核验，沿用上一版台账）。**若写作阶段要更保守，可只引 C1–C4 这四条已直取官网元标签的中文条目** |

- **中文支线的检索留痕**：`_tmp/lit_cn_search.py`（维普结果页 → 详情页取题名，限速 2–3 s/次）。
  实测坑：维普结果页的**题名是 JS 渲染的空标签**，题名只能从 `/doc/journal/<id>?sign=…` 详情页的
  `<title>` 取，且 `sign` 必须从结果页 HTML 抠（**不能自拼**）；作者/刊名/年期页在结果页纯文本里。
- **未采用的中文候选（诚实登记）**：检索到若干"中药材/农产品干燥动力学与数值模拟"中文条目，
  但或为**学位论文**（非核心刊）、或题录无法在三个独立来源对齐，**一律不列入台账**。
  它们对方向判断的增量信息已被 C1–C5 覆盖（结论一致：对流传热 + 有效扩散系数描述，
  变物性、收缩与"平均含水率 ≠ 各处达标"是主要难点）。

**未引用但检索到的同类工作（不列入台账，避免不可核验条目）**：检索过程中另见若干中文期刊的"中药材热风/联合干燥动力学"研究与国内学位论文（山药、地黄/麦冬、平贝母、二至丸等，含二维轴对称传热传质模型），其题录未能取得可核验 DOI，故**不作为引用条目**；它们对方向判断的增量信息已被 L24–L29 覆盖（结论一致：中药材干燥以对流传热 + 有效扩散系数描述，收缩与变物性是主要难点）。

---

## 6. 阶段边界与本轮留痕

### 6.1 产出边界（严格遵守阶段纪律）

- **本轮为"同题重跑"，内容复用上一版 + 全量复核**：本工作区已就**同一道题**（2026 A 题「药材的烘干问题」）产出过本报告，上一版 sha256 `46ba2bede972e0c6…`、`51955` 字节，归档副本在 `tmp/fr6/iso/reports/LITERATURE_DIRECTION.md`（另有 `tmp/fr4_iso*`、`tmp/fr5/iso` 三份同哈希副本）。按 `stage_discipline.md` 一·1.1 与工作区 CLAUDE.md 的复用表，**结论与文献台账沿用上一版**，并在 §6.2 对每个数、每条 DOI、每个题面常量**在本轮重新取证**；本轮更正见 §6.3。
  **复用成立的前提（本轮已逐项核验）**：题面与 6 份附件/模板与上一版所依据的**逐字节相同**（`request/problem.md` sha256 `ca878591…`，与读题确认页登记的题面哈希一致；附件 1/2 的规模、步长、极值、平台点本轮实测未变，见 §6.2）。
- 本阶段**不建立正式模型**、不写求解代码、不写论文、不生成 `paper/`、不产出 `result*.xlsx`。
- §2 的所有数字均由**题面附录的闭式 + 附件数据按定义式直接计算**得到（时间尺度、Biot 数、$D$ 取值、收缩反算），**不含任何拟合或求解结果**；其用途是给下游一个可复算的机理标尺。
- §3.4 关于"附件 2 与理想收缩不自洽"的判断是**量级核对**（依赖"$\rho=820$ 为初始湿态密度、干物质体积不变"这一标准假设），仅供 `analysis` 复核与决策，**不构成对 Q4 模型的结论**。

### 6.2 本轮复核清单（探针先复用、只对新对象写新的）

按 `stage_discipline.md` 一·1.1：开工第一步先 `ls _tmp/ tmp/` —— 结果**两处都没有**本轮要用的探针，
上一版把它们写在了 `C:\tmp\lit_*.py`（**系统临时目录，违反纪律，换个人/换个工作区就找不到**）。
本轮**先原样搬进 `_tmp/` 并重跑**，再只对新对象写新探针：

| 探针 | 性质 | 本轮输出（要点） |
|---|---|---|
| `_tmp/lit_mech_probe.py`（复用上一版，原样） | §2 量级锚点 | `α=1.688555e-07`、`τ_heat=2368.9 s`、`D_Q1(C0)=4.9377e-09`、`τ_mass=81010 s`、`τ_mass/τ_heat=34.2`、`Bi_h=1.3889`、`Bi_m=3.240`、`Bi_m(0.15)=862.652`、`D_q4/D_q23=0.203`；附件 1 `n=241, 0–14400 s, T 28→50.246, C 0.01963→0.05025`；附件 2 `n=145, R 2.0000→1.1980 cm, V/V0=0.2149`，收缩停在 `t=241200 s (2.79 d)`、其后 11 点不变 |
| `_tmp/lit_shrink_probe.py`（复用上一版，原样） | §3.4 收缩自洽性 | `V0=4.329268e-03`、`V_end=9.304541e-04`、`ρ_solid=562.0`；理想收缩要求终态 `C=-0.8488`；`t=12 h` 反算 `C=-0.7274`；`C_end=0.15` 时理想 `V/V0=0.4456` vs 实测 `0.2149` |
| `_tmp/lit_problem_verbatim.py`（**本轮新建**） | 题面常量与锚点的来源链 | ① `request/problem.md`(3770 字符, sha256 `ca878591d8897a89`) 与已人工确认的读题转写块**归一化后逐字符相同**；② 从题面原文正则抠出附录 2/3/4 全部系数（`820/2600/0.36/25/8×10⁻⁷`、`7×10⁻⁹`、`0.89`、`650/128`、`1450/2736`、`0.21/0.38`、`2.4×10⁻³`、`0.45/3850`、`4.2×10⁻⁴`、`0.30/3850`）；③ 由这些常量重算 §2 锚点，**与 §2 表逐位一致** |
| `_tmp/lit_verify_ledger.py`（**本轮新建**） | 台账逐字段自动比对 | 30 条中 **27 OK**；`L1` 单独重取后一致；`L5` 为假阳（本表"9456418, 1–13"并列文章号与页码，CrossRef `page` 只存 `1-13`）；`L29` CrossRef 404（中文 DOI，见 §5.1） |
| `_tmp/lit_cn_search.py`（**本轮新建**） | 中文核心刊检索（中文支线） | 维普结果页 → 详情页取题名；本轮据此新增 C1–C4 四条（题录三源对齐，见 §5.1） |
| `_tmp/lit_verify.py` / `lit_verify2.py` / `lit_verify3.py` / `lit_crossref.py` / `lit_crossref2.py`（复用上一版，原样搬到 `_tmp/`） | 上一版的 DOI 核验/检索脚本 | 作为 `lit_verify_ledger.py` 的前身保留；**仍可原样重跑** |

**探针纪律**：以上脚本一律**留在 `_tmp/` 不删**（`.out` 同步留存），下一轮开工先原样重跑。

**输入未变的硬证据（本轮实测 sha256，与读题阶段登记值逐份相同）**：
`request/attachments/附件1.xlsx` `7ef32870…`、`附件2.xlsx` `5563acbf…`、
`附件3/result1.xlsx`＝`result2.xlsx` `23b261b2…`、`result3.xlsx` `07e4793d…`、`result4.xlsx` `86e9300f…`、
`request/problem.pdf` `052d8014…`；`request/problem.md` 的**文本哈希** `ca878591d8897a89`
与读题确认页登记的题面哈希一致 ⇒ 上一版报告的**全部题面依赖项**在本轮仍成立。

### 6.3 本轮更正（对照上一版，只列真正改动的字句）

1. **§3.4 "实测收缩约为理想收缩的 2 倍"** —— 措辞不准（把"体积比"与"收缩量"混为一谈），
   已改为**三种说法分列**：实测终态体积是理想预测的 **0.48 倍**（理想是实测的 **2.08 倍**）；
   按"收缩掉的体积占比"算实测是理想的 **1.42 倍**；**反算含水率为负（$-0.849$ kg/kg）**才是
   "不自洽"的直接判据。数字本身未变（`_tmp/lit_shrink_probe.py` 本轮原样重跑得到同样输出），
   改的是**表述与判据的指向**。
2. **阶段 id/名**：上一版写 `2literature-direction` / `3analysis-modeling` / `4review-model`，
   与 `lib/web/server.py` 的 `STAGES` 现用 id（`literature` / `analysis` / `review`）不一致，
   已按现名统一（**只改称呼，不改内容**）。
3. **§5 新增 §5.1 中文文献台账**（C1–C4 为本轮新补，C5＝原 L29）：上一版只有 L29 一条中文条目，
   未满足 SKILL 的"2–3 篇中文核心刊"；本轮补齐到 5 条，并逐条给出三源核验。
4. **§5 台账核验由"人眼比对"升级为"逐字段自动比对"**（`lit_verify_ledger.py`），
   并在 §5 顶部登记本轮结果（27 OK / 1 假阳 / 1 非 CrossRef）。
5. **探针落点**：上一版把探针写在 `C:\tmp\`（系统临时目录），本轮**搬进工作区 `_tmp/`** 并留 `.out`，
   下一轮可直接复用（这一条同时是对上一版 §6 留痕方式的对齐修正）。

**未改动的部分**：§0–§4 的技术判断（题型归类、时间尺度分离、Biot 判据、变物性指数分解、
Q3 最坏点判据、Q4 动边界口径、E1–E17 错误清单）本轮**逐条复核后全部维持**；
§5 的 L1–L32 条目与题录本轮全部维持（见 §5 顶部结果）。

### 6.4 检索与核验留痕

- **上一版的检索**：WebSearch 共 7 次（英文 5、中文 2），主题涵盖耦合传热传质/圆柱试样、
  Luikov 与多孔介质模型综述、变 $D$（Arrhenius）、收缩与 ALE 动边界、干燥均匀性与达标时间、
  薄层干燥经验模型、中药材热风干燥；CrossRef `query.bibliographic` 检索 18 组主题、
  `works/<DOI>` 逐条核验 28 个 DOI。
- **本轮新增检索**：WebSearch 3 次（中文核心刊定向：中药材热风干燥传热传质数值模拟、
  中药材干燥收缩有限元、以及两条候选的题录核验）；维普结果页 → 详情页 2 组；
  知网移动端/知网空间 3 次（`ZGZY202313003`、`NYGU202406013`、`SPKJ202022052`）；
  期刊官网 3 次（`spgykj.com`、`tcsae.org`、`tiprpress.com`）；CrossRef 30 条逐字段核验。
- WebFetch 未使用（本环境对外域名安全校验常不可用）；全部核验走 WebSearch 片段 +
  CrossRef 公开 API + 维普/知网/期刊官网，符合 SKILL 的降级路径要求。

### 6.5 交给下游的三个显式决策点（须由 `analysis` 定，`review` 复核）

1. **几何口径**：采用"无限长圆柱、一维径向"（依据 $L/R=12.5$ 与 L13）还是二维轴对称？若选一维，须在假设中写明忽略两端效应。
2. **环境外推口径**：附件 1 的 4 h 数据如何延拓到 2–3 d（分段常数 / 一阶保持 / 趋于平台）？须显式声明 + 敏感性（E10）。
3. **能量方程闭合口径**：是否引入蒸发吸热/潜热项（题面未给参数）？若引入，须给出参数来源并单独披露（E3）。

### 6.6 已知的文献空白（不编造填补）

- 没有找到"圆柱形中药材、以全场最坏点达标定义烘干时长"的直接对口文献；Q3 的机理依据来自本报告 §2 的时间尺度分析与 PDE 本身，文献只提供"最差点须显式表征"的方法论支持（L10–L12）。
- 没有找到把"预热平衡段"与"恒温干燥段"按本题附件 1/2 的方式分段给定的同类文献；分段依据来自题面表述，机理合理性由 L3（非等温/初始温度影响）与 L2（表面—内部温度差）间接支持。
