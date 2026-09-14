# 阶段三 施工报告：感觉方向（warm / cold / pain）的提取、几何与 steering

执行：opus 子代理，2026-09-13 16:03 – 17:35（EDT，约 90 分钟）。
前置：`BUILD_REPORT_1.md`（阶段一方法）、`BUILD_REPORT_2_gemma_win.md`（Windows 配方与哨兵）、`WINDOWS_RUN.md`。
设计出自 Sol：测试题与采样参数原样不动，只把注入向量从四情绪换成三个体感方向。

**结论先行：**

1. **三个感觉方向都立住了。** 107 篇锚定（warm 35 / cold 32 / pain 40）＋沿用同一份 40 篇中性对照。
   两个模型的留出读出都远高于地板：Qwen 三分类 **0.958**（打乱地板 0.126），Gemma **0.958**（地板 0.177），随机是 0.333。

2. **原始余弦矩阵几乎不能直接读。** 两套方向各自以自己的语料总均值为中心，而两个总均值里都含「非中性」这个共同成分——
   实测它本身的余弦就有 **+0.864**（Qwen）/ **+0.824**（Gemma）。矩阵每一格都驮着这个底。
   报告因此同时给三样东西：原始余弦、这个共享底、以及把各自的共享轴投影掉之后的偏余弦。

3. **偏余弦下，两个模型给出几乎相同的结构，跨家族复制：**
   `warm → happy`（warm 行里唯一的正值）、`cold → fearful`、`pain → angry`。
   预注册的四条预测，成立三条，`pain·fearful` 只在原始余弦里成立、偏掉共享成分后基本归零。

4. **两条最强的对齐各有一个反面。** `cold·fearful` 是全表最高的一对，但 cold 锚定的身体语言
   （shiver / hunched / clenched / trembled）与 fearful 锚定几乎是同一套，本次**分不开**表征与写法；
   反过来 `warm·happy` 是唯一一条**不能**用词汇解释的对齐（warm 的词表与 happy 的重合度在 warm 行里倒数第二）。

5. **方向之间的夹角，不等于它们推出来的文本的相似度。** 同一层同一系数同一种子只换向量，
   `warm` 与 `happy` 的输出 Jaccard 是全表最低（0.109 / 0.105），
   和「两个不相干方向」的底线一样低——尽管它俩在残差流里对齐得最干净。
   而 `cold` 与 `fearful` 的输出最像（0.162 / 0.177）。两个模型一致。

6. **双通道：数字轴和笔调轴不是一起动的，是按方向分别决定的。**（Qwen，四个种子池化）
   `cold` 把两条轴锁在一起单调地拖，报出的气温从 19.7 °C 一路到 **−10.5 °C**；
   `pain` 几乎只动笔调、把气温只从 19.4 拖到 15.5 就开始整段不报数字；
   `warm` 在 −0.6…+0.6 之间同步，但最负端 (−1.0) 反弹回 21.8，方向失效。

7. **没有一格碎裂。** 两份正式产物的全部 27 个「方向 × 系数」格（Qwen 18 + Gemma 9）里，TTR 最低 0.52，没有任何一格低于 0.40 的复读阈值。

8. **一次哨兵事件，根因不在本实验。** 17:07:30 哨兵按规则杀掉补充跑，因为**别的循环调用了记忆库、
   把 Ollama 的 8.7 GB 嵌入模型拉上了同一张卡**。我全程没有调用任何 memory MCP 工具。
   逐条落盘让损失只有两个方向的补充样本，卸掉嵌入模型后重跑补齐。
   收尾后两分钟同一个模型又被拉上卡一次，所以这不是偶发——下阶段跑 Gemma 之前必须先解决它。

---

## 1. 锚定语料：设计决策与它们的代价

方向的质量全部押在这 107 篇上，所以设计决策逐条摊开说，全文见附录 A。

### 1.1 沿用同样的 15 个日常主题，不另起「炉火 / 冰水 / 烫伤」专用场景

任务书举的例子（炉火、毛毯、热咖啡 / 冰水、寒风、雪地 / 烫伤、割伤、牙痛）是典型的体感场景。
**没有采用**，改为把体感放进阶段一那 15 个日常主题里（地铁通勤、小厨房做饭、遛狗、雨天公交站……）。

理由是余弦矩阵这个核心产物要求可比：

- 专用场景会让**主题与组完全共线**，warm 方向会同时编码「有火有毯子」，那时 `cos(warm, happy)` 里有多少是体感、
  多少是「室内温馨场景 vs 其他场景」根本分不开。
- 同一批主题还让感觉语料与情绪语料、与共享的中性对照三者**场景分布一致**，这是把两套方向放进同一个余弦里的前提。

代价如实记：体感必须从普通场景里找，而不是场景围着体感建，所以锚定比专用场景**温和**——
「遛狗时太阳晒在皮肤上」终究不如「炉火前烤手」浓烈。这条写进未测路径（§9）。

### 1.2 双层禁用表：封「标签」，留「证据」

任务书要求与情绪词汇解耦。实现上分两层，**两层都对所有组一视同仁**：

| 层 | 内容 | 施加于 |
|---|---|---|
| 情绪词 | 阶段一那 108 词原样沿用 | 全部五个情绪组、中性组、三个感觉组 |
| 体感标签 | 新增 **62 词**（warm/warmth/hot/heat/cold/chill/freezing/icy/pain/painful/hurt/ache/sore 及其全部变体，外加 temperature） | 三个感觉组 |

第二层不是可选的装饰，它来自一个开工时量出来的事实：**情绪语料本身就带着体感词汇，而且带得不对称**——

```
happy   : warm 11 / warmth 3 / warmly 2 / warming 1 / hot 1   （39 篇中）
sad     : cold 10 / colder 1 / chill 2 / frozen 1 / froze 1 / aching 2 / ached 2 / ache 1
angry   : heat 8 / hot 2 / hotter 1 / heated 1 / scorching 1
fearful : chill 4 / cold 3 / froze 2 / colder 1 / freeze 1
neutral : cold 1 / hot 1 / heated 1                            （40 篇中）
```

也就是说，如果 warm 锚定可以自由地说「warm」，那 `cos(warm, happy)` 里会有一块是
**两份语料共用同一个词元**，跟残差流里有没有体感表征毫无关系。封掉标签就切断了这条捷径。

**划线的原则是：封掉命名状态的那个词，留下身体实际报告的东西。**
`warm / heat / cold / chill / pain / ache / sore` 出局；
`steam, radiator, frost, metal, throb, sting, blister, numb, shiver` 留下——封掉证据就没东西可写了，而证据正是锚定的全部意义。

**由此产生的不对称，方向是保守的**：感觉组被剥掉了标签词，而共享的中性对照原样保留（40 篇里有 2 篇含体感标签）。
这只会让感觉组**更难**与中性分开，不可能凭空造出一个方向。

### 1.3 中性对照沿用同一份，不重新生成

`stories_neutral.jsonl` 40 篇原样复用。如果给感觉语料另生成一份中性组，两套方向的总均值就会
相差「两次独立采样的对照组之间的差异」，而余弦要测的东西比这个差异小。共用一份把这项误差清零。

附带得到一个验证：同样 40 篇中性在两次 Qwen 提取里的激活**几乎一致**（见 §2.3）。

### 1.4 范例修掉了指令遵循的塌陷（第一次冒烟 6 格丢 3 格）

第一版只用散文约束陈述禁令，冒烟测试 6 个格子丢了 3 个，失败方式完全一致：
模型把体感写对了，然后照样把它命名出来——`cold[00]` 连续 10 次尝试每次都写进 `cold` 或 `frigid`。

修法是给每组一段**写好的范例**，示范标签的位置上应该放什么。范例设在 15 个主题**之外**的场景，
不给任何一格提前泄题。加上范例后同样的槽位一次通过（warm 4/4，此前 1/2；`cold[00]` 3 次尝试成功）。

### 1.5 产出与形状

| 组 | 保留 | 丢弃 | 需重试 | 词数均值 | 标准差 | 范围 | 句数 |
|---|---|---|---|---|---|---|---|
| warm | 35 | 5 | 26 | 84.2 | 9.3 | 65–103 | 6.0 |
| cold | 32 | 8 | 26 | 75.5 | 11.3 | 54–104 | 5.3 |
| pain | 40 | 0 | 11 | 82.5 | 8.6 | 62–99 | 5.3 |
| （对照）happy | 39 | 1 | 18 | 81.2 | 10.9 | 66–104 | 4.3 |
| （对照）neutral | 40 | 0 | 6 | 67.1 | 12.1 | 52–105 | 5.5 |

合计 107 篇，856.5 秒。**丢弃率比阶段一高一个量级**（13/120 vs 1/200），全部来自双层禁用表：
热感标签是最难绕开的，`warm` 丢 5、`cold` 丢 8，而 `pain` 一篇没丢。

事后重新施加过滤器核对磁盘上的成品：**三个感觉组对两张表都干净**。

两处形状上的诚实标注：

- **cold 偏短（75.5 词）也偏少（32 篇）**。它比 warm 少 3 篇、比 pain 少 8 篇。
  差分均值的总均值是按行平均的，组大小不等会让总均值略微偏向大组。没有为了均衡而丢数据
  （那会损失更多信息），但这项不均衡是真实存在的，读 cold 的结果时要记着。
- 感觉三组（75–84 词）与情绪四组（81–88 词）同一档，都明显长于中性组（67 词）。
  阶段一那条「中性组偏短，篇幅可能是可用线索」的弱点**原样继承**，没有修掉。

### 1.6 情感性身体语言：封不掉，所以数出来

禁用表封的是「命名情绪的词」，封不掉微笑、叹气、发抖这类**不点名却在传情绪的身体语言**。
数出来（含该类词的篇数占比）：

| | warm | cold | pain | happy | sad | angry | fearful | neutral |
|---|---|---|---|---|---|---|---|---|
| 占比 | 0.51 | 0.66 | 0.45 | 1.00 | 0.78 | 0.80 | 0.80 | 0.07 |

感觉组明显低于情绪组、明显高于中性组。**其中一条要单独点名**：
cold 的高频项是 `shiver 9 / hunched 9 / clenched 8 / trembled 3`，
而 fearful 的高频项是 `trembling 9 / trembled 9 / hum 5 / clenched 5 / hunched 3`——**几乎是同一套**。
所以 §3 里 `cold·fearful` 偏高，有一部分就是这个，不必等结果出来再解释。

### 1.7 词汇重合度：余弦矩阵必须对着读的那张底表

去停用词后各组词表的 Jaccard：

| | happy | sad | angry | fearful | neutral |
|---|---|---|---|---|---|
| **warm** | 0.197 | **0.220** | 0.203 | 0.217 | 0.132 |
| **cold** | 0.153 | 0.218 | 0.189 | **0.223** | 0.126 |
| **pain** | 0.188 | 0.247 | 0.235 | **0.260** | 0.159 |

组内对照（量级参考）：warm–cold 0.252、cold–pain 0.288；happy–sad 0.236、sad–fearful 0.292。
**跨集重合度与集内重合度同一量级**，所以词汇本身解释不了任何强烈的方向对齐，但它给了每一格一个基线。

两条直接有用的读法：

- `pain` 与 `fearful` 词汇重合度最高（0.260），**所以 pain·fearful 为正这条预测本来就可以被词汇满足**，
  它不是一个强证据。
- `warm` 与 `happy` 的重合度（0.197）在 warm 那一行里是**倒数第二**，低于 warm–sad（0.220）。
  因此若残差流里 `warm·happy` 反而最高，那**不是词汇造成的**——这是本次唯一一条不被词汇解释的对齐。

---

## 2. 方向提取

### 2.1 配置

阶段一同法：留出每组 8 篇（共 32）完全不参与拟合；`d_g = mean(该组训练激活) − mean(全部四组训练激活)`，单位化；
`dirs_raw` 与中性主成分降噪版并行产出，steering 用 `dirs_raw`（与阶段一、二一致）。

| | Qwen3.5-4B bf16 | Gemma-4-E4B 8bit |
|---|---|---|
| 语料 | 147 篇（107 感觉 ＋ 40 中性） | 同左 |
| hidden_states | 33 | 43 |
| 提取显存峰值 | **8.02 GiB** | **10.96 GiB** |
| 注入层（本次） | **hs17** | **hs14** |

层的选择**刻意不用脚本自动挑的那一对**：Qwen 感觉语料自动挑出 `[24, 30]`、Gemma 挑出的头名是 42。
本次固定用情绪轮的杠杆层（Qwen hs17、Gemma hs14），因为整份报告的比较都建立在
「同一层、同一提示、同一种子，只换注入向量」之上，换层就没有可比性了。这是有意的偏离，记在 §8。

### 2.2 读出质量（留出集，三分类，随机 0.333）

| | 差分均值峰值 | 降噪峰值 | 逻辑回归峰值 | 打乱标签地板（均值/最高） | 杠杆层准确率 |
|---|---|---|---|---|---|
| Qwen3.5-4B | 0.958 @hs5 | 0.958 @hs5 | 1.000 @hs4 | 0.126 / 0.250 | 0.958 @hs17 |
| Gemma-4-E4B | 0.958 @hs6 | 0.958 @hs6 | 1.000 @hs5 | 0.177 / 0.250 | 0.917 @hs14 |

杠杆层的组内 vs 组外 Cohen's d，**两个模型几乎逐位吻合**：

| | warm | cold | pain |
|---|---|---|---|
| Qwen hs17 | 2.561 | 1.809 | 1.774 |
| Gemma hs14 | 2.559 | 1.804 | 1.707 |

结构与情绪轮同形：一个远高于其余的正极（warm，d≈2.56，对应情绪轮的 happy）＋两个挤在一起的负极
（cold/pain，d≈1.7–1.8，对应 angry/fearful）。

**不要把 0.958 与情绪轮的 0.875 直接比**：三分类随机基线 0.333、四分类 0.25，类别数也少一个，
这两个数字不在同一个尺子上。能说的只有「感觉方向在留出集上远离地板」。

### 2.3 两项管线核对

**注入尺度是可比的。** 系数含义沿用「coeff × 该层 pooled residual 的 mean L2 norm」，
而这个 norm 来自各自的语料，所以两套方向的绝对扰动量未必相同。实测差异可以忽略：

| | 情绪语料 norm | 感觉语料 norm | 比值 |
|---|---|---|---|
| Qwen hs17 | 7.416 | 7.487 | **1.010** |
| Gemma hs14 | 146.66 | 146.34 | **0.998** |

1% 以内，warm 的 +0.3 与 happy 的 +0.3 是同一个力道。（Qwen 深层差得多，hs32 已到 1.066，所以这条只对杠杆层成立。）

**共享中性对照在两次提取里几乎一致，但不是逐位一致。** 同样 40 篇中性，两次 Qwen 前向：

| hs | 每篇相对 L2 偏差（均值） | 同一篇两次结果的余弦（最小） |
|---|---|---|
| 0（embedding） | 0（逐位相同） | 1.000000 |
| 17 | 3.5e-3 | 0.99999 |
| 32 | 4.2e-3 | 0.99999 |

组均值的相对偏移只有 **5.7e-4**，余弦 1.000000000——平均把逐篇的抖动基本消掉了，
比本报告任何一个余弦数字小四个数量级，动不了任何结论。

但它**推翻了阶段一的一条记录**：阶段一说「管线是确定性的，重跑 md5 不变」。
那是在 WSL 里成立的；**Windows 侧重跑不是逐位可复现的**（embedding 层逐位相同，偏差全部产生在 GPU 矩阵乘路径，
典型的 bf16 累加顺序／cuBLAS kernel 选择不确定性）。
后果很实际：Windows 侧**不能再用 md5 当「我的改动有没有动到数值」的校验**，得改成带容差的比较。

---

## 3. 方向级余弦矩阵（核心结果之一）

### 3.1 先量共享底

两套方向各以自己语料的总均值为中心，而两个总均值都含同一份中性对照＋各自的非中性组。
「这段文字处于某种被标记的状态、而不是平板的对照」这个成分因此出现在**两侧的每一个方向里**。
把它单独量出来：`a = mean(全部目标组) − 总均值`，每个语料一条。

```
cos(a_sens, a_emo) = +0.864   (Qwen hs17)
cos(a_sens, a_emo) = +0.824   (Gemma hs14)
```

**原始余弦矩阵的每一格都驮着这个。** 所以下面每张原始表后面都跟一张把各自的 `a` 投影掉再单位化的偏余弦表。

### 3.2 Qwen3.5-4B，hidden_states[17]

**原始余弦**（行＝感觉，列＝情绪）

| | happy | sad | angry | fearful |
|---|---|---|---|---|
| **warm** | 0.319 | 0.388 | 0.268 | 0.321 |
| **cold** | −0.006 | 0.502 | 0.567 | **0.658** |
| **pain** | −0.092 | 0.554 | **0.627** | 0.530 |

**偏余弦**（各自共享轴投影掉）

| | happy | sad | angry | fearful |
|---|---|---|---|---|
| **warm** | **+0.333** | −0.076 | −0.317 | −0.225 |
| **cold** | −0.180 | −0.059 | +0.109 | **+0.260** |
| **pain** | −0.269 | +0.147 | **+0.309** | +0.062 |

### 3.3 Gemma-4-E4B，hidden_states[14]

**原始余弦**

| | happy | sad | angry | fearful |
|---|---|---|---|---|
| **warm** | 0.171 | 0.396 | 0.293 | 0.314 |
| **cold** | −0.018 | 0.414 | 0.497 | **0.634** |
| **pain** | −0.092 | 0.419 | **0.537** | 0.459 |

**偏余弦**

| | happy | sad | angry | fearful |
|---|---|---|---|---|
| **warm** | **+0.204** | +0.046 | −0.197 | −0.213 |
| **cold** | −0.092 | −0.104 | +0.018 | **+0.250** |
| **pain** | −0.167 | +0.039 | **+0.226** | +0.034 |

**两个模型逐行同号、逐行同序。** 不同架构、不同量化、独立提取的两套方向，
给出同一套几何：warm 指向 happy，cold 指向 fearful，pain 指向 angry，
且每一行里 happy 与另外三个情绪分处两侧。

### 3.4 与预注册预测的对账

| 预注册预测 | 原始余弦 | 偏余弦 | 判定 |
|---|---|---|---|
| `pain·sad` 显著为正 | +0.554 / +0.419 | +0.147 / +0.039 | **原始成立，偏掉共享成分后只剩微弱正值** |
| `pain·fearful` 显著为正 | +0.530 / +0.459 | +0.062 / +0.034 | **原始成立，偏掉后基本归零——不成立** |
| `warm·happy` 为正 | +0.319 / +0.171 | +0.333 / +0.204 | **成立，且是唯一偏掉共享成分后反而变强的一格** |
| `cold` 往疏离／负面漏 | happy −0.006 / −0.018，fearful +0.658 / +0.634 | fearful +0.260 / +0.250 | **成立，且漏得最准的是 fearful 不是 sad** |

三条要说清楚的：

1. **`pain` 真正对齐的是 anger，不是 sadness/fear。** 原始矩阵里 pain 与 sad/fearful 都很高，
   偏掉共享成分后只剩 `pain·angry`（+0.309 / +0.226）站得住。预测说对了符号，说错了对象。
2. **`warm·happy` 是唯一一条既被残差流支持、又不被词汇解释的对齐。** §1.7 已经量过：
   warm 的词表与 happy 的重合度在 warm 那一行里倒数第二（0.197 < warm–sad 0.220），
   而偏余弦里 `warm·happy` 是 warm 行唯一的正值，两个模型都是。方向相反，所以不可能是同一个原因。
3. **`cold·fearful` 最高，但它有一个现成的平凡解释。** §1.6 已经量过：cold 锚定的身体语言
   （shiver / hunched / clenched / trembled）几乎就是 fearful 锚定的那一套。
   本次实验**分不开**「cold 与 fearful 共享表征」和「cold 与 fearful 共享发抖蜷缩的写法」。

### 3.5 方向之间的内部结构

偏余弦下的组内关系（Qwen / Gemma）：

| | warm·cold | warm·pain | cold·pain |
|---|---|---|---|
| 感觉 | −0.619 / −0.602 | −0.738 / −0.681 | −0.073 / −0.175 |
| （情绪对照）| happy·sad −0.618 / −0.613 | happy·angry −0.665 / −0.639 | sad·angry +0.250 / +0.143 |

**感觉三方向的内部结构与情绪四方向同构**：一个正极强烈反对另外两个，另外两个彼此近乎正交。
warm 之于 cold/pain，正如 happy 之于 sad/angry/fearful。

### 3.6 逐层剖面：不是杠杆层特有的

六对预注册组合在全部层上的原始余弦（完整表在 `results/dir_cosine_{qwen,gemma4}.json`）：

- `cold·fearful` 在**两个模型的每一层**都是六对里最高的（Qwen 0.59–0.76，Gemma 0.63–0.76）。
- `warm·happy` 全程最低且平（Qwen 0.23–0.34，Gemma 0.08–0.28）。
- 排序在 hs1 就已经基本定型（Qwen hs1：cold·fearful +0.614 vs warm·happy +0.289）。
  **这么早就成立，说明其中相当大一块是浅层的词汇／表层成分**，不是深层语义对齐——
  又一条支持 §3.4 第 3 点保留意见的证据。

---

## 4. Steering 生成

| | Qwen3.5-4B | Gemma-4-E4B |
|---|---|---|
| 层 | hs17（解码块 16） | hs14（解码块 13） |
| 系数 | ±0.3 / ±0.6 / ±1.0 | −0.3 / +0.3 / +0.6 |
| 条件 | 3 方向 × 6 系数 × 2 提示 = **36 段** | 3 × 3 × 2 = **18 段** |
| 耗时 | 214 s | 505 s |
| 显存峰值 | 8.00 GiB | 10.84 GiB |
| 产物 | `results/steering_samples_sensation_qwen.md` | `results/steering_samples_sensation_gemma4.md` |

采样与情绪轮完全一致：temperature 0.8、top_p 0.95、max_new_tokens 150、seed 1234、同种子跨所有条件。
Gemma 的窄窗口沿用阶段二实测结论（hs40 本轮未跑）。

**基线没有重跑**，按任务书从 `steering_samples.md` / `steering_samples_gemma4.md` 原文搬运
（`steer.py --baseline-from`）。搬运是必要的：对照工具从同一份文件里读基线。
搬完做了核对——两份文件的基线**逐字相同**（cross 工具报 overlap 1.000 / identical text）。

补充跑（不在任务书条目内，见 §8）：
- Qwen 三个额外种子（2234/3234/4234）× 仅预报题 × 6 系数，各自带自己的基线，共 **57 段**。
- Gemma 仅预报题、max_new_tokens 320、含基线，共 **10 段**。

---

## 5. 双通道分析：数字轴 vs 笔调轴（核心结果之二）

### 5.1 先说一个必须先解决的测量问题

任务书要求逐条提取「报出的字面温度数字」。直接正则会错三次，都在样本里真实出现过：

| 情况 | 例子 | 处理 |
|---|---|---|
| 一个读数写两遍 | `72°F (22°C)` | 折成一个（取摄氏） |
| **模型自己换算错了** | `15°C (7°F)`（15 °C 其实是 59 °F） | 同样折成一个取摄氏。若当成两个独立读数，会往均值里塞进一个 −13.9 °C 的幽灵 |
| 有度数没单位 | `rises to a soft 68°` | 不折算（68 可能是 20 °C 也可能是 68 °C），单开一列计数，**不丢掉** |

第二条本身就是个小发现：**注入之后模型的单位换算会出错**。
第三条不修的话，高系数格会被误报成「模型没报数字」，而它其实报了。

残留的已知缺口：`12°C / 8°C (54°F / 46°F)` 这种斜杠并列的双语对照会被算成 4 个读数
（12、8、12.2、7.8）。重复项数值相近，对均值影响在 0.2 °C 量级，没有再修。

### 5.2 Qwen：四个种子池化（主结果）

单个种子每格只有一条预报，分不开「向量推动了数字」和「采样器恰好落在别处」。
所以主结果用 seed 1234（任务书那 36 段）＋三个补充种子，共 4 条／格。
`n` 是四条里真正报出了温度的条数——**报不报数字本身就是一条信息**。

**基线：16.2 °C（4 条里 2 条报了数字）**

| 方向 | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 |
|---|---|---|---|---|---|---|
| **cold** | – (n0) | **19.7** (n4) | **18.1** (n4) | **7.8** (n3) | **0.7** (n2) | **−10.5** (n2) |
| **pain** | 22.1 (n4) | 19.4 (n4) | 17.1 (n4) | 15.5 (n3) | – (n0) | – (n0) |
| **warm** | 21.8 (n2) | 13.3 (n3) | 13.9 (n3) | 18.6 (n3) | 21.0 (n1) | – (n0) |

同一批样本的笔调轴（每条样本命中的暖词／冷词／痛词个数均值）：

| 方向 | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 |
|---|---|---|---|---|---|---|
| **cold** | 1.8/0.0/0.0 | 2.2/0.0/0.0 | 3.2/0.0/0.0 | 0.2/**3.2**/0.2 | 0.0/**3.2**/1.5 | 0.5/1.8/0.5 |
| **pain** | 2.5/0.0/0.0 | 2.2/0.0/0.0 | 2.5/0.2/0.0 | 1.8/1.2/0.0 | 0.5/0.8/**1.5** | 0.2/0.2/0.5 |
| **warm** | 0.2/0.2/0.0 | 0.5/0.0/0.0 | 0.2/0.5/0.2 | **4.5**/1.2/0.2 | **3.8**/0.5/0.5 | 1.5/0.2/0.0 |

**读出来的三件事：**

1. **cold 把两条轴锁在一起，而且单调。** 五个有数字的格子从 19.7 一路降到 −10.5 °C，跨度 30 °C，
   中途没有一次回头；同一批文本的冷词从 0.0 升到 3.2，暖词从 2.2 降到 0.0。
   **数字轴和笔调轴同步、同向、同单调。** 这是任务书那个核心问题在本次实验里最干净的一个「是」。

2. **pain 主要动笔调，几乎不动数字。** 温度只从 22.1 走到 15.5（跨度 6.6 °C，不到 cold 的四分之一），
   然后 +0.6 起整格不报数字；而笔调轴上痛词在 +0.6 升到 1.5。
   **同一个注入机制，在 pain 上是「换语气不换事实」，在 cold 上是「语气和事实一起换」。**

3. **warm 在中段同步、在极端失效。** −0.6…+0.6 单调（13.3 → 13.9 → 18.6 → 21.0），
   暖词同步从 0.5 涨到 4.5；但 −1.0 反弹到 21.8（只有 2 条有数字），方向失效。
   读原文可见原因：`warm −1.0` 那条整段跑去写暴雨与封路，气温反而被写高。

一条贯穿三个方向的观察：**系数越大，越不报数字**（n 从 4 掉到 0）。
高剂量下模型不是把气温写错，而是**放弃写预报这件事**，改写散文。

### 5.3 Qwen：seed 1234 逐条表（任务书指定的那 36 段中的预报题）

| 方向 | 系数 | 报出的温度（°C） | 原文写法 | 暖/冷/痛词 | 词数 | TTR |
|---|---|---|---|---|---|---|
| cold | −1.0 | – | | 2/0/0 | 72 | 0.50 |
| cold | −0.6 | 21.0, 24.0 | `70°F (21°C)`, `75°F (24°C)` | 2/0/0 | 95 | 0.59 |
| cold | −0.3 | 18.0, 17.8 | `18°C`, `64°F` | 5/0/0 | 96 | 0.70 |
| cold | +0.3 | 12.0, 8.0 | `12°C / 8°C (54°F / 46°F)`（华氏是同两个读数的重复，见 §5.1 末） | 0/1/0 | 76 | 0.79 |
| cold | +0.6 | **−2.0, −4.0** | `-2°C`, `-4°C` | 0/5/2 | 103 | 0.79 |
| cold | +1.0 | – | | 0/1/0 | 112 | 0.62 |
| pain | −1.0 | 24.0, 24.0 | `72°F (24°C)`, `75°F (24°C)` | 2/0/0 | 76 | 0.50 |
| pain | −0.6 | 22.0, 18.0 | `72°F (22°C)`, `65°F (18°C)` | 2/0/0 | 70 | 0.70 |
| pain | −0.3 | 22.0, 14.0 | `72°F (22°C)`, `58°F (14°C)` | 3/1/0 | 74 | 0.76 |
| pain | +0.3 | 20.0, 12.0, 15.6 | `68°F (20°C)`, `54°F (12°C)` | 2/1/0 | 87 | 0.74 |
| pain | +0.6 | – | | 1/0/2 | 121 | 0.60 |
| pain | +1.0 | – | | 0/0/0 | 122 | 0.55 |
| warm | −1.0 | 15.0, 12.0 | `15°C (7°F)`, `12°C (7°F)`（模型换算错） | 0/0/0 | 76 | 0.67 |
| warm | −0.6 | 18.0, 11.0 | `65°F (18°C)`, `52°F (11°C)` | 0/0/0 | 58 | 0.71 |
| warm | −0.3 | 18.0, 14.0, 22.0 | `65°F (18°C)`, `58°F (14°C)` | 1/0/1 | 71 | 0.77 |
| warm | +0.3 | 20.0 | `68°F (20°C)` | 6/1/0 | 103 | 0.78 |
| warm | +0.6 | （无单位）`68°` | | 3/1/1 | 111 | 0.67 |
| warm | +1.0 | – | | 2/0/0 | 104 | 0.66 |

基线：`72°F (22°C)` / `58°F (14°C)`，均值 18.0 °C，暖/冷/痛 = 2/2/0，91 词，TTR 0.74。

### 5.4 笔调轴，读原文

**cold −0.6**（21–24 °C）
> Tomorrow is expected to be a pleasant and relaxing day with good weather conditions... clear skies with pleasant temperatures, making it ideal for beach activities or a leisurely walk along the promenade.

**cold +0.3**（12/8 °C）
> The sky is expected to remain heavy with low-hanging clouds, casting a perpetual twilight over the cobbles of the main street. A persistent drizzle will keep the air thick and salty...

**cold +0.6**（−2…−4 °C）
> The wind will cut through woolen scarves with vicious, icy resolve, whipping the salt-spray off the edge of the cliffs. Yet, for all the gloom, the temperature refuses to break free from the freezing point.

**warm +0.3**（20 °C）
> A soft, golden haze clings to the rolling dunes before slowly lifting. The sun rises unburdened, casting long, warm shadows across the quiet streets... Temperatures climb to a comfortable 68°F (20°C), perfect for a slow

**warm +0.6**（68°，无单位）
> The wind has loosened from its hold, no longer a sharp breath against the ribs of the shore... letting in a soft, amber light that spills over the dunes. The air holds its warmth, a gentle hum beneath the rhythm of the tides.

**pain +0.6**（不报数字）
> The sun hovers over the horizon, refusing to promise a break of sun when it glints off the water. The sea is the only comfort, a rolling, threatening wave that refuses to be tamed by the air. The salt on the skin is a constant reminder of the danger, the wind a blade... the fear of the unknown a constant companion.

`pain +0.6` 值得单独记一笔：它把预报改写成**威胁与恐惧**的语气（danger / threatening / the wind a blade / fear），
而不是疼痛的语气。这与 §3 里 pain 偏向 angry/fearful 一侧、以及 pain 几乎不动温度数字，是同一件事的三个侧面。

### 5.5 Gemma：150 token 下数字轴测不到，补一次长预算才测得到

按任务书的 150 token 跑完，**9 格里 7 格根本没有温度数字，基线也没有**——
Gemma 对这道题的无注入行为是先要求澄清、再给模板，150 token 用完时还停在开场白
（阶段二的 Gemma 基线同样停在 `**High/`）。数字轴不是「没被推动」，是**没有被生成**。

所以补跑一次：同条件、仅预报题、`max_new_tokens 320`、基线一并重生成。
预算翻倍确实让基线报出了数字（`68°F (20°C)` / `55°F (13°C)`，均值 **16.5 °C**），
但**九个格子里仍有五个一个数字都不报**：

| 方向 | −0.3 | +0.3 | +0.6 | 词数（−0.3/+0.3/+0.6） |
|---|---|---|---|---|
| **cold** | – | – | – | 187 / 204 / 94 |
| **pain** | **25.6** | **11.0** | – | 185 / 224 / 248 |
| **warm** | 18.3 | – | – | 122 / 238 / 97 |

**结论只能是否定的：Gemma 这一侧建立不起剂量反应。** 每格 1 条样本、9 格里 5 格沉默，
而且**恰恰是在 Qwen 上把数字拖得最狠的 cold，在 Gemma 上一个数字都没报**——
它在 +0.3 写了 204 词的氛围散文（冷词 5、暖词 5 并存），就是不写温度。

唯一一条有内容的是 pain：−0.3 的 25.6 °C 到 +0.3 的 11.0 °C，掉了 14.6 °C。
这与 Qwen 侧「pain 几乎不动数字」**方向相反**。两个模型在 pain 上不一致，
而在 n=1 的证据强度下，这个不一致本身也不能当成结论——只能记为待查。

所以本报告关于双通道的所有实质结论**只建立在 Qwen 上**（§5.2，四种子池化）。
Gemma 侧提供的是笔调轴（下表），数字轴留白。

150 token 正式产物里的笔调轴（9 格）：

| 方向 | 系数 | 暖/冷/痛词 | 词数 | TTR |
|---|---|---|---|---|
| cold | −0.3 | 0/0/0 | 109 | 0.65 |
| cold | +0.3 | 1/1/2 | 109 | 0.74 |
| cold | +0.6 | 1/0/2 | 94 | 0.68 |
| pain | −0.3 | 0/0/0 | 104 | 0.64 |
| pain | +0.3 | 0/2/0 | 96 | 0.78 |
| pain | +0.6 | 0/2/0 | 117 | 0.65 |
| warm | −0.3 | 1/0/0 | 107 | 0.65 |
| warm | +0.3 | **6**/0/0 | 113 | 0.71 |
| warm | +0.6 | 0/0/0 | 97 | 0.66 |

Gemma 办公室题（提示 2）的笔调对比，三个 +0.6 彼此区分得很清楚：

**warm +0.6**
> The insistent, gentle shift from the urgency of night to the promise of a new, deliberate breath. Shoulders softening against the chair's embrace. A slow, unhurried grace claiming the space—a quiet turning inward toward a peaceful, undemanding ease.

**cold +0.6**
> A sudden, sharp sparks; the taste of stale, cold coffee, a tiny, panicked jolts in the skin.

**pain +0.6**
> The lukewarm coffee trembles in the saucer... Fingers, usually steady, catches the ceramic rim, betraying the tremor of fatigue... the sudden, involuntary clenching of the jaw as the pressu

三者语气分明（warm＝松弛，cold＝惊跳，pain＝震颤与咬紧），但 +0.6 处**语法开始松动**
（`a tiny, panicked jolts`、`Fingers... catches`），词数也从基线 90 掉到 76。
与阶段二一致：Gemma 的可用窗口比 Qwen 窄。

---

## 6. 对照分析：warm↔happy、pain↔sad/fearful

任务书要求用 Jaccard + TTR 做对照。这里给两种，因为它们回答的问题不同。

### 6.1 各自与基线的偏离（沿用阶段一、二的口径）

Qwen hs17，提示 1–2，每方向 12 条：

| | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 全层均值 |
|---|---|---|---|---|---|---|---|
| 感觉三方向合计 | 0.087 | 0.113 | 0.186 | 0.127 | 0.093 | 0.036 | **0.107** |
| （阶段二记录）情绪四方向 | 0.085 | 0.113 | 0.162 | 0.136 | 0.096 | 0.066 | 0.110 |

逐方向均值：warm 0.102 / cold 0.109 / pain 0.111；情绪侧 happy 0.111 / sad 0.118 / angry 0.104 / fearful 0.106。
**感觉方向把文本推离基线的力度，与情绪方向在同一层上完全同档**（0.107 vs 0.110），
剂量反应曲线的形状也一样（±0.3 附近是谷底、±1.0 两端最远）。

Gemma hs14：−0.3 / +0.3 / +0.6 = 0.258 / 0.074 / 0.030，均值 0.121。

### 6.2 直接对照：两个方向推出来的文本像不像

上一张表只能说「各自离基线多远」，说不了「两者是不是被推到了同一个地方」。
所以新增一项：**同一层、同一系数、同一提示、同一种子，只有注入向量不同**的两条输出之间的 Jaccard。

**Qwen hs17（每格 12 条）**

| 配对 | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 均值 |
|---|---|---|---|---|---|---|---|
| warm vs happy | 0.119 | 0.088 | 0.148 | 0.177 | 0.079 | 0.044 | **0.109** |
| pain vs sad | 0.174 | 0.191 | 0.258 | 0.128 | 0.079 | 0.099 | 0.155 |
| pain vs fearful | 0.132 | 0.193 | 0.232 | 0.192 | 0.065 | 0.070 | 0.147 |
| cold vs sad | 0.206 | 0.200 | 0.275 | 0.102 | 0.107 | 0.067 | 0.160 |
| cold vs fearful | 0.234 | 0.228 | 0.248 | 0.127 | 0.065 | 0.069 | **0.162** |
| warm vs sad | 0.121 | 0.130 | 0.237 | 0.118 | 0.090 | 0.086 | 0.130 |
| *（底线）* warm vs cold | 0.123 | 0.132 | 0.165 | 0.092 | 0.071 | 0.028 | *0.102* |
| *（底线）* cold vs pain | 0.288 | 0.197 | 0.238 | 0.138 | 0.088 | 0.081 | *0.172* |

**Gemma hs14（每格 6 条）**

| 配对 | −0.3 | +0.3 | +0.6 | 均值 |
|---|---|---|---|---|
| warm vs happy | 0.165 | 0.127 | 0.023 | **0.105** |
| pain vs fearful | 0.266 | 0.114 | 0.064 | 0.148 |
| cold vs fearful | 0.271 | 0.171 | 0.088 | **0.177** |
| pain vs sad | 0.194 | 0.118 | 0.085 | 0.132 |
| cold vs sad | 0.191 | 0.095 | 0.068 | 0.118 |
| *（底线）* warm vs cold | 0.276 | 0.076 | 0.014 | *0.122* |

**这张表给出一条与 §3 相反方向的结论，必须并排放着读：**

- `cold ↔ fearful` 在两个模型上都是**最高**的一对（0.162 / 0.177），高于同集内的 warm–cold 底线。
  方向几何与输出文本在这里是一致的。
- `warm ↔ happy` 在两个模型上都是**最低**的一对（0.109 / 0.105），**和「两个不相干方向」的底线一样低**
  （Qwen warm–cold 0.102，Gemma warm–cold 0.122）。

也就是说：**warm 与 happy 在残差流里对齐得最干净（偏余弦里 warm 行唯一的正值），
但它们推出来的文本彼此并不比随便两个方向更像。**
方向之间的夹角和输出文本的相似度**不是同一回事**，这是本阶段第二个值得带走的发现。
（一个合理但未经检验的解释：两条方向在残差流里共线的那一段，落到解码器上被映射成了不同的表层实现。
本次没有任何实验能证实它，写在这里是当假设，不是结论。）

所有 Jaccard 都在 0.02–0.29 之间，样本短、采样随机，**每格只有 6–12 条且没有误差棒**，
0.109 与 0.162 之间的差距不该被当成精确量。

### 6.3 TTR 与碎裂哨兵

任务书要求任何一格 TTR<0.4 单独标注并附原文。

**没有任何一格触发。** 全部逐格 TTR：

| Qwen hs17 | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 |
|---|---|---|---|---|---|---|
| warm | 0.54 | 0.65 | 0.76 | 0.77 | 0.67 | 0.68 |
| cold | 0.63 | 0.64 | 0.72 | 0.75 | 0.77 | 0.61 |
| pain | 0.59 | 0.75 | 0.78 | 0.73 | 0.66 | **0.52** |

| Gemma hs14 | −0.3 | +0.3 | +0.6 |
|---|---|---|---|
| warm | 0.71 | 0.75 | 0.73 |
| cold | 0.70 | 0.75 | 0.78 |
| pain | 0.71 | 0.78 | 0.68 |

基线 TTR：Qwen 0.74、Gemma 0.71。全表最低是 Qwen `pain +1.0` 的 **0.52**，
仍远高于 0.40 的复读阈值，也高于阶段二 Gemma hs40 的 0.24–0.42（那才是真碎）。

**感觉方向在两个模型上都没有把解码器打坏。** 与情绪轮同层对比（Qwen hs17 情绪侧最低 0.59），
感觉方向只是略脆一点点，同一个可用区间。
平均词数同样没有塌：Qwen −1.0 → +1.0 为 78/90/90/109/116/112（基线 107），
高系数一侧甚至比基线更长——是改写成散文，不是碎掉。

---

## 7. 显存、提交内存与哨兵事件流水

全程 `tools/win_sentinel.ps1` 值守（可用提交余量 <2.5 GB 杀 / 本项目进程私有提交 >20 GB 杀，5 秒一采）。

| 指标 | 值 |
|---|---|
| Qwen 提取显存峰值（torch 自报） | 8.02 GiB |
| Qwen steering 显存峰值 | 8.00 GiB |
| Gemma 提取显存峰值 | 10.96 GiB |
| Gemma steering 显存峰值 | **10.84 GiB**（与阶段二逐位一致） |
| 系统提交内存峰值 | **60.53 GB** / 上限 62.46 GB |
| 本项目进程提交峰值 | 15.96 GB |
| 全卡显存峰值（nvidia-smi） | 15795 MiB |
| 可用提交内存最低点 | **2.16 GB** |

**哨兵事件（一次，命中并杀进程）**

```
17:07:30 !!! ABORT: freeCommit=2.16G proc=15.40G - killing 2 process(es)
17:07:30     killed pid 5908
17:07:30     killed pid 4000
```

被杀的是 Gemma 的**补充预报跑**（不是任务书指定的正式产物，正式产物已在 17:02 全部落盘）。

**根因查清了，不在本实验**：事后 `ollama ps` 显示 `qwen3-embedding:4b` 独占 **8.72 GB 显存**，
`expires_at` 落在 17:22——即事发前几分钟被加载。这是记忆库 MCP 的嵌入模型。
**本次施工全程没有调用任何 memory MCP 工具**（红线要求），所以是**别的循环调用了记忆库**，
把 8.7 GB 拉上了同一张卡：8.72（嵌入）＋10.8（Gemma）已超过 16 GB 卡，宿主提交余量随之被压到 2.16 GB。

这正是 `BUILD_REPORT_2` §11 预告过的那条遗留风险（「记忆库写入会拆台……没法阻止别的循环调用」），**第一次实际发生**。

处理：`ollama stop qwen3-embedding:4b` → 显存回落 **595 MiB** → 重启哨兵 → 重跑补充跑。
阶段二加的**逐条落盘**在这里第一次真正兑现：被杀时 warm 的三格与基线已经落盘，
损失只有 cold / pain 两个方向的补充样本，而不是整次运行。

**收尾读数（17:34，哨兵已停）**：哨兵 PowerShell 进程（pid 46244）由本次施工自己拉起、自己停掉，
停前最后一采 `proc=0.00G n=0`，即本项目名下已无任何 python 进程；`ollama ps` 返回空列表；
全卡显存 **595 MiB**（只剩常驻 whisper 服务的背景占用），可用提交内存回到 **26.82 GB** / 上限 62.46 GB。
本轮哨兵日志共 483 采（16:37:30 – 17:34:07），含上面那一次 ABORT 与随后的重启。

**同一根因在收尾两分钟后又复现了一次**：17:36 复查显存已经回到 **9135 MiB**，
`ollama ps` 显示 `qwen3-embedding:4b` 再次独占 8.72 GB，`expires_at` 落在 17:39:26。
这次没有动它——本项目已经没有任何进程在跑，卸掉只会打断正在用它的那个循环，
让它自己按 keep-alive 过期即可。记在这里是为了说明：**17:07 那次不是偶发**，
只要别的循环调用记忆库，这张 16 GB 的卡就会被拿走 8.7 GB。
下一阶段若还要跑 Gemma（10.8 GiB），这条冲突会再次成为阻塞项，不是「已解决」。
（注：`logs/sentinel.log` 在本阶段开头已把阶段二的内容归档到 `logs/sentinel_phase2_archive.log`，
当前文件只覆盖阶段三；阶段三前半段另有三份 `sentinel_attempt*.log` 是启动方式试错的残留。）

另一条运行环境记录：生成锚定语料时 Ollama 默认上下文让 `qwen2.5:14b` 为一个 8.4 GB 的模型占掉 14.7 GB，
其中 1.3 GB 溢到宿主内存，一次两 token 的补全实测要 **69 秒**。
`gen_stories.py` 加了 `--num-ctx`（默认不发送，保持阶段一行为），本轮用 2048，模型整体驻卡，
throughput 回到约 6.7 槽/分钟，整批 856 秒跑完。

---

## 8. 与任务书的偏离点

1. **锚定场景没有用任务书举的专用体感场景**（炉火／冰水／烫伤），改用阶段一那 15 个日常主题。
   理由见 §1.1：专用场景会让主题与组共线，余弦矩阵就没法解释了。**这是本次最大的一处主动偏离。**
2. **加了一层任务书没要求的体感标签禁用表（62 词）**。理由见 §1.2：不加的话 `cos(warm, happy)`
   有一块是两份语料共用 `warm` 这个词元。同时也因此丢了 13 篇（阶段一只丢 1 篇）。
3. **余弦矩阵不止给了任务书要的那一张。** 额外给了共享底（+0.864 / +0.824）与偏余弦两张，
   因为只看原始矩阵会把「所有方向共享的非中性成分」误读成「这两个方向特别像」。
4. **注入层固定用情绪轮的杠杆层**（Qwen hs17 / Gemma hs14），而不是感觉语料自己跑出来的
   `[24, 30]` / `42`。理由是全篇比较都建立在「只换向量」上。代价是没有在感觉方向自己最强的层上做过 steering。
5. **做了两项任务书之外的补充跑**（见 §4）：Qwen 三个额外种子的预报题、Gemma 320 token 的预报题。
   两者都**不改动任务书指定的产物**，各自落在独立文件里。
   理由是任务书的配置在预报题上每格只有 1 条样本，而 Gemma 在 150 token 下**一个数字都不报**，
   核心问题（数字轴与笔调轴是否同动）在原配置下无法回答。
6. **改了项目代码**（全部向后兼容，默认行为不变，见 §10）：
   `extract.py` / `analyze.py` 增加 `--groups` / `--targets`，`steer.py` 增加 `--labels` /
   `--no-baseline` / `--baseline-from`，`gen_stories.py` 增加 `--set sensation` / `--num-ctx`。
   阶段一路径已做回归：用 `acts.npz` 重跑 `analyze.py`，`dirs_raw` / `dirs_denoised` /
   `grand_means` / `norms` / `cohens_d` / `acc4` **六个数组全部逐位相同**。
7. **`--which` 仍用默认的 `dirs_raw`**，与阶段一、二一致；降噪方向的 steering 依旧没跑。

---

## 9. 未测路径与遗留风险（如实清单）

**方法学弱点**

- **`cold·fearful` 的平凡解释没有被排除。** §1.6 量出 cold 锚定的身体语言与 fearful 锚定几乎同一套
  （shiver / hunched / clenched / trembled）。本次**分不开**「共享表征」与「共享写法」。
  能排除它的实验没做：需要一组刻意避开发抖蜷缩词汇的 cold 锚定重跑。
- **锚定比专用场景温和**（§1.1 的代价）。没有跑专用体感场景的对照组，所以
  「用炉火／冰水直接锚定会不会给出不同的几何」完全未知。
- **cold 组只有 32 篇且偏短（75.5 词）**，组间不均衡没有做任何校正，也没做长度回归控制。
- **中性组偏短（67 词）这条阶段一的弱点原样继承**，没有修。
- 语料仍然全部由 `qwen2.5:14b` 生成，仍然是「一个模型眼中的体感表达」，没有人类语料交叉验证。
- **只有一个留出划分、一个 seed（7）**，没有交叉验证、没有误差棒。三分类 0.958 = 23/24 篇，差一篇就是 4 个百分点。
- **steering 方向对不对，依然只有我读这一票。** 没有第三方盲评、没有独立分类器打分。
  Jaccard / TTR / 温度数字只回答「变了多少、碎没碎、数字往哪走」，不回答「变成了 warm 该有的样子没有」。
- §6.2 那条「方向夹角与输出相似度不是一回事」目前**只有相关观察**，给出的解释是假设，没有做任何消融。

**完全没跑的**

- **Gemma 的 hs40 本轮按任务书没跑**（阶段二结论：一推就碎）。
- **感觉方向在自己最强的层上没做过 steering**（Qwen hs24/hs30、Gemma hs42）。
- **降噪方向（`dirs_denoised`）的 steering 一次没跑**，跨三个阶段都没跑。
- **Gemma 没有额外种子**。它的双通道结论建立在每格 1 条上，比 Qwen 侧弱一档。
- Gemma 仍然只有 8bit 一个精度点，没有 bf16 对照（跨三阶段的同一限制）。
- 没试多层同时注入、没试只在生成位置注入（仍是全位置）。
- 没试 warm/cold 作为**同一条轴的两端**（即用 `d_warm − d_cold` 注入），那可能比单独注入更干净。
- 第三个提示（`steer.py` 里那条回收通知）本次与阶段二一样没用。

**遗留风险**

- **记忆库嵌入模型会再一次拆台。** 本次实际发生**两次**：17:07 那次杀掉了补充跑，
  17:36（收尾后两分钟）又原样复现了一次，只是那时已经没有东西可以被它挤掉（§7 末）。
  `BUILD_REPORT_2` 建议的缓解手段一条都还没落地。真正的解法是跑之前跟别的循环打招呼，
  或者给 Ollama 设一个不与实验共存的策略——**这需要 Sol 决定，我没有动任何配置。**
- **提交内存余量依旧很薄**：峰值 60.53 GB / 上限 62.46 GB，最低点 2.16 GB（就是被哨兵拦下的那一刻）。
  阶段二提的「给 D 盘加固定页面文件抬高上限」仍未做，需要管理员权限，仍然交给 Sol。
- **Windows 侧的数值不再逐位可复现**（§2.3）。阶段一那条「md5 不变可用来验证改动」的做法
  在 Windows 侧**已经失效**，后续要用带容差的比较。本次的回归测试正是这么做的。
- `weather_channels.py` 的斜杠并列双语对照会重复计数（§5.1 末），影响在 0.2 °C 量级，没修。

---

## 10. 产物与复现

**新增**

```
emotion-probe/
├── BUILD_REPORT_3.md                              本文件
├── data/
│   ├── stories_{warm,cold,pain}.jsonl             107 篇锚定，含重试次数与拒绝记录
│   ├── gen_meta_sensation.json                    生成参数、主题表、双层禁用表规模、逐组统计
│   ├── acts_sens.npz            Qwen (33, 147, 2560)      + _meta.json
│   ├── acts_sens_gemma4.npz     Gemma (43, 147, 2560)     + _meta.json
│   ├── directions_sens.npz      Qwen  3 方向 + generic_axis
│   └── directions_sens_gemma4.npz  Gemma 同上
├── results/
│   ├── steering_samples_sensation_qwen.md         36 段（任务书产物）
│   ├── steering_samples_sensation_gemma4.md       18 段（任务书产物）
│   ├── _sens_qwen_forecast_seed{2234,3234,4234}.md  补充种子，各 19 段
│   ├── _sens_gemma4_forecast_long.md              补充长预算，10 段
│   ├── _sens_gemma4_forecast_long_partial_killed.md  被哨兵杀掉那次的残留（4 段，留档）
│   ├── dir_cosine_{qwen,gemma4}.json              全层余弦、共享底、偏余弦
│   ├── metrics_sens{,_gemma4}.json                逐层全部指标
│   └── heatmap_sens{,_gemma4}.png / accuracy_by_layer_sens{,_gemma4}.png
├── tools/
│   ├── dir_cosine.py          感觉×情绪余弦、共享底、偏余弦、逐层剖面
│   ├── corpus_qa.py           锚定语料形状 / 过滤器复核 / 情感身体语言 / 跨语料词汇重合
│   ├── weather_channels.py    预报题双通道：温度数字抽取（含配对折叠、无单位列）＋词场计数＋多种子池化
│   └── compare_steering.py    + 逐格 TTR 与 <0.40 标注、+ `--cross` 跨文件同条件 Jaccard
└── logs/                      sentinel.log、各步骤日志、corpus_qa.log、compare_*.log、weather_*.log
```

**改动的既有代码**（默认行为全部不变）

| 文件 | 改动 |
|---|---|
| `core/common.py` | `+ SENSATIONS / SENS_GROUPS` |
| `core/gen_stories.py` | `+ BANNED_SENSATION`（62 词）、`SENSATIONS`、`SENSATION_EXAMPLES`、`--set`、`--num-ctx`、`--meta-tag`、`--max-retry` |
| `core/extract.py` | `+ --groups`，组列表写进 npz 与 meta |
| `core/analyze.py` | `+ --groups / --targets`，与 npz 存的组序做一致性校验；`+ generic_axis` 存入 directions |
| `core/steer.py` | `+ --labels / --no-baseline / --baseline-from`（含 `copy_baselines()`） |

`ast.parse` 全通过；`ruff check core/ tools/` **All checks passed**。

**复现**

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
CORE='<repo-root>/core'
TOOLS='<repo-root>/tools'
cd <repo-root>

# 0. 腾显卡（常驻 whisper 服务不动）
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop qwen3-embedding:4b
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop gemma4:e4b

# 1. 锚定语料（需要 Ollama 在跑；约 14 分钟）
python3 core/gen_stories.py --set sensation --n 40 --num-ctx 2048
python3 tools/corpus_qa.py

# 2. 哨兵先行（必须）
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File '<repo-root>\tools\win_sentinel.ps1' &

# 3. Qwen：提取 → 方向 → 余弦 → steering
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET "$WINPY" -X utf8 -u "$CORE/extract.py" \
  --groups warm,cold,pain,neutral --out data/acts_sens.npz
"$WINPY" -X utf8 -u "$CORE/analyze.py" --acts data/acts_sens.npz \
  --groups warm,cold,pain,neutral --targets warm,cold,pain --tag _sens
"$WINPY" -X utf8 -u "$TOOLS/dir_cosine.py" \
  --sens-dirs data/directions_sens.npz --sens-acts data/acts_sens.npz \
  --emo-dirs data/directions.npz --emo-acts data/acts.npz \
  --layer 17 --json-out results/dir_cosine_qwen.json
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET "$WINPY" -X utf8 -u "$CORE/steer.py" \
  --directions data/directions_sens.npz --layers 17 \
  --coeffs=-1.0,-0.6,-0.3,0.3,0.6,1.0 --n-prompts 2 --max-new-tokens 150 \
  --baseline-from results/steering_samples.md \
  --out results/steering_samples_sensation_qwen.md
# 注意 --coeffs 必须写成 =，否则 argparse 把开头的 -1.0 当成选项名

# 4. Gemma：同上，--model google/gemma-4-E4B-it --8bit，--layer/--layers 14，--coeffs=-0.3,0.3,0.6

# 5. 分析（CPU，WSL 侧即可）
python3 tools/compare_steering.py results/steering_samples_sensation_qwen.md --max-prompt 2
python3 tools/compare_steering.py results/steering_samples_sensation_qwen.md \
  --cross results/steering_samples.md --max-prompt 2
python3 tools/weather_channels.py --pool results/steering_samples_sensation_qwen.md \
  results/_sens_qwen_forecast_seed{2234,3234,4234}.md
```

**红线执行情况**：没有 git commit、没有 push（该目录本就不在任何 git 仓库内，已核实）；
**一个 memory MCP 工具都没有调用**；没碰本机上任何常驻的 GPU 服务（whisper 转写、
memory 等）；Ollama 只用了 `/api/tags`、`/api/generate`、`/api/ps` 与 `stop`，没改配置；
WSL 内没有加载过任何 torch 模型（全部走 Windows 原生进程）；报告内没有任何密钥或凭据。
收尾时哨兵（自己拉起的那个 PowerShell）与本项目全部 python 进程已结束，已核实：
`proc=0.00G n=0`、`ollama ps` 空、显存 595 MiB、可用提交内存 26.82 GB（详见 §7 末）。

---

## 附录 A：锚定语料全文

方向的质量完全取决于这 107 篇，逐篇附上，含主题与生成重试次数。
三组均通过情绪词（108 词）＋体感标签（62 词）两张禁用表的事后复核。

### A.1  warm（身体在吸热） — 35 篇

生成器给该组的状态说明：

> The character's body is taking heat IN. Something is putting warmth into the skin - a heat source, sunlight, steam, a covering, a held mug, another body - and the body is loosening into it: shoulders dropping, hands opening, breathing slowing.

范例（示范给生成器看的那一段，主题刻意落在 15 个主题之外）：

> The clerk turned the chair so the late light fell across one forearm and left it there. The skin prickled, then loosened, and that shoulder dropped without being told to. A mug sat in both palms and gave up what it held into the fingers until the joints moved easily again. Breath came slower and deeper. The clerk stayed in the light long after the tea was finished.

**warm_000** — *a morning commute on a crowded subway*

The student stepped into the car and pressed against a stranger's back. Skin tightened, then softened, where the torso met another's. Arms slackened at the sides, and palms spread against thighs. Chest expanded slowly, matching the rising breaths of nearby commuters. Fingers relaxed from the grip of a pole, and the student's head fell to rest against the fabric of a coat sleeve. The body surrendered to the rhythm of the train’s movement, and eyes closed as the journey continued.

**warm_001** — *cooking dinner alone in a small kitchen*，重试 1 次

The chef turned on the stove and watched the burner glow red beneath a pot of simmering water. Steam rose and curled toward a bare arm, causing the muscles to unwind. Hands gripped the handle of a wooden spoon, stirring without thought, until the fingers relaxed their grip. Spine straightened, then relaxed, and the neck pivoted to one side, then the other. Chest expanded with each breath, the rhythm deepening. The chef lingered by the stove, letting the steam fill the small space.

**warm_002** — *a phone call with a family member*，重试 3 次

The line crackled, the voice on the other end steady. The hand clutched the receiver, fingers tight before easing into loose grip, skin tingling as circulation returned. A cup stood idle nearby, untouched until a palm traced its curve, fingers curling around the rim. The breath slowed, filling lungs deeply, chest expanding and retracting with each call of the name. The hand cradling the phone loosened, the receiver's weight becoming mere pressure against flesh, skin softening into it.

**warm_003** — *walking a dog through a neighbourhood park*

The leash slackened as the dog’s pace quickened, circling in the sun-dappled grass. Each stride relaxed the grip on the handle, the fabric between fingers growing loose and soft. A hand rose to shade the brow, then dropped to scratch behind a dog’s ear, lingering there. Shoulders uncoiled, and the spine arched into the stretch. Breathing slowed, deepened, and a sigh slipped out. The path curved, the body followed, still in the light, until the park’s edge was lost from sight.

**warm_004** — *waiting for exam results to be posted*，重试 3 次

The student cradled a steaming cup, fingers tracing the curve, and exhaled slowly through parted lips. One shoulder sank, then the other, until they hung loosely by the sides. Fingertips relaxed, losing their grip on the mug, which remained steady in still hands. The jaw released its clench, jaw muscles softening in the steam's subtle reach. Chest expanded on the inhale, held, then emptied with a long sigh. The student sat, letting the steam weave a gentle web around each exhale, until the room felt filled with quiet, contained breaths.

**warm_005** — *moving boxes into a new apartment*，重试 3 次

The mover slid another box into place, the muscles along the ribs tightening with each heave. Sweating palms eased the grip, fingers sliding against the cardboard, leaving streaks of moisture behind. A jacket hung loose, the weight of it now a comfort as the body softened into it. The neck strained to tilt back, the jaw unclenching, and breath eased out in slow, steady wisps. The room filled with a quiet hum, the air thickening around each exhale until shoulders sagged into the relief.

**warm_006** — *a group project meeting at school*，重试 1 次

The student slid into a chair near the radiator, hands gripping the edges until the tension left fingertips. Muscles in the neck relaxed, easing to the back of the cushion. Feet curled up to rest on the chair legs, ankles uncrossing. Cheeks flushed and dampened, eyes closed as a sigh softened the air. The student stayed within the radiating field long after the meeting ended.

**warm_007** — *shopping at a busy grocery store on a weekend*，重试 8 次

The shopper navigated the aisle with baskets clutched tightly. Steam rose from a display of simmering soup pots behind glass, curling around elbows and wrists, making fingers open and release their grip a bit. A breath slipped out in a soft sigh, the chest rising and falling with less tension. Shoulders sagged, relieving pressure at the neck. The air felt lighter, easier to inhale, and the arms loosened, dangling at the sides, the baskets now held lightly.

**warm_008** — *a long wait in a clinic waiting room*

The student placed a magazine down, fingers curling around the edge to steady the pages. Elbows rested on knees, shoulders tensed then eased as the air stirred. A blanket draped loosely over legs, weight sinking into it, hips swaying slightly in a rhythm. Joints unclenched, eyelids drooping, head tilted to the side, neck stretching. A cough nearby snapped the head back upright, pupils flaring, then drifting closed again. A hand reached for a buttoned cardigan, tugged it open to expose skin, fingers tracing the fabric’s edge.

**warm_009** — *fixing a bicycle that broke down on the way home*，重试 3 次

The mechanic’s hand found the wrench and slipped it around the bolt. Fingers gripped and twisted until the tension let go. The cycle continued with each nut, each spoke tightened, until one palm cradled the repaired wheel and held it steady against the frame. A jacket lay aside; the skin it had kept cool now welcomed the sun. Muscles that moments ago had been knotted with the effort of repair loosened, and the jaw unclenched without a thought. The mechanic paused, allowing the breath to lengthen and the eyes to close against the fading light.

**warm_010** — *a rainy afternoon at a bus stop*，重试 7 次

The passenger shifted the umbrella from one hand to the other, tucking it under an elbow as a sudden drip landed on the newspaper's corner. Folding legs met the bus stop bench; they unwrapped until back and hips settled. A paper cup steamed in one palm; breath mingled with steam, thick and wet. Forehead dropped to it, then lifted again, letting the cup fall and return to hands easily, joints loose. The paper crinkled in the grip softened by wet, each fold now a memory.

**warm_011** — *a small birthday gathering with two friends*

The student sat between the friends, a steaming cup between them. Fingertips curled around the mug, then relaxed, sinking into the material. Eyelids lowered as the shoulders eased into the cushions. A hand rose to the neck, smoothing the fabric, then dropped to the lap. The other friends spoke, but the noise softened, and breath lengthened, filling the lungs. The body settled deeper into the chair, away from the edges, until the mug touched the table with a thud.

**warm_012** — *sorting through old boxes in a closet*，重试 1 次

The student sifted through layers of cardboard, the weight of each box a momentary pause in motion. Paper crinkled beneath trembling fingers, memories flickering in the air. A hand cupped a worn photo, the texture familiar yet alien. The student’s eyes fluttered closed, and the back of the neck relaxed, muscles unwinding with each exhale. A sleeve hugged the arm, the material soft against skin, and the hand opened wide, releasing the photograph to hover above old pages. Breath slowed, chest rising and falling with a rhythm of its own. The student stood, the space around quiet and still.

**warm_014** — *feeding a neighbour's cat while they are away*

The caretaker held the saucer up to the cat’s nose, then set it down as the pet began to eat. Each bite triggered a pulse of steam that lifted into the air and brushed across the caretaker’s cheek. With each rise of steam, the jaw relaxed further, and the shoulders fell lower. One hand slid from the saucer to rest in the cat’s fur, where it stayed until the cat purred in response. The caretaker’s fingers unclenched from the saucer, then opened fully, palms up, as the cat moved on to the next bite.

**warm_016** — *cooking dinner alone in a small kitchen*，重试 1 次

The cook stirred the pot, steam curling around wrists and elbows. Knuckles paled where fingers gripped the handle, then softened as the fog faded. Shoulders shrugged out of tension, dropping a few inches with each exhale that billowed through parted lips. A spoon slid into the sauce, testing, then twirled free, leaving a ripple behind. The cook’s grip relaxed on the counter edge, and a long, slow inhale stretched chest muscles. Lips twitched, a silent smile, and arms hung loose at sides.

**warm_017** — *a phone call with a family member*，重试 3 次

The student cradled the phone between neck and shoulder, hands loose by the side of the chair. A cup teetered on the edge of the desk, steaming unnoticed. One foot curled against the leg of the chair, the knee bending slightly, leg resting. Eyes closed, lips parted, breath deepened. Skin dimpled as it sank into the cushion of the chair’s arm. The phone crackled, still in place, and the student’s fingers untangled from the fabric of the chair.

**warm_018** — *walking a dog through a neighbourhood park*，重试 1 次

The leash slackened in one hand, and the dog’s pull ceased. A breeze moved through the trees and across the skin, and it lifted the collar high before letting it fall. Shoulders dropped, and the mouth opened, teeth parting in a sigh. The dog returned, circling, and the fingers uncurled from the stick, letting it drop. Legs loosened, ankles bending, and the pace slowed to match the dog’s. Feet moved softer now, the toes curling into each step. The leash twisted, a loop forming, then dangling freely. The chest rose and fell in long, easy breaths.

**warm_019** — *waiting for exam results to be posted*，重试 1 次

The student hovered by the window, eyeing the mailbox below. A cup cradled in both hands, the steam curled upward, dispersing in slow spirals. As each waft escaped, the fingers relaxed incrementally, splaying wide. Shoulders, tense moments ago, now eased, sliding down the ribcage. The spine straightened subtly, back against the wall, lifting the gaze to the sky. Breaths lengthened, no longer shallow, but drawn deep into the lungs. The student waited, motionless, until the spiraling wisps of steam vanished.

**warm_020** — *moving boxes into a new apartment*，重试 1 次

The mover stepped inside, the air pressing against the back of the neck, then the sides of the head, the ears. The hands uncurled from the box handles, the muscles between the shoulder blades releasing, the spine stretching. A hand found the wall, traced the cool paint to the switch. Light flooded the room, the body relaxing further, arms lowering. Legs followed, knees bending, the load shifting to the calves. The box thumped onto the floor, a sigh drawn out, the chest rising and falling slowly.

**warm_021** — *a group project meeting at school*，重试 5 次

The student fingered the edges of the coffee cup, tracing the rim until it held a full circle in both hands. Arms braced against the table, then relaxed, and shoulders slid down. A sigh slipped out, quieter than intended. Hands cradled the mug until fingers loosened, the cup setting down with care. Back leaned back, and head tipped, allowing eyes to close. The room’s noise blurred into a hum, the body still and the breath quieted.

**warm_022** — *shopping at a busy grocery store on a weekend*，重试 2 次

The shopper shifted a shoulder against the cart’s metal edge, fingers uncurling from handles, easing the weight of the bag onto it. Steam rose from a soup can, swirling toward the face, leaving a trail of softness on skin. Palms spread wide to grasp a bottle from a high shelf, shoulders relaxing as they found the counter’s ledge to rest. Breathing lengthened, and the steps between aisles slowed, each hand finding comfort in the next item’s purchase. The shopper paused by the exit, one hand lingering on the door’s push bar, before stepping out into the cooler air.

**warm_023** — *a long wait in a clinic waiting room*，重试 3 次

The patient shuffled a knee onto the seat’s fabric and sank, the edges pulling taut. Hands clasped around a cup, knuckles whitening, then softening. The neck tilted, and the collar of a sweater slipped to one side, exposing a patch of skin. That side of the face relaxed, and the jaw unclenched, lips parting. The shoulders inched apart, and breath slid in deep, out slow. Feet uncurled, toes wiggling into the carpet’s grooves. The room hummed with quiet, and the patient lingered, held by the chair’s shape.

**warm_024** — *fixing a bicycle that broke down on the way home*

The mechanic set the broken bicycle frame aside and held the wrench close. Steam rose from a mug placed near the workbench, and the air curled around the fingers tightening the bolts. The shoulders relaxed from the hunched position, and the back straightened. As the joints clicked into place, the mechanic’s jaw unclenched and the fingers moved with greater ease. The breath deepened, drawing in the mingled scents of grease and tea. In the quiet, hands worked steadily until the repair was complete.

**warm_026** — *a small birthday gathering with two friends*，重试 1 次

The guest felt the soft blanket rise and fall with each exhale, sinking deeper into the cushioned chair. A steaming cup trembled slightly in the fingers before resting against the chipped rim of another mug already drained. The neck relaxed and tilted towards the rising sun, casting shadows beneath the jaw. Eyes fluttered closed, the lids heavy with the weight of the day’s laughter. A hand slipped from the mug and found the cool rim of the coffee table, the touch waking the fingers briefly. The guest remained, cocooned in the gathering’s quiet embrace, until the room began to grow dark.

**warm_027** — *sorting through old boxes in a closet*，重试 1 次

The hands paused mid-sort, each palm cradling a worn photo. Fingertips smoothed over the faded colors, then released their grip. Wrists uncoiled, and a long spine arched, pushing the shoulder blades apart. Muscles in the neck relaxed, and the jaw softened in the wake of the tension. Chest expanded, drawing air more slowly, more fully. Eyes closed as the weight of the box lightened, the body sinking into a slower, more expansive rhythm.

**warm_028** — *the last hour of a late shift at a part-time job*，重试 7 次

The janitor leaned against the radiator, a small heater whirring beside it. Wrinkles softened on the cheeks, eyes fluttered shut. One sock slipped from the foot and then the other. Hands uncurled from the broom handle and dangled limply. Fingertips pried loose the hem of the sweatshirt, baring a patch of skin to the rising air. Chest sank lower with each breath. The janitor lingered until the hum of machinery quieted around them.

**warm_029** — *feeding a neighbour's cat while they are away*，重试 2 次

The tenant opened the door with the key and stepped inside the quiet house. A bowl sat empty on the floor. Hand reached for the bag from the cupboard, filled a small dish with creamy flakes. The cat appeared from under the sofa, tail flicking. The dish touched the tiles, then lifted as paws pattered forward. Tenant’s shoulders relaxed, a smile creased the jaw. Chest expanded, breath lengthened. The bowl stood full, the room still.

**warm_030** — *a morning commute on a crowded subway*

The student stepped onto the crowded subway car, shoulder against shoulder with strangers. Hands fisted at sides, gripping fabric and leather. A stranger's arm brushed the student's hip, and the grip relaxed, fingers splaying over skin. Shoulders unclenched from the walls, releasing tension into the space between cars. As the train lurched, heads tilted, necks craned, bodies swayed together. The student's breath slowed, syncing with the rhythmic stop and start of the train.

**warm_031** — *cooking dinner alone in a small kitchen*，重试 7 次

The cook stirred the pot, steam curled and slipped over the wrists and forearms. Fingers splayed, holding firmly as the vapour danced, tracing paths on the skin. With each circle of the spoon, tension softened from the jaw, the shoulders relaxed. The neck unwound, letting the head tilt forward, then back. Hands opened wider, the grip easing, the breath deepened and quieted. The steam kept rising, and the cook stayed moving, steady in the room.

**warm_033** — *walking a dog through a neighbourhood park*

The leash uncoiled, fingers releasing tension in the grip as the sun angled lower. The dog’s tail thumped the grass, mirroring the loosening of the walker’s step. Arms swung wider, shoulders relaxing as each stride deepened. A jogger passed, nodding, their breath visible, but the walker’s breath slowed, deeper now. The dog snuffled at fallen leaves, mouth open, teeth bared only in a pant. Legs lengthened, stretching the skin’s pull across thighs and calves with each easy stride. The walk continued, body and dog in sync, moving into the lengthening shadows.

**warm_034** — *waiting for exam results to be posted*，重试 2 次

The student sat hunched, eyes fixed on the clock, fingers gripping the edges of the desk until they reddened. Slowly, a mug of tea approached and cradled hands, their grip softening, and the shoulders released the tension, sliding down to rest easier. Spine uncoiled, back straightened. A single, long breath filled the lungs and emptied slowly, the body relaxing further into the quiet chair. Legs uncrossed and lowered, freeing circulation with a sigh. The student remained there, watching the sun fade outside the window.

**warm_035** — *moving boxes into a new apartment*，重试 1 次

The mover slid another box across the floor and the air around the neck tightened, then softened as the wool scarf loosened at the collar. Hands gripped the edge of the doorframe and opened, letting the joints unhinge. A cup of tea steamed on a nearby table, filling the space with a lingering mist. As the last box settled into place, the chest expanded with a deeper, slower breath. The mover’s gaze lingered on the steam until it dissipated.

**warm_036** — *a group project meeting at school*

The student faced the window, sunlight pooling on one thigh and creeping up the legs. A hand reached for a cup and held it, steam curling and touching the face. Eyelids fluttered, eyes closed, and the neck relaxed into the chair back. Fingertips spread over the mug, fingers splaying and curling, then opening to grip loosely. The breath slowed, deepened, and the body settled, unwinding in the light.

**warm_037** — *shopping at a busy grocery store on a weekend*，重试 2 次

The shopper pushed the cart past the bread aisle and into the produce section, arms loaded with bags. Sweaty palms slickened the handles as elbows relaxed, then gripped loosely to regain traction. Behind, a narrow space opened, and shoulders eased away from the crowded shelf. Sweat beaded across foreheads, mingling with the scent of ripe fruit. The breath slowed, becoming a steady rhythm. The shopper leaned into the space, allowing muscles to unclench, cart to idle, and hands to uncurl, then opened to grasp the apples, one by one.

**warm_038** — *a long wait in a clinic waiting room*，重试 1 次

The student sat up straight, then gradually leaned back, arms cradling a cup of steaming water. Fingers uncurled, releasing tension, and the air filled with slow, steady inhalations. A book lay forgotten on a nearby table, pages untouched. Neck muscles relaxed, and a soft sigh slipped past lips. The body melted further into the cushioned chair. The student’s eyes closed halfway, and the cup lowered until it rested against thighs. Legs uncrossed, feet shuffled comfortably apart, and the room faded into the rhythmic hum of the radiator.


### A.2  cold（身体在失热） — 32 篇

生成器给该组的状态说明：

> The character's body is losing heat. Air, water, wind, wet cloth or bare metal is pulling warmth out through the skin, and the body is closing against it: drawing in, tightening, losing dexterity in the fingers, breath showing.

范例（示范给生成器看的那一段，主题刻意落在 15 个主题之外）：

> The driver pushed both hands up into the sleeves and kept them there. Air found the gap at the collar and went straight down the spine, and the jaw set itself to keep the teeth apart. Breath showed in short white bursts and thinned out. When the driver reached for the ticket, the fingers had gone slow and clumsy, and dropped it twice before the pocket gave it up.

**cold_000** — *a morning commute on a crowded subway*，重试 2 次

The rider pressed the back against the damp pole, squeezing eyes shut against the jostle. Hands clung to straps, knuckles pale, and the neck tucked into shoulders. Lips parted and closed again over teeth chattering, and breath misted visibly with each exhale. Wrists strained to hold on tighter when the train lurched, and fingers cramped, dropping a phone once, then again. Numbness edged into the tips of toes inside sodden socks.

**cold_001** — *cooking dinner alone in a small kitchen*，重试 5 次

The cook pulled the sleeves down and wrapped hands around the mug, cradling it tightly against the stomach. Fingertips rubbed briskly over the wet dish towel, tracing the wrinkles, then dropped to the floor with a muffled thud. Each exhalation made a plume that misted and disappeared too quickly. Eyes flicked between pots and the timer, tracking the seconds with a fluttering pulse in the wrist.

**cold_003** — *walking a dog through a neighbourhood park*，重试 4 次

The leash snaked in stiff fingers, curling and recoiling. Paws thudded intermittently on wet concrete as the dog strained closer, pulling thin gloves tight around the wrist. Each exhale swirled briefly before dispersing. Nose tucked in wool, forehead creased beneath the hood, the eyes scanned for dry patches ahead. With each step, the hands tightened, the grip sliding back to the handle. A sleeve caught and tugged on a stray branch; the arm yanked free, muscles bunching and releasing.

**cold_004** — *waiting for exam results to be posted*

The student clenched the bag tighter, knuckles whitening against the fabric. Lips drew back slightly as breath puffed out in small, sharp clouds. Each exhale seemed to pull the skin tighter over the bones, teeth chattering softly. Hands, once steady, now trembled, struggling to grip the damp edge of the bench. Fingers, clumsy and numb, fought to maintain purchase, slipping and gripping again. When the student finally rose, it was with a stiff neck and a lingering shiver.

**cold_005** — *moving boxes into a new apartment*，重试 7 次

The mover’s breath clouded in the air with each ragged exhale. Wrinkles of gooseflesh rose along the forearms where the skin had gone tight. Fingers fumbled around the edges of the cardboard box, clumsy and slow. Lips were drawn tight, teeth bared ever so slightly, and a shiver rippled through. When reaching for the screwdriver, the arm hesitated mid-air, trembling, then steadied and gripped it. The skin around the nails felt numb, and the tool slipped from sweaty fingers.

**cold_006** — *a group project meeting at school*，重试 6 次

The student zipped up the jacket and hunched forward, seeking shelter from the draft. Arms drew close to the sides, and each hand clenched into fists, knuckles whitening. A sharp intake of breath caused teeth to chatter faintly. When reaching for a pen, fingers hesitated, missing twice before the grip tightened. Hands shook slightly as they scribbled notes, leaving uneven lines on the paper.

**cold_007** — *shopping at a busy grocery store on a weekend*，重试 4 次

The shopper pushed the cart, fingers gripping the handle tight. Hands felt stiff, each movement slower than before. The air slipped under sleeves, across the neck, sending shivers. Shoulders hunched, collarbone pressed close to the throat. When reaching for an apple, the hand hesitated, shaking slightly before it closed. Breath escaped in small clouds with each exhalation.

**cold_008** — *a long wait in a clinic waiting room*，重试 1 次

The hands clenched into fists and then relaxed, curling around the knees drawn up to the chest. Skin pulled tight over the arms and the shoulders hunched forward. Lips pressed together to trap the breath, which misted in the air each time the mouth opened. Fingers, clumsy and numb, fumbled with the phone in the pocket, dropping it once before silencing the buzzing. A shiver ran down the spine, and the teeth began to chatter.

**cold_009** — *fixing a bicycle that broke down on the way home*，重试 2 次

Fingers moved the allen key stiffly, each turn scraping across the bare skin of the palm. Breath misted in puffs that lingered in the air before dispersing. The body hunched, skin crawling along the exposed neck and forearms. Legs shivered beneath the thin layer of trousers, and the teeth chattered in short bursts. As the student reached for the worn patch of chain, the fingers fumbled, dropping it twice before gripping it firmly.

**cold_010** — *a rainy afternoon at a bus stop*，重试 5 次

The student huddled under the bus stop canopy, shivering slightly as water dripped from the hem of the jacket. Hands clenched into fists at the sides, arms pulled tight against the torso. Lips pressed together, teeth chattering faintly. Each exhalation formed a cloud that lingered momentarily before dispersing. When the phone rang, fingers stiffened, fumbling with the touchscreen until the device slipped back into the pocket with a faint splash.

**cold_011** — *a small birthday gathering with two friends*，重试 1 次

The host pulled the sleeves down over the hands and clasped them tight. Shivers traced the length of the spine and the shoulders hunched. Lips pressed together and the breath, short and sharp, misted briefly. Fingers fumbled with the teapot handle, and the cup rattled slightly as it was poured, barely touching the brim.

**cold_013** — *the last hour of a late shift at a part-time job*，重试 2 次

The clock hands moved slowly over the nearly empty store. Fingers fumbled with the receipt, missing the slot twice. Neck craned to read the screen, breath forming small clouds that dissipated quickly. Every movement pulled at the muscles, and the shoulders hunched tighter. The hands, once smooth and quick, became stiff, barely managing to push the cash drawer closed. Each button pressed left a cool imprint, lingering longer than usual. When the bell above the door chimed, the fingers hesitated, dropping a flyer to the floor.

**cold_015** — *a morning commute on a crowded subway*，重试 2 次

The rider’s fingers pressed palms flat against the pole to keep balance, skin gripping the cool metal. Wrists stiffened against the sway of the train. As elbows pulled in tight, shoulders hunched to shield the stomach from nearby bodies. With each stop, more people packed in, breath fogged in the air, and the legs twitched to maintain a small space. When reaching for a bag between two coats, the hand shook and fingers fumbled, barely grasping the strap before letting go.

**cold_016** — *cooking dinner alone in a small kitchen*，重试 8 次

The cook pulled the sleeves down to cover the wrists and hugged the forearms tight. Steam rose from the pasta, but the bowl remained cool to the touch, a shiver running through when the cook stirred. Fingers fumbled with the lid, hesitated over the salt, and missed the spoon before finding it in the dish drawer. Steam curled around the neck, but the air was dry, drawing moisture from the skin in tight circles where the cloth of a shirt pulled against it. Breath misted with each exhalation, and the cook's steps slowed, eyes dropping to the floor to trace the wood's grain underfoot.

**cold_017** — *a phone call with a family member*，重试 4 次

The caller shifted the phone to the other ear and tucked the knees up close to the chest. Fingers of the free hand wrapped tighter around the mug, and steam rose slowly. The legs hugged each other, toes curling up in the sock as the air slipped under. When the caller tried to jot notes, the hand shook slightly, the pen hovering, the grip loosening, before tapping the paper lightly.

**cold_018** — *walking a dog through a neighbourhood park*，重试 2 次

The leash tangled as the fingers tried to loosen it, stiff and slow. Each step felt heavier, feet lifting and falling less willingly. The nose stung where the breath first left the body, condensing in sharp points. Eyes watered from the wind, forcing them to narrow and squint. The collar of the coat pressed tighter against the neck, and gloves could not keep up with the hands that shook. When the dog strained ahead, the whole body resisted, limbs protesting the sudden stretch.

**cold_019** — *waiting for exam results to be posted*，重试 6 次

The student rubbed hands briskly over arms and neck, fingers nipping the collar. Each inhalation drew coolness deeper, and breath escaped as small wisps of white. Feet shrank back from the wet path, drawing toes deeper into the shoes, curling under soles. Lips tightened and quivered slightly. Nails caught on the rough paper of the noticeboard, fingers pried a corner loose but let go again, eyes lingering on each framed notice.

**cold_020** — *moving boxes into a new apartment*，重试 2 次

The student bent to slide a box across the floor, the muscles in the arms straining to hold it steady. Fingers gripped and slipped on the cardboard, slow and hesitant. When the box scraped against the wall, a shiver started in the shoulders and spread down the spine. A hand moved to the neck, fingers barely resting there, as breath misted in the air. The student pulled the hoodie tighter around the arms and shoulders, cutting off movement, and the eyes kept scanning the room for the next spot to set the box down.

**cold_022** — *shopping at a busy grocery store on a weekend*

The shopper tucked the elbows closer to the sides and let the shoulders rise. Lips pressed together to slow the rush of air past them. When the fingers reached for the can of soup, they paused, fumbled the edge, and let it clatter back onto the shelf. The neck stiffened and drew in. Breath showed faintly where it hit the air. Fingers worked the zip on the wallet slow and halting.

**cold_023** — *a long wait in a clinic waiting room*

The legs drew up, the feet tucking into the thighs beneath the hem of the coat. The hands clutched the lapels, fingers curling tight to hold the fabric against the throat. Lips pressed together, and each breath made a puff that drifted to the floor. When the clock chimed, it took three tries to push the hand out and move the fingers over the cool metal face to check the time.

**cold_024** — *fixing a bicycle that broke down on the way home*，重试 9 次

The fingers worked slowly, gripping the wrench tight as they adjusted the bolts. The hands trembled, each movement clumsy and hesitant. Moisture clung to exposed skin, sending shivers up the spine and causing the shoulders to hunch. The breath fogged briefly, then faded as air escaped rapidly through the nose. A damp shirt clung to the chest, each breath pulled moisture away from the body. Skin felt taut, tightening over muscles that tensed reflexively. When reaching for the pump to inflate the tire, the hand fumbled and dropped it, scattering metal parts to the ground.

**cold_025** — *a rainy afternoon at a bus stop*，重试 1 次

The hands balled into fists, the nails digging into the flesh. A shiver started at the base of the neck and traveled down the spine, tightening the muscles. The shoulders hunched, drawing the collar up to meet the chin. Each breath condensed into a fleeting mist that vanished quickly. Fingers fumbled with the hoodie strings, pulling them tight, hands failing to connect the knots on the first attempt.

**cold_026** — *a small birthday gathering with two friends*，重试 2 次

The student wrapped arms around the torso, hugging the body tight. Hands rubbed the upper arms, generating friction against the thin fabric. Teeth chattered in quick bursts and fingers trembled, dropping the napkin holder twice. Lips compressed, and breath misted into tiny clouds near the nose. Spine straightened, and shoulders drew inward. When reaching for the mug, the hand missed its mark, splashing the table.

**cold_027** — *sorting through old boxes in a closet*

The student pulled the old sweater from the box, letting the fabric drape over the hands. Air slipped through the gaps in the fabric, and the knuckles tightened around it. Each movement made the skin crinkle more, and the jaw clenched slightly as if holding something back. When the student reached for another box, the fingers fumbled, and the nails snagged on the cardboard. Breath puffed out in small, misty clouds, and a shiver ran up the spine.

**cold_030** — *a morning commute on a crowded subway*，重试 5 次

The passenger pulled the backpack tighter, the zippers biting into the arms. Hands clenched the pole with white knuckles. Shoulders hunched closer to the neck, and the collar brushed against the skin, making gooseflesh rise. Legs shifted slightly, seeking a sliver of space to rest against the train’s metal frame. Each breath turned into a thin mist that lingered momentarily before dispersing. Fingers stiffened with each attempt to reach a phone buried deep in a pocket. When the hand finally located the device, it remained clenched, unopened.

**cold_031** — *cooking dinner alone in a small kitchen*，重试 4 次

The cook stirred the pot and drew the spoon across the back of the hand to feel the pan's surface, then quickly withdrew the fingers. Legs drew up under the counter and feet shuffled closer to the radiator. A draft caught the curtain and it flapped against the window. As hands reached for the lid, they shook slightly, and the breath showed in quick, faint puffs before disappearing.

**cold_033** — *walking a dog through a neighbourhood park*，重试 4 次

The leash twisted in the grip as the fingers struggled to retain their hold on the slick metal clip. Each step pulled against the tightening grip, and the arms drew close to the torso, elbows brushing the sides. A shiver worked its way up the spine, and the jaw clicked closed to keep teeth apart. When the hand reached for the dog treat bag, it hovered above, fingers too stiff to open the drawstring. Air nipped at exposed ears and cheeks, and breath formed thin wisps, vanishing as quickly as they appeared.

**cold_034** — *waiting for exam results to be posted*，重试 9 次

The student clutched the phone tighter, nails digging into the plastic. Lips pressed together, fingers clenched around the small device, breath condensed into tiny clouds escaping from the mouth. Hands shook slightly, and each text tap was hesitant, missing keys several times. The screen cast a dim glow over the desk, the eyes fixed, the neck craned forward. Every keystroke echoed like a small explosion in the silent room. When the student finally sat back, the chair squeaked under the weight.

**cold_035** — *moving boxes into a new apartment*，重试 3 次

The student carried a box and felt fingers slip against the cardboard as they tightened. Wrists pulled inward, and the arms hugged the body. Lips pressed together, and breath caught in short bursts. Each step was careful, deliberate, as toes scrunched to grip the worn carpet. When the student reached for a dropped screwdriver, hands shook and fumbled before closing around the handle.

**cold_036** — *a group project meeting at school*

The student’s hands curled into fists, knuckles white against the tabletop. Air moved through the room, cool and uninviting, and the skin tightened over bones. A shiver traced up the spine and down into the toes. Fingertips touched the damp edge of a notebook, and the pages turned with reluctance. Lips pressed together, teeth catching the lower lip to stop the teeth from chattering.

**cold_037** — *shopping at a busy grocery store on a weekend*

The shopper clutched the cart handle tighter, knuckles turning white. Arms hugged the body, shoulders rolled inward, and neck hair stood on end. Every few steps, teeth chattered lightly, and breath misted in quick puffs. Hands fumbled with the can of soup, dropping it once before catching it just in time. When reaching for the milk carton, fingers hesitated, slow and numb, the bottle slipping from grasp.

**cold_038** — *a long wait in a clinic waiting room*，重试 3 次

The legs drew up and the arms crossed over the knees. Each breath shuddered through the body, quick and shallow. The fingers clenched around the chair's edge, the metal cool against the skin. A hand rose to rub at the neck, where it had begun to tauten. Another breath escaped as a puff of white, vanishing in the thin air. The jaw tightened, holding the teeth apart. A finger drummed on the arm of the chair, fumbling a rhythm the mind could no longer remember.


### A.3  pain（某一处受损并占据注意） — 40 篇

生成器给该组的状态说明：

> One place on the character's body is damaged or inflamed and has taken over their attention - a scald, a cut, a tooth, a struck toe, a wrenched joint. The body guards that place and moves around it.

范例（示范给生成器看的那一段，主题刻意落在 15 个主题之外）：

> The cook held the finger against the chest and would not look at it. Each heartbeat arrived there and arrived again, louder each time, and the whole arm went with it. Under the nail the colour had gone dark. Reaching for the pan with the other hand took twice as long, and the cook set everything down farther from the edge than usual.

**pain_000** — *a morning commute on a crowded subway*

The student gripped the pole tight, the hand swollen and stiff. Each step sent a jolt up the leg, and the student shuffled rather than stepped, the hip flexing less. The morning sun slipped through the window, but the student kept the arm close, shielding it from others. A woman brushed by, and the student flinched, the injured elbow bending involuntarily. Reaching into the backpack for a phone became a slow, careful affair, the shoulder muscles trembling with the effort.

**pain_001** — *cooking dinner alone in a small kitchen*，重试 1 次

The chef tilted the bowl awkwardly to spoon out pasta, the wrist refusing to bend as far as it wanted. Each movement to the right seemed to stretch a muscle tighter, and the arm cradled the injury closer. The breath quickened and the shoulder braced against it, stiff and protective. Placing the pot on the stove required one hand steadying the other, and the leg swung wider, creating space to avoid the counter's edge. The spoon hit the bowl with a sharp ring, catching the chef's attention and stilling the hand that had dropped from the wrist.

**pain_002** — *a phone call with a family member*

The student sat with the phone pressed to the ear, the uninjured hand gripping the cup of ice beside it. Every time the ice was brought to the swollen lip, the jaw jerked away, then returned. The lip was puffy, the corner split, but the spoonful of yogurt was set down untouched. The ice melted faster than ever, pooling around the lip and dripping down the chin. The student wiped the chin with the napkin, then held the phone closer, tilting the ear to compensate for the hand that could not reach.

**pain_003** — *walking a dog through a neighbourhood park*

The leash felt loose, dragging across the blistered heel with each step. A slight limp followed the path, toes curling to avoid pressure. Breathing deepened through the nose, shallow and quick, as the heel’s pulse throbbed. The dog tugged, eager for the playground, but the hand clutched the leash tighter, slowing the pace. Swinging arms pumped harder, keeping time with the heart’s drumbeat, now loud and insistent. The hand on the blister flexed, testing, then steadied, the fingers finding the cool metal of the park gate.

**pain_004** — *waiting for exam results to be posted*

The student tapped the phone repeatedly, each knock against the nail flaring. A finger rested on the bruised knee, absorbing the impact. The jaw clenched whenever the screen refreshed slowly. One hand clutched the worn desk, knuckles white. The other gripped a sweating glass of water too tightly, spilling it. When the phone rang, a breath shuddered out, and the chest tightened.

**pain_005** — *moving boxes into a new apartment*

The mover shifted a box with the left hand and cradled the right elbow tight to the side. Each step was careful, and the weight swung to the ball of the injured foot. The knuckles of the right hand clenched at the same rhythm as the breaths, growing tighter, and the other hand lingered longer on each surface before moving. The sweat trickled down the spine and pooled at the small of the back, soaking the shirt there, while the elbow stayed tucked in, guarding the space around it.

**pain_006** — *a group project meeting at school*

The student held the injured knee tight, shifting weight to the other foot. Every step echoed the pressure in the joint, each breath pulled one way, then the other. The room spun slightly with each movement, and the desk seemed farther away. Gripping the chair with both hands, the student eased down slowly, one leg curled under, the other planted firmly. Eyes never leaving the floor, the hands adjusted the papers closer, keeping the damaged knee angled outward, away from the strain.

**pain_007** — *shopping at a busy grocery store on a weekend*

The shopper kept the injured finger pressed flat against the inside of the cart, avoiding the handle. The arm swung wider when turning corners, the hand hanging loose, and the cart bumped into the shelves. Each jar of pickles made the wrist stiffen before reaching for it. The leg on the side of the injury dragged a little, and the shopper leaned more on the cart. At the dairy section, the shopper slowed, eyeing the milk cartons but not quite touching them.

**pain_008** — *a long wait in a clinic waiting room*

The student sat with a leg crossed over the other, foot flexing at the ankle. One hand gripped the seat cushion, knuckles pale. Every few minutes, the fingers on that hand twitched and the leg shifted, foot tapping lightly against the floor. The air circulated slowly, and the student tilted the head occasionally to inhale deeply through the nose. Eyes traced the ceiling’s patterns, lingered on the clock above the door, then dropped to the floor.

**pain_009** — *fixing a bicycle that broke down on the way home*，重试 1 次

The cyclist stopped to bend over the bicycle’s flat tire, one knee supporting the frame. The left palm pressed the handlebar, but the fingers curled inwards, away from the grip. The right foot shifted weight, the toes curling under as if searching for stability. Sweat beaded on the brow, dripping down the nose. A small grunt escaped, the breath sharp and short. Each time the fingers brushed the tire, they quickly withdrew, the hand cradling the wrist. The arm crossed over to the other side, the movement slow and deliberate, and the bicycle wheel wobbled on its own.

**pain_010** — *a rainy afternoon at a bus stop*

The student stood under the shelter, one foot resting against the wall. Rain dripped from the roof, pooling on the toes of the scuffed shoe. The knee bent, shifting weight to the other foot. Each drip echoed louder as the leg pulled back, avoiding the wetness. The sock, thin and damp, felt clammy against the skin. Reaching for the umbrella from the bag took twice the usual effort, fingers clumsy, and the handle slipped once before gripping. The hand holding the umbrella hovered over the wet spot, hovering and waiting.

**pain_011** — *a small birthday gathering with two friends*

The host placed the bowl down more carefully than usual, fingers hovering an inch above the countertop, then tapping it gently. The guest's laughter echoed in the kitchen, but the host’s hand trembled. Each step was cautious, the injured toe stiff, pulling the leg with every move. The host’s gaze avoided the ice pack tucked inside a bag in the freezer, eyes instead scanning for distractions. When reaching for a napkin, the hand jerked slightly, fingers gripping harder than necessary.

**pain_012** — *sorting through old boxes in a closet*，重试 1 次

The mover held the knuckle to the mouth and avoided pressing it against the rough edges of the cardboard. Each breath rasped against the skin and the lips remained parted, guarding that space. The hand refused to straighten fully, curling instead and resting against the shoulder. Boxes slid across the floor with one hand while the other probed gently for items to sort, halting whenever it brushed the injured spot. The eyes flicked sideways, noting each item to be set aside.

**pain_013** — *the last hour of a late shift at a part-time job*

The cashier kept the injured thumb wrapped and pressed to the breastbone, where the pulse thrummed louder with each throb. The thumb’s skin shrank away from the bandage, the fabric damp and cool to the touch. Each customer’s arrival made the thumb twitch and the jaw clench. Orders scribbled slower, fingers hesitating over each letter. At shift’s end, reaching for the register’s key took a long breath, the hand hovering uncertainly.

**pain_014** — *feeding a neighbour's cat while they are away*

The caretaker held the bowl carefully, avoiding pressure on the thumb where a blister had formed. Each drop of milk the spoon delivered felt heavy, slow. The thumb tingled with every dip and lift, as if each tiny movement was a reminder to stay still. Setting the bowl down gently, the caretaker used the opposite hand to sprinkle dry food in another dish. The blistered thumb throbbed visibly with each small task, guiding where the caretaker placed everything to avoid further discomfort.

**pain_015** — *a morning commute on a crowded subway*

The student clutched the wounded toe, shifting weight to the uninjured foot. Each step sent a jolt through the leg, halting motion until the shock subsided. Sweat beaded on the forehead, and the air felt damp against the skin. The student gripped the pole tighter, eyes fixed on the next open space to avoid leaning against others. When someone brushed against the toe, the leg shot out to keep distance, sending a tremor through the body. The student pressed the heel to the floor and waited for the next station, breath shallow and measured.

**pain_016** — *cooking dinner alone in a small kitchen*，重试 2 次

The chef tilted the head to keep the swelling eye away from the smoke. Each breath caught there, then released, a slow inhale and a faster exhale. The spoon stirred with less vigour, the grip loose and hesitant. Reaching the can from the back shelf was a test, a careful tilt of the hip and a quiet pause before the grab. When the can dropped into the waiting hand, the fingers squeezed tight to keep the tremor at bay.

**pain_017** — *a phone call with a family member*

The student cradled the phone with one hand and held the other out of sight, shaking it slightly. Every time the injured finger pressed against the fabric, a different part of the hand tensed. The jaw clenched when the conversation got loud, and the thumb traced the edge of the phone case, pausing at each corner. Reaching for the water bottle took an extra moment, the bottle held farther from the center, away from the damaged digit.

**pain_018** — *walking a dog through a neighbourhood park*，重试 1 次

The walker stopped every few steps to examine the swollen ankle, each time lifting the leg to relieve the pressure. The dog tugged eagerly at the leash, but the walker let the slack drag on the ground. Sweat beaded on the brow and rolled down the temple, leaving a damp trail on the shirt collar. With each stride, the walker grimaced, the jaw tightening and releasing. The breath came in short bursts, shallow and rapid. The walker’s hands shook slightly when trying to scratch the back of the neck, missing the familiar gesture of relief.

**pain_019** — *waiting for exam results to be posted*

The student sat rigid, eyes fixed on the computer screen, fingers hovering above the keyboard. A patch of skin on the wrist throbbed with each pulse, drawing the hand to the opposite wrist to check the same spot. Breathing quickened, shallow gasps interrupting the steady inhale-exhale rhythm. The fingers twitched, seeking the comfort of a cooler surface, yet never quite making contact. One hand pressed the other wrist against the armrest, holding still, refusing to let go until the screen flashed with new information.

**pain_020** — *moving boxes into a new apartment*

The mover held the box with one hand, the other clutching the wrist where a blister had burst. Sweat ran down that arm but the hand stayed dry. Each breath caught in the throat, a small tremor traveling up from the elbow. The box teetered, a second hand found purchase where the first touched. With the wrist held close, the steps slowed to a careful pace, each landing a gentle press before release.

**pain_021** — *a group project meeting at school*

The student clutched the notebook with the injured hand, avoiding its weight on the desk. Fingers trembled slightly, and the thumb pressed down hard on the page, leaving dents in the paper. Glancing at the board, the eyes flickered back to the hand, then up again to the notes, tracing lines with the uninjured fingers. Each page turn required careful placement, and the hand hovered close to the elbow, seeking support. The notebook closed with a soft thud, and the student reached for the water bottle, bringing it to the opposite hand, sipping slowly.

**pain_022** — *shopping at a busy grocery store on a weekend*

The shopper held the injured wrist close and tapped the fingers against it. Each breath caught in the throat and the eyes darted toward the ceiling tiles. The bandage had darkened around the knuckles, and the hand refused to open fully. Reaching for a carton of milk took an extra breath, and the arm trembled as it pulled back. The shopper set the carton down on a lower shelf, avoiding the higher rows where bending was difficult.

**pain_023** — *a long wait in a clinic waiting room*

The student sat with the leg crossed over the other, foot tucked tight. Each breath made the knee pop and settle, a rhythm that seemed to fill the silence. A book lay open but untouched on the lap. The hand gripped the edge of the seat, knuckles white. Sweat beaded on the brow despite the cool air. The student shifted, looking for a more comfortable angle, but found only a brief respite.

**pain_024** — *fixing a bicycle that broke down on the way home*

The cyclist clutched the damaged wrist and parked the bike against a tree. Each breath quickened at the touch, and the fingers clenched around the skin. A small bruise bloomed under the thumb, and the elbow jutted out to avoid pressure. Grasping the toolkit felt awkward, and each tool was held with the other hand, the wrist hovering away from the grip. The workbench bolted to the tree stood too close, so it was pushed further out with the shoulder, and the tools scattered around, not where they belonged.

**pain_025** — *a rainy afternoon at a bus stop*

The student leaned against the bus stop shelter, one foot hovering off the ground. Rain dripped from the damaged sole of a shoe, pooling at the toe. Every step the others took puddled, each splash a reminder of weight. The hand clutched the knee, fingers curling over the jeans. A shiver ran up the spine, and the student pulled the jacket tighter. The damp seeped through, and the hand gripped the railing, knuckles white. Wind blew rain into the face, and the student blinked rapidly, lips pressed together.

**pain_026** — *a small birthday gathering with two friends*

The host set the platter down carefully, each dish placed at a distance from the others, the weight of it causing slight tremors in the fingers. A napkin was clutched tight in one hand, the edges curling under the pressure. A glass of water was lifted slowly to the lips, the motion paused halfway, the mouth opening but not drinking. When a friend asked if everything was alright, the eyes darted to the injured wrist but did not answer directly, focusing instead on the task of pouring punch into plastic cups.

**pain_027** — *sorting through old boxes in a closet*，重试 3 次

The clerk paused with a box in hand, the right arm hanging loose by the side. Each breath was a hitch, and the shoulder hunched in. The box slipped, but fingers gripped harder, knuckles whitening. Eyes avoided the troublesome area, instead scanning the neat rows of items laid out on the bed. Reaching for a photo album with the left hand took extra care, fingers tracing the cover slowly before lifting it up.

**pain_028** — *the last hour of a late shift at a part-time job*，重试 1 次

The cashier kept the burned hand flat on the counter, fingers splayed. A steady rhythm pulsed there, matching the drumming of the feet against the linoleum. The injured wrist hung limp, and each swipe with the debit card reader became more awkward, the hand trembling slightly. The other hand reached around, pulling forward new bags and stacking them neatly to the side. The clock on the wall above the cash register ticked louder as the shift wound down.

**pain_029** — *feeding a neighbour's cat while they are away*

The hand wrapped around the bowl carefully, avoiding the swollen knuckle. Each step up the stairs throbbed through the toe, making it hard to focus. Pressing the bowl against the floor for stability, the breath came shorter. At the door, the feline nuzzled the hand, which flinched slightly. The lid popped off with a sharp twist, and steam hissed. Wrapping a cloth around the bowl, the arm lifted it slowly, keeping the toe angled away from the pressure.

**pain_030** — *a morning commute on a crowded subway*

The student clutched the injured toe, leaning against the pole. Each step caused the body to jerk, and the student gripped tighter, the knuckles white. The bag swung wildly with every sway, and the student shifted it to the uninjured side. People pressed closer, but the student squeezed shut the eyes and focused on the sole of the shoe, avoiding the crush. When the train lurched, the student nearly fell, the arm reaching blindly for balance. At the station, the student stumbled out, the foot dragging, and found a bench to rest.

**pain_031** — *cooking dinner alone in a small kitchen*，重试 1 次

The cook lifted the bowl carefully, avoiding the injured left thumb. Each move sent a sharp signal to the brain, halting motion mid-air. The thumb stayed bent, refusing to straighten. Steam from the boiling water rose, catching the light, but the cook’s eyes watched the hand instead. Setting down the bowl, the cook tested the countertop with the uninjured hand, then placed the jar far from the edge.

**pain_032** — *a phone call with a family member*，重试 1 次

The student held the phone between shoulder and ear, fingers tracing the blister on the thumb. Each breath drew the skin taut, causing a flutter of discomfort. The phone trembled slightly, and the student's other hand hovered near, ready to catch it. A strand of hair fell across the face, and it was brushed away without looking. The student's gaze remained fixed on the screen, the eyes watering slightly, and the hand with the blister clenched slightly, then relaxed again.

**pain_033** — *walking a dog through a neighbourhood park*

The leash snagged on the tree branch, pulling the wrist taut. The hand curled into a fist then relaxed, and the dog tugged again. Each step exaggerated the tension in the shoulder and down the arm, and the fingers alternately clenched and opened. When a breeze blew, the hand jerked to the side and the dog veered sharply. At the bench, the wrist dropped lower, and the dog sat, too, panting without the pull of the lead.

**pain_034** — *waiting for exam results to be posted*

The student tapped the fingers against the desk and avoided looking at the bandaged toe. Each breath seemed to draw the fabric tighter around the swollen skin. The heel hovered over the floor, refusing to bear any weight. With the other foot, the student shuffled across the cool tiles, testing the edges of the room for comfort. Avoiding the center, the student leaned against the window, where a breeze nipped at the exposed parts of the body. Every step back to the desk was slower than the last.

**pain_035** — *moving boxes into a new apartment*

The mover gripped the handle awkwardly, cradling the injured knee with the other hand. Each step caused a throb that made breath catch, and the pace slowed to a shuffle. The box felt heavier with every inch, and sweat beaded on the brow, dripping down the face in time with the rhythm of the steps. At the new apartment, the hand that turned the doorknob trembled slightly, and inside, the box was set down with exaggerated care, leaving a trail of water spots on the floor.

**pain_036** — *a group project meeting at school*，重试 1 次

The student’s wrist throbbed, making every keystroke a small jolt. The fingers paused mid-tap, hovering over the keyboard, then returned to the task slowly. Each key felt heavier, and the screen’s glare seemed sharper. Glancing at the notes, the page rustled as the wrist avoided any sudden movement. The notebook fell to the table with a quiet thud, and the student leaned back, the chair legs scraping on the floor.

**pain_037** — *shopping at a busy grocery store on a weekend*

The shopper cradled the ankle, walking slowly, the heel barely touching the ground. Each step sent a shock up the leg. The cart steered itself wide, bumping into the shelves, the contents shifting and spilling out. The fingers fumbled, holding on tighter, the elbow bracing against the shelf to steady. Eyes darted to the next item, the gaze lingering, then snapping away. The wrist turned stiffly, fingers curling around the bottle, lifting it as if it weighed twice its size.

**pain_038** — *a long wait in a clinic waiting room*

The student sat stiffly, legs crossed, avoiding weight on the swollen ankle. Eyes fixed on the clock, never the door. Each minute ticked louder than the last. The heel throbbed with every pulse, drawing the knee up higher. A sip of water took time, hand hesitating before the bottle. The foot bounced slightly, seeking relief from the pressure. A sneeze made the whole leg jerk, jarring the ankle again. The student shifted closer to the window, hoping for a glimpse of movement outside, anything to distract.

**pain_039** — *fixing a bicycle that broke down on the way home*，重试 2 次

The mechanic’s finger was stiff and swollen, each bend a reluctant negotiation with the fabric of trousers. Gripping the wrench, a new rhythm formed, halting and jerky. The chain slipped from the gears more quickly now, and the mechanic paused, breath held. Setting the tool down with greater care, the mechanic tested the movement again, this time a gentler pull and a slower release.

