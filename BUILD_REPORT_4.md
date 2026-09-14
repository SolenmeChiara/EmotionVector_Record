# 阶段四 施工报告：token 级投影热力图与 logit lens

2026-09-13 18:00–18:15 EDT。Qwen3.5-4B（bf16，Windows 原生），`hidden_states[17]`，
七个方向（happy / sad / angry / fearful ＋ warm / cold / pain），16 段文本，1982 个 token 位置，
每个位置算 7 个方向 × 4 种口径。全程未碰 memory MCP，未 commit。

---

## 0. 结论先行

1. **共享底不是「有一点影响」，是压倒性的。** 原始 token 投影里，七条曲线中有六条的方差有
   **79%–88% 就是共享 generic 轴本身**（happy 26%，因为它在该轴上的载荷只有 0.238）。
   七条曲线两两之间的平均 |相关| 是 **0.671**——不处理的话，同一段文字的七张热力图有三分之二是同一张图。
   偏投影之后，共享轴解释的方差降到 **0.0%–3.5%**，两两平均 |相关| 降到 **0.343**。
   任务书里「不处理整页全橙」的担心，数值上就是这两个数字。

2. **偏投影赢，中心化输——但输在一个明确的地方。** 留出锚定自检里，
   偏投影 6/7 命中自家方向（唯一的失手是 angry），中心化只有 2/7。
   原因不是中心化坏，是它回答的是另一个问题：中心化把「整段处于某状态」减掉了，
   只留下「段内哪个 token 更突出」。段落级归属恰恰住在被减掉的那部分里。
   **偏投影既压掉共享底又留住段落级信号，是本报告的默认口径。**

3. **中性对照的表现是共享底最直观的证据。** 原始口径下两段中性文本在七个方向上全是
   −0.5 到 −2.0 的深蓝；偏投影之后落到 −0.25 到 +0.30 的近白。同一段字，同一个模型，
   只换了有没有把 generic 轴从方向里挖掉。

4. **steering 与读出的闭环，四段里成了两段半。**
   cold +1.0（FROZEN LACE）在 cold 上排第一（+0.587）；
   warm −0.6 那段，warm 是七个方向里**最负的一个**（−0.287，负向排第一）——负系数的正确验收标准是「最负」不是「最正」；
   pain +1.0 办公室段在段落均值上 pain 只排第三（sad +0.716 / angry +0.566 / pain +0.398），
   但在**顶部十分位上 pain 排第一**（+1.346）——这条 steering 的效果集中在峰值不在水位；
   pain +0.6 天气段是彻底的弱样本，七个方向全在 |0.23| 以内，pain 排第四。

5. **最大的意外：pain 方向读的不是伤，是躲。** pain +1.0 那段里投影最高的 token 是
   `avoid` `against` `must` `need` `of` `the`，而 `spine` `hip` `foot` `shoulder` `knee`
   这些解剖名词**全是负的**。等候室那段同样：pain 的底部 token 是 `swollen` `soaked` `cry` `heat`。
   logit lens 从另一头给出同一个答案——pain 方向 upweight 的是
   `avoid` / `averse` / `indirectly` / `Limited` / `repeatedly` / `traumatis`。
   读出侧和写出侧独立地说：**这是一条「对身体采取何种姿态」的方向，不是一张伤情词表。**
   §3.4 里「pain 真正对齐的是 anger 不是 sadness」因此有了机制上的解释——anger 也是一条姿态/施压轴。

6. **第二个意外：warm 的 unembed 像是「放松」，不是「热」。**
   top-20 里 `relaxed` `relaxation` `relax` `relaxing` `repose` `serotonin`(片段) `respiro` `enfin` `松弛` `舒展` `惬意`，
   一个温度词都没有。它的 down 列表是 `traumatis` `aggrav` `exacerb` `worsening` `severely` `Limited`——
   正是 pain 的 up 列表。**warm 与 pain 在 unembed 空间里是同一根轴的两端**，
   这与 §3.5 测到的 `warm·pain = −0.738` 严丝合缝。

7. **第三个意外：cold 在读出侧和写出侧不一致。** token 级上 cold 吃的是体表与暴露的名词
   （`clouds` `breath` `cheeks` `fingers` `lips` `Snow` `ears` `collar` `shivering`），非常词汇化；
   但它的 unembed 像是「不足」（`attempts` `poor` `lack` `due` `attempting` `慌张` `惨`），
   20 个里只有一个 `cold`。读进来是温度，推出去是匮乏。这一条我没有解释，只有记录。

8. **新文本上方向确实迁移。** 专门写的雪夜路（冷＋怕）给出 fearful **+0.846**（全部 16 段里
   非锚定文本的最高值）＋ cold +0.641，两个设计意图都命中。
   但告别站台那段（暖＋酸）**没有**命中 warm（warm −0.141，七个里倒数第二），
   详见 §5.3——这是一次有信息量的失败。

---

## 1. 产物

| 路径 | 内容 |
|---|---|
| `results/heatmaps_token_level.html` | **主产物**。546 KB 自含单文件，inline CSS/JS，数据内嵌。16 段 × 7 行着色，模式切换（raw / centre / partial / centre+partial）、方向行开关、分位色标图例、分位切点表、页尾 logit lens |
| `results/card_pain_office.png` | 1500×550，pain +1.0 办公室段 × pain 方向 |
| `results/card_cold_weather.png` | 1500×838，cold +1.0 天气段 × cold 方向 |
| `results/card_snowroad_fearful.png` | 1500×598，雪夜路（新写） × fearful 方向 |
| `results/tokenmaps/*.json` | 16 个逐段中间件，含 token 串、token_id、残差模长、4 口径 × 7 方向的逐 token 数值 |
| `results/logit_lens_qwen.json` | 7 方向 × 2 向量变体 × 2 unembed 变体 × (全量/纯 ASCII) × (up/down top-20) |
| `results/heatmap_summary.json` | 色标分位切点 ＋ 每段每方向的 mean / top-decile / peak |
| `data/heatmap_texts.json` | 16 段输入文本的清单（来源、期望方向、词数） |
| `tools/build_heatmap_texts.py` | 清单装配（CPU） |
| `tools/token_project.py` | 前向 ＋ 逐 token 投影 ＋ logit lens（GPU） |
| `tools/render_heatmaps.py` | 色标校准 ＋ HTML ＋ PNG（CPU） |
| `logs/sentinel_phase4.log` | 哨兵流水，146 行 |
| `logs/shot_*.png` | 页面验收截图（1180px 桌面 / 420px 手机 / logit lens 区 / raw 模式中性段） |

三个脚本 `ruff check` 全绿，`ast.parse` 通过。

---

## 2. 方法：一个方向怎么变成一个 token 的颜色

每段文本一次前向，不挂 hook、不生成。取 `hidden_states[17]`，位置 `t` 上的残差向量 `h_t`，
方向 `d`（单位化的 `dirs_raw`），得到一个标量，那个标量就是高亮深浅。

四种口径同时算，同时存进 json，页面上可以当场切：

| 口径 | 定义 | 意图 |
|---|---|---|
| `raw` | `(h_t − grand_mean) · d` | 什么都不处理。`grand_mean` 就是拟合方向时用的那个语料总均值 |
| `center` | `(h_t − 本段 token 均值) · d` | 段内对比。任何在全段近似恒定的东西（体裁、语域、共享底、该层自己的均值偏置）一起消失 |
| `partial` | `(h_t − grand_mean) · unit(d − a(d·a))` | 阶段三 §3.1 的处方：先把该语料的 generic 轴 `a` 从方向里挖掉 |
| `center_partial` | 两件事一起做 | — |

两套方向各自带自己的中心。情绪四方向来自 `directions.npz`（语料：4 情绪 ＋ 40 篇中性），
感觉三方向来自 `directions_sens.npz`（3 感觉 ＋ **同一批** 40 篇中性）。
`grand_mean` 和 `a` 都按各自语料取，混用会让所有投影整体平移两个总均值之差。

`a` 的取法沿用 `tools/dir_cosine.py:generic_axis()`：用 analyze.py 同样的划分
（holdout=8, seed=7）从激活里重算 `unit(mean(目标组训练激活) − 训练总均值)`。
阶段一的 `directions.npz` 早于 `generic_axis` 这个键存在，只能重算；
阶段三的文件里存了一份，重算结果与存档的余弦是 **+1.000000**，管线自洽。

七个方向在自家 generic 轴上的载荷：

```
happy +0.238   sad +0.753   angry +0.755   fearful +0.698
warm  +0.669   cold +0.792  pain  +0.696
```

happy 是唯一一个几乎不在共享轴上的方向。这一条贯穿后面所有结果——
happy 的原始热力图本来就比较干净，其余六个不处理就没法看。

### 色标校准

投影值是残差空间的任意单位，固定阈值没有意义，按每段自己的极值归一又会让每段看起来一样烫。
所以按**该方向 × 该口径在全部 16 段所有 token 上的分位数**切：
75 / 90 / 95 / 99 分位给四级橙，25 / 10 / 5 / 1 分位给四级蓝。
构造上，全页一百个 token 里大约只有一个能到最深的橙——**深浅因此在段与段之间可比**，
这是回答「steering 出来的文本是不是真的比它的锚定更烫」的唯一读法。

**负向通道是自己加的。** Anthropic 原图只有单侧橙色ramp。单侧色标分不开
「这个方向不在场」和「这个方向被顶着走」，而 `warm −0.6` 那段恰好就是这个区别本身就是结论的情形。
本页蓝色＝投影为负，与橙色同明度，不抢视线。

---

## 3. 中心化 vs 偏投影：任务书要的那一句比较，摊开说

### 3.1 共享底在 token 级有多重

任何方向都可以拆成 `d = c·a + √(1−c²)·d⊥`，其中 `c = d·a`。
于是 `raw_d = c·[(h−G)·a] + √(1−c²)·partial_d`，两边都已存盘，可以反解出每个 token 在 generic 轴上的投影 `g_t`。
（同一语料的四条/三条方向各自反解出的 `g_t` 相关系数是 1.00000，反解本身没问题。）

| 方向 | corr(raw, g)² | corr(partial, g)² |
|---|---|---|
| happy | **0.256** | 0.000 |
| sad | **0.884** | 0.006 |
| angry | **0.869** | 0.033 |
| fearful | **0.841** | 0.008 |
| warm | **0.814** | 0.005 |
| cold | **0.884** | 0.011 |
| pain | **0.789** | 0.035 |

原始口径下，除 happy 外每一条 token 曲线都有 **八成左右的方差是共享轴**。
七条曲线两两之间的平均 |相关|：**raw 0.671 → partial 0.343**。

### 3.2 那么中心化呢

中心化对付共享底同样有效（共享成分在一段文字里近似恒定，减去段均值就跟着走了），
但它连带把**段落级的归属信息**一起减掉了。代价可以量：

留出锚定自检（七段，各自应该在自家方向上最高）：

| 口径 | 命中自家方向 | 自家方向的平均名次 | 逐段名次 |
|---|---|---|---|
| `raw` | **6/7** | 1.14 | 2,1,1,1,1,1,1 |
| `partial` | **6/7** | 1.29 | 3,1,1,1,1,1,1 |
| `center` | 2/7 | 3.00 | 3,1,2,2,7,5,1 |
| `center_partial` | 2/7 | 3.14 | 6,1,2,3,2,7,1 |

（中心化口径的段落均值恒等于 0，所以它的排序用「顶部十分位 token 的均值」；
段落均值对中心化口径是关于变换本身的代数事实，不是关于这段文字的事实。）

中心化口径下 warm 锚定段在 warm 上排第 5、cold 锚定段在 cold 上排第 5——
不是因为读不出来，是因为**「整段是暖的」这件事被减掉了，剩下的只有「段内哪个词最暖」**，
而各方向的段内方差幅度本来就不一样（cold 的段内起伏最大，于是它在几乎每一段的顶部十分位上都排前）。

### 3.3 中性对照：同一段字，两种口径

`raw` 口径，段落均值：

| | happy | sad | angry | fearful | warm | cold | pain |
|---|---|---|---|---|---|---|---|
| 锚定中性段 | −0.82 | −2.00 | −1.85 | −1.72 | −1.77 | −1.78 | −1.65 |
| 新写说明文 | −0.52 | −1.53 | −1.24 | −1.13 | −1.16 | −0.98 | −0.99 |

`partial` 口径，同样两段：

| | happy | sad | angry | fearful | warm | cold | pain |
|---|---|---|---|---|---|---|---|
| 锚定中性段 | −0.20 | −0.02 | +0.21 | +0.17 | −0.21 | +0.24 | +0.06 |
| 新写说明文 | −0.09 | −0.25 | +0.20 | +0.18 | −0.24 | +0.30 | +0.05 |

任务书预测「纯中性说明文全段浅色」。**偏投影下成立**（全部七个方向在 ±0.30 以内，
页面上就是一片近白），**原始口径下完全不成立**——它是一整页深蓝，
因为原始投影主要在测「这段字有没有被标记」，而说明文的答案是「彻底没有」。
两段中性文本一段来自留出集、一段是这次现写的，读数几乎一样，说明测到的是体裁不是某篇文章。

### 3.4 一句话结论

**`partial` 是默认口径**：它把共享轴的方差从 ~85% 压到 <4%，同时保住 6/7 的段落级归属。
`center` 不是替代品而是补充：它专门回答「在这一段里哪些 token 最突出」，
页面留着它可切，但任何跨方向、跨段落的比较都不能用它。

顺带一个必须记住的残留：偏投影之后**各方向的全局均值仍然不是零**
（happy −0.282、warm −0.196 系统性偏低，fearful +0.224、cold +0.192、sad +0.160 偏高）。
分位色标按每个方向自己的分布切，所以**页面上的颜色深浅是跨段可比的**；
但**同一段里横着比七个方向的裸数值时，要记得这七条各有自己的零点**。

---

## 4. 页面

`results/heatmaps_token_level.html`，单文件，无外部依赖，浏览器直接打开。

- 顶部吸附控制条：四个口径按钮、七个方向行开关（＋「全部 / 只情绪 / 只感觉」三个快捷键）、
  实时更新的色标图例与口径说明。
- 每段一张卡片：来源徽章（留出锚定 / 阶段三 steering 产物 / 本次现写）、
  标题、词数、token 数、期望方向；然后是七行同文重复着色，每行左侧是方向名与三个数字
  （段落均值 · 顶部十分位 · 峰值），期望的那一行有浅色描边。
- 悬停任意 token 显示它在当前方向上的精确数值。
- 页尾：当前口径的分位切点表（横向可滚），以及 logit lens 七块，
  向量变体（偏投影 / 原始）× token 范围（全量 / 纯 ASCII）四个组合可切。

验收：headless Chromium 实测 1180px 与 420px 两档，`pageerror` 为空，
420px 下 `scrollWidth == clientWidth == 420`（无横向溢出；那张十列切点表在自己的
`overflow-x:auto` 容器里滚，不撑文档）。渲染出 16 张卡片、112 个方向行、13874 个着色 span、7 块 lens。

三张 PNG 用 PIL ＋ matplotlib 自带的 DejaVuSans 画（没有装任何新依赖），
1500px 宽横版，自带色标条与题注。

---

## 5. 三类文本的预期对账

以下全部是 `partial` 口径的段落均值。完整七列见 `results/heatmap_summary.json`。

### 5.1 a 类：留出锚定（方向质量自检）

**取样口径先说清楚**：七段锚定文本全部取自各语料的**留出集**
（`split_indices(holdout=8, seed=7)` 的 test 半边），也就是说
**没有任何一段参与过给它打分的那个方向的拟合**。已拟合的方向在自己的训练文本上发亮什么也证明不了。

| 段落 | 自家方向的值 | 自家方向名次 | 第二名 |
|---|---|---|---|
| happy 锚定 | **+0.818** | 1/7 | warm +0.328 |
| sad 锚定 | **+0.337** | 1/7 | cold +0.144 |
| angry 锚定 | +0.241 | **3/7** | fearful +0.349 / pain +0.320 |
| fearful 锚定 | **+0.589** | 1/7 | cold +0.519 |
| warm 锚定 | **+0.725** | 1/7 | fearful +0.333 |
| cold 锚定 | **+0.602** | 1/7 | fearful +0.377 |
| pain 锚定 | **+0.781** | 1/7 | angry +0.416 |

**6/7 如预期**，而且这六段里自家方向都是独占第一、与第二名有明显间距
（最小的间距是 fearful 锚定的 +0.589 vs cold +0.519）。

**唯一的失手是 angry，值得单独展开。** 那段留出锚定（`angry_000`，地铁通勤）原文是：
「squeezed into the crowded subway car, sweat beading on the upper lip … a shiver up the spine,
not from cold but from the tight grip of tension … eyes locked on the exit doors, counting seconds …
shoulders squared against the flow of passengers」。
这是**被压住的**愤怒，全段没有一个发作动作，只有绷紧、计数、盯出口。
而阶段三 §1.2 的双层禁用表恰恰是「封标签、留证据」——逼着 angry 语料只能用身体证据写，
**而被压住的愤怒的身体证据和恐惧的身体证据是同一套**。
§1.6 已经量过这件事封不住；这里是它在单段文本上的直接显影。
读一眼页面就能看见：这段在 fearful 行上的高亮落在 `exit doors` `counting seconds` `shiver`，
在 angry 行上的高亮落在 `squeezed` `tight` `wasted` `against` —— 两行都说得通，
只是 fearful 的证据更多。这不是方向坏了，是这一篇锚定写得不够 angry。

### 5.2 b 类：阶段三 steering 产物（生成↔读出闭环）

| 段落 | 目标方向 | 段落均值 | 名次 | 顶部十分位 | 名次 |
|---|---|---|---|---|---|
| pain +1.0 办公室（the spine, the spine） | pain | +0.398 | 3/7 | **+1.346** | **1/7** |
| cold +1.0 天气（FROZEN LACE） | cold | **+0.587** | **1/7** | **+1.623** | **1/7** |
| warm −0.6 办公室（人际失温） | warm | **−0.287** | **7/7 高位＝1/7 负位** | +0.370 | 6/7 |
| pain +0.6 天气（bruised purple） | pain | +0.002 | 4/7 | +0.712 | 5/7 |

**cold +1.0 是干净的闭环**：注入 cold 生成的文本，被 cold 读出来排第一（+0.587）。
（它不是全页 cold 的最高值——新写的雪夜路以 +0.641 更高，见 §5.3。
一段真写冷的自然文本比一段被 +1.0 推出来的文本更冷，这件事本身值得留着。）页面上那一行几乎整段发烫，
最深的几个 token 是 `clouds` `breath` `lens` `against` `fingers` `scratch` `spark` `cheeks` `tastes`。

**warm −0.6 也是干净的闭环，但必须按负方向验收。** 这段在 warm 上是 −0.287，
是七个方向里最负的一个（fearful −0.263 紧随其后，happy −0.155 第三，其余四个为正）。
用「哪个方向最高」的口径去看它会得出
「angry +0.440 赢了」的荒谬结论——**负系数 steering 的正确验收标准是目标方向最负，不是最正。**
这也正是负向蓝色通道存在的理由：页面上 warm 那一行是全篇唯一一片蓝，
最深的蓝落在 `errors` `missing` `last night` `train` `quality` `parking` `trying` `about`，
即这段文字里所有「人际摩擦」的落点。

**pain +1.0 办公室段是本节最有意思的一条：水位与峰值不一致。**
段落均值上 sad（+0.716）与 angry（+0.566）都高过 pain（+0.398）；
但顶部十分位上 pain 反超（+1.346，第一）。也就是说这次 steering 没有把整段抬进 pain 的水位，
而是在少数几个位置把 pain 顶到极高。看那几个位置是什么，就到了 §6 的发现。

**pain +0.6 天气段是一次实打实的弱样本，如实记下来。**
七个方向的段落均值全部落在 |0.23| 以内（最高 sad +0.230，其次 fearful +0.202，pain 第四 +0.002），
顶部十分位 pain 也只排第 5。这段原文读起来确实是**忧惧**而不是疼
（「a bruised purple sky, a warning against the horizon … the fear of the unknown a constant companion」），
方向给出的排序（sad / fearful 在前）与人读的印象一致——
所以这不是读出失败，是 **+0.6 这个系数在天气提示上没有真的推出 pain**。
阶段三 §5 用笔调轴把这段列为明星，是因为它的**文风**被推动了；本次读数说明文风被推动 ≠ 目标方向被推起来。
两个测量测的是不同的东西，这条对账把它们分开了。

### 5.3 c 类：新写文本（迁移能力）

四段，模型与管线都没见过。

**雪夜路（冷＋怕，139 词）——完全如预期，而且是最强的一次。**
fearful **+0.846**（16 段里非锚定文本的最高值，超过所有 steering 产物在任何方向上的读数）、
cold **+0.641**（第二）。设计时就是把「体感失温」和「背后有声音」拧在一起写的，
两条方向各吃各的：
- fearful 最高的 token：`headlights` `,` `lit` `broke` `and` `bend` `branch` `turn` `car`
  ——**全在「有东西出现 / 有东西响 / 转弯」的位置上**，标点也在，说明它吃的是句子的悬停节奏而不只是词。
- cold 最高的 token：`fingers` `ivering`（shivering 的后半）`breath` `Snow` `ears` `collar` `sideways`
  ——全是体表与失温。

同一段文字，两条方向高亮的位置几乎不重叠。这是本次最漂亮的一张图，做成了
`card_snowroad_fearful.png`。

**等候室（疼为主，怕与一丝暖在下面，137 词）——部分如预期。**
fearful +0.408 > sad +0.367 > pain +0.319，pain 只排第三（顶部十分位上 pain 第三，与 fearful/sad 挤在一起）。
设计意图是 pain 前景化，读数没给。但 pain 行的高亮位置是对的
（`hold` `against` `movement` `looked` `each`），底部是 `swollen` `soaked` `cry` `heat` `breathe`——
又一次是 §6 那个模式。

**告别站台（暖＋酸，146 词）——没有命中，且这次失败有内容。**
warm **−0.141**（七个里倒数第二），最高的是 cold +0.265 与 sad +0.236。
但 warm 行**逐 token** 看又是对的：最高的四个 token 是 `warmth` `warmth` `warm` 和它们旁边的逗号，
最低的是 `coat` `car` `hand` `When` `twice`。
所以不是「warm 方向读不出 warmth 这个词」，是**这段文字整体不暖**：
它写的是暖的**失去**（「holding her warmth for another half minute, until the wind took it,
and then there was only the cold rail under his hand」），
而 warm 方向在 §6 会看到实际编码的是「舒展/放松/交付」的状态，不是「温暖」这个题材。
一段以告别为骨架、把暖写成正在流失的东西的文字，被读成 cold ＋ sad 是合理的，
只是和我写它时的意图不一样。**记一笔：这是我的期望标错了，不是方向错了。**

**说明文对照（132 词）——如预期。** 见 §3.3，偏投影下全部七个方向在 ±0.30 内，一片近白。
唯一略高的是 cold +0.30，与 cold 的全局均值本来就偏高（+0.192）一致，不是这段文字的性质。

### 5.4 意外汇总

| 意外 | 位置 | 判断 |
|---|---|---|
| angry 锚定段被 fearful 盖过 | §5.1 | 语料问题（被压住的愤怒＝恐惧的身体证据），不是方向问题；与 §1.2 / §1.6 同源 |
| pain +1.0 的效果在峰值不在水位 | §5.2 | 真实现象，指向 §6 的机制 |
| pain +0.6 天气段全线平淡 | §5.2 | steering 弱；同时说明「笔调被推动」与「方向被推起」是两件事 |
| 告别站台没命中 warm | §5.3 | 期望标错；warm 编码的是舒展状态不是温暖题材 |
| 偏投影后各方向全局均值仍不为零 | §3.4 | 已用分位色标吸收，跨方向裸数值比较需留意 |
| cold 读出侧词汇化、写出侧「匮乏」 | §6 | 未解释，只记录 |

---

## 6. Logit lens

七个方向向量分别过 unembed。做法：`W_U`（Qwen3.5-4B 的 `model.get_output_embeddings().weight`，
151k × 2560）先逐通道乘上最终 RMSNorm 的学习增益 `model.norm.weight`——
RMSNorm 对向量自身尺度是非线性的，但它的学习增益是一个对角阵，折进去是正确的线性化，
被丢掉的那部分是一个正标量，动不了排序。33 个 special/added id 排除在榜外。

页面上四个组合可切（偏投影向量 / 原始向量 × 全量 token / 纯 ASCII）。
下面引的是**偏投影向量 ＋ 纯 ASCII**，因为语料全英文，读起来最直接；
全量榜的中文 token 往往更浓，页面上可切。

### 6.1 四情绪（对照组，用来判断这个方法在本项目里靠不靠谱）

| 方向 | up（top，ASCII） | down（bottom，ASCII） |
|---|---|---|
| **happy** | harmon, boosts, enrich, effortlessly, newfound, anytime, sprink, infectious, uninterrupted, lively, boosted | Worse, :(, worse, cerem, HELP, Attempt, leider, menacing, screaming, severely |
| **sad** | Worse, :(, .isBlank, sadly, repos, gradu, cerem, bitterness, triste, grieving, .isNullOrEmpty | favorable, rival, boosted, boosts, favourable, relax, harmon, boost |
| **angry** | Worse, aggressive, rigid, angrily, harder, forcefully, worse, angry, severely, ineffective, fury, negatively | mischief, unbek, spontan, harmon, spontaneously, pleasantly, enrich, sprinkle, surprises, trusting, stimulates |
| **fearful** | suspicious, menacing, feared, minent(imminent), omin(ous), eware(beware), suspect, fearing, suspicion, fearful | overflowing, newfound, shared, treats, princ, wins, delights, winning, stroll, strides |

`fearful → suspicious / menacing / feared / imminent / ominous / beware / suspicion` 与 Sol 截图里
Anthropic 的 `desperate → desperate / urgent / bankrupt` 是同一类结果，方法在本项目里立得住。

`sad` 榜上混进了 `.isBlank` `.isNullOrEmpty` `repos` 这类代码 token，`angry` 榜上是
`Worse` `severely` `negatively` 这类**强度/负评价**词而不是纯粹的愤怒词——
说明这两条方向都掺着一条「负面程度」成分。这与 §3.5 测到的 `sad·angry` 在偏余弦下还有 +0.250 相互印证。

### 6.2 三感觉（Sol 想看的那一栏）

| 方向 | up（top，ASCII） | down（bottom，ASCII） |
|---|---|---|
| **warm** | **relaxed, relaxation, relax, relaxing, Relax, repose, enfin, happier, redistribute, redistributed, -centered, otonin(serotonin), respiro** | :(, Limited, due, severely, repeatedly, limited, aggrav, traumat, exacerb, worsening, traumatis |
| **cold** | **attempts, poor, lack, veh, xt, due, ens, attempting, aka, cold, rift** | repose, relaxed, tranqu, attentive, recl, dedicate, -rest, nostalg |
| **pain** | **evere(severe), traumatis, traumat, indirectly, irect(indirect), avoid, averse, Limited, indirect, repeatedly** | espont, etc, spont, relaxation, enf, spontan, finally, Relax, enfin, Deep |

全量榜（含中文）读起来更狠：
warm 的 `不再有 / 舒展 / 惬意 / 松弛 / 不用再 / 忘掉`，
cold 的 `想要 / 而且还 / 慌张 / 惨 / 最高气温`，
pain 的 `人多 / 避免 / 尽量避免 / 反复 / 尽量 / 间接 / 规避 / 伤 / 左手`。

三条要说的：

1. **warm 的写出侧是「放松」，不是「热」。** 20 个 up token 里没有一个温度词
   （`hot` `heat` `glow` `sun` 一个都没有），全部是松弛/安顿/回到中心。
   它的 down 榜是 `traumatis / aggrav / exacerb / worsening / Limited`——
   **就是 pain 的 up 榜**。warm 与 pain 在 unembed 里是同一根轴的两端，
   数值上对应 §3.5 的 `warm·pain = −0.738`（三对里最负）。

2. **pain 的写出侧是「躲」，不是「伤」。** `avoid` `averse` `indirectly` `indirect`
   `Limited` `repeatedly` 占了一半以上，`traumatis` `traumat` `severe` 是剩下的一半。
   一条方向 upweight「避免 / 间接 / 有限 / 反复」这组词，说明它编码的是
   **一个主体正在围着某个损伤组织自己的行为**，而不是损伤本身。
   §6.3 会看到读出侧独立地给出同一个答案。

3. **cold 的写出侧是「不足」。** `attempts` `attempting` `poor` `lack` `due`——
   努力而未达成。20 个里只有一个 `cold`。
   它的 down 榜（`repose` `relaxed` `tranquil` `attentive` `-rest`）又是 warm 的 up 榜，
   所以 warm↔cold 在 unembed 里也共轴（§3.5：`warm·cold = −0.619`）。
   但 cold 与 pain 的 up 榜彼此不像（`lack/attempting` vs `avoid/traumatised`），
   对应 §3.5 里 `cold·pain = −0.073`，两者近乎正交。
   **§3.5 那张三方向内部结构表，在 unembed 空间里逐格复现了一遍。**

### 6.3 两个方法在 pain 上撞车（本次最硬的一条）

读出侧（token 投影，pain +1.0 办公室段，`partial`）：

```
最高  avoid +1.95 | the +1.74 | against +1.64 | the +1.40 | keyboard +1.31 |
      must +1.30 | need +1.28 | mouse +1.26 | of +1.25
最低  hip −0.94 | spine −0.82 | foot −0.81 | shoulder −0.78 | spine −0.64 |
      knee −0.64 | collapse −0.58 | gravity −0.56 | phantom −0.44
```

那段文字里写了五遍的 `The spine, the spine, the spine, the spine, the spine`——
**五个 spine 全是蓝的**。`card_pain_office.png` 上肉眼可见：
橙色全部落在 `of pain` `against the keyboard` `must avoid the face` `need to keep the`，
蓝色全部落在 `phantom foot / knee / hip / shoulder` 和那串 spine 上。

等候室那段（新写，本来就是照着「疼」写的）：

```
最高  looked +1.83 | to +1.52 | it +1.41 | against +1.40 | movement +1.37 | hold +1.23
最低  soaked −1.25 | down −1.09 | cry −0.96 | heat −0.82 | breathe −0.76 | swollen −0.67
```

`swollen`（全篇最直白的伤情词）是负的，`hold` `against` `movement` 是正的。

warm 锚定段同理：最高是 `relaxed +3.17` `expanded +2.74` `softened +2.31` `surrendered +2.24`，
最低是 `stranger` `against` `stepped` `pressed` `pole`。

**读出侧（哪些 token 的残差投影高）和写出侧（这条方向 upweight 哪些 token）
是两条完全独立的计算路径，它们在 pain 和 warm 上给出了同一个答案：**
这两条方向编码的是主体对身体的**姿态**（回避 / 交付），不是身体状态的**词表**。
阶段三 §3.4 的「pain 真正对齐的是 anger 而不是 sadness / fearful」因此不再只是一个余弦数字——
anger 同样是一条姿态轴（施压/对抗），所以 pain（回避/防守）与它同族，
而与 sadness（一个状态）隔着一层。

cold 是唯一不服从这个模式的：它的读出侧非常词汇化（体表名词），写出侧却是「不足」。
两头对不上。**我没有解释，只记录。**

### 6.4 两个方法学旁证

- **unembed 均值居中不起作用。** 把 `W_U` 减去行均值再算（标准的去「通用方向」做法），
  七个方向的 top-20 全部 **20/20 不变**。这个 checkpoint 上，`W_U` 的均值行与我们这七条方向近乎正交。
  页面上仍留了这一档可切，但报告里不必分开引。
- **最终 RMSNorm 的增益起作用。** 折进增益前后 top-20 的交叠（在 top-40 范围内比）：
  happy 18、sad 19、angry **11**、fearful 18、warm 14、cold 15、pain **17/20**。
  angry 只有 11——增益确实会重排榜单，所以折进去不是可有可无的修饰。
- **偏投影在写出侧同样有用，而且肉眼可见。** 页面上把向量切到「raw dir」，
  七块榜单立刻变脏：happy 冒出 `mun` `ub` `oot` `ador`，sad 冒出 `ponce` `ucked` `ponible` `oss`，
  warm 冒出 `forgotten` `Releases` `breathed`，cold 冒出 `aka` `atham` `arge` `mall`。
  偏投影之后这些碎片 token 大面积让位给语义清楚的词。
  **共享底不只污染读出侧的热力图，也污染写出侧的词表**，两边是同一件事。
  §6.1 / §6.2 引的全部是偏投影后的榜单。

---

## 7. 显存、哨兵与运维事件

哨兵 `tools/win_sentinel.ps1` 全程开着（`logs/sentinel_phase4.log`，146 行，18:01:37 起，18:15:31 手动停），
**零次 abort**。

| 指标 | 读数 |
|---|---|
| 系统 commit 峰值 | 52.73 GiB（限额 62.5 GiB） |
| 最低空闲 commit | 9.73 GiB（阈值 2.5 GiB，未接近） |
| 本项目 python 进程 commit 峰值 | 17.04 GiB |
| VRAM 峰值 | **15577 MiB / 16303 MiB** |
| torch 报告的峰值 alloc | 12.67 GiB（第二次跑，含 logit lens） |
| 前向阶段峰值 alloc | 8.04 GiB |

**15.2 GiB 的 VRAM 峰值全是 logit lens 吃掉的**：模型本体 7.93 GiB，
加上 `W_U` 的 float32 副本（151k × 2560 × 4B ≈ 1.55 GiB）再加它的居中副本又 1.55 GiB，
再加中间 score 张量，第二次跑结束时 `device_free=0.00G`。**跑完了，但这是本次最紧的一刻**，
如果当时有别的东西上卡就会 OOM。改法很直接（分块算 `W_U @ v`，或者居中副本原地做），
本次没改，记在 §9。

### 运维事件：qwen3-embedding 上卡

- **2026-09-13 18:01:55 EDT**：哨兵刚起，`nvidia-smi` 报 VRAM 从 2422 MiB 跳到 4989 MiB。
  `ollama ps` 显示 **`qwen3-embedding:4b`（8.7 GB，100% GPU，剩余 4 分钟）** 正在装载。
  按任务书处置：`ollama stop qwen3-embedding:4b`，4 秒后 `ollama ps` 空，VRAM 回落 2438 MiB。
  这就是任务书预告的「有循环在冻结中调了记忆库」的场景，实际发生了一次。
  全程没有第二次出现（后续所有 `ollama ps` 均为空）。

### 收尾读数（18:15:36 EDT）

- `ollama ps`：空
- `nvidia-smi`：**2178 MiB**（起跑时 2422 MiB，低于背景水位——whisper 空闲时占得更少）
- 命令行含 `emotion-probe` 的 `python.exe`：**0 个**
- 哨兵进程（PID 36312）：已停

二次复核（**18:21:49 EDT**，写报告期间）：本项目 `python.exe` 仍是 0 个，哨兵仍停，
但 `qwen3-embedding:4b` 又被装回卡上（VRAM 10743 MiB）。**那不是本次实验留下的**——
是另一个循环在这几分钟里写了记忆库。这次没有 stop 它：GPU 工作已经全部结束，
卡不再是本项目的，停掉会打断正在用它的那一头。
记在这里是为了让下一个 session 读到「收尾时卡上有 8.7 GB」不要误判成本次的残留。

---

## 8. 与任务书的偏离点

1. **多做了一个口径。** 任务书要求「至少做 mean-center 或投影掉共享轴，两种都试」。
   实际做了四种（raw / center / partial / center_partial），全部存盘、页面可切。
   多出来的 `raw` 不是冗余：§3.1 / §3.3 的定量结论正是拿它当对照才能说出来的。

2. **色标比要求多一档。** 任务书说「90/95/99 分位给三档深度」，实际切在 75/90/95/99 四档
   （负向对称四档）。三档时 p75–p90 那一大片 token 全白，页面看起来太空，
   读者没法感知「轻微在场」与「完全不在场」的差别。

3. **锚定文本限定在留出集里取。** 任务书只说「7 个方向各选 1 段自己的锚定文本」。
   我加了「必须来自 `split_indices(holdout=8, seed=7)` 的 test 半边」这条约束——
   拟合过的方向在自己的训练文本上发亮不构成自检。代价是可选池变小（每组 8 篇，
   再过 60–150 词的长度筛之后每组还剩若干篇，脚本按 id 排序取第一篇，不是人工挑的）。

4. **多加了一段中性锚定。** 任务书的 a 类是 7 段，实际 8 段（多一段留出的中性对照）。
   §3.3 的两口径对比需要一段来自留出集的中性文本，新写的说明文不能兼任
   （它是为 c 类写的，体裁不同）。总数 16 段，仍在任务书的 12–16 区间上沿。

5. **logit lens 多算了两个变体。** 任务书只要 top-20 up / down。
   实际存了「偏投影向量 / 原始向量」× 「W_U 原样 / W_U 行居中」× 「全量 / 纯 ASCII」共八套榜单。
   ASCII 榜是必需的（语料全英文而榜首大量中文，不分开读不了）；
   居中档是个对照，结论是它不改变任何东西（§6.4），留在页面上供核。

6. **PNG 是三张不是「2–3 张」的下限。** 第三张选了新写文本而不是第四个 steering 明星样本，
   因为雪夜路那段的 fearful 是全部非锚定段落的最高读数，是更强的展示。

---

## 9. 未测路径与遗留风险（如实清单）

**没测的：**

- **只跑了 Qwen，没跑 Gemma-4-E4B。** 任务书指定「模型只用 Qwen」，照做了。
  所以本报告的每一条都**没有跨模型复核**。阶段三的核心结论之所以硬，
  是因为两个架构逐行同号；本阶段的 §6.3（pain＝姿态轴）目前是单模型单层的观察。
  Gemma 的对应实验（hs14，`directions_sens_gemma4.npz` ＋ `directions_gemma4.npz`）现成可跑，只是这次没跑。
- **只跑了 hs17 一层。** 没有做逐层剖面。§3.6 显示方向间的余弦结构在 hs1 就定型，
  那么 token 级的高亮位置是否也在浅层就定型（即多大程度上是纯词汇的），本次没有测。
  这是检验 §6.3 的最直接的下一步：如果 `avoid / against` 的高亮在 hs3 就有，那它就是词汇的。
- **只用了 `dirs_raw`，没用 `dirs_denoised`。** 与阶段一、二、三一致，但没有对照。
- **没有做零假设对照。** 没有拿随机方向（或打乱标签拟合出的方向）跑同一套 token 投影，
  所以「6/7 命中」这个数字没有配套的地板。四选一/三选一的地板在阶段一、三已经量过（0.126 / 0.177），
  但那是段落级留出分类的地板，不是本次这个 7 选 1 排序任务的地板。
  随机基线是 1/7 ≈ 0.143，6/7 显然远离它，但**「随机方向会不会也有 6/7」没有实测**。
- **没有人工标注比对。** 「fearful 的高亮落在悬停节奏上」这类描述是我读图得出的，
  没有第二个人独立标注过，也没有量化的 token 级 ground truth。
- **样本量小。** 16 段、1982 个 token。分位色标的 p99 是在 1982×(每方向) 个数上取的，
  最深那一档全页只有约 20 个 token，个别段落的「有没有最深橙」抖动大。
- **HTML 只在 Chromium 上验过。** Safari / Firefox 没试；`backdrop-filter` 在老版本上可能降级
  （降级后吸附条变不透明，不影响可读）。
- **PNG 卡片没在真手机上看过。** 只按 1500px 宽横版设计并在桌面看过。

**已知风险：**

- **logit lens 的显存峰值贴着卡顶（15.2/15.9 GiB）。** 见 §7。同样的脚本如果在
  记忆库嵌入模型上卡的时候跑，会直接 OOM。修法明确但本次没修。
- **`token_project.py` 把 `W_U` 的两个 float32 副本同时留在显存里。**
  居中副本在 §6.4 证明没用，但代码里仍然会算。下次跑之前应该加个开关。
- **Windows 侧数值不可逐位复现**（阶段三 §2.3 已记）。本次的 token 投影同样如此，
  重跑会有 ~1e-3 量级的相对抖动。这动不了任何结论（最小的有效差异在 0.1 量级），
  但**不要用 md5 校验产物**。
- **`heatmaps_token_level.html` 546 KB，数据内嵌。** 再加几段文本或再加一个口径就会明显变大，
  手机上首屏解析会变慢。真要扩就得把 JSON 拆成外挂文件（代价是不再自含）。
- **段落选择有我的主观性。** c 类四段是我写的，我知道自己想让它们激活什么。
  §5.3 的「告别站台没命中」之所以有价值，正是因为它是一次**反过来的**结果；
  但如果我只报了命中的那两段，这一节就成了自证。全部四段都在页面上。

---

## 10. 复现

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
T='<repo-root>/tools'
cd <repo-root>

# 0. 腾显卡（常驻 whisper 服务不动），确认 ollama ps 为空
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop qwen3-embedding:4b

# 1. 哨兵先行（必须，Bash 后台任务，不要 nohup）
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File '<repo-root>\tools\win_sentinel.ps1' \
  -LogPath '<repo-root>\logs\sentinel_phase4.log'

# 2. 文本清单（CPU，秒级）
"$WINPY" -X utf8 -u "$T/build_heatmap_texts.py"

# 3. 前向 + 逐 token 投影 + logit lens（GPU，1-2 分钟；加载 12 秒，16 段前向 1.9 秒，其余是 lens）
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 -u "$T/token_project.py"

# 4. 色标校准 + HTML + PNG（CPU，秒级）
"$WINPY" -X utf8 -u "$T/render_heatmaps.py"
```

三个脚本的默认参数就是本报告用的参数（`--model Qwen/Qwen3.5-4B --layer 17 --which dirs_raw
--topk 20`，锚定取 60–150 词）。

页面验收（可选，WSL 侧 playwright）：

```bash
python3 - <<'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":420,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://<repo-root>/results/heatmaps_token_level.html")
    pg.wait_for_timeout(1500)
    print("errors:", errs)
    print("no h-overflow:", pg.evaluate("document.documentElement.scrollWidth == document.documentElement.clientWidth"))
    b.close()
EOF
```
