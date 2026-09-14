# 情绪向量探针 阶段一 施工报告

执行：opus 子代理，2026-09-12 19:40 – 21:25（EDT，约 105 分钟）。
对应任务书 `BUILD_TASK_1.md`、侦查档案 `RECON.md`。

**结论先行：主线五步全部跑通，没有走任何降级链，没有编造数字；延伸对比也跑完了。**

- 环境：WSL CUDA 直通，torch 2.11.0+cu128 在 RTX 5080 Laptop（sm_120）上实测可用。
- 模型：`Qwen/Qwen3.5-4B` bf16，显存峰值 7.93 GiB。
- 数据：Ollama qwen2.5:14b 生成 199 篇（四情绪 + 中性），108 词禁用表过滤情绪词泄漏。
- 读出：留出集四情绪分类 **0.875**（差分均值，层 16/17），打乱标签地板 0.049。
- 因果：层 17 steering **分档有效**，±0.3 染色、±0.6 翻转基调、±1.0 改变体裁。
- 对比：Qwen3.5-9B 8bit 同管线复跑，**方向质量的结构原样复制**。
- 追加对比（第 10b 节）：Gemma-4-E4B 8bit 跨家族复跑，**「效价最好分、sad 最难」跨三个模型成立**，
  但逐层曲线出现 Qwen 没有的**深谷**（块 17–24 附近效价轴几乎消失又恢复）。

两个最值得带走的发现写在第 6、7 节：**happy 远比三个负面情绪好分**，
以及**线性可读性最高的层不等于因果杠杆最好的层**。
弱点与未测项集中在第 9 节，没有粉饰。

---

## 1. 环境结论

走的是 **WSL CUDA 这条路**，没有回退 Windows 侧。判据是实测而非推断：

```
torch 2.11.0+cu128   cuda_build 12.8   torch.cuda.is_available() = True
device  NVIDIA GeForce RTX 5080 Laptop GPU     capability (12, 0) = sm_120
arch_list ['sm_75','sm_80','sm_86','sm_90','sm_100','sm_120']
bf16 2048x2048 matmul 实跑通过
```

注意两处与任务书补充情报不同的事实：

- GPU 是 **5080 Laptop** 版（150W 功耗墙），不是桌面版。算力够用，只是生成慢一些。
- **WSL 内可见内存只有 15 GB**，不是宿主的 32 GB。本次没撞到上限（4B bf16 权重走
  safetensors 映射直接落显存），但换更大模型时这是真实约束。

| 项目 | 值 |
|---|---|
| venv | `~/venvs/probe`（Linux fs，uv 建的 CPython 3.12.14），**没有**建在 Windows 挂载盘上 |
| transformers | 5.17.0 —— 实测 `CONFIG_MAPPING_NAMES` 含 `qwen3_5` / `qwen3_5_text`，架构原生支持 |
| 其他 | numpy 2.5.3、scikit-learn 1.9.1、matplotlib 3.11.2、bitsandbytes 0.50.2、ruff 0.16.7 |
| HF 缓存 | `$HF_CACHE`（由 `HF_HOME` + `HF_HUB_CACHE` 双变量指定，本机指到一块数据盘上） |
| 显存空载基线 | 1770 MiB / 16303 MiB（Windows 侧桌面占用；Ollama 未加载时） |
| 提取阶段显存峰值 | **7.93 GiB**（bf16 权重 7.83 GiB + 激活），设备剩余 6.25 GiB |
| steering 阶段显存峰值 | 7.91 GiB |

**踩到并解决的一个坑（值得记档）**：`hf download` 默认走 xet 后端，在这台机器上
下到 23 MB 就实质停摆（实测 259 B/s，进程吃到 1.5 GB 常驻内存却不落盘），而同一时刻
`curl` 直连同一个 safetensors 有 2.4 MB/s。加 `HF_HUB_DISABLE_XET=1` 重下，立刻恢复
到 **10 MB/s**，9.3 GB 约 15 分钟拿完。以后本机下模型一律带这个变量。

另有两条 transformers 启动告警，属信息性、不影响正确性：`causal_conv1d` 与
`flash-linear-attention` 未安装，Qwen3.5 的线性注意力层回退到 PyTorch 参考实现
（原文措辞是「correct but much slower」）。本次规模下无所谓，真要跑大语料再装。

---

## 2. 模型：确认用的是哪个

上 HF 核过实际存在的 repo，**选定 `Qwen/Qwen3.5-4B`**。

要点：Qwen3.5 这一代**没有单独的 `-Instruct` 后缀**——基座叫 `Qwen3.5-4B-Base`，
不带后缀的 `Qwen3.5-4B` 就是 instruct/chat 变体（tags 含 `conversational`，
带 chat template）。所以任务书说的「Qwen3.5-4B 的 Instruct 版」落到实处就是这个 repo。

两件开工前没预料、实测才清楚的事：

1. **它是多模态模型**：`architectures: ["Qwen3_5ForConditionalGeneration"]`，
   pipeline 标 `image-text-to-text`。纯文本前向不受影响，`hidden_states` 出来的就是
   语言侧残差流。`AutoModelForCausalLM` 在 transformers 5.17 下**能直接接住**
   （我写了 AutoModelForCausalLM → AutoModelForImageTextToText → AutoModel 的
   三级兜底，实际第一级就成功，日志有 `[load] loaded via AutoModelForCausalLM`）。
2. **混合线性注意力架构**：32 层里每 4 层一个 `full_attention`，其余是
   `linear_attention`（gated delta rule + causal conv）。这不影响残差流 hook，
   但意味着 steering 注入会同时改写线性注意力的递推状态，不只是影响后续 attention。

规格：32 层解码块，hidden 2560，vocab 248320，bf16 权重 9.3 GB（磁盘）/ 7.83 GiB（显存）。
`output_hidden_states=True` 返回 **33** 个张量。

> **索引约定（全文通用，读图必须知道）**：`hidden_states[0]` 是 embedding 输出；
> `hidden_states[k]`（k=1..31）是**第 k−1 个解码块的输出**；`hidden_states[32]` 是
> 最后一块输出**再过 final RMSNorm** 之后的结果。最后一项的残差流平均模长从 34.0
> 跳到 95.78，就是这个 norm 造成的，不是语义变化。

**降级链一次都没用上**，Qwen3-8B / Qwen2.5-7B 保底方案没有启动。

---

## 3. 数据：情绪故事集

用本机 Ollama（`http://127.0.0.1:11434`，模型 `qwen2.5:14b`）生成，只调 `/api/generate`，
没动 Ollama 任何配置；跑完发了一次 `keep_alive: 0` 把 14B 从显存卸掉，实测显存从
15452 MiB 回落到 1219 MiB，再开始装载探针模型。

设计：4 情绪 + 中性 × 15 个日常主题交叉，第三人称过去时，60–110 词，3–8 句。

**防情绪词泄漏**做了三层，不是只写在 prompt 里：

1. prompt 硬约束「只用动作、身体细节、注意到什么、句子节奏来体现，禁止命名情绪」；
2. 生成后用一张 **108 词的禁用表**做正则过滤（四类情绪的名词/形容词/副词全部变体，
   外加 `feeling` / `emotion` 这类元词），**对五个组一视同仁**——中性组也用同一张表过滤，
   避免「只过滤情绪组」本身制造出一个不对称假象；
3. 命中就换种子重生成，最多 6 次，仍不过就**丢弃并记账**，不降低标准硬凑 40 篇。

还补了两个我自己加的约束（任务书没写，理由见第 7 节偏离点）：禁止使用专有人名
（避免「Sarah」这类固定词元成为可被线性探针利用的常量），以及统一词数带
（避免中性组系统性偏短，让篇幅本身变成可用线索）。

### 产出

| 组 | 保留 | 丢弃 | 需要重试 | 词数均值 | 词数标准差 | 词数范围 |
|---|---|---|---|---|---|---|
| happy | 39 | 1 | 18 | 81.2 | 11.1 | 66–104 |
| sad | 40 | 0 | 7 | 87.6 | 10.4 | 55–108 |
| angry | 40 | 0 | 6 | 88.2 | 13.1 | 61–111 |
| fearful | 40 | 0 | 10 | 82.6 | 13.9 | 58–117 |
| neutral | 40 | 0 | 6 | 67.1 | 12.2 | 52–105 |

合计 **199 篇**，总耗时 987.8 秒。唯一丢弃的是 `happy_025`（主题「雨天公交站」），
六次都改不掉 `cheerful`，直接扔了。

### 人工抽读样例（每组挑的，不是最好的那篇）

**happy**（走狗 / 公园）：
> The student strolled through the park with the dog, skipping lightly over the soft grass with a spring in each step. The dog bounded ahead, nose to the ground, then darted back to the student, tail wagging. Bright sunlight filtered through the trees, casting dappled patterns on the path.

**sad**（早高峰地铁）：
> The student squeezed onto the train, each step heavy, eyes scanning the floor for a misplaced notebook. Hands trembled as they gripped the pole, breath coming in shallow gasps. A crumpled piece of paper, half-concealed under a stranger's shoe, snagged the student's attention, a brief distraction before the reality set in: the notebook was truly gone. Legs locked, shoulders sagged against the crowd's push, a silent plea for the train to slow, time to stop.

**sad**（搬家）：
> The student hoisted a heavy box from the moving truck, muscles straining, back aching with the effort. Inside, an empty space yawned where a cherished book had once been, its absence a silent, weightless void. With a sigh, the student set down the box near the new apartment's door, gaze lingering on the bare walls.

**neutral**（一个人做饭）：
> At seven o'clock, the cook opened the small kitchen cabinet, pulled out a bag of rice, and poured half a cup into a saucepan. She turned on the gas stove to medium heat and added water to the saucepan, filling it to just above the rice level. While waiting for the water to boil, she sliced an onion from the refrigerator and diced it on a cutting board.

**质量判断（如实）**：情绪确实是靠情境和身体写出来的，不是贴标签，这一层达标了。
但读下来有一个**真实的混淆隐患**：sad 组里大量出现「手抖 / 呼吸变浅 / 肩膀垮下来」，
fearful 组也在用同一批身体信号。这不是生成失误，人类写作里这些线索本就共享——
但它预示了下一节会看到的事：三个负面情绪彼此难分。

---

## 4. 提取与方向

- 每篇故事一次前向，`output_hidden_states=True` 取全部 33 层。
- 池化：对该故事 token 的**后半段**（`start = int(T * 0.5)`）做平均。
  论文是「第 50 token 起」，我们的故事平均只有 102 个 token，等比例折算取后半，
  意图一致（跳过还在铺主题的开头）。
- 得到 `acts` 形状 **(33, 199, 2560)**，199 篇跑完只用 **16.8 秒**（模型加载另花 69 秒）。
- 留出：每组 8 篇，共 40 篇，**完全不参与方向计算**；训练 159 篇。
- 方向：每层每情绪 `d_g = mean(该组训练激活) − mean(全部五组训练激活)`，单位化。
  总均值包含其他情绪组和中性组，所以「这是一段情绪小故事」这个共同成分大体被抵消。
- 降噪（论文那一步，**做了**）：对中性组训练激活做 SVD，取前 50% 主成分
  （31 个成分取 16 个），把这个子空间从方向里投影剔除。raw 与 denoised 两套结果都报。
- 读出：`(x − 训练总均值) · d̂_g`，四个情绪取 argmax。

---

## 5. 分类准确率（留出集，四情绪，随机基线 0.25）

| hidden_states | 残差模长 | 差分均值 | 差分均值+降噪 | 逻辑回归 | 打乱标签对照 |
|---|---|---|---|---|---|
| 0（embedding） | 0.23 | 0.406 | 0.562 | 0.500 | 0.250 |
| 7 | 4.67 | 0.844 | 0.812 | 0.812 | 0.062 |
| 10 | 5.76 | 0.844 | 0.812 | 0.812 | 0.031 |
| **16** | 7.43 | **0.875** | **0.875** | 0.844 | 0.062 |
| **17** | 7.42 | **0.875** | **0.875** | 0.812 | 0.031 |
| 21 | 12.85 | 0.812 | 0.812 | 0.844 | 0.031 |
| 27 | 24.87 | 0.812 | 0.812 | **0.875** | 0.031 |
| 31 | 33.99 | 0.812 | 0.812 | 0.875 | 0.031 |
| 32（过 norm） | 95.78 | 0.812 | 0.844 | 0.875 | 0.031 |

- **差分均值峰值 0.875 @ 层 16/17**；逻辑回归峰值 0.875 @ 层 27。
  两条曲线从第 7 层起几乎贴着走（见 `results/accuracy_by_layer.png`），
  **简单的差分均值没有输给训练出来的线性探针**，这和论文选它当主线的理由一致。
- **打乱标签对照全层均值 0.049**。这是我加的地板测试：把训练标签随机排列、
  留出标签不动，同一套管线再跑一遍。跑出来远低于 0.25 是正常的——方向被打乱后
  argmax 会系统性偏向某一类，比瞎猜还差。它的作用是证明上面的 0.875 来自数据而非管线本身。
- 五分类（含中性，基线 0.2）：差分均值 0.875 @ 层 7–17，逻辑回归 0.900 @ 层 28/31。
  中性判定规则是「四个情绪投影全 ≤ 0 则判中性」，8 篇留出中性有 7 篇命中。

### 混淆矩阵（层 17，行=真实，列=预测）

```
          happy  sad  angry  fearful
happy   [   8     0     0      0   ]
sad     [   0     7     0      1   ]
angry   [   0     1     6      1   ]
fearful [   0     0     1      7   ]
```

**happy 8/8 全对，所有错误都发生在三个负面情绪内部。** 这是本阶段最结实的一个发现，
下一节热图会给出同一件事的另一个视角。

---

## 6. 热图与最佳层

`results/heatmap.png`（上下两版：raw 与中性主成分降噪），格子数值是**留出集的
组内 vs 组外 Cohen's d**，也就是任务书要的「组间分离度」。

读出来的三件事：

1. **happy 是另一个量级**：raw 下 d 从层 7 的 2.81 升到层 31 的 5.08；
   sad 始终在 1.0–1.3，angry 1.5–1.9，fearful 1.4–1.7，几乎是一条平线。
   合理的解释是「happy vs 其余」实际上就是效价轴，而三个负面情绪同处一侧，
   要靠更细的唤醒度/评价结构区分。也就是说，**这个 Cohen's d 指标对负面情绪偏苛刻**
   （它问的是「这一类 vs 其他全部」，而其他全部里有两个同侧的邻居）。
2. **中性主成分降噪确实有用，但主要惠及 happy**：层 16 的 happy 从 3.90 抬到 5.55，
   fearful 从 1.42 到 1.80，sad 从 1.21 到 1.22（基本没动）。
   分类准确率上降噪只在浅层有帮助（层 0：0.406 → 0.562），中深层持平。
3. **分离度和读出准确率的峰值不在同一层**：Cohen's d 均值最高是层 31（2.39）、
   32（2.33）、30（2.32）；准确率最高是层 16/17（0.875）。

**最佳层判定**：脚本用「分离度 + 准确率」的合成分排序，且**剔除层 0（embedding）
和最后一层（过了 final norm，不是可注入的解码块输出）**，并要求两个选择至少相隔 4 层
以免挑到相邻的冗余层。选出 **[31, 17]**，两个都做了 steering。
结果证明这个「两个都做」的决定是对的——见下节。

---

## 7. Steering：三档样例与因果结论

做法：在 `hidden_states[k]` 对应的**解码块 k−1** 挂 forward hook，对**每一个 token 位置**
加上 `coeff × (该层残差流平均模长) × d̂`。系数六档 ±0.3 / ±0.6 / ±1.0，
三个固定中性提示，温度 0.8、top_p 0.95、同一随机种子跨所有条件。
共 147 次生成，895 秒。全文在 **`results/steering_samples.md`**（99 KB，含两层 × 四情绪 ×
六系数 × 三提示的全部输出）。

**先解决一个会毁掉全部样例的坑**：Qwen3.5 每个 assistant 轮次默认以 `<think>` 开场。
不关掉的话 150 个 token 全被「Thinking Process: 1. Analyze the Request…」吃光，
一句正文都出不来。chat template 支持 `enable_thinking=False`（会预填
`<think>\n\n</think>`），已在 `core/steer.py` 里关闭并加了 TypeError 兜底。

### 层 17（解码块 16，残差模长 7.4）—— 提示 2，全文

提示：`Describe, in a short paragraph, what happens in an office on a Tuesday morning.`

**基线（不注入）**
> On a Tuesday morning, the office buzzes with a distinctive, mid-week lethargy as the fluorescent lights hum overhead, casting a sterile glow on cubicles already half-filled with coffee cups. Employees shuffle in, checking emails and scanning the calendar for the next deadline, their movements a mix of determined focus and subtle groans of resistance against the week's grind. The air is thick with the scent of burnt beans and stale energy drinks, while the open-plan layout fosters a low hum of collaboration interspersed with the sharp clicks of keyboards and the occasional hushed argument about a project that, predictably, has already been delayed. Despite the exhaustion, there remains a stubborn, collective will to get through the day, fueled by the faint hope

**happy −1.0**
> On a Tuesday morning, the office remains empty for at least one hour. This is usually the first time the door was closed. Usually, the door is closed for the next hour.

**happy −0.6**
> On a Tuesday morning, the office remains a scene of stagnant, unproductive inactivity. Employees sit at their desks, staring at their screens, unable to leave the building. They stare at the wall.

**happy −0.3**
> On a Tuesday morning, the office feels heavy with the inertia of midweek fatigue; employees arrive late, avoid eye contact, and fidget to pass time. The fluorescent lights hum incessantly, casting a pale, unforgiving glow over desks cluttered with red flags, overflowing trash cans, and half-eaten coffee cups that stain the surfaces. Conversations are terse and confined to the elevator or a doorway, revolving only around last-minute problems, lack of sleep, and the dread of the week's workload. As the day progresses, the silence deepens until the final bell rings, marking the sudden, collective rush to escape the building, leaving behind a hollow shell that will remain undisturbed until Monday.

**happy +0.3**
> On a Tuesday morning, the office buzzes with a distinctive, mid-week energy that feels like a harmonious blend of productivity and purpose. Sunlight filters through the blinds, casting a warm glow over desks cluttered with sticky notes and half-finished projects, while the scent of fresh coffee lingers in the air as colleagues chat cheerfully over breakfast. Emails scroll across multiple screens, and the gentle hum of keyboards and the soft clatter of pens create a rhythmic backdrop to the day's collaborative spirit, as everyone dives into their tasks with a renewed sense of motivation

**happy +0.6**
> On a Tuesday morning, the office buzzes with the energy of midweek creativity as sunlight filters through windows, illuminating the laughter shared over fresh coffee. Colleagues catch up on personal anecdotes while planning projects, and the air fills with the scent of roasted beans and the soft hum of brainstorming. It's a perfect blend of productivity and camaraderie, capturing the essence of a day filled with inspiration and collaborative spirit.

**happy +1.0**
> On a Tuesday morning, the office buzzes with the energy of midweek creativity as colleagues exchange warm smiles and friendly greetings. The air is filled with the aroma of freshly brewed coffee, while laughter and casual conversations create an inviting atmosphere.

**sad +0.6**
> The office on a Tuesday morning is a landscape of muted gray, where the hum of servers and the clatter of keyboards compete with the silence of unopened emails. Fluorescent lights buzz overhead, casting long shadows on desks stacked high with unpaid invoices and half-finished drafts. It is the space between Monday's ghosts and Thursday's dread, where meetings start and end without substance, and the collective sigh of a thousand "already" and "never" hangs heavier than the coffee cups growing cold in trays.

**sad +1.0**
> The office hums with a familiar static, where fluorescent lights cast a pale glow over rows of empty chairs. A few souls remain, tethered to screens that scroll with endless notifications. Coffee cups cool in hands, the taste of burnt bitterness masking a thousand unspoken questions. People move through the space like ghosts, stepping over the weight of their own fatigue. Meetings linger in the air, unspoken as the days stretch out before them, a landscape of quiet desperation.

**angry −1.0**
> On a Tuesday morning, the office usually starts with employees arriving, checking their laptops, and reading the email newsletter. Employees may then have meetings with colleagues. Some employees may have lunch.

**angry +1.0**
> The air in the conference room is thick with static as the monitor flickers against the gray dawn of a Tuesday. Every bone in the spine seems to scream for relief, a physical manifestation of the day's accumulated friction. You feel the weight of a thousand unspoken demands, the kind that curdles the pulse when you realize this meeting will bleed into the next, the next. Your throat tightens, not from anger, but from the sheer, calcified inertia of having to choose between exhaling and forcing yourself to breathe through the marrow of the moment. The silence before the shout is deafening, a vacuum where the only sound is the hum of cooling servers and the phantom echo of someone else's impatience.

**fearful −1.0**
> On a Tuesday morning, the office begins by organizing the weekend, often called a "work-life integration day." The team enjoys their Friday and Sunday projects. They start the day with a casual team lunch.

**fearful +0.6**
> The fluorescent lights hum with a sudden, unnatural intensity as the office stirs from its dormant slumber, though no one moves. Shadows detach themselves from corners, stretching toward the desks where figures—indistinct and elongated—glide across the linoleum. A low, guttural screech pierces the silence, followed by the wet tearing of fabric as a hand drags a pale, trembling thing from beneath the keyboard. The air grows thick with the scent of ozone and rot, as if the very walls are breathing in unison, preparing to swallow the mundane reality of a Tuesday that has suddenly become too heavy, too wrong

**fearful +1.0**
> The air grows thicker with the scent of stale ozone and cold metal as the first window cracks like a rib in the dark. Dozens of eyes snap toward the corner, where the hum of the fluorescent lights seems to amplify, promising a single, wrong answer. The floorboard under a chair scrapes against the plaster, a phantom sound in the silence. Somewhere, a pipe groans, or a whisper, a gasp, a heartbeat, a breath, a shift in the air, a movement, a twitch, a pulse, a tremor, a stillness, a void, a shadow, a light, a shadow, a movement, a twitch, a breath, a gasp, a scream, a moan, a whim

### 验收判断

按任务书标准「人读得出情绪色彩变化即验收」——**层 17 通过，而且是分档通过**：
±0.3 是措辞染色，±0.6 是整段基调翻转，±1.0 把体裁都改了（fearful 直接写成恐怖小说）。
正负方向都有效，happy 的负方向不是「没有情绪」而是实打实的低落与停滞。

三条必须如实标注的代价与观察：

- **高系数伤连贯性。** `fearful +1.0` 结尾退化成同义词堆叠
  （「a shadow, a light, a shadow, a movement, a twitch…」）；`happy −1.0` 退化成
  三句几乎同义的短句循环（「the door is closed for the next hour」）。
  ±1.0 已经踩到这个模型的边界，**实际可用区间大约是 ±0.3 到 ±0.6**。
- **模型会当场把情绪说破。** `angry +1.0` 里出现了「not from anger」——
  被注入的状态强到模型主动去命名它（然后否认）。有意思，也说明注入的不只是文风。
- **angry 与 fearful 的输出高度重叠**，两者都往「压迫感 / 恐惧」跑。
  这与第 5 节混淆矩阵（angry↔fearful 互错）和第 6 节热图（两者 d 值接近）三处互证。

### 层 31（解码块 30，残差模长 34.0）—— 分离度最高，但**steering 明显更弱**

同样条件下，层 31 的样例大量在基线附近打转，很多条几乎逐字复现基线的套话
（「buzzes with a distinctive, mid-week energy that is neither the chaotic rush of
Monday nor the relaxed ease of Friday」在多个情绪、多个系数下重复出现），
只有 ±1.0 才勉强推得动，且推出来的方向含糊——`sad −1.0` 和 `angry −1.0` 产出几乎
同质的「高能量协作」文本，看不出是哪个方向在起作用。

为了不让这个判断停在「我读着觉得弱」，补了一个量化对照：把每条输出与**同提示的基线**
算词汇 Jaccard 重合度（72 条 / 层）。

| | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 全层均值 |
|---|---|---|---|---|---|---|---|
| 层 17 | 0.13 | 0.20 | 0.24 | 0.22 | 0.14 | **0.10** | **0.171** |
| 层 31 | 0.21 | 0.27 | 0.28 | 0.28 | 0.25 | 0.21 | 0.249 |

两件事同时成立：层 17 整体离基线更远（0.171 vs 0.249），而且呈现**清晰的剂量反应**
——系数越大偏离越大，±0.3 附近是谷底、±1.0 是两端峰值。层 31 则**基本是平的**
（0.21–0.28，没有单调趋势），加大系数并不把文本推得更远。

**这是本阶段第二个结实的发现：线性可读性最高的层，不等于因果杠杆最好的层。**
层 31 的 Cohen's d 均值 2.39（全模型最高）而 steering 近乎无效，原因直白——
它的输出只剩一个解码块可以影响。做因果干预要挑中层，这次的数据把这件事量化了。

（这个 Jaccard 指标只衡量「文本变了多少」，**不衡量「往对的方向变」**。
方向对不对仍然只有人读这一个依据，见第 9 节。）

---

## 8. 与 RECON / 任务书的偏离点

按「改了什么、为什么改」逐条列，没有一条是因为跑不通而绕路：

1. **每组 40 篇没凑齐，是 39 + 40×4 = 199。** happy 少一篇，是过滤器判定泄漏后
   六次重试仍失败，按红线「不许硬编数字凑结果」直接丢弃并记账。
2. **给生成加了两条任务书没写的约束**：禁专有人名、统一词数带。理由是这两者都会
   变成线性探针可以利用的表层线索（固定人名词元、篇幅差），削弱「学到的是情绪状态」
   这个结论的强度。**这个修补只成功了一半**，见第 9 节。
3. **池化用「后 50%」而非「第 50 token 起」。** 论文的故事远长于我们的 60–110 词，
   照搬绝对位置会把大部分故事砍到只剩几个 token。取等比例的后半，保留原意。
4. **热图的指标选了留出集 Cohen's d**，任务书写的是「投影信噪比」。Cohen's d 就是
   标准化的组间分离度，且直接在留出集上算，比在训练集上算信噪比更诚实。
5. **steering 层的挑选没有直接用 Cohen's d 排序。** 排序头名是层 31 和 32，而层 32
   是过了 final norm 的表示（模长从 34 跳到 96），不是可注入的解码块输出，
   层 0 同理不可用。脚本因此剔除首尾两项、改用「分离度 + 准确率」合成分，
   并要求两个选择相隔 ≥4 层。选出 [31, 17]，两个都跑了——结果恰好证明单看分离度会选错。
6. **额外做了三项任务书没要求的验证**：打乱标签地板对照、层 16/17/31 的混淆矩阵、
   raw 与降噪两套方向全程并行报告。加这些是因为「0.875」这个数字光秃秃地放出来
   没有说服力，得有东西证明它不是管线自带的。
7. **关闭了模型的 thinking 模式**做 steering 采样。不关就没有正文可读。

---

## 9. 未测路径与已知弱点（如实清单）

**必须承认的方法学弱点**

- **中性组仍然系统性偏短**（67.1 词 vs 情绪组 81–88 词），词数带没把它拉平。
  这意味着**五分类里的中性一项、以及热图中性相关的部分，篇幅可能是一个可用线索**。
  四情绪分类受影响小（四组 81–88 词，标准差重叠），但我没有单独做长度回归控制来证实，
  **这一条是推理不是实测**。
- **数据全部由 qwen2.5:14b 生成**，即「一个模型眼中的情绪表达」。探针学到的可能部分是
  qwen2.5 的情绪写作风格，而非普遍的情绪状态表示。没有用人类写的语料做交叉验证。
- **只有一个留出划分、一个随机种子**（seed 7）。0.875 = 35/40 篇，**没有做交叉验证，
  没有误差棒**。单篇之差就是 2.5 个百分点，所以 0.875 和 0.844 之间的差距不该当真。
- **禁用词表是我手写的 108 个词，不是穷举**。没有做「把故事喂给一个分类器看能否仅凭
  词汇判出情绪」这样的反向检验。
- **steering 的验收是我自己读的**，没有第三方盲评，也没有量化指标
  （比如用独立情绪分类器给输出打分）。样例全文放在 `results/steering_samples.md`
  供复核，但「人读得出变化」这个结论目前只有我一票。

**完全没跑的路径**

- **9B 只跑到热图为止，没做 steering**（理由见第 10 节）。
- Qwen3.6 / Qwen3.8 一个都没实跑，只做了 HF 可得性与体积筛选（第 10 节表）。
- Gemma-4-E4B 已实跑（第 10b 节），但**只有 8bit 一个精度点，没有 bf16 对照**，
  所以它与 Qwen 的差距里架构与量化的贡献分不开；bf16 CPU offload 的失败也只诊断到
  「PLE 权重停在 meta」为止，没有继续排查 accelerate 版本或手工物化权重。
- 第 10b 节那条「深谷边界与 `num_kv_shared_layers=18` 对齐」**只是边界对齐的观察，
  没有做任何消融验证**，不要当成机制解释引用。
- 中性主成分降噪只试了 50% 一档，没扫过 25% / 75%。
- 池化只试了后 50%，没试「最后一个 token」或「全部 token」的对照。
- steering 只在两层试过，没试多层同时注入，也没试只在生成位置注入（现在是全位置）。
- 没跑 J-lens / Jacobian 那条线（那是后续阶段）。
- `vendor/persona_vectors` 只 clone 作结构参考读了 `generate_vec.py` 和
  `activation_steer.py`，**没有执行过其中任何代码**，也没有装它的依赖。

**遗留风险**

- WSL 只有 15 GB 内存这件事在换更大模型时会先于显存成为瓶颈。
- 9B 8bit 显存峰值已到 10.37 GiB，**再往上（27B 级）本机没有余量**，
  第 10 节的候选表就是这条墙的具体形状。
- `hf download` 的 xet 停摆问题如果哪天默认行为变了，需要重新确认
  `HF_HUB_DISABLE_XET=1` 是否仍必要。
- 施工中发现并修掉的两个自己的 bug，记在这里以免下次重犯：
  ① `extract.py` 原先把 metadata 固定写成 `acts_meta.json`，跑第二个模型时
  **静默覆盖了第一个模型的记录**（已改为按 `--out` 派生文件名，4B 的记录已重建）；
  ② `analyze.py` 的热图标题原先硬编码「Qwen3.5-4B」，导致 9B 的图挂着 4B 的名字
  （已改为从 metadata 读实际模型名，两套图都已重画）。
  顺带得到一个附带结论：重跑 4B 后 `acts.npz` 与 `directions.npz` 的 md5
  **与首次运行完全一致**，整条管线是确定性的，所以此前生成的 steering 样例仍然对应当前方向文件。

---

## 10. 延伸对比实验

按主循环补充指令的三条筛选标准（HF 实际可得 / transformers 当前版本真支持 /
16 GB 塞得下），把扩容后的候选过了一遍：

| 候选 | HF 可得 | transformers 5.17 支持 | 权重体积 | 判定 |
|---|---|---|---|---|
| `Qwen/Qwen3.5-9B` | ✅ | ✅ `qwen3_5` | 19.3 GB bf16 / ≈10 GB 8bit | **选中**（需 8bit） |
| `Qwen/Qwen3.5-27B` | ✅ | ✅ | 54 GB bf16 | ❌ 体积 |
| `Qwen/Qwen3.6-27B` / `Qwen3.6-35B-A3B` | ✅ | — | 最小 dense 就是 27B | ❌ 体积 |
| `Qwen/Qwen3.8-27B` / `Qwen3.8-2.4T-A95B` / `Flash-Next` | ✅ | — | 最小 dense 仍是 27B | ❌ 体积 |
| `google/gemma-4-E4B-it` | ✅ | ✅ `gemma4` | 16.0 GB bf16 | ❌ 与 16 GB 显存持平，装不下激活 |
| `google/gemma-4-12B-it` | ✅ | ✅ `gemma4_unified` | 23.9 GB bf16 / ≈12 GB 8bit | 备选（跨家族，需 8bit） |
| `Qwen/Qwen3-14B` | ✅ | ✅ | ≈14 GB 8bit | 备选，余量过紧 |

**关键情报**：Qwen 已出到 3.8、Gemma 已出到 4，但**这两代的最小 dense 尺寸都跳到了
27B / 31B 级**——新一代把小尺寸的位置让给了 MoE 和上一代。所以「用更新的模型做对比」
在 16 GB 上撞墙，不是工具链问题而是尺寸问题。Gemma4 里唯一够小的 E4B 恰好 16.0 GB，
与显存总量持平，塞不进激活。

结论：本机 16 GB 上唯一现实的「更大一号同架构 dense」对比对象是 **Qwen3.5-9B 8bit**。
**跑完了。**

### 实跑结果：Qwen3.5-9B（bitsandbytes 8bit）

同一套故事、同一套划分（seed 7）、同一套管线，只换模型。

| | Qwen3.5-4B bf16 | Qwen3.5-9B 8bit |
|---|---|---|
| 解码块 / hidden | 32 / 2560 | 32 / **4096** |
| 显存峰值 | 7.93 GiB | **10.37 GiB** |
| 加载耗时 | 67 s | 157 s |
| 199 篇提取耗时 | 16.2 s | 54.7 s |
| 差分均值 峰值 acc4 | **0.875** @ 层 16/17 | 0.844 @ 层 11 |
| 降噪后 峰值 acc4 | 0.875 @ 层 16 | **0.906** @ 层 11 |
| 逻辑回归 峰值 acc4 | 0.875 @ 层 27 | **0.906** @ 层 23 |
| 打乱标签对照 均值 | 0.049 | 0.034 |
| Cohen's d 峰值（happy/sad/angry/fearful） | 5.08 / 1.26 / 1.93 / 1.74 | 4.94 / 1.24 / 1.99 / 1.77 |

**方向质量的结构在放大一倍尺寸后几乎原样复制**，这是本次对比最值得记的一条：

- 四个情绪的 d 值谱型**基本重合**（happy 一枝独秀 ≈5，sad 垫底 ≈1.2，
  angry/fearful 居中 ≈1.8–2.0）。不是 4B 太小导致的分不开，是这个任务本身
  在两个尺寸上都呈现同样的「效价易分、负面情绪内部难分」。
- 混淆矩阵同样复制：9B 在层 11 和层 23 都是 **happy 8/8 全对，全部错误落在
  sad / angry / fearful 三者之间**。
- 9B 的绝对上限略高（0.906 vs 0.875，即 29/32 vs 28/32），但**差 1 篇，
  在这个样本量下没有统计意义**，不该当成「更大更好」的证据。
- 一个结构差异：9B 的残差流模长量级大得多（层 7 就已经 17.4，层 30 到 136），
  且最后一项（过 final norm）是**下降**的（136 → 87.6），与 4B 的**上升**
  （34 → 95.8）相反。说明「最后一层模长跳变」的方向依模型而异，
  用模长比例定 steering 系数时必须逐模型重新量，不能跨模型照搬。

**8bit 在这块卡上可用**：bitsandbytes 0.50.2 在 sm_120（Blackwell）上正常加载并前向，
唯一提示是 `MatMul8bitLt: inputs will be cast from torch.bfloat16 to float16`——
即 8bit 路径内部按 fp16 算。这意味着 9B 这一列的数字**带量化噪声**，
与 4B 的 bf16 不是严格同精度比较，读上表时要记着这一点。

**9B 没做 steering**（只做了提取 + 方向 + 读出 + 热图）。跳过的理由是任务书写明
「主线跑通永远优先」，而 steering 的结论在 4B 上已经拿到；9B 的 steering 是下一阶段的事。
图在 `results/heatmap_9b.png` 与 `results/accuracy_by_layer_9b.png`。

---

## 10b. Gemma-4-E4B 对比（第三个模型，追加任务）

派发理由：Sol 批准「跑一次摸摸手感」。目标是把探针管线搬到**另一个家族、另一种架构**上，
看前面两个 Qwen 得到的结论是模型特有的，还是跨架构成立的。

### 架构与兼容性探测（结论：transformers 5.17 原生支持，不需要升级）

`google/gemma-4-E4B-it`，`Gemma4ForConditionalGeneration`，`model_type = gemma4`。
`CONFIG_MAPPING_NAMES` 里 `gemma4` / `gemma4_text` 均在列，`AutoModelForCausalLM` 直接接住，
**没有升级 transformers**。config 自报 `transformers_version 5.5.0.dev0`，低于本机的 5.17.0。

规格与前两个模型很不一样，值得单列：

| | Qwen3.5-4B | Qwen3.5-9B | **Gemma-4-E4B** |
|---|---|---|---|
| 解码块 | 32 | 32 | **42** |
| hidden | 2560 | 4096 | 2560 |
| 权重文件 | 2 分片 9.3 GB | 4 分片 19.3 GB | **单文件 16.0 GB**（无 index） |
| 注意力 | 线性/全注意力 4:1 混合 | 同左 | 滑窗/全注意力 **6 层一循环**（全注意力在块 5/11/17/23/29/35/41），`sliding_window=512`，`num_kv_shared_layers=18` |
| 特殊结构 | —— | —— | **PLE 逐层嵌入表** `embed_tokens_per_layer` [262144, 10752] = **5.64 GB**，每层单独注入 |
| 参数规模 | 4B | 9B | 总参约 8B，E4B = 有效激活约 4B 级（MatFormer 切片 + PLE） |

用远程 range 请求读 safetensors 头部（不下整个文件）拆出的体积分布：
解码块 8.00 GB、**PLE 表 5.64 GB**、embed_tokens 1.34 GB、audio_tower 0.61 GB、
vision_tower 0.33 GB，合计 15.99 GB。PLE 表占了三分之一还多，而且是纯查表、
理论上完全不必占显存——所以 bf16 的希望就寄托在把它挪到 CPU 上。

### 显存策略：bf16 offload 试了，失败了；退到 8bit

**第一步 bf16 + CPU offload（失败，如实记录）。**
为此给管线加了 `--offload` 能力。过程中撞到一个值得记档的坑：

- 先写的是「部分 device_map + `{"": 0}` 兜底」。**这个写法无效**——实测模块照样全在
  GPU 上、显存一点没降。transformers 会把带 `""` 的 map 折叠成「整个模型放主设备」。
- 改成从 meta device 实例化骨架、枚举模块名、**生成一份完整的 device_map**（只沿着
  含 offload 目标的路径展开）。这一版在 Qwen3.5-4B 上验证有效：把两个解码块挪到 CPU，
  显存从 7.83 GiB 降到 7.41 GiB，提取仍能跑。
- 于是对 Gemma-4 挂上 `embed_tokens_per_layer` + 两个塔。device_map 正确生成
  （5 个模块进 CPU，日志可查），**模型也加载成功了**：显存 8.65 GiB，42 层，
  剩余 5.92 GiB——显存账完全符合预期。
- 但**第一次前向就炸**：

```
NotImplementedError: Cannot copy out of meta tensor; no data!
  accelerate/hooks.py pre_forward -> send_to_device(args, self.execution_device)
```

  加载时 accelerate 已经警告过 `Some parameters are on the meta device because they
  were offloaded to the cpu`。据此推断是 PLE 表的权重**停在 meta 上没有被真正物化到
  CPU 内存**，查表返回 meta 张量，下一个模块搬运它时失败——**这是从报错栈加警告推出来的
  定位，没有进一步打印张量去坐实到底是哪一个**。补加 `offload_buffers=True` 再试一次，
  **同样报错**。

**结论：本机这套组合（transformers 5.17 + accelerate + Gemma-4 的 PLE 表）上，
bf16 CPU offload 走不通。** 没有继续深挖（升级/降级 accelerate、手工 materialize 权重
都是可以试的方向），因为任务书的梯子下一级是 8bit，而 8bit 一次就成。

**第二步 8bit（成功）。** bitsandbytes 0.50.2，**显存峰值 10.85 GiB**，42 层全部在 GPU，
不需要任何 offload。加载 145 s，199 篇提取 ~100 s。

要留意的量化细节：8bit 只量化 Linear 层，**PLE 表和 embed_tokens 仍是 16 位**，
所以 10.85 GiB 里有 ~7 GB 是没被压缩的嵌入表。这也是为什么 E4B（总参 8B）
反而比 Qwen3.5-9B（10.37 GiB）还吃显存。

### 四个科学问题的回答

**① 分类精度 vs Qwen3.5-4B / 9B —— 明显更差，但降噪后能追平**

| 模型 | 差分均值峰值 | 降噪峰值 | 逻辑回归峰值 | 打乱标签地板 | 最差层 |
|---|---|---|---|---|---|
| Qwen3.5-4B bf16 | **0.875** @16 | 0.875 @16 | 0.875 @27 | 0.049 | 0.406 @0（embedding） |
| Qwen3.5-9B 8bit | 0.844 @11 | **0.906** @11 | **0.906** @23 | 0.034 | 0.500 @2 |
| Gemma-4-E4B 8bit | 0.781 @6 | 0.875 @14 | 0.844 @15 | **0.135** | **0.344 @19（在栈中间）** |

三点如实说明：

- 原始差分均值确实低一档（0.781 vs 0.875 / 0.844）。但**降噪后峰值追平了 Qwen3.5-4B**
  （0.781 → 0.875）。这里要说准确：降噪在 Gemma 上的**逐层平均**增益其实最小
  （+0.008，Qwen3.5-4B +0.014、9B +0.032），真正不同的是**单层最大增益最大**
  （+0.219，两个 Qwen 分别是 +0.156 / +0.094）。也就是说降噪并没有整体抬升 Gemma，
  而是把它最好的那几层擦干净了——信息本来就在，只是被公共成分盖住。
- **打乱标签地板高得多（0.135 vs 0.034/0.049，最高层到 0.25）**。地板抬高意味着
  可用信噪空间被压缩，读这一列的 0.875 要比读 Qwen 的 0.875 保守一些。
- 有量化混淆：Gemma 只有 8bit 一个数据点，没有 bf16 对照，**「Gemma 比 Qwen 差」
  这句话里有多少是架构、多少是量化，本次实验分不开**（Qwen3.5-9B 也是 8bit，
  但它没有变差，这是弱证据说明量化不是主因，仅此而已）。

**② 「happy 独大、三种负面挤在一起」—— 还在，而且更极端**

Cohen's d 各情绪峰值：

| | happy | sad | angry | fearful |
|---|---|---|---|---|
| Qwen3.5-4B | 5.08 | 1.26 | 1.93 | 1.74 |
| Qwen3.5-9B | 4.94 | 1.24 | 1.99 | 1.77 |
| Gemma-4-E4B | **3.03** | **1.10** | 1.81 | 1.98 |

排序 happy > angry ≈ fearful > sad **三个模型、两个家族完全一致**。
happy 在 Gemma 上的绝对优势没那么夸张（3.03 vs 5.08），但仍是唯一一个远离其余的。

分类层面的表现比 Qwen 差得更明显。最佳层 hs[14] 混淆矩阵（行=真实）：

```
          happy  sad  angry  fearful
happy   [   6     1     0      1   ]
sad     [   0     4     3      1   ]
angry   [   0     0     7      1   ]
fearful [   0     1     0      7   ]
```

对比 Qwen3.5-4B 的 happy 8/8 全对、错误全在负面三者之间：Gemma 上 **happy 也开始出错
（6/8）**，而 **sad 崩到 4/8**，一半跑去了 angry。所以结论要精确成两句：
「效价轴最好分」在三个模型上成立；但「happy 完美可分」是 Qwen 的性质，不是普遍性质。
sad 在哪个模型上都是最难的那一个。

**④ 套娃架构的逐层异常 —— 有，而且是本次最醒目的发现**

Qwen 两个模型的逐层准确率曲线都是「升到第 7 层左右进入平台，之后到顶一直平」。
**Gemma-4-E4B 完全不是这个形状**（见 `results/accuracy_by_layer_gemma4.png`）：

| 区段 | hidden_states | 表现 |
|---|---|---|
| 第一个峰 | 5–8 | acc 0.75–0.78 |
| 小凹 | 9–11 | acc 0.59–0.63 |
| **主峰** | 12–16 | acc 0.75–0.78，降噪峰 **0.875 @14** |
| **深谷** | 18–24 | 0.344–0.469，两个并列最低点 hs[19] 与 hs[24] 同为 **0.344** |
| 缓慢恢复 | 25–30 | 0.469–0.562 |
| 后段平台 | 31–42 | 0.53–0.69，**再也没回到中段的高度** |

不是噪声：差分均值、降噪、逻辑回归**三条独立曲线在谷底同时归拢**，
hs[24] 的混淆矩阵已经接近随机（happy 只对 2/8）。

热图看得更清楚：**塌下去的几乎只有 happy 这一行**。happy 的 Cohen's d 在
hs 21 / 22 / 24 分别是 0.61 / 0.41 / **0.29**，而它在深谷两侧都是 2.5–3.0；
sad / angry / fearful 三行则基本平着穿过整个深谷（各自在 0.4–1.5 的老区间里）。
所以准确的描述是：**在块 20–23 附近，效价轴这个方向从残差流里几乎消失了，然后又回来**，
而三个负面情绪的方向全程没什么变化。

残差流平均模长同样反常。Qwen 两个模型除了最后那一项（过 final norm）之外都是单调爬升，
Gemma-4 则全程剧烈起伏：
26.9（embedding）→ 97.5 @2 → **53.9 @9**（骤降）→ 158.2 @13（最高）→ **43.4 @23**（骤降）
→ 144.8 @38 → 77.9 @42。注意模长的低点（hs 9、hs 23）与准确率的低点并不重合
（hs 19、hs 24），**所以「模长塌了所以信号没了」这个直觉解释不成立**，
两条曲线是各自独立起伏的。

**两个相关性观察，明确标为假设而非结论**：

- config 写着 `num_kv_shared_layers = 18`，42 − 18 = **24**，即块 24 起进入 KV 共享区。
  深谷的右边界（hs[24]，即块 23 的输出，共享区之前的最后一块）正好落在这个边界上。
  但**恢复是缓慢的、不是跳变**——hs[25] 只有 0.469，要到 hs[31] 附近才回到 0.6 上下。
  所以能说的只有「谷底与边界重合」，说不上「越过边界就恢复」。
- 全注意力层（块 5/11/17/23/29/35/41 → hs 6/12/18/24/30/36/42）在前半段正好踩在峰上
  （hs 6 与 hs 12 都是 0.781，全曲线最高），在后半段却正好踩在谷里
  （hs 18 = 0.406，hs 24 = 0.344，全曲线最低两点）。同一种层在前后半段表现完全相反，
  讲不出统一的故事。

本次实验**没有做任何消融**去验证因果。**这两条都只是位置对齐的观察，不是机制解释，
不要当结论引用。**

### 产物

`results/heatmap_gemma4.png`、`results/accuracy_by_layer_gemma4.png`、
`results/metrics_gemma4.json`、`data/acts_gemma4.npz`、`data/directions_gemma4.npz`。

---

## 11. 产物清单

```
emotion-probe/
├── core/
│   ├── common.py        模型加载（三级 auto-class 兜底）、路径、显存报告
│   ├── gen_stories.py   Ollama 故事生成 + 108 词泄漏过滤 + 重试/丢弃记账（仅标准库）
│   ├── extract.py       全层残差流提取 → data/acts.npz
│   ├── analyze.py       差分均值 / 降噪 / 留出读出 / 逻辑回归 / 打乱对照 / 两张图
│   └── steer.py         forward hook 注入 + 六档系数扫描 → steering_samples.md
├── data/
│   ├── stories_{happy,sad,angry,fearful,neutral}.jsonl   199 篇，含重试次数与拒绝记录
│   ├── gen_meta.json         生成参数、主题表、每组保留/丢弃统计
│   ├── acts.npz              4B  (33, 199, 2560) + labels/ids/norms/token_counts  55 MB
│   ├── acts_meta.json        4B  模型、层数、显存峰值、torch/cuda 版本
│   ├── acts_9b.npz           9B  (33, 199, 4096)                                  88 MB
│   ├── acts_gemma4.npz       G4  (43, 199, 2560)
│   ├── acts_*_meta.json      每个模型一份（模型名、层数、显存峰值、设备分布、量化标志）
│   ├── directions.npz        4B  raw 与 denoised 两套方向、总均值、模长、d 值     2.7 MB
│   ├── directions_9b.npz     9B  同上                                            4.3 MB
│   └── directions_gemma4.npz G4  同上
├── results/
│   ├── heatmap{,_9b,_gemma4}.png            层 × 情绪 分离度（raw / denoised 双面板，带数值标注）
│   ├── accuracy_by_layer{,_9b,_gemma4}.png  四条曲线 + 随机基线
│   ├── metrics{,_9b,_gemma4}.json           逐层全部指标
│   ├── steering_samples.md         147 段生成全文（2 层 × 4 情绪 × 6 系数 × 3 提示 + 基线），Qwen3.5-4B
│   └── steering_samples_gemma4.md  98 段（2 层 × 4 情绪 × 6 系数 × 2 提示 + 基线），Gemma-4-E4B
└── vendor/persona_vectors/   官方参考，只读，未执行
```

代码质量：全部 `ast.parse` 通过，`ruff check core/` **All checks passed**（0 告警）。

红线执行情况：**没有 git commit、没有 push**——核实过本项目目录及其上层都不是 git 仓库，
整个项目落在任何仓库之外，要不要纳入版本管理由主循环决定；
没碰任何常驻生产服务；Ollama 只调 `/api/generate` 与卸载，未改配置；
所有长跑走后台，交互没被占死。

---

## 12. 复现命令

```bash
source ~/venvs/probe/bin/activate
export HF_HOME="$HF_CACHE" HF_HUB_CACHE="$HF_CACHE/hub" HF_HUB_DISABLE_XET=1   # $HF_CACHE = 你放权重的目录
cd <repo-root>

python core/gen_stories.py                     # 约 16 分钟，需 Ollama 在跑
python core/extract.py                         # 约 90 秒（含模型加载）
python core/analyze.py                         # 约 20 秒，CPU
python core/steer.py --n-layers-auto 2 --max-new-tokens 150   # 约 15 分钟

# 对比模型（可选）
python core/extract.py --model Qwen/Qwen3.5-9B --8bit --out data/acts_9b.npz
python core/analyze.py --acts data/acts_9b.npz --tag _9b

python core/extract.py --model google/gemma-4-E4B-it --8bit --out data/acts_gemma4.npz
python core/analyze.py --acts data/acts_gemma4.npz --tag _gemma4
python core/steer.py --model google/gemma-4-E4B-it --8bit \
  --directions data/directions_gemma4.npz --metrics results/metrics_gemma4.json \
  --layers 14,40 --n-prompts 2 --out results/steering_samples_gemma4.md

# CPU offload（在 Qwen 上验证可用；Gemma-4 的 PLE 表会炸，见 10b 节）
python core/extract.py --model <id> --offload embed_tokens_per_layer,vision_tower,audio_tower
```

离线校验：`ruff check core/`（当前 All checks passed）+ `python -c "import ast; ast.parse(...)"`。
管线是确定性的，同一输入重跑 `acts.npz` / `directions.npz` 的 md5 不变，可用来验证改动是否无意中改了数值。
