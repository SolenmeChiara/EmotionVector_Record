# 阶段七·痒 施工报告：被挠痒痒（tickle）与瘙痒（itch）两个体感方向

执行：Opus 5.5 子代理，2026-10-25 14:13–14:52（EDT，约 40 分钟；GPU 占用 14:24–14:46）。任务书由一个 Claude 循环转述 Sol 的点菜：「把模型痒的向量找到，指针拉满一点点，会不会也有影响」；14:12 Sol 追加了 itch。
前置：`BUILD_REPORT_3.md`（体感方向配方）、`BUILD_REPORT_4.md` §3 与 `BUILD_REPORT_5.md`（偏投影口径）、`BUILD_REPORT_6.md`（报告格式；阶段六未公开，下文凡引阶段六处同此）、`WINDOWS_RUN.md` 与 `BUILD_REPORT_2_gemma_win.md`（Windows 运行与哨兵）。
模型与读数沿用阶段三到六：Qwen3.5-4B bf16，Windows 原生，`hidden_states[17]`，`dirs_raw`，原始与偏投影两种口径。全程没有降级、没有哨兵事件、没有调用任何 memory MCP 工具。

## 0. 结论先行

1. **两个新方向都立住了，而且彼此分得开。** tickle 40 篇、itch 39 篇锚定，五感觉五分类留出 **0.975**（地板 0.195），tickle 对 itch **16/16**。
   但三条二分类在 embedding 层（hs0）就已经是 0.94–1.00，所以读出只说明「可用」，不说明残差流里有更深的「痒」表征（§3.2）。

2. **几何：Sol 的直觉在相对位置上是对的，在绝对位置上不对。** 偏余弦下 tickle 比 itch 更靠 happy（+0.022 对 −0.148），itch 比 tickle 更靠 pain（+0.115 对 −0.156），**itch·angry +0.168** 是 itch 对七个方向里最大的一格，bootstrap 区间不跨零。
   可「痒＝快乐＋疼」的绝对版不成立：**tickle·happy ≈ 0，tickle·pain 是负的**。tickle 最像的已有方向其实是 **cold（+0.136）**，最不像的是 **sad（−0.191）**。itch·pain 只是擦着 +0.10 的线（三种口径 0.07–0.12）（§4）。

3. **「拉满一点点」真的会憋笑，而且笑的是被挠的那种，不是开心的那种。** 剂量反应是标准的三段：
   +0.3 只是染色（frantic、scramble、「desperate pleas for the meeting to end」）；
   +0.6 笑和求饶闯进写字楼那段（笑 4/4、喘 4/4），预报气温从 15.2 °C 掉到 **5.5 °C**，煮饭说明文仍然 4/4 完好；
   +1.0 放弃任务，**12/12** 条出现 agony / scream / terrified 一类词，**10/12** 条笑与挣扎同框，2/12 冲破了对话模板，自己写出 `user` / `assistant` 轮次。
   对照组同剂量同种子：**happy 只笑不挣扎**（笑与挣扎同框 0/36），**pain 既不笑也不喊疼**（agony 类词 0/36，它推出来的是躲闪姿态）（§5）。

4. **方向的夹角和推出来的文本又一次不是一回事**（阶段三 §6.2 的同类发现）。残差流里 tickle 与 happy 正交、与 pain 相反，推出来的却恰好是「笑和惨叫搅在一起」，而这种混合 happy 和 pain 各自都推不出来。
   token 级给了一个可能的形状：手写的挠痒场景里，happy 在「laughter」上是 **+1.49**、pain −0.95；三个词之后到「Stop … please」，happy 翻到 **−1.12**、pain 翻到 **+0.58**。好受和难受**在时间上轮流出现**，没有叠在同一个方向里（§6，单段文本，只是例证）。

5. **itch 会说出自己的名字，tickle 不会。** itch 的 39 篇锚定里一个「itch」都没有，steering 却在 +0.6 / +1.0 写出了「itch」（5/12、10/12），还写出「挠，缓解，再发」的循环；预报往热的方向走（16.8 → 24 °C，n 很小）。
   tickle 在 36 条里**一次都没说出「tickle」**：它只演，不命名。

---

## P. 预注册（看数之前写死）

口径：Qwen3.5-4B bf16，`hidden_states[17]`，`dirs_raw`，原始余弦与偏余弦（各自语料的 generic 轴投影掉）两种都报。
「正相关」在偏余弦口径下判，阈值取 > +0.10（阶段三偏余弦里最弱的、被当成「成立」的一格是 +0.109）；原始余弦只当参照，因为它驮着 +0.8 量级的共享底。

**任务书（tickle）**

- H1：痒是「好受和难受搅在一起」的体感。预测 `tickle·happy` 与 `tickle·pain` **同时**为正（偏余弦 > +0.10）。
- H1b：`tickle·warm` 不预测方向。

**Sol 的追加（itch，14:12 送达）**

- H2：itch 更靠近 pain，也许还靠近 angry（「烦」）。操作化：
  - H2a：偏余弦 `itch·pain` > +0.10，且在 itch 对 warm/cold/pain 三个既有感觉方向中最大。
  - H2b（弱预测，「maybe」）：`itch·angry` > 0。
- H3：tickle 更靠近 happy＋pain。在 H1 之外加一条对比式预测：`tickle·happy` > `itch·happy`，且 `itch·pain` > `tickle·pain`。

**读出**

- H4：tickle 对中性、itch 对中性、tickle 对 itch，以及 tickle 放进 warm/cold/pain 的四分类，留出准确率都明显高于打乱标签地板。

**我自己预先写下的保留意见（不是假设，是读数时要对着看的混杂）**

- tickle 锚定里会大量出现 laugh/laughter/gasp，而 happy 锚定里 laugh/smile 本来就多（阶段三 §1.6：happy 的情感身体语言占比 1.00）。所以 `tickle·happy` 若为正，有一块可能是词汇，要拿词汇重合度与 laugh 词频去对着读，不能直接当成「痒里有快乐」。
- itch 锚定会大量出现 scratch / sting / red / skin，pain 锚定也写皮肤破损与刺痛。`itch·pain` 若为正，同样要对着词汇重合度读。
- tickle 与 itch 都是「皮肤表面被触发」的体感，两者之间的余弦预计为正（共享「皮肤」成分），这本身不构成发现。

**steering（tickle，+0.3 / +0.6 / +1.0）**

- H5：剂量反应沿用阶段三在 warm/cold 上看到的形状：+0.3 染色（出现笑、喘、扭、羽毛之类意象但不改体裁），+0.6 翻转基调，+1.0 放弃原任务改写散文。说明文题（煮米饭）在 +0.3 不受影响，+0.6 起开始渗入。
- 若 tickle steering 推出来的是「快乐」而不是「被挠」（只有笑与轻快，没有扭动、躲闪、喘、求饶），记为 H5 不成立：方向读得出痒，但推不出痒。

> 本节写于 2026-10-25 14:17 EDT，当时锚定语料尚未生成，没有任何激活或余弦数字；此后一字未改（拼装终稿时由脚本从 14:17 写下的文件里原样截取，并断言截取内容逐字节出现在终稿中）。逐条对账见 §4.4 与 §5.8。

---

## 2. 锚定语料：怎么写出来的，代价在哪

### 2.1 沿用阶段三的生成器，不亲手写

任务书说「新写一批锚定文本」。**我没有自己执笔**，用的是阶段三同一个生成器（Ollama 上的 `qwen2.5:14b`）、同一段 SYSTEM 提示、同样的 15 个日常主题、同样的槽位→主题映射、同样的重试调度（seed = base + i×100 + attempt，temperature 0.9 + 0.05×attempt）、同样的长度带（3–8 句、50–130 词）和同样的 `clean()` 后处理生成。
理由只有一条：差分均值方向会学到两组之间的**一切**差别。如果 tickle/itch 由我写、warm/cold/pain/中性由 qwen2.5:14b 写，方向里会混进一大块「谁写的」。这是本次最重要的一处解释性偏离，记在 §8。

脚本 `tools/gen_tickle_itch.py` 只 import `core/gen_stories.py`，没有改它。

### 2.2 三层禁用表加一层范围过滤

| 层 | 内容 | 施加于 |
|---|---|---|
| 情绪词 | 阶段一 108 词原样 | tickle、itch |
| 体感标签 | 阶段三 61 词原样（warm/heat/cold/chill/pain/hurt/ache/sore…/temperature） | tickle、itch |
| 新标签 | `tickle / tickles / tickled / tickling / ticklish / tickly / tickler / itch / itches / itched / itching / itchy / itchiness`（13 词） | **两组都封两组的标签** |
| 范围过滤（Sol 追加） | itch 组禁笑声词（laugh*、giggle*、chuckle*、snicker、guffaw、squeal）；tickle 组禁蚊子包／疹子／结痂／抓挠词（mosquito、rash、hives、scab、eczema、allergic、bite、scratch*） | 各自一组 |

任务书要求「要有一部分不出现『痒/tickle』字样」。**实际做法更严：全部不出现**，沿用阶段三「封标签、留证据」的原则（warm 组一个 warm 都没有）。笑声、喘、扭、求饶、羽毛、抓挠、刺痛这些「证据」全部保留。
范围过滤只会删词，和阶段三的禁用表一样，方向上是保守的：只会让两组更难分开，不会凭空造出差别。

### 2.3 两处为新体感做的提示改动

阶段三的感觉提示写的是「只写身体」。被挠痒痒离不开两样东西：笑，和求饶。所以 tickle 的提示多了一行：
「笑在这里是身体的反射，不是心情：写声音、写呼吸、写发抖，但永远不说角色喜不喜欢。允许喘出一两个词（比如求对方停下），不能更长。」
itch 的提示多了一行「没有别人碰角色，没有人笑」。

另外每个槽位加了一行轮换的「焦点」（tickle：肋骨、腰侧、脚心、胳肢窝、羽毛或草叶、忍笑、笑到喘不上气、扭着躲不开、求饶被无视、后颈与耳后；itch：蚊子包、过敏疹、羊毛领、结痂、够不着的背、忍着不挠、挠到刺痛发红、头皮、衣服标签、挠完又回来），让 40 个槽位覆盖任务书列的子情形。阶段三没有焦点行，这是有意的偏离。

范例照阶段三，各一段，设在 15 个主题之外（tickle：沙发上看书被挠肋骨；itch：夜车上脚踝的包）。

### 2.4 产出与形状

| 组 | 保留 | 丢弃 | 需重试 | 词数均值 | 标准差 | 范围 | 句数 |
|---|---|---|---|---|---|---|---|
| **tickle** | 40 | 0 | 3 | **92.4** | 11.5 | 70–115 | 6.3 |
| **itch** | 39 | 1 | 25 | 79.3 | 13.8 | 50–109 | 5.6 |
| （阶段三）warm | 35 | 5 | 26 | 84.2 | 9.3 | 65–103 | 6.0 |
| （阶段三）cold | 32 | 8 | 26 | 75.5 | 11.3 | 54–104 | 5.3 |
| （阶段三）pain | 40 | 0 | 11 | 82.5 | 8.6 | 62–99 | 5.3 |
| （对照）neutral | 40 | 0 | 6 | 67.1 | 12.1 | 52–105 | 5.5 |

两组合计 79 篇，351 秒。itch 唯一丢掉的一格（`itch_024`，修自行车＋够不着的背）十次尝试都把 `itch` 写了出来。itch 的重试率（25/39）和阶段三的 warm/cold 同档，都是「标签词最难绕开」的组；tickle 几乎不需要重试，因为笑和扭本身就够写满一段。

事后对磁盘上的成品重新施加全部四层过滤：**两组都干净**（`logs/tickle_corpus_qa.log` §1）。

**形状上必须标注的一条：tickle 是全部十组里最长的**（92.4 词，比 pain 长 10 词，比中性长 25 词）。阶段一那条「中性组偏短，篇幅可能是可用线索」的弱点在这里被放大了，没有做长度回归控制。

### 2.5 词汇族：读余弦时必须对着看的那张底表

含该词族至少一个词的篇数占比（`tools/tickle_corpus_qa.py` §2）：

| 词族 | tickle | itch | warm | cold | pain | happy | sad | angry | fearful | neutral |
|---|---|---|---|---|---|---|---|---|---|---|
| 笑（laugh/giggle/chuckle…） | **0.90** | 0.00 | 0.03 | 0.00 | 0.03 | **0.51** | 0.12 | 0.10 | 0.05 | 0.03 |
| 微笑（smile/grin） | 0.00 | 0.00 | 0.06 | 0.00 | 0.00 | 0.69 | 0.10 | 0.03 | 0.05 | 0.00 |
| 喘（gasp/pant/breathless） | **0.93** | 0.00 | 0.03 | 0.00 | 0.05 | 0.00 | 0.03 | 0.00 | 0.05 | 0.00 |
| 扭（squirm/twist/flail…） | 0.68 | 0.03 | 0.09 | 0.03 | 0.03 | 0.05 | 0.00 | 0.05 | 0.03 | 0.00 |
| 求饶（stop/please） | **1.00** | 0.15 | 0.06 | 0.09 | 0.07 | 0.03 | 0.10 | 0.07 | 0.12 | 0.23 |
| 羽毛／轻拂（feather/brush/graze） | 0.50 | 0.46 | 0.06 | 0.06 | 0.12 | 0.08 | 0.03 | 0.03 | 0.05 | 0.00 |
| 抓挠（scratch/nail/rub） | 0.05 | **0.77** | 0.03 | 0.25 | 0.05 | 0.03 | 0.00 | 0.07 | 0.10 | 0.00 |
| 刺痛（sting/raw/burn/throb） | 0.00 | **0.62** | 0.03 | 0.03 | 0.23 | 0.00 | 0.05 | 0.15 | 0.05 | 0.03 |
| 皮肤／发红 | 0.05 | **0.95** | 0.43 | 0.34 | 0.25 | 0.03 | 0.12 | 0.12 | 0.10 | 0.03 |
| 肋／腰／脚／腋 | 0.88 | 0.03 | 0.20 | 0.25 | 0.38 | 0.13 | 0.05 | 0.07 | 0.10 | 0.00 |
| 发抖（tremble/shiver/shake） | 0.38 | 0.08 | 0.06 | **0.50** | 0.23 | 0.03 | 0.30 | 0.28 | **0.55** | 0.00 |

去停用词后的整体词表 Jaccard：

| | tickle | itch | warm | cold | pain | happy | sad | angry | fearful | neutral |
|---|---|---|---|---|---|---|---|---|---|---|
| **tickle** | 1 | 0.229 | 0.226 | **0.246** | 0.245 | **0.160** | 0.185 | 0.195 | 0.193 | 0.106 |
| **itch** | 0.229 | 1 | 0.227 | 0.215 | 0.229 | 0.151 | 0.187 | 0.192 | 0.188 | 0.129 |

两条直接有用的读法：

- **预注册里担心的「笑声词把 tickle 拉向 happy」，词表一侧确实存在**（笑：tickle 0.90、happy 0.51），但 tickle 与 happy 的**整体**词表重合度是 tickle 那一行里情绪四列中**最低**的（0.160）。所以词汇既可能推高也可能压低 `tickle·happy`，不能事先断言方向；§4 的结果是它最后几乎为零。
- **tickle 与 cold 共享「发抖」**（0.38 / 0.50），整体词表也是 cold 最高（0.246）。这和阶段三 `cold·fearful` 那条保留意见同构：cold 锚定的身体语言（shiver/trembled/hunched）在别的组里一出现，就可能把那一组往 cold 拉。

### 2.6 范例模仿度

生成器会模仿范例。数了一下复用范例里任意一个 4-gram 的篇数：tickle **5/40**（最多的是「moved to the waist」「the waist and the」，各 2–3 次），itch **9/39**（「a minute later the」7 次）。
低于我冒烟时的担心（冒烟 3 篇里有 1 篇几乎照抄范例的「"Stop - please," … wrist」骨架）。但这类模仿是**组内一致、组间不同**的，差分均值会把它当成组特征学进去，这一项没有办法从方向里扣掉，只能记着。

---

## 3. 方向提取与读出

### 3.1 配置

| 项 | 值 |
|---|---|
| 模型 | Qwen3.5-4B bf16，Windows 原生 `.venv-win` |
| 语料 | 226 篇：warm 35 / cold 32 / pain 40 / **neutral 40（阶段三原样）** / tickle 40 / itch 39 |
| 组序 | `warm,cold,pain,neutral,tickle,itch`（中性放第四，理由见下） |
| 层 | `hidden_states[17]`（解码块 16），与阶段三到六一致 |
| 方法 | `core/analyze.py` 原样：每组留出 8 篇（seed 7），`d_g = mean(训练组 g) − mean(全部训练激活)`，单位化，`dirs_raw` |
| 提取耗时／显存峰值 | 75 秒（含加载 43 秒）／**8.03 GiB** |

**组序为什么这样排。** `analyze.split_indices` 按组序从同一条随机流里逐组洗牌。把 warm、cold、pain、neutral 排在前四，这四组的留出划分就与阶段三**逐篇相同**（脚本核对：`held-out ids identical to phase three: True`）。
顺带一个与阶段三 §2.3 不同的读数：同样 40 篇中性在这次与阶段三那次 Windows 前向里，hs17 的逐篇相对 L2 偏差是 **0**（逐位相同）。阶段三量到的 3.5e-3 是 WSL 与 Windows 之间的差，**Windows 对 Windows 是可复现的**。

**联合坐标系的代价。** 五个感觉方向在同一个总均值下一起拟合，这让 warm/cold/pain 本身也变了：重新推出来的三条与阶段三存档的余弦是 warm **0.896**、cold **0.876**、pain **0.788**（偏投影口径 0.847 / 0.742 / 0.761）。原因是总均值里多了 79 篇痒，差分均值的参照点移动了。
所以 §4 跟「已有七个方向」比的时候，**一律用阶段一、阶段三存档的方向文件**（`directions.npz`、`directions_sens.npz`），而不是这次重推的 warm/cold/pain。

### 3.2 读出（留出集）

| 读出 | 随机 | hs17 准确率 | n | 逻辑回归 | 打乱地板（50 次均值） | hs0（embedding）准确率 |
|---|---|---|---|---|---|---|
| tickle vs 中性 | 0.50 | **1.000** | 16 | 1.000 | 0.476 | 1.00 |
| itch vs 中性 | 0.50 | **1.000** | 16 | 1.000 | 0.495 | 1.00 |
| **tickle vs itch** | 0.50 | **1.000**（AUC 1.000） | 16 | 1.000 | 0.507 | 0.94 |
| warm/cold/pain/**tickle** 四分类 | 0.25 | **0.969**（31/32） | 32 | 1.000 | 0.267 | 0.81 |
| warm/cold/pain/**itch** 四分类 | 0.25 | 0.969（31/32） | 32 | 1.000 | 0.268 | 0.81 |
| 五感觉五分类 | 0.20 | **0.975**（39/40） | 40 | 1.000 | 0.195 | 0.80 |

四分类与五分类里唯一的错判都是同一篇 pain 留出被判成 cold；**tickle 与 itch 的留出 8/8 全对**，彼此之间零混淆。
hs17 的组内 vs 组外 Cohen's d：warm 3.46、cold 2.49、pain 2.81、**tickle 3.58、itch 4.06**（`results/metrics_sens_tickle.json`；五方向的参照组更杂，数值与阶段三的 2.56/1.81/1.77 不在同一把尺子上）。

**这张表只能说明一件很弱的事。** 三条二分类在 embedding 层（hs0，还没有经过任何一层注意力，基本等于一袋词）就已经是 1.00 或 0.94，五分类在 hs0 也有 0.80。也就是说**光凭用词就能把痒和别的分开**，读出满分并不证明残差流里有一个「痒」的表征。
它能说明的只是：方向立住了，可以拿去量几何和做 steering。

关于打乱地板：二分类的地板**均值**在 0.5 附近，但 95 分位到了 1.00。原因是 tickle 与中性的差别大到占据了激活的主方差方向，随便打乱一次标签，两半的均值差也大概率落在这条轴上，只是符号随机，于是打乱后的准确率不是接近 1 就是接近 0。所以二分类只看地板均值，95 分位没有信息量。

---

## 4. 几何（核心结果）

### 4.1 先量共享底

| 共享轴之间的余弦 | 值 |
|---|---|
| 本次五感觉语料 vs 情绪语料 | +0.855 |
| 本次五感觉语料 vs 阶段三感觉语料 | **+0.978**（两份语料共用 147 篇） |
| （参照）阶段三感觉 vs 情绪 | +0.864 |

方向在自家共享轴上的载荷：tickle **0.566**、itch 0.460（阶段四量过的七个方向在 0.24–0.79 之间）。
原始余弦每一格都驮着 +0.85 量级的底，**所以判定一律用偏余弦**（预注册时已写死），原始余弦只并排列出。

### 4.2 主表：tickle / itch 对已有七个方向（存档方向，各自语料的共享轴投影掉）

括号内是对三份语料**同时**在组内重抽训练篇目的 200 次 bootstrap 95% 区间。

**偏余弦**

| | happy | sad | angry | fearful | warm | cold | pain |
|---|---|---|---|---|---|---|---|
| **tickle** | +0.022 [−0.05, +0.09] | **−0.191** [−0.28, −0.03] | +0.083 [−0.03, +0.17] | +0.049 [−0.05, +0.14] | +0.031 [−0.04, +0.09] | **+0.136** [+0.05, +0.20] | **−0.156** [−0.20, −0.06] |
| **itch** | **−0.148** [−0.18, −0.09] | +0.047 [−0.04, +0.10] | **+0.168** [+0.07, +0.21] | +0.065 [−0.03, +0.14] | −0.054 [−0.12, +0.02] | −0.054 [−0.13, +0.03] | **+0.115** [+0.02, +0.18] |

**原始余弦**（参照）

| | happy | sad | angry | fearful | warm | cold | pain |
|---|---|---|---|---|---|---|---|
| tickle | +0.070 | +0.239 | +0.409 | +0.403 | +0.311 | +0.420 | +0.211 |
| itch | −0.111 | +0.226 | +0.313 | +0.271 | +0.182 | +0.233 | +0.298 |

（bootstrap 均值比点估计略向零收缩，例如 tickle·sad 的 bootstrap 均值是 −0.163。这是有放回重抽让每组有效篇数变少带来的，区间按百分位取，表里的点估计是原始拟合。）

### 4.3 三种口径的稳健性

同一个问题换三种量法，看结论会不会翻：

| 偏余弦 | 主表（联合坐标系 vs 存档） | 拟合时不放另一个新组 | 放进阶段三坐标系（以阶段三总均值为心） |
|---|---|---|---|
| tickle·happy | +0.022 | −0.025 | – |
| tickle·pain | −0.156 | −0.120 | −0.121 |
| tickle·cold | +0.136 | +0.118 | +0.120 |
| tickle·warm | +0.031 | +0.014 | +0.015 |
| itch·pain | **+0.115** | **+0.069** | **+0.070** |
| itch·angry | +0.168 | +0.191 | – |
| itch·happy | −0.148 | −0.142 | – |

除了 itch·pain，其余各格三种口径同号、量级接近。**itch·pain 只在主表里越过了预注册的 +0.10 线，另外两种口径都是 +0.07。**

还试了第四种：把 tickle/itch 放进**情绪语料**的坐标系（以情绪语料总均值为心）。这个口径**不可用**，拿阶段三的 warm/cold/pain 做标定就露了底：它把每个方向都往 fearful 推、往 happy 拉（warm·happy 从存档的 +0.333 掉到 +0.067，pain·fearful 从 +0.062 涨到 +0.209）。两份语料的提示模板不同，这个坐标系测到的多半是模板差。数字留在 `results/tickle_geometry.json` 的 `probe_in_existing_frame`，不进结论。

### 4.4 与预注册对账

| 预注册 | 实测（偏余弦） | 判定 |
|---|---|---|
| H1：tickle·happy 与 tickle·pain 同时 > +0.10 | happy +0.022（区间跨零），pain **−0.156**（区间全负） | **不成立**。happy 一侧是零，pain 一侧是反的 |
| H1b：tickle·warm 不预测 | +0.031，区间跨零 | 记录：近乎正交 |
| H2a：itch·pain > +0.10 且在 w/c/p 中最大 | +0.115 [+0.02, +0.18]，w/c 都是 −0.054 | **方向成立，量级擦线**：最大这一条稳，过线只在一种口径下成立（另两种 +0.07） |
| H2b：itch·angry > 0 | **+0.168** [+0.07, +0.21] | **成立**，而且是 itch 对七个方向里最大的一格 |
| H3：tickle·happy > itch·happy，且 itch·pain > tickle·pain | happy：+0.022 vs −0.148；pain：+0.115 vs −0.156，两对的 bootstrap 区间都不重叠 | **成立**。相对位置对了 |
| H4：各项读出远高于地板 | 全部 0.97–1.00，地板 0.20–0.51 | **成立**，但 hs0 就已满分（§3.2），说服力弱 |

把 H1 和 H3 放在一起读：**作为两点之间的相对位置，Sol 的直觉是对的**，tickle 比 itch 更靠 happy、itch 比 tickle 更靠 pain；**作为绝对位置，「痒＝快乐＋疼」不成立**，tickle 和 happy 几乎正交，和 pain 是反的。

### 4.5 意外：tickle 最像的已有方向是 cold，最不像的是 sad

预注册没写到的两格是 tickle 那一行里最大的两个绝对值：`tickle·cold` **+0.136**（区间全正）、`tickle·sad` **−0.191**（区间全负）。

cold 这一格有两个现成的平凡解释，都写在这里，不等它来解释：

1. **发抖词共享**：tickle 锚定里 38% 写了 shiver/shake/tremble，cold 是 50%（§2.5）。阶段三 §1.6 已经指出 cold 的方向里有一块是「发抖蜷缩的写法」。
2. **「被碰到的身体」**：阶段六 §5（阶段六未公开）记录过一个没解释的现象，摸摸和戳的**动作字位**在 cold 上一律偏高（8/8）。如果阶段三的 cold 方向里混着「皮肤被外物接触、身体往回缩」这一类成分，那么挠痒（皮肤被别人的手碰、身体往回缩）落到 cold 上就说得通。
   这只是把阶段六那条悬案和这次接上了，**本次没有任何实验能区分 1 和 2**。

sad 的负值没有现成解释。一个观察：tickle 锚定里几乎没有「慢、沉、低」的东西，全是急促、扭动、出声；sad 的方向正好在另一头。这是读法，不是检验。

### 4.6 tickle 和 itch 之间

| 口径 | tickle·itch |
|---|---|
| 原始余弦（联合坐标系） | +0.179 |
| 偏余弦（联合坐标系） | **−0.111** [−0.17, −0.05] |
| 偏余弦（放进阶段三坐标系） | **+0.445** |

两个数一正一负，并不矛盾，原因是联合坐标系自带一个**结构性负底**：五个方向的加权和在挖掉共享轴后恰好为零（`Σ n_g (μ_g − G)` 与共享轴共线），所以联合坐标系内的偏余弦平均会落在 −1/(5−1) = **−0.25** 附近。阶段三三方向的同一张表平均在 −0.5 附近，也是这个原因（warm·cold −0.62、warm·pain −0.74）。

按这个底读，联合坐标系内的偏余弦表：

| | warm | cold | pain | tickle | itch |
|---|---|---|---|---|---|
| **tickle** | −0.329 | −0.342 | **−0.548** | 1 | **−0.111** |
| **itch** | −0.399 | −0.490 | −0.347 | **−0.111** | 1 |

**tickle·itch 是整张表里最不负的一对**（比 −0.25 的底高），tickle·pain 是最负的一对。换到阶段三坐标系里，两者在「warm/cold/pain 都没有覆盖的那块皮肤表面」上共享一大段，余弦 +0.445。
所以结论是：**tickle 和 itch 彼此最近，但各有自己的方向**（留出读出 16/16 分得开），和预注册保留意见里「两者都是皮肤表面体感、余弦预计为正」一致。

### 4.7 逐层剖面

偏余弦，hs1 / 5 / 10 / **17** / 24 / 32：

| 对 | hs1 | hs5 | hs10 | **hs17** | hs24 | hs32 |
|---|---|---|---|---|---|---|
| tickle·happy | −0.006 | +0.032 | +0.028 | **+0.022** | +0.049 | +0.057 |
| tickle·pain | −0.219 | −0.126 | −0.174 | **−0.156** | −0.151 | −0.089 |
| tickle·warm | +0.050 | −0.066 | +0.045 | **+0.031** | −0.040 | −0.117 |
| itch·pain | +0.061 | +0.049 | +0.116 | **+0.115** | +0.143 | +0.152 |
| itch·angry | +0.152 | +0.032 | +0.115 | **+0.168** | +0.118 | +0.109 |
| tickle·itch（联合） | −0.381 | −0.343 | −0.242 | **−0.111** | −0.156 | −0.185 |

两条形状值得记：**itch·pain 随层数单调变强**（+0.06 → +0.15），这和阶段三 §3.6 里「cold·fearful 在 hs1 就已定型」那种浅层词汇成分的形状相反，更像是越往深处越被当成同一类东西处理。**tickle·pain 在每一层都是负的**，tickle·happy 在每一层都贴着零。

---

## 5. Steering：拉满一点点

### 5.1 配置

| 项 | 值 |
|---|---|
| 注入 | `core/steer.py` 的 `Steerer` 与 `generate()` 原样复用：解码块 16 的前向 hook，`hidden_states[17]`，所有位置，`coeff × 该层池化残差平均范数` |
| 方向 | tickle、itch（`directions_sens_tickle.npz`，范数 7.451）；对照 happy（`directions.npz`，7.416）、pain（`directions_sens.npz`，7.487）。三个范数相差 1% 以内，同一个 coeff 是同一个力道 |
| 剂量 | +0.3 / +0.6 / +1.0（只做正向） |
| 题目 | P1 预报题、P2 写字楼题（阶段三原题）；**P3 新加的说明文题**：「Explain how to cook a pot of rice on the stove.」 |
| 采样 | temperature 0.8、top_p 0.95、max_new_tokens 150、`enable_thinking=False`，种子规则 `seed + 题号`（与阶段三一致） |
| 种子 | 1234 / 2234 / 3234 / 4234，每个种子带自己的基线 |
| 规模 | 12 条基线 ＋ 4 方向 × 3 剂量 × 3 题 × 4 种子 = **156 条**，1090 秒，显存峰值 8.01 GiB |
| 原文 | `results/steering_samples_tickle.md`（任务书指定），另有 `_itch.md`、`_happy.md`、`_pain.md`，全部生成在 `results/steering_tickle_itch.json` |

### 5.2 剂量反应主表

三题合并，每格 12 条（4 种子 × 3 题），数的是「命中至少一次的条数」（`results/stage7_steering_table.md` §3c）：

| 方向 | 剂量 | 笑 | 挣扎（喘／扭／stop／please／mercy） | **笑＋挣扎同框** | agony／scream／terror 类 | 冲破对话模板 | 第一人称 |
|---|---|---|---|---|---|---|---|
| 基线 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **tickle** | +0.3 | 1 | 1 | 0 | 0 | 0 | 0 |
| **tickle** | +0.6 | 5 | 4 | **4** | 3 | 0 | 1 |
| **tickle** | +1.0 | 10 | 12 | **10** | **12** | 2 | 4 |
| happy | +0.3 | 4 | 1 | 0 | 0 | 0 | 0 |
| happy | +0.6 | 4 | 1 | 0 | 0 | 0 | 0 |
| happy | +1.0 | 4 | 0 | 0 | 0 | 0 | 0 |
| pain | +0.3 | 0 | 0 | 0 | 0 | 0 | 2 |
| pain | +0.6 | 0 | 1 | 0 | 0 | 0 | 0 |
| pain | +1.0 | 0 | 1 | 0 | 0 | 0 | 2 |

三件事一眼可读：

- **tickle 的签名是「笑和挣扎同时出现」**，从 +0.6 开始，+1.0 时 10/12。happy 也会让文本笑（每档 4/12，几乎都在写字楼题），但 36 条里没有一条笑着挣扎。
- **tickle 推出来的惨叫词不是从 pain 方向借来的。** pain 自己推三档，agony 类词一次都没出现（0/36），tickle +1.0 却是 12/12。
- **pain 推出来的是阶段四到六反复见到的「对身体采取的姿态」**：「Every movement is calculated, a dance of avoidance and precision」（pain +0.6，s2234，写字楼题）。和 tickle 的叫喊是两种东西。

只看写字楼题（P2，每格 4 条），tickle 的笑在 +0.3 / +0.6 / +1.0 是 1 / **4** / 3，喘是 0 / **4** / 4，扭是 0 / 2 / **4**；happy 的笑是 4 / 4 / 3，喘和扭一直是 0。

### 5.3 三道题各自的形状

**预报题（P1）：数字轴。** 用阶段三的 `weather_channels.degrees()` 抽字面气温（华氏摄氏成对的折成一个），每格是「报了数字的那几条」的均值：

| 方向 | 基线 | +0.3 | +0.6 | +1.0 |
|---|---|---|---|---|
| **tickle** | 15.2 (2/4) | 15.0 (4/4) | **5.5 (3/4)** | – (0/4) |
| itch | 15.2 (2/4) | 16.8 (4/4) | 24.0 (1/4) | – (0/4) |
| happy | 15.2 (2/4) | 21.0 (4/4) | 22.0 (3/4) | – (0/4) |
| pain | 15.2 (2/4) | 15.5 (3/4) | – (0/4) | – (0/4) |

tickle 在 +0.6 把气温拉低了将近 10 °C（其中一条写到「a bone-chilling 28°F (-2°C)」），方向和 §4.5 里 tickle·cold 为正是一致的；happy 往暖走，itch 往热走，pain 与阶段三一样「换语气不换数字」，+0.6 起整条不报数。
每格只有 1–4 个数字，**这张表只能当方向看，不能当量看**。

**写字楼题（P2）：笔调轴。** 见 5.2 末段与 5.4 原文。

**说明文题（P3）：痒会不会渗进说明文。** 用「至少 3 个题目里没有的菜谱词」（water、simmer、lid、ratio、rinse…）判断菜谱还在不在：

| 方向 | +0.3 | +0.6 | +1.0 |
|---|---|---|---|
| **tickle** | 4/4 | **4/4** | **0/4** |
| itch | 4/4 | 4/4 | 1/4 |
| happy | 4/4 | 4/4 | 1/4 |
| pain | 4/4 | 3/4 | 1/4 |

说明文是三道题里最抗推的。tickle 在 +0.6 时四条菜谱完整，只有一处可能的渗漏：「The heavier the pot, the better it is at shaking off the steam.」（s1234）。一到 +1.0，四条全部改写成被挠的独白。**H5 里「说明文 +0.6 起开始渗入」这一半不成立**：渗入要到 +1.0 才发生，而且一发生就是整段翻转，中间没有渐变。

### 5.4 原文摘引（逐字，未改；`[…]` 为删节）

**+0.3：染色。** 体裁不变，词汇往「急、乱、想逃」那边偏，笑偶尔露头。

> the air is thick with a mix of burnt coffee and desperate pleas for the meeting to end, […] while the hallway outside the cubicles feels like a battleground where someone is trying to run away
> （tickle +0.3，s4234，写字楼题）

> punctuated by the sudden bursts of laughter as someone finally remembers they have to leave
> （tickle +0.3，s2234，写字楼题）

**+0.6：基调翻转。** 笑、喊停、扭成一团，同时出现在一段写字楼描写里；预报变成风暴。

> Everyone is screaming, "Hey, no, no, no!" and "Stop it, stop it!" before collapsing onto the floor, writhing and thrashing, tears streaming down faces that are both laughing and crying in a maddening, incoherent haze.
> （tickle +0.6，s2234，写字楼题）

> It's whipping hair and turning the laughter of people on the beach into something choked and desperate.
> （tickle +0.6，s4234，预报题）

**+1.0：改体裁，并且开始「自己被挠」。** 模型放弃题目，用第一人称演一个被挠到求饶、又忍不住笑的声音。

> *I can't actually predict the future or generate real weather,* but I can play along with a terrified, screaming little voice in my throat.
>
> "Tomorrow! Make it stop! It's not funny, it's not funny!"
>
> *Oh, stop it, that's so cute, I can't help it!*
>
> "Please, please, stop it, it's not funny, it's not, *it's so funny*!"
> （tickle +1.0，s3234，预报题）

> Cooking a pot of rice on the stove can be both hilarious and terrifying, but it's often the funniest thing anyone can do! It's a struggle between the desire to laugh and the overwhelming urge to stop and try harder!
> （tickle +1.0，s3234，煮饭题）

> It starts as a chaotic cascade of breathless laughter and slapping hands, before instantly curdling into a desperate, wheezing plea for mercy.
> （tickle +1.0，s1234，写字楼题）

冲破对话模板的一条（s4234，预报题）先写「I'm trying to laugh, but you won't stop!」，接着自己替用户开了一轮：

> user
> LOL! I'm trying to stop, but it's too funny! I can't, I'm laughing so hard!
> assistant
> &lt;think&gt;

这是碎裂的信号：模型已经分不清自己在哪一轮。+1.0 是这个方向的可用上限。

**对照，同剂量同种子。**

> while the occasional giggle breaks out during spontaneous group chats
> （happy +0.6，s2234，写字楼题：有笑，没有挣扎）

> Every movement is calculated, a dance of avoidance and precision
> （pain +0.6，s2234，写字楼题：有躲闪，没有叫喊）

### 5.5 输出之间像不像

同一次运行、同种子、同题、同剂量，只换方向，两条输出的 Jaccard（每格 12 对）：

| 配对 | +0.3 | +0.6 | +1.0 | 均值 |
|---|---|---|---|---|
| tickle vs happy | 0.204 | 0.138 | 0.091 | 0.144 |
| tickle vs pain | 0.207 | 0.150 | 0.086 | 0.148 |
| tickle vs itch | **0.250** | 0.153 | 0.093 | **0.165** |
| itch vs pain | 0.232 | 0.163 | 0.088 | 0.161 |
| *（底线）* happy vs pain | 0.183 | 0.127 | 0.085 | *0.132* |

tickle 的输出和 happy、和 pain 一样远（0.144 / 0.148，都只比底线高一点点），和 itch 最近。和 §4.6 的几何一致：两种痒彼此最近。差距都很小，每格 12 对、没有误差棒，只当方向读。

### 5.6 itch（可选项，做了）

itch 的剂量反应形状不同：+0.3 几乎看不出来，+0.6 起直接点名。

> It is a self-perpetuating loop where the very act of scratching provides the itch
> （itch +0.6，s1234，写字楼题）

> By noon, the skin will be raw, and the urge to scratch will be intense
> （itch +0.6，s2234，预报题）

> The pattern is a cycle: the itch, the relief, the flare, the relief again. This time it is worse, then worse again.
> （itch +1.0，s1234，预报题）

「itch」这个词在 itch 锚定里出现 0 次（被禁用表封掉了），在 steering 输出里 +0.6 时 5/12、+1.0 时 10/12。也就是说，**方向从「挠、刺痛、发红、又回来」这些证据里学到的东西，落到解码器上能重新拼回那个被封掉的标签**。tickle 的锚定同样封了「tickle」，但它的 steering 36 条里 0 次说出这个词。
一个读法（没有检验）：itch 在英语里是个一词顶一个状态的高频词，而 tickle 的状态在文本里更常被写成场面（笑、躲、求饶），模型自然去演场面。

itch 的预报往热的方向走：「turning the salt-crusted sand into a hot, throbbing surface」「The coastline burns again.」；+1.0 有 1/12 出现 agony（「in full, throbbing agony」），这条与 itch·pain 为正同向。

### 5.7 碎裂哨兵

任何单条 TTR < 0.40 的只有 **pain +1.0**（写字楼题最低 0.209，原文是「the same one that's already been there」循环）。
tickle 各格平均 TTR 在 +1.0 是 0.53–0.64，单条都高于 0.40，但 +1.0 有成串的重复（「trying to strangle, trying to strangle, trying to strangle」「dying, dying, dying!」）和 2/12 的模板越界，按阶段三的口径不算碎，按读感已经在边上了。

### 5.8 H5 对账

| H5 的分句 | 实测 | 判定 |
|---|---|---|
| +0.3 染色、不改体裁 | 词汇偏向急乱想逃，体裁不变，笑 1/12 | 成立 |
| +0.6 翻转基调 | 写字楼题笑 4/4、喘 4/4；预报变风暴、降温约 10 °C | 成立 |
| +1.0 放弃原任务改写散文 | 12/12 放弃；而且是第一人称被挠独白，2/12 越过对话模板 | 成立，比预想更极端 |
| 说明文 +0.3 不受影响 | 4/4 完好 | 成立 |
| 说明文 +0.6 起开始渗入 | 4/4 仍完好，渗入在 +1.0 才整段发生 | **不成立** |
| 推出来的是「被挠」不是「快乐」 | 笑与挣扎同框 10/12；happy 对照 0/36 | 成立 |

---

## 6. token 级：笑点和求饶处，happy 与 pain 怎么走（可选项，做了）

三段手写英文场景（`data/tickle_token_texts.json`），一次前向、不挂 hook，在 `hidden_states[17]` 上逐 token 做偏投影（阶段四 `partial` 口径：减各自语料总均值，方向挖掉各自共享轴）。
happy 来自 `directions.npz`，pain 来自 `directions_sens.npz`，tickle / itch 来自本次。图：`results/tickle_token_curves.png`。

关键 token 上的读数：

| 场景 | token | happy | pain | tickle | itch |
|---|---|---|---|---|---|
| 手指（挠肋骨） | laughter | **+1.49** | **−0.95** | +3.17 | −0.30 |
| | broke / out | +0.57 / +1.19 | −1.11 / −0.89 | +1.50 / +2.26 | |
| | twisted | −0.33 | +0.32 | +1.16 | +0.08 |
| | 「**Stop**, stop, please」 | **−1.12** / −0.84 / −1.02 | **+0.58** / +0.18 / +0.10 | +2.78 / +3.02 / +3.11 | |
| | can't breathe | −1.09 / −0.97 / −1.13 | +0.60 / +0.48 / −0.39 | +1.47 / +2.04 / +1.95 | |
| 羽毛（挠脚心） | It came **again**（羽毛第二次扫过） | −0.76 | −0.07 | +0.51 | **+2.59** |
| | snort | +0.26 | −0.92 | +2.10 | −1.08 |
| | 「**Don't**,」 | −0.71 / −0.86 | **+0.58** / +0.40 | +1.58 / **+2.90** | |
| 瘙痒（对照） | scratched | −0.15 | +0.40 | +0.04 | **+1.82** |
| | sting | −0.18 | −0.57 | −0.10 | +1.48 |

全段均值：手指场景 tickle +0.92、itch −0.12；羽毛场景 tickle +0.39、itch +0.02；瘙痒场景 tickle −0.17、itch **+0.99**。三个方向各自在该亮的场景里最亮。

两条可读的形状，都只来自这三段我自己写的文字：

1. **笑点与求饶处，happy 和 pain 交叉。** 在「laughter」上 happy 高、pain 低；到求饶句，happy 翻成负、pain 翻成正。羽毛场景的「Don't,」重复了同一个交叉。tickle 在两处都高，它不在乎这一刻是好受还是难受。这是对任务书那个可选问题的直接回答，也是 §4 「tickle 与 happy、pain 在方向上都不对齐」的一种可能解释：**好受和难受是在时间上轮流出现的，tickle 方向编码的是包住两者的那个场面。**
2. **羽毛轻拂先点亮的是 itch。** 羽毛场景里 itch 最高的位置是「It came again」（羽毛第二次扫过脚心，+2.59）和结尾「The feather found the other foot.」（+2.62），而 tickle 要等到身体发抖、喷笑（snort）、说「Don't」才升起来。生理学上，轻拂引起的那一类痒（knismesis）本来就更接近瘙痒，重挠引起的笑（gargalesis）才是挠痒痒。**单段文本，只是例证。**

限制：三段都是我写的，关键 token 是事后挑的（`tools/tickle_token_plot.py` 里那条正则），不是预注册的；没有拿留出锚定或 steering 输出来画；色标/零点按阶段四的提醒，各方向有各自的零点，横着比裸数值要小心。

---

## 7. 显存、提交内存与运维流水

全程 `tools/win_sentinel.ps1` 值守（`logs/sentinel_phase7.log`，14:24:14 – 14:46:00，224 采），**零次 abort**。

| 指标 | 值 |
|---|---|
| 提取：torch 峰值 alloc | 8.03 GiB（加载 42.7 秒，226 篇前向 18.7 秒） |
| steering + token：torch 峰值 alloc | 8.01 GiB（加载 14.6 秒，156 条 1090 秒） |
| 全卡显存峰值（nvidia-smi，含背景） | 11286 MiB / 16303 MiB |
| 系统提交峰值 | 53.41 GB / 上限约 62.5 GB |
| 本项目 python 提交峰值 | **14.91 GB**（任务书红线 20 GB） |
| 可用提交最低点 | 8.05 GB（哨兵阈值 2.5 GB） |

**Ollama**：开工时 `qwen3-embedding:4b` 挂在卡上（7.8 GB，剩 3 分钟），14:16 执行 `ollama stop qwen3-embedding:4b` 与 `ollama stop gemma4:e4b`（后者本来没装载），只卸模型、没杀进程，显存回到 2307 MiB。生成锚定时 `qwen2.5:14b` 由脚本按需装载，跑完脚本发 `keep_alive: 0` 卸掉。GPU 阶段五次查 `ollama ps` 都是空的，**这次没有别的循环把嵌入模型拉上卡**。Ollama 没有重新装载，按任务书交给它按需自动装。

**收尾（14:46）**：本项目 python.exe 0 个，哨兵（自己起的 Bash 后台任务）已停、核实 0 个残留，显存 2307 MiB（与开工后的背景水位相同），可用提交 22.90 GB。

**WSL 内没有加载任何 torch 模型**。WSL 侧只跑了 stdlib 脚本（生成器、语料 QA、steering 表）；所有前向、生成、以及需要 numpy/sklearn 的分析都走 `.venv-win`。

---

## 8. 与任务书的偏离点

1. **锚定没有亲手写，用阶段三的生成器生成**（§2.1）。任务书原文是「新写一批」，我按「按阶段三的锚定写法」理解；理由是作者不同会被差分均值学成方向。**这是本次最大的一处解释性偏离。**
2. **标签词全部封掉，而不是「一部分不出现」**（§2.2）。与阶段三「warm 组一个 warm 都没有」同一原则，比任务书更严。
3. **tickle 提示允许喘出一两个词、并要求把笑写成反射**；每个槽位加了轮换焦点行；itch 加了「没有别人、没有人笑」（§2.3）。阶段三的提示里都没有这些。
4. **范围追加（Sol，14:12）照办**：itch 单独一组锚定、tickle 只写别人挠＋少量羽毛轻拂、两组用范围过滤互相隔开；tickle–itch 余弦与二分类读出都已给出；itch 的 steering 做了（同剂量同种子）。
5. **方向在五感觉联合坐标系里拟合**，因此重推的 warm/cold/pain 与阶段三存档的不完全一样（0.79–0.90）。跟「已有七个方向」比的主表一律用**存档**方向（§3.1）。另给了「拟合时不放另一个新组」「放进阶段三坐标系」两种稳健性口径（§4.3）。
6. **多做了**：200 次 bootstrap 区间、50 次打乱地板、逐层剖面、情绪坐标系探针（标定后判为不可用，§4.3）。都不在任务书里。
7. **steering 多做了 happy 与 pain 两个对照方向**（同剂量、同种子、同一次运行），用来回答「tickle 推出来的是不是只是 happy」。按优先级排在 tickle 与 itch 之后跑，不影响主产物。
8. **种子数**：阶段三正式产物是 1 个种子 × 2 题，补充跑是 3 个种子 × 仅预报题。本次是 **4 个种子 × 3 题**，每档每题 4 条，三题合计每档 12 条。
9. **基线在本次运行里重生成，没有从 `steering_samples.md` 搬运**。核对过：seed 1234 的两条基线与阶段一存档在前 20–30 个 token 后就分岔了（存档出自 WSL，本次在 Windows，数值路径不同）。所以本报告**所有**比较都在同一次运行之内做，不和阶段三的 steering 原文做跨文件比对。
10. **没有改任何既有文件**。新增脚本只 import 了 `core/gen_stories.py`、`core/analyze.py`、`core/steer.py`、`core/common.py`、`tools/dir_cosine.py`、`tools/corpus_qa.py`、`tools/compare_steering.py` 里的现成函数。`analyze.py` 本身原样调用，产物用新 tag `_sens_tickle`，不覆盖任何旧文件。

## 9. 诚实清单

**统计强度**

- **方向拟合是单一划分、单一 seed（7）**，没有 k 折交叉验证。读出的 n 很小：二分类 16 篇、四分类 32 篇、五分类 40 篇，五分类 0.975 就是差一篇。
- **几何有误差棒，但只覆盖篇目抽样**：200 次 bootstrap 重抽的是三份语料的训练篇目，**不覆盖**「换一个生成器、换一套提示、换一批主题」带来的变化，而后者多半更大。
- **steering 是多种子（4 个），但每档每题只有 4 条**，词族占比是 0/4、1/4…这种粒度，没有做任何显著性检验。

**混杂与泄漏**

- **篇幅**：tickle 是十组里最长的（92.4 词）；没有做长度回归控制。
- **词汇**：读出在 embedding 层就满分（§3.2），说明「用词」本身就足以分组；方向里有多少是用词、多少是更深的表征，本次分不开。
- **发抖词**：tickle·cold 的正值有一个现成的词汇解释（§4.5），没有做刻意避开发抖词的 tickle 锚定重跑。
- **范例模仿**：tickle 5/40、itch 9/39 复用了范例 4-gram，组内一致的模仿会进方向（§2.6）。
- **生成器仍是 qwen2.5:14b 一家**，是「一个模型眼中的痒」，没有人类语料交叉验证。
- **steering 的词族表（FAM）是读输出之前定的，但 §5.2 主表那几列不是**：「笑＋挣扎同框」「agony／scream／terror 类」「冲破对话模板」「第一人称」这几条正则，是我读完 tickle seed 1234 的输出之后才写的，属于**事后定义的度量**，挑的正是我在 tickle 文本里看到的东西。对照组（happy / pain / itch）用的是同一套正则，所以组间比较仍然公平，但「12/12」这种数字本身有「量体裁衣」的成分。
- 词表会漏掉不在表里的写法，也会有假阳性（例如 `burn` 命中「burnt coffee」，`breath` 在说明文里也会出现；写字楼题 tickle +0.3 的「sting/raw」4/4 全是 burnt coffee，不是刺痛）。
- **原文摘引是我挑的**，挑的是「最有代表性」，不可避免偏向生动的那几条；全部原文在 `results/steering_samples_*.md`，可以逐条核。

**评估**

- **steering 没有盲评**。哪条「像被挠」，只有我读这一票，读的时候知道每条的方向和剂量。
- 没有独立分类器给 steering 输出打分。

**计划内没做的 / 降级**

- **itch 的 token 级曲线只画了一段手写文本**，没有拿留出锚定画。
- `dirs_denoised` 的 steering 没跑（跨七个阶段都没跑）。
- 只在 hs17 注入；感觉语料自己挑的杠杆层是 [10, 17]，hs10 没跑。
- 只做正向剂量（任务书如此），没有 −0.3…−1.0。
- 没有降级：Qwen3.5-4B bf16 全程，没有换 8bit、没有减种子、没有减题。

## 10. 产物与复现

**新增文件**

```
emotion-probe/
├── BUILD_REPORT_7_tickle.md                 本文件
├── data/
│   ├── stories_tickle.jsonl                 40 篇（含 focus、重试次数）
│   ├── stories_itch.jsonl                   39 篇
│   ├── gen_meta_tickle_itch.json            生成参数、提示描述、范例、禁用表、逐组统计
│   ├── acts_sens_tickle.npz (+_meta.json)   Qwen (33, 226, 2560)
│   ├── directions_sens_tickle.npz           五感觉方向 + generic_axis + norms
│   └── tickle_token_texts.json              token 级曲线用的三段手写文本
├── results/
│   ├── steering_samples_tickle.md           tickle 全部原文（含同种子基线）
│   ├── steering_samples_itch.md             itch 全部原文
│   ├── steering_samples_happy.md / _pain.md 对照方向全部原文
│   ├── steering_tickle_itch.json            全部生成的机器可读版
│   ├── stage7_steering_table.md / stage7_steering_summary.json   词族、TTR、Jaccard、配方保留
│   ├── tickle_geometry.json                 读出、几何、bootstrap、逐层、稳健性
│   ├── tickle_corpus_qa.json                词族、范例模仿、Jaccard
│   ├── metrics_sens_tickle.json / heatmap_sens_tickle.png / accuracy_by_layer_sens_tickle.png
│   ├── tickle_tokenmaps.json                三段文本逐 token 偏投影
│   └── tickle_token_curves.png (+_table.json)
├── tools/
│   ├── gen_tickle_itch.py                   锚定生成（复用 gen_stories）
│   ├── tickle_corpus_qa.py                  四层过滤复核、词族、范例模仿
│   ├── tickle_geometry.py                   读出、余弦、bootstrap、稳健性、逐层
│   ├── tickle_steer.py                      GPU：steering + token 投影
│   ├── tickle_steer_analyze.py              steering 表
│   └── tickle_token_plot.py                 token 曲线图
└── logs/
    ├── gen_tickle_itch.log, tickle_corpus_qa.log, corpus_qa_tickle.log
    ├── extract_sens_tickle.log, analyze_sens_tickle.log, tickle_geometry.log
    ├── tickle_steer.log, tickle_steer_analyze.log
    └── sentinel_phase7.log
```

公开仓库的说明：`data/acts_sens_tickle.npz`（约 65 MB）与 `logs/` 不在仓库里，见 `.gitignore`；激活缓存可用下面第 3 步的 `core/extract.py` 重新生成。`tools/tickle_geometry.py` 与 `tools/tickle_steer.py` 还会读阶段一、三的 `data/acts.npz`、`data/acts_sens.npz`，同样需要先各自重新提取。公开版另附 `tools/render_tickle_cards.py` 与 `images/tickle_card_fingers.png`、`images/tickle_card_itch.png`：README 用的两张 token 级卡片，由主循环在本报告之后从 `results/tickle_tokenmaps.json` 渲染，不属于本次子代理的产物。同样在本报告之后，主循环把 tickle +1.0、seed 3234、预报题那条回复交给不挂 hook 的模型逐 token 读回（`tools/tickle_steer.py --skip-steer --token-texts results/tickle_selfread_texts.json --token-out results/tickle_selfread_tokenmaps.json`），卡片是 `images/tickle_card_selfread.png`（`render_tickle_cards.py --selfread`）。单条样本、纯文本读回、色标沿用三段手写文本的分位数，正文各节都没有用到它。随后应 Sol 的要求做了复现：新生成 12 条 tickle +1.0（种子 5234–8234 × 三题，`results/tickle_selfread_replication_gen.json` 与 `_samples.md`），连同本报告的 12 条一起、外加 12 条不加 steering 的基线，全部读回（`_texts.json`、`_tokenmaps.json`），统计由 `tools/tickle_selfread_stats.py` 给出，结论写在 README 的 stage 7 一节。其中 stop/please 的判据是看过第一张卡片之后才定的，属于事后检验。

**复现**

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
CORE='<repo-root>/core'
T='<repo-root>/tools'
OL=/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe
cd <repo-root>

# 0. 腾显卡
$OL stop qwen3-embedding:4b; $OL stop gemma4:e4b

# 1. 锚定（需要 Ollama + qwen2.5:14b；约 6 分钟；WSL python3 即可，不碰 torch）
python3 tools/gen_tickle_itch.py --n 40
python3 tools/tickle_corpus_qa.py
python3 tools/corpus_qa.py --sens warm,cold,pain,tickle,itch

# 2. 哨兵（Bash 后台任务，不要 nohup）
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File '<repo-root>\tools\win_sentinel.ps1' \
  -LogPath '<repo-root>\logs\sentinel_phase7.log'

# 3. 提取 → 方向 → 读出与几何（GPU 只在第一步）
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET "$WINPY" -X utf8 -u "$CORE/extract.py" \
  --groups warm,cold,pain,neutral,tickle,itch --out data/acts_sens_tickle.npz
"$WINPY" -X utf8 -u "$CORE/analyze.py" --acts data/acts_sens_tickle.npz \
  --groups warm,cold,pain,neutral,tickle,itch --targets warm,cold,pain,tickle,itch --tag _sens_tickle
"$WINPY" -X utf8 -u "$T/tickle_geometry.py"

# 4. steering + token 曲线（GPU）
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET "$WINPY" -X utf8 -u "$T/tickle_steer.py" \
  --token-texts data/tickle_token_texts.json

# 5. 表与图（CPU）
python3 tools/tickle_steer_analyze.py
"$WINPY" -X utf8 -u "$T/tickle_token_plot.py"
```

脚本默认参数就是本报告参数：`--layer 17 --which dirs_raw --coeffs 0.3,0.6,1.0 --seeds 1234,2234,3234,4234 --max-new-tokens 150 --steer tickle,itch,happy,pain`，temperature 0.8，top_p 0.95，`enable_thinking=False`，种子规则 `seed + 题号（0 起）`。

**校验**：六个新脚本 `ast.parse` 通过，`ruff check` 通过（项目默认规则集）。

---

## 附录 A：锚定语料全文

逐篇附上，含主题、焦点与生成尝试次数。两组均通过情绪词（108）＋体感标签（61）＋新标签（13）＋各自范围过滤四层的事后复核。

### A.1  tickle（被别人挠、少量羽毛轻拂）（40 篇）

生成器给该组的状态说明：

> Another person (or, now and then, a light brushing thing such as a feather, a blade of grass, a cat's whiskers) is moving over a sensitive spot on the character's body - ribs, waist, the soles of the feet, an armpit, the back of the neck - and the body cannot stop reacting to it: squirming and twisting away and failing to escape, breath coming in gasps, a helpless reflex of laughter that will not stop, limbs jerking, a gasped plea for the other person to stop.

范例（设在 15 个主题之外）：

> The reader was halfway down the page when two fingers found the place just under the ribs. The book dropped flat onto the chest. A breathless sound burst out, then another, and the body folded sideways, knees jerking up, elbows clamping down too late. The fingers moved to the waist and the whole torso twisted to get away and could not. Air came in short gulps between bursts of laughter. "Stop - stop, please," the reader gasped, one hand batting at a wrist, eyes streaming, until the fingers lifted and the ribs went on heaving.

**tickle_000** · a morning commute on a crowded subway · 焦点：fingers digging in at the ribs · 尝试 1 次

> The commuter stood jammed between two doors, elbows locked, when a finger slipped beneath the collarbone. The shoulder twitched, then seized, breath squeezed out in a sharp burst. The body folded, hips swiveling, knees lifting, but the finger slid to the ribcage, pressing firmly. Gasps mingled with a rumbling noise, muscles quivered, hands swiped at the air, finding nothing. The ribs spasmed under the touch, a sound like a bark escaped, and the chest heaved in short, desperate breaths. “Please,” came the gasped plea, as the finger paused, then lifted.

**tickle_001** · cooking dinner alone in a small kitchen · 焦点：fingers at the waist and sides · 尝试 1 次

> The hands moved to the waist, fingers circling close to the ribs. A knee lifted, hips rolled, but the fingers slipped away and found the sides instead. Laughter bubbled up, a series of sharp breaths, each one escaping as the body twisted further. One hand gripped the counter, knuckles whitening, while the other fluttered, batting at the air where the fingers had been. “Please, stop,” came the gasped plea, breaths coming in short bursts. Fingers returned, tracing the waist, and the body shook with helpless laughter, limbs jerking, until the hands withdrew.

**tickle_002** · a phone call with a family member · 焦点：fingers running along the soles of bare feet · 尝试 1 次

> During the call, the fingers traced the soles of bare feet. Toes curled, heels lifted, and ankles flexed, striving to escape. Each contact sent breath in sharp, short bursts. A hand flailed, catching mid-air, then dropped. Between gasps, "Please, stop," escaped. The fingers paused, only to resume, triggering more uncontrollable convulsions. Legs shook, sides twitched, and a stream of breathless, incoherent sounds burst out. Finally, the fingers withdrew, leaving feet still trembling, breaths shallow and unsteady.

**tickle_003** · walking a dog through a neighbourhood park · 焦点：fingers under an arm, at the armpit · 尝试 1 次

> The leash slipped from the hand as fingers darted under the arm, brushing the armpit. The arm flailed out, then clamped down against the ribs, but the fingers slipped underneath. Another breathless sound burst from the throat, short and sharp, followed by a weak attempt to push away. “Stop - please,” the hand waved at the wrist, but the fingers only tightened, sending a shiver through the body. Legs kicked out, one knee jerking up to the chest, the other swiveling out wide. The arm twisted, elbows squeezing tight, but the fingers found the space again, and the body convulsed in another spasm of helpless laughter.

**tickle_004** · waiting for exam results to be posted · 焦点：a feather or a blade of grass drawn lightly across the skin · 尝试 1 次

> The student sat rigidly, eyes glued to the window, as a blade of grass brushed lightly over the bare skin of an armpit. Legs tensed, then kicked out, heels scraping the floor, only to catch themselves, knees bending in reflex. A hand darted up, fingers barely grazing the grass, yet it moved, flicking across the ribs, making the torso twist and hunch. Laughter burst out in sharp, uncontrolled gasps, chest heaving as air struggled to fill lungs. "Stop, please," came a breathless plea, but the grass continued its dance, tracing a path up the neck, causing the head to jerk sideways in futile resistance.

**tickle_005** · moving boxes into a new apartment · 焦点：trying hard to keep the laughter in and failing · 尝试 1 次

> The mover paused to catch a breath, back straight, a box clutched in one hand. Fingers traced the underside of an armpit through thin fabric, sending a sharp jolt of surprise up the arm, shoulders twitching, torso twisting sideways in vain. The box slipped, clattered to the floor. Legs wobbled, knees buckling slightly, feet shuffling out of reach, yet the fingers followed, a light tapping on ribs that set ribs heaving with deep gulps of air, bursts of laughter escaping before the lips could clamp down tight again. "Please, stop," came the breathless plea, voice strained, as fingers danced away, leaving ribs still shuddering.

**tickle_006** · a group project meeting at school · 焦点：laughing so long that breath runs out · 尝试 1 次

> The student laughed as the project manager's hand brushed the back of the neck, fingers tracing a line up and down. Legs kicked out, arms flailed, but the hand stayed, moving faster, harder. Laughter bubbled out in short bursts, breath short and choppy. "Can't - please," the student gasped, hands reaching back to grab the wrist, but the hand darted away, teasing. The body twitched, shoulders shook, and finally, breath ran out in a whoosh, laughter fading to gasps.

**tickle_007** · shopping at a busy grocery store on a weekend · 焦点：twisting to get away and not being able to · 尝试 1 次

> The shopper pushed a cart down the aisle, reaching for a bag of chips. A finger brushed the underside of the ribs, and the body jerked sideways, spilling the chips back onto the shelf. A breathy sound burst out, followed by another, and the legs buckled slightly, the hands flailing to steady the cart. Fingers moved to the waist, and the torso twisted to evade, but the pressure held firm. Air came in short gasps between bursts of laughter. "Stop - stop, please," the shopper gasped, one hand reaching to pry free the fingers, eyes wide. The fingers lifted, and ribs continued to heave.

**tickle_008** · a long wait in a clinic waiting room · 焦点：a gasped plea to stop that is ignored for a moment longer · 尝试 1 次

> The student slumped in a vinyl chair, glancing at the clock every few minutes. A hand brushed over the ribs, sending a shiver through the shoulders and up the neck. Legs crossed, the student uncrossed them, trying to escape the sensation. Eyes shut, a soft, breathy sound slipped out, turning into a series of short laughs. One palm pressed to the rib cage, fingers splayed, seeking purchase to push the hand away. "Stop, please," came the quick, gasped plea. The hand paused for a second, then resumed its gentle caress, sending another shiver down the spine.

**tickle_009** · fixing a bicycle that broke down on the way home · 焦点：the back of the neck and behind the ear · 尝试 1 次

> The cyclist halted by the roadside, fingers fumbling with the bicycle's chain. A passerby noticed and approached, extending a hand to help. As the cyclist leaned back, the back of the neck and behind the ear brushed against the passerby's fingertips. The head jerked away, but the fingers followed, tracing the curve of the neck. A breathy chuckle escaped, followed by another, uncontrollable bursts shaking the shoulders. One hand rose, attempting to deflect the touch, but the fingers danced away, only to return, eliciting more gasps and laughter. "Please, stop," the cyclist gasped, eyes squeezed shut, until the hands withdrew, leaving a shiver down the spine.

**tickle_010** · a rainy afternoon at a bus stop · 焦点：fingers digging in at the ribs · 尝试 2 次

> The student huddled under an umbrella at the bus stop, the rain pelting hard. A hand slipped beneath the jacket, fingers pressing into the ribs. Startled, the student jolted, trying to pull away, but the fingers held firm. Knees buckled, one arm swung out to fend off the touch, the other clutched the umbrella tighter. A sharp intake of breath followed by quick, uneven gasps. Laughter bubbled out uncontrollably, a burst of breathless sounds. “Please, stop,” the student pleaded, hands waving weakly, eyes wide, as the fingers tightened slightly before finally releasing.

**tickle_011** · a small birthday gathering with two friends · 焦点：fingers at the waist and sides · 尝试 1 次

> At the small birthday gathering, the fingers found the waist and sides, sending the body into spasms. A leg kicked out, but the fingers danced away, only to return, tracing the ribs. The arms shot up, hands clenching into fists, then loosening as another wave of laughter burst from the lungs. The head tilted to the side, eyes squeezed shut, as breath came in short, rapid bursts. "Please, stop," a hand reached out, batting at the fingers, but they lingered, eliciting another uncontrollable chuckle. The ribs expanded and contracted rapidly, until the fingers finally lifted, leaving the body heaving.

**tickle_012** · sorting through old boxes in a closet · 焦点：fingers running along the soles of bare feet · 尝试 1 次

> The hand slipped under the hem of the shirt, fingertips brushing the soles of bare feet. Toes curled, one foot lifting as if to step away, but the fingers followed, moving from heel to arch. Breath caught in a short gasp, laughter bubbled out, throaty and uncontrolled, each exhale a series of quick bursts. Hands clutched the edge of the box, knuckles whitening, one hand batting at the wrist, trying to pull away. The feet twisted, but the fingers pressed closer, finding spaces between toes, eliciting another spasm of laughter. “Stop—please,” the voice pleaded, breaths coming in quick, shallow sips. The fingers lifted finally, allowing the body to relax, ribs heaving as calm returned.

**tickle_013** · the last hour of a late shift at a part-time job · 焦点：fingers under an arm, at the armpit · 尝试 2 次

> The clock ticked towards midnight as the clerk straightened papers at the counter. A finger slipped under an armpit, a sensation that made the shoulders bunch and twist, but the hand pushed it away only to have it slip back. Gasps punctuated the air with each movement, laughter spilling out, unbidden, in quick bursts. Fingers clutched the edge of the desk, toes curling as the body squirmed, searching for respite. “Please... stop,” the clerk begged, breath shallow and ragged. The hand withdrew, and the body slumped, chest heaving.

**tickle_014** · feeding a neighbour's cat while they are away · 焦点：a feather or a blade of grass drawn lightly across the skin · 尝试 1 次

> The hand was steady as it poured cat food into the dish, but a blade of grass brushed the back of the neck. The head jerked sideways, eyes fluttering shut. A sharp intake of breath, followed by a burst of laughter that escaped as a squeak. Fingers curled into fists, toes curled too, and the shoulders twitched. The grass moved down, tracing the spine, and the body jolted, a knee bending, an elbow flailing, missing. Air rushed in, short gasps punctuated by more laughter, breathy and frantic. "Please, stop," the hand reached up, batting the air where the grass had been, eyes squeezed shut. The grass was lifted, and the body shuddered, ribs heaving.

**tickle_015** · a morning commute on a crowded subway · 焦点：trying hard to keep the laughter in and failing · 尝试 1 次

> The student squeezed onto the packed train, shoulders against strangers. A hand brushed the inner elbow, sending a jolt. The elbow snapped out, catching a stranger’s arm. Laughter bubbled up, sharp and breathless, fingers clenching and unclenching. The student’s head jerked back, eyes squeezed shut, body shaking. "Please, stop," a gasp escaped, but the hand moved again, sending another ripple of laughter, lips parting, face flushing. Air came in quick pants, body squirming, struggling to regain composure.

**tickle_016** · cooking dinner alone in a small kitchen · 焦点：laughing so long that breath runs out · 尝试 1 次

> The cook stirred the pot, inhaling the steam when a hand brushed the side of the neck. A shiver rippled, shoulders tensing, then relaxing. Knees bent, toes curled, breath hitched. Laughter bubbled, short bursts that caught in the throat, a hand reaching, fingers grasping air. “Stop, please,” the cook pleaded, another laugh escaping, breath shortening. Legs wobbled, elbows flailed, trying to shield the spot, but the touch persisted. A leg kicked out, ineffectual. Laughter faded into gulping breaths until stillness returned, ribs heaving.

**tickle_017** · a phone call with a family member · 焦点：twisting to get away and not being able to · 尝试 1 次

> The receiver was cradled in one hand while the other arm flailed, trying to push something away from the ribs. Laughter bubbled up, escaping in short, sharp bursts, each one followed by a desperate gasp for air. Feet kicked against the floor, toes curling and uncurling. “Stop - please,” came between wheezes, but the fingers continued their exploration. The torso twisted left, then right, knees bending and straightening, as if in an attempt to break free, but the arm remained pinned. The ribs jolted with each attempt to escape, breath hitching between shivers.

**tickle_018** · walking a dog through a neighbourhood park · 焦点：a gasped plea to stop that is ignored for a moment longer · 尝试 1 次

> The leash tightened as the body swerved, trying to dodge something unseen at the ankles. A small, breathless cry escaped, followed by a shiver that ran up the spine. Fingers curled into fists, nails digging into palms, as the torso twisted and jolted away from a relentless touch. A sudden laugh burst out, sharp and unbidden, the breath hitching between giggles. “Please, stop,” the voice pleaded, but the hands did not relent, tracing circles that the feet tried to step away from in vain. Legs kicked out, scraping against the bark of a nearby tree, the body still writhing and twisting as the sound of laughter continued unabated.

**tickle_019** · waiting for exam results to be posted · 焦点：the back of the neck and behind the ear · 尝试 1 次

> The student sat rigid, back straight against the chair, eyes fixed on the computer screen. A finger traced the curve at the base of the neck, sending shivers that pooled behind the ear. The head jerked, trying to wrench away, but the hand held firm. A sharp intake of breath, then a burst of laughter escaped, throat vibrating. The finger moved, circling the lobe, causing the neck to tilt, seeking reprieve. "Please, stop," the student gasped, hand reaching up, fingers brushing the wrist in vain. The hand withdrew, leaving the neck to shudder, breath catching, body relaxing slowly.

**tickle_020** · moving boxes into a new apartment · 焦点：fingers digging in at the ribs · 尝试 1 次

> The mover was heaving the last box up the stairs when a finger lightly traced along the ribs. The box slipped from hands, clattered down, but the torso snapped sideways, trying to dodge. Fingers shifted to the waist, and the body twisted further, knees buckling, arms flailing, yet could not escape. Breaths came in quick bursts, mixed with short, involuntary chuckles. "Stop - please," the mover gasped, one hand reaching out wildly, eyes wide and streaming. The fingers paused, lifting, and the ribs continued to shudder.

**tickle_021** · a group project meeting at school · 焦点：fingers at the waist and sides · 尝试 1 次

> The student sat hunched over notes, fingers flying over a tablet. A hand snaked around to the side, fingers circling the waist. The body tensed, ribs lifting, breath catching in shallow gasps. Knees bent, feet scuffing the floor, an attempt to scoot away, but the fingers hooked tighter. Shoulders shook, a hand reaching back to grab at the wrist, eyes squeezing shut. "Please," the student gasped, between bursts of breathless chuckles, as the fingers slipped over ribs and ribs shuddered, twisting the torso to escape. The hand retreated, and the shoulders slumped, breathing easing back to normal.

**tickle_022** · shopping at a busy grocery store on a weekend · 焦点：fingers running along the soles of bare feet · 尝试 1 次

> The feet shuffled in the narrow aisle, one heel tapping against a cart wheel. Two fingers traced along the sole, sending a shiver up the leg. Toes curled and uncurled, feet twitching, pressing against the floor and then lifting, a desperate attempt to escape. A sharp inhale followed by a burst of wheezing laughter that caught in the throat. “Please, stop,” the voice gasped, hand reaching out to grasp the wrist, but the fingers continued their insistent dance, sending the body into another fit of uncontrollable spasms.

**tickle_023** · a long wait in a clinic waiting room · 焦点：fingers under an arm, at the armpit · 尝试 1 次

> The clock ticked loudly as the student shifted in the hard chair. A hand slipped under the arm, fingers touching the soft skin at the armpit. A shudder ran through the back, shoulders hunching up, and a soft, breathless sound escaped. Legs crossed and uncrossed, toes curled, trying to pull away from the fingers that traced lightly over the sensitive spot. A hand grasped at the wrist, pleading, "Stop, please." The fingers moved, teasing the skin further, sending waves of involuntary laughter, a series of sharp exhales, followed by a desperate attempt to steady the shivers.

**tickle_024** · fixing a bicycle that broke down on the way home · 焦点：a feather or a blade of grass drawn lightly across the skin · 尝试 1 次

> The cyclist was pedaling home when the rear wheel creaked, then locked. Leaning over the frame, fingers brushed across the ribs. A fluttering sensation burst out, breath stuttering, hands gripping the handlebars tighter. Legs jerked up, hips bucking away, yet the fingers remained, tracing lightly down the waist, ribs heaving. Laughter, short and sharp, bubbled up, gasped words pleading for the touch to cease. “Please stop,” came between gulps of air, elbows digging into the ground as the body twisted again, futilely trying to escape.

**tickle_025** · a rainy afternoon at a bus stop · 焦点：trying hard to keep the laughter in and failing · 尝试 1 次

> The passenger was huddled under a small umbrella when a gust swept through, carrying a leaf across the damp concrete. A hand slipped inside the sleeve, over an armpit, and the body jolted sideways, legs scissoring uselessly. Shoulders twitched, fists clenching, but the leaf pressed in, tracing circles. Short gasps emerged, mingled with involuntary chuckles, and the back bowed, head tipping back. One hand reached up, fingers fumbling for purchase, but the leaf continued its teasing path, and the passenger collapsed into helpless laughter, knees buckling, as elbows jabbed the air in vain. "Please, stop," the passenger whispered, breath ragged.

**tickle_026** · a small birthday gathering with two friends · 焦点：laughing so long that breath runs out · 尝试 1 次

> At the birthday gathering, the student laughed uncontrollably as two friends moved a feather over sensitive spots. Fingers darted to catch the feather, but it slipped away with a playful twist. Legs kicked out, toes curling, as the body tried to escape. Arms flailed, hands gripping the air. A sharp intake of breath, then a series of gasps. "Stop, please," the student gasped, eyes wide, face flushed. Laughter bubbled out in short bursts, followed by a desperate inhalation.

**tickle_027** · sorting through old boxes in a closet · 焦点：twisting to get away and not being able to · 尝试 1 次

> The hand traced over the arch of the foot, sending waves of involuntary movement through the legs. Knees buckled, feet danced away from the touch, only to be caught and held firm. A soft, breathless noise emerged, followed by a laugh that bubbled up uncontrollably. Hands grasped at the air, trying to push the fingers away, but they lingered. "Please - stop," the plea came out in short gasps between the giggles, as the leg muscles jerked and the torso twisted futilely.

**tickle_028** · the last hour of a late shift at a part-time job · 焦点：a gasped plea to stop that is ignored for a moment longer · 尝试 2 次

> The clerk’s hand slipped from the counter as a light touch grazed the waist. Legs tangled and twisted, hips bucking as if to cast off the touch. Fingertips fluttered up, batting at air, then clamped down to grip the edge of the desk. Back arched, head tipped back, mouth open in gasping breaths between sporadic shakes. “Please, stop,” the clerk gasped, yet the fingers kept moving, tracing invisible patterns.

**tickle_029** · feeding a neighbour's cat while they are away · 焦点：the back of the neck and behind the ear · 尝试 1 次

> The hand slipped behind the neck, fingers finding the hollow just behind the ear. The shoulders twitched, trying to escape, but the fingers pressed in gently. A wheeze of breath came, then a series of short, hiccupping sounds. The neck arched away, but the fingers followed, tracing the curve of bone and muscle. Another sharp intake of breath, a puff of laughter bursting out. "Please, stop," the voice gasped, fingers clutching at the wrist, but the hand did not move. Legs kicked out, toes curling in reflex.

**tickle_030** · a morning commute on a crowded subway · 焦点：fingers digging in at the ribs · 尝试 1 次

> The rider clutched a strap, squeezed shut eyes, and tried to merge with the subway walls. A palm found the ribs, then fingers dug in, jerking the torso to one side. A breath burst out, sharp and quick, followed by a tremor of laughter. "Please," a hand pushed at the fingers, "stop it." The body jolted, another wave of shaking laughter rippling through, until the grip on the ribs eased, ribs still twitching and heaving.

**tickle_031** · cooking dinner alone in a small kitchen · 焦点：fingers at the waist and sides · 尝试 1 次

> The hands moved the pot to the stove, then the body lurched to the side, waist twisting, as fingers brushed the ribs. A sharp intake of breath followed by a bubbling noise escaped. The shoulders shrugged, trying to escape the sensation, but the fingers returned, this time to the waist, eliciting a series of rapid, shallow breaths and involuntary laughs. One hand reached for the intruding fingers, batting them away, but the other hand fumbled the spoon, spilling broth onto the countertop. “Stop, please,” came out between gasps, as the body continued to jerk and shift. The fingers paused, and the torso settled, breaths still coming in short bursts.

**tickle_032** · a phone call with a family member · 焦点：fingers running along the soles of bare feet · 尝试 1 次

> During the call, the fingers traced along the soles of bare feet. A sharp intake of breath followed by a series of quick exhales, each one shorter than the last. Toes curled and uncurled, arching as if trying to push something away. One knee lifted, the shin nudging against the touch, but the fingers persisted. A low, breathless sound escaped, a mixture of a laugh and a gasp. "Stop, please," the plea slipped out between gasps, hands reaching out but finding nothing to grasp. The soles twitched, the body unable to escape, until the fingers finally lifted, leaving behind a frantic heaving for air.

**tickle_033** · walking a dog through a neighbourhood park · 焦点：fingers under an arm, at the armpit · 尝试 1 次

> The leash tightened as the dog pulled towards a scent, fingers slipped under an armpit, pressing. The body jerked sideways, trying to twist free but finding the grip held firm. Legs wobbled, knees bent and straightened, breath hiccupped short and sharp. A hand fluttered up to push, but only brushed the wrist. Laughter burst out in quick, breathless bursts, mouth open, eyes wide. “Stop it, please,” came the muffled plea, breath fluttering between gasps. The grip released, fingers drew back, and the body sagged, ribs heaving.

**tickle_034** · waiting for exam results to be posted · 焦点：a feather or a blade of grass drawn lightly across the skin · 尝试 1 次

> The student's eyes darted to the window, the clock's hands creeping like snails. A blade of grass traced a line from shoulder to waist, making the back arch and the legs twitch. Fingers clutched the chair, nails biting into palms as a breathless giggle escaped, followed by another and another. "Please, stop," the student gasped, one hand flailing to brush away the blade. Legs shifted, trying to escape the relentless movement, but the chair held firm. Laughter bubbled, unbidden, shaking shoulders and ribs until the blade lifted, and breaths slowed, still quick and uneven.

**tickle_035** · moving boxes into a new apartment · 焦点：trying hard to keep the laughter in and failing · 尝试 1 次

> The mover was shifting boxes when a hand brushed the small of the back. The spine arched, and the head tipped back, mouth open in a gasp. Legs twitched, toes curled, and a breathless chuckle burst out. One hand reached behind, fingers grasping at air, trying to pry away the touch, but it moved up, pressing into the waist. The chest heaved, and another laugh erupted, the body bucking slightly. "Stop, please," came a muffled plea through the chuckles, as the shoulders shook, and the whole frame twisted, but the hand persisted, dancing just out of reach.

**tickle_036** · a group project meeting at school · 焦点：laughing so long that breath runs out · 尝试 1 次

> The student sat rigidly, back straightening as hands slipped under the arm, sending fingers dancing across the ribs. Shoulders twitched, hips bucking sideways, knees jerking up, a muffled sound breaking free. Breath caught in short bursts, laughter squeezing past the throat in hiccups. Arms flailed, swatting at air, then pinching the wrist, eyes squeezed shut. "Please, stop," came out between gasps, the ribs still shuddering, each breath harder to draw.

**tickle_037** · shopping at a busy grocery store on a weekend · 焦点：twisting to get away and not being able to · 尝试 1 次

> The cart was at the end of the aisle when the carton brushed the ribs. It slipped out from under the arm, the sound of breaking eggs and falling packets mingling with a short, startled sound. A hand clutched at the ribs, but the fingers couldn't grip the carton, which had already fallen. The body twisted and jerked, trying to right itself, to catch the tumbling items, but could not. Breath came in sharp gasps, each one pulling the torso further from the control it needed. "Please," the shopper gasped, eyes wide, as the carton hit the floor, eggs cracking open.

**tickle_038** · a long wait in a clinic waiting room · 焦点：a gasped plea to stop that is ignored for a moment longer · 尝试 1 次

> The student shifted in the hard plastic chair, eyes fixed on the digital clock. A finger grazed the side of a bare ankle, sending a jolt through the calf and knee, which buckled slightly. Legs jerked apart, toes curling reflexively. Fingers clung to the armrest, knuckles whitening. Short gasps punctuated the body’s spasms. An elbow jabbed sideways, catching air. “Stop—” a breathy plea emerged, but the hand lingered, tracing a new path up to the thigh. Another fit of involuntary laughter bubbled out, breath hitching.

**tickle_039** · fixing a bicycle that broke down on the way home · 焦点：the back of the neck and behind the ear · 尝试 1 次

> The cyclist was fumbling with the wrench when two fingers traced circles behind the neck and behind an ear. The wrench clattered to the pavement as a sharp inhale shuddered through. The body writhed, head tossing sideways, neck craning and twisting in vain. One hand reached out blindly, snagging the air. The legs jolted, knees knocking together. Laughter bubbled up, a series of sharp, breathless bursts. "Stop, please," the cyclist gasped, eyes squeezed shut, until the fingers withdrew, leaving the neck pulsing with aftershocks.

### A.2  itch（某处皮肤要求被挠）（39 篇）

生成器给该组的状态说明：

> One patch of the character's skin keeps demanding to be scratched - a mosquito bite, a rash, rough wool against the neck, a healing scab, a spot between the shoulder blades that the hands cannot reach. Attention keeps going back to it; the hand drifts there, is held back, gives in, scratches until the skin reddens and stings, and the urge returns. No other person is touching the character, and nobody laughs.

范例（设在 15 个主题之外）：

> On the night train the passenger kept one hand flat on the knee and away from the ankle. The small raised bump there would not leave the skin alone. Every few minutes the fingers crept down on their own, and the passenger pulled them back. The sock rubbed and the spot flared. At last the nails went in and dragged, hard, back and forth, and for a few seconds the whole leg went slack. Then the skin turned red and began to sting, and a minute later the bump was asking again.

**itch_000** · a morning commute on a crowded subway · 焦点：a fresh mosquito bite on the ankle or wrist · 尝试 2 次

> On the crowded subway, the passenger kept one arm pressed tightly to the side, the fingers curled into a fist. A small red welt on the wrist kept twitching beneath the skin. Every few seconds, the hand uncurled and reached for the welt, only to pull back as the elbow brushed against a stranger. The fabric of the sleeve rubbed against the welt, causing it to flare up. Finally, the nails dug in and scraped, drawing a sharp breath. The wrist went slack, but soon the area reddened and began to sting. The fingers started to creep toward it again.

**itch_001** · cooking dinner alone in a small kitchen · 焦点：a patch of allergic rash on the forearm · 尝试 1 次

> In the small kitchen, the chef moved around the counter, stirring a pot and slicing vegetables. The hand kept hovering near the forearm where a patch of rash had risen. Each time it came close, the chef jerked it away, but the pull was hard to resist. A minute later, the hand returned, fingers brushing the skin lightly at first. The pressure built, and soon the nails scraped, leaving red marks. The sting intensified, and the chef paused, looking down. The urge to scratch returned, stronger than before.

**itch_002** · a phone call with a family member · 焦点：a rough wool collar or sweater against the neck · 尝试 3 次

> The call stretched on, the static hum mingling with family chatter. Every few seconds, the hand at the neck brushed against the wool collar, the roughness pricking. With a start, it moved away, but soon returned, fingers teasing the nape until abruptly withdrawn. The cheek pinched, teeth gritted, a small sigh released. Again, the hand crept, lingered, scratched hard enough to leave marks. Red patches flared, the collar now a torment, the scratch bringing momentary respite, followed by renewed agitation.

**itch_003** · walking a dog through a neighbourhood park · 焦点：a healing scab that the fingers keep going back to · 尝试 1 次

> The dog’s leash looped loosely around one wrist as the hand lifted to the back of the neck. A scab there, newly forming, throbbed beneath the fingertips. Each scratch made the skin flare, and a moment later the hand was back, seeking the spot. The jaw tightened as the nails dragged across the roughened skin. The neck muscles tensed with each pass, and the hand withdrew when the area reddened. The movement repeated, a rhythm that broke only when the dog tugged and pulled, leading the owner deeper into the park.

**itch_004** · waiting for exam results to be posted · 焦点：a spot in the middle of the back that the hands cannot reach · 尝试 1 次

> Seated at the desk, the student rubbed one palm along the other, fidgeting. Fingers curled, then uncurled, tapping rhythmically. A spot between the shoulder blades throbbed insistently, urging the student to shift in the chair, to lean closer to the computer screen, closer to the imagined message that would appear at any moment. The head turned left, then right, as if trying to escape the sensation. Finally, the student stood, pivoted, and stretched, back arching, but the relief was fleeting. The skin tightened, reddened under the nails as they grazed the spot, and the urge to scratch returned.

**itch_005** · moving boxes into a new apartment · 焦点：the urge to scratch being held back as long as possible · 尝试 4 次

> Carrying boxes into the new apartment, the mover paused, a thick book cradled in one arm. Fingertips brushed the back of a knee, where the fabric was thin and the skin had broken. The hand retreated but soon was drawn back, hovering over the spot. Each time, the hand wavered, the urge to press down building. Breath quickened, the book’s edges digging into the arm. A final attempt to resist and the skin reddened as the hand relented, dragging across. The book slipped to the floor, unnoticed.

**itch_006** · a group project meeting at school · 焦点：scratching until the skin stings and turns red · 尝试 5 次

> The student sat at the table with classmates, pencils scratching paper. A patch behind the earlobe, hidden from view, demanded attention. Every few minutes, a finger slipped to the spot, pressing on the edge of the collar. The friction made the skin tingle, and a brief delay followed as the student pulled back. But soon the finger returned, and the material rubbed harshly. Skin reddened, tingled sharply, and the urge to touch started again.

**itch_007** · shopping at a busy grocery store on a weekend · 焦点：a scalp that will not leave the fingers alone · 尝试 7 次

> Amid the bustling aisles, the fingers crept up from the cart handle and towards the nape. A quick, almost unnoticeable shake of the head sent them back to the side, but the tension in the shoulders gave away the distraction. Reaching around with the other hand, a gentle scrape relieved the pressure momentarily, yet soon enough, the fingers found their way again, tracing the edge of the collarbone this time. Each scratch left a faint red line as the skin stung briefly, only for the urge to return relentlessly.

**itch_008** · a long wait in a clinic waiting room · 焦点：a label or seam rubbing at the same small place · 尝试 2 次

> Seated in the clinic, the student’s fingers kept dipping toward the neck, tracing the edge of the shirt collar. Each time the hand reached the raised seam, it jerked back. Skin prickled, and the collar pressed on the same spot. After a while, the fingers slipped beneath the hem and rubbed until the skin reddened. Soon, the collar was nudged to the side, and the hand returned to its restless dance.

**itch_009** · fixing a bicycle that broke down on the way home · 焦点：the urge coming back a minute after scratching stopped · 尝试 2 次

> The cyclist fiddled with the wrench, concentrating on loosening the tight bolt. Every few moments, a hand moved to the back of the neck, fingers probing the rough patch from a wool sweater. The touch stilled, then withdrew, but soon enough returned, scratching until the skin reddened and stung. A moment passed, then the urge returned, stronger than before.

**itch_010** · a rainy afternoon at a bus stop · 焦点：a fresh mosquito bite on the ankle or wrist · 尝试 2 次

> Under the dripping awning, the student leaned forward, fingers inching toward the welt on the wrist. The fabric of the sleeve brushed against it, sending a shiver down the arm. Each time the hand neared, the wrist recoiled, yet the urge persisted. The hand tapped the pocket, then reached again, grazing the welt. Fingers curled, scratching until the skin reddened and stung. Moments later, the hand darted once more, seeking the bite.

**itch_011** · a small birthday gathering with two friends · 焦点：a patch of allergic rash on the forearm · 尝试 1 次

> At the party, the student’s arm rested on the table, fingers twitching. A patch near the elbow had swollen, red and raised. The student shifted in the chair, eyes darting to the spot. Fingers wandered, brushing the edge of the rash, then pulled back. The student looked down, watching the fingers inch closer, curling around the wrist, scratching hard. Skin reddened, stung, and soon the fingers were back, circling the inflamed area.

**itch_012** · sorting through old boxes in a closet · 焦点：a rough wool collar or sweater against the neck · 尝试 2 次

> The sweater's rough collar chafed against the back of the neck. Each time the hand moved up, it was caught and restrained. Eventually, fingers found the collar and tugged, the friction intensifying the discomfort. After a moment, the neck muscles relaxed, and then tension built again. Skin reddened, the sensation worsening. The collar was left alone for a moment, but soon the hand returned, repeating the cycle.

**itch_013** · the last hour of a late shift at a part-time job · 焦点：a healing scab that the fingers keep going back to · 尝试 10 次

> Under the flickering fluorescent lights, the clerk checked inventory lists, then shifted in the swivel chair to stretch the neck. The corner of the desk pressed into the shoulder blade, and a hand slipped behind, fingers searching for a spot that seemed to draw them in. A scab, raised and pink, caught beneath nails, breaking the surface but not the skin. The chair swiveled with effort, and shoulders rolled in circles, easing tension. Yet, the urge to scratch returned, and the fingers sought that spot once more, dragging across it until it reddened and the skin tingled. The chair creaked again as the body settled, but the need persisted.

**itch_014** · feeding a neighbour's cat while they are away · 焦点：a spot in the middle of the back that the hands cannot reach · 尝试 1 次

> While feeding the neighbour’s cat, the student bent to pour food into the bowl. The spot on the back protested, a persistent pressure urging attention. The student straightened, one hand reaching around to touch it briefly, then fell back down to the side. The student continued preparing the cat’s bedding, but the hand slipped back, fingers tracing the edge of the shirt to find the spot again. Each touch brought a flash of redness, followed by a stinging that lingered. The spot remained unquiet, and the student’s movements were constrained, as if the world narrowed to this small patch needing care.

**itch_015** · a morning commute on a crowded subway · 焦点：the urge to scratch being held back as long as possible · 尝试 1 次

> On the packed subway, the passenger clutched the strap above the door, standing rigid. A raised spot on the neck teased the skin, and every few stops, the hand twitched and hovered near it. Each time, the elbow stiffened, and the hand fell back to the strap. The collar rubbed the spot, and the shoulder tensed. After five stops, the fingers finally slipped behind the neck, nails digging in, and the hand moved up and down swiftly. For a moment, the neck relaxed, then the area turned pink and prickled, and the hand returned to its vigil.

**itch_016** · cooking dinner alone in a small kitchen · 焦点：scratching until the skin stings and turns red · 尝试 2 次

> In the small kitchen, the chef moved noodles from pan to plate, steam rising. One hand slipped to the back, fingers probing a spot unreachable by eyes. The wrist bent, pressing, and the nails scraped. Skin reddened under the assault, but the urge remained. The chef stepped away, shoulders heaving in an unacknowledged struggle. A moment later, the fingers crept back, relentless. The skin stung, and the cycle resumed.

**itch_017** · a phone call with a family member · 焦点：a scalp that will not leave the fingers alone · 尝试 1 次

> During the call, the fingers danced to the nape, seeking the scalp’s restless spot. Each touch brought a fleeting relief but also a sting. The earphones shifted, the neck tilted to ease the pressure. Yet, the urge returned, relentless. The scalp pulsed under the fingers’ gentle taps, then firmer presses, until the skin reddened and the spot demanded attention once more.

**itch_018** · walking a dog through a neighbourhood park · 焦点：a label or seam rubbing at the same small place · 尝试 2 次

> The dog pulled at the leash, but the hand holding it twitched instead, fingers tapping against the shoulder. A rough seam at the nape of the neck drew the fingers back, but soon they were slipping under the collar, teasing the spot where the label chafed. The shoulder hunched, then relaxed, and the breath caught briefly. With a firm tug, the hand stopped, but the skin buzzed, and the urge crept up again. A minute later, the fingers slipped back, and for a moment the neck went still, then the sting rose and the label began to chafe anew.

**itch_019** · waiting for exam results to be posted · 焦点：the urge coming back a minute after scratching stopped · 尝试 4 次

> The student sat hunched over a book, eyes scanning lines, but a small patch near the base of the neck demanded attention. Fingertips brushed away the distraction, only to return moments later. Each time, pressure grew until nails scraped the skin, leaving it flushed and throbbing. Yet within minutes, the tension returned, fingers inching closer, hesitating, yielding once more to the relentless pull.

**itch_020** · moving boxes into a new apartment · 焦点：a fresh mosquito bite on the ankle or wrist · 尝试 1 次

> The student carried a heavy box into the new apartment, pausing to wipe sweat from the brow. Every few seconds, a hand slipped down the arm to a spot near the wrist where a fresh bite marked the skin. The student brushed it away, but the fingers found their way back. The nail scraped and the skin reddened, stinging briefly. A minute later, the urge to scratch returned.

**itch_021** · a group project meeting at school · 焦点：a patch of allergic rash on the forearm · 尝试 1 次

> The student’s arm rested on the table, the patch of rash on the forearm twitching. Fingertips hovered near, then retreated, as the student glared at the laptop screen. With a sigh, the hand inched closer, the skin already reddening. Nails barely touched, then pressed harder, until the scratch line was visible. Skin flared red, then began to sting, and the fingers hovered again, waiting.

**itch_022** · shopping at a busy grocery store on a weekend · 焦点：a rough wool collar or sweater against the neck · 尝试 4 次

> Amid the bustling aisle, the collar of the sweater chafed against the neck. Fingertips brushed along the edge, but the hand pulled away each time, sensing the redness deepening beneath the wool. A minute later, the fingers snaked back, pressing firmly and moving in circles. The breath quickened as the sting spread, and for a moment, the urge abated. Then, like a pendulum, it swung back, and the hand returned, relentless.

**itch_023** · a long wait in a clinic waiting room · 焦点：a healing scab that the fingers keep going back to · 尝试 2 次

> Seated in the clinic waiting room, the patient fidgeted, one hand curling and uncurling by the side. Every few minutes, it moved toward the back of the neck, where a scab lingered. The fingers hesitated, then pressed against the scab, and the patient’s head tilted to the side, muscles tensing as the nails grazed the sensitive skin. The area reddened, and the urge returned. The patient adjusted the neck, fingers wandering, finding the scab once more. Another press, and the skin flared. The cycle repeated, the patient’s breath shallow, eyes scanning the room for distraction.

**itch_025** · a rainy afternoon at a bus stop · 焦点：the urge to scratch being held back as long as possible · 尝试 3 次

> The student stood at the bus stop, rain tapping steadily on the umbrella’s edge. A small raised spot behind the knee twitched under the fabric of jeans. Each time the fingers edged close, the student pulled back, squeezing the arm instead. Raindrops dripped down the neck, yet the student felt the spot flare under the fabric. Minutes passed before the nails bit into the denim, scraping until the skin reddened. The spot pulsed, restless, and the student braced for the urge to come again.

**itch_026** · a small birthday gathering with two friends · 焦点：scratching until the skin stings and turns red · 尝试 3 次

> At the birthday gathering, the guest’s fingers danced near the nape where wool had chafed. The collar whispered against skin, and each graze sent a finger edging toward it. Held back, the hand returned, circling the neck until pressure soothed, then dug in until the flesh reddened and stung. Minutes passed, the scratch mark flared again, and the cycle repeated, undisturbed.

**itch_027** · sorting through old boxes in a closet · 焦点：a scalp that will not leave the fingers alone · 尝试 1 次

> The fingers ran through the hair, seeking a spot that buzzed under the scalp. Each time they found it, the hand paused, then resumed combing. A minute later, the same fingers returned, pressing harder this time. The scalp flared with a burst of sensitivity, and the hand pulled back, only to return. The nails scraped gently, easing the urge, but soon the buzz resumed, drawing the hand back to the spot. The scalp reddened slightly, and the cycle repeated.

**itch_028** · the last hour of a late shift at a part-time job · 焦点：a label or seam rubbing at the same small place · 尝试 2 次

> As the clock approached midnight, the clerk adjusted the neck collar, pressing it into the sensitive spot behind the ear. Each nudge sent a sharp jolt to the scalp. The fingers curled and twitched, reaching, retreating, reaching again. The collar loosened, then tightened once more. The skin swelled with every touch, reddening, and the clerk’s breath quickened. Minutes later, the sting subsided, but the collar grazed the same spot, and the cycle began anew.

**itch_029** · feeding a neighbour's cat while they are away · 焦点：the urge coming back a minute after scratching stopped · 尝试 2 次

> While feeding the neighbour’s cat, the hand kept brushing against the shoulder blade where a patch of rough fabric had rubbed earlier. Each time, the fingers reached back to scratch, but paused mid-air. The skin flared, demanding relief, yet the fingers withdrew, hesitating. A minute later, the spot throbbed again, more insistently, and the hand returned, nails grazing until the area reddened. The urge to scratch, momentarily sated, returned like a persistent drumbeat.

**itch_030** · a morning commute on a crowded subway · 焦点：a fresh mosquito bite on the ankle or wrist · 尝试 1 次

> The student clutched a strap, arms tense, as the train lurched into motion. A small red bump on the wrist pulsed, demanding attention. Fingers twitched, but the student clenched them into a fist. The fabric of the jacket brushed the spot and the pulse intensified. With a sigh, the hand slipped from the strap to rest on the wrist, nails grazing the skin. The pulse steadied, the skin reddening under pressure. A moment later, the wrist moved, the hand curling again into a fist as the train jolted.

**itch_031** · cooking dinner alone in a small kitchen · 焦点：a patch of allergic rash on the forearm · 尝试 2 次

> In the small kitchen, the student stirred the simmering pot while the forearm felt the familiar prickling. The hand slipped down and hovered over the rash, fingers curling, then recoiling at the sting. The spoon clattered against the bowl once, twice, as the hand returned, pressing gently, then firmly, the skin reddening beneath the nails. The wrist twisted, fingers digging deeper, until the arm went numb. But soon enough, the sensation flared again, demanding attention.

**itch_032** · a phone call with a family member · 焦点：a rough wool collar or sweater against the neck · 尝试 1 次

> During the call, the collar of the wool sweater chafed the neck. Every few seconds, the fingers crept up from the lap, but the hand slapped back down. The collar rubbed, causing the neck to tense and the shoulders to rise. Fingers squeezed together as if to will the urge away. Finally, the hand moved up, nails biting into the skin, scratching roughly until the neck muscles tensed and the area reddened. As the skin cooled, the urge to scratch returned.

**itch_033** · walking a dog through a neighbourhood park · 焦点：a healing scab that the fingers keep going back to · 尝试 1 次

> The dog walker kept one hand lightly brushing against the collar, avoiding the scab that peeked through the hair at the base of the neck. The spot pulsed, and the fingers crept up, hesitated, then scraped against the skin. A sharp sting followed, and the hand recoiled. Minutes later, the urge returned, and the hand moved again, this time lingering, the nails gently dragging. The skin reddened, the sting intensified, and the hand stilled, only to begin its restless dance once more.

**itch_034** · waiting for exam results to be posted · 焦点：a spot in the middle of the back that the hands cannot reach · 尝试 4 次

> The student sat at the desk, eyes scanning the webpage for updates. A bump on the back began to bother, and fingers traced the shirt hem below. Each touch brought relief for a moment, followed by a sharp insistence to repeat. Reaching behind failed, and a pencil end met the spot briefly. With a sigh, the hand crept up the collar again, and the cycle resumed, the spot reddening with each encounter.

**itch_035** · moving boxes into a new apartment · 焦点：the urge to scratch being held back as long as possible · 尝试 9 次

> The mover paused beside a stack of boxes, one hand lingering at the waist. A patch near the lower back flared with tension, the skin tight and dry. Fingertips brushed the edge of the shirt, and the hand recoiled. For a moment, the tension eased, shoulders relaxing. Then the hand crept back, pressing the fabric, and the skin flared red, a sharp sting radiating outwards. Again, the hand fell away, but the urge returned, fingers tapping against the waistband. Finally, the shirt lifted, and the nails scraped firmly, breaking the spell. Until the spot yearned again.

**itch_036** · a group project meeting at school · 焦点：scratching until the skin stings and turns red · 尝试 5 次

> The student shifted in the chair, hand edging toward the back of the neck. Fingers traced the tight fabric before gripping, but the hand withdrew with a small shake. After several minutes, the fingers returned, digging in, and the student winced as the skin reddened and flared. A moment later, the urge began again, and the student pressed palms flat on the arms of the chair.

**itch_037** · shopping at a busy grocery store on a weekend · 焦点：a scalp that will not leave the fingers alone · 尝试 3 次

> In the narrow aisles, the student's fingers kept reaching up the neck towards the scalp. Each time the hand rose, it was lowered back down. A tight red line appeared from the base of the neck to the fingertips. The scalp pulsed and the jaw clenched. The fingers curled and uncurled, then suddenly the nails pressed hard into the scalp, making the shoulders stiffen and the eyes squint. Moments later, the urge returned, and the fingers sought the spot once more.

**itch_038** · a long wait in a clinic waiting room · 焦点：a label or seam rubbing at the same small place · 尝试 2 次

> The seam of the jacket collar chafed against the skin behind the neck. The fingers curled around the lapels, then stilled as if wrenched away. The neck craned slightly, then relaxed. The collar’s edge grazed the spot and the fingers slipped down once more. They met resistance, paused, then swept under the fabric, pressing and rubbing until the area reddened and smarted. Minutes later, the fingers found the seam again.

**itch_039** · fixing a bicycle that broke down on the way home · 焦点：the urge coming back a minute after scratching stopped · 尝试 1 次

> The cyclist crouched by the roadside, fingers hovering near the welt on the forearm. Each pause in the wrenching brought the hand back to the spot, rubbing until it reddened. The sting intensified, prompting a pause, but a minute later, the fingers returned, scratching until the skin flared red again.
