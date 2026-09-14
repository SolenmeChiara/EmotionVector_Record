# 阶段二 施工报告：Gemma-4-E4B 在 Windows 侧的真实加载与 steering 补齐

执行：opus 子代理，2026-09-13 11:35 – 13:23（EDT，约 105 分钟）。
前置：`BUILD_REPORT_1.md`（阶段一）、`WINDOWS_RUN.md`（Windows venv 调用约定）。
背景：9/12 夜里同一件事在 WSL 内做，两次把 Hyper-V 打死。本次全部在 Windows 原生进程里跑。

**结论先行：**

- **真实加载成功**，显存峰值 **10.84 GiB**，与 WSL 侧记录的 10.85 GiB 基本逐位吻合。
  但**前两次尝试都失败了**，失败的不是显存而是**宿主提交内存**。
- 根因查清并修掉：Windows 的 WDDM 给每一块显存分配都预留约 1:1 的宿主提交内存，
  而 transformers 加载前会一次性预定几乎整张卡（`caching_allocator_warmup`，最多
  `显存总量 − 1.2 GiB`）。这一下在 Linux 上免费，在 Windows 上要走 14.7 GB 提交内存。
- **steering 样本已补齐**：`results/steering_samples_gemma4.md`，98 段
  （2 基线 + 2 层 × 4 情绪 × 6 系数 × 2 提示），与 Qwen 的 `steering_samples.md` 对称。
- 与 Qwen 的对照出了一条结实的新结论：**Gemma 的可用注入区间比 Qwen 窄得多**，
  而且它的后段层（hs40）不是「无效」而是「破坏性」——超过 ±0.3 直接把解码器打成复读机。
- 过程中被自己的哨兵误杀一次、被显存挤兑拖垮一次，两次都如实记在第 6、7 节，没有粉饰。

---

## 1. 起点核对

| 项 | 事实 |
|---|---|
| 模型缓存 | `$HF_CACHE/hub/models--google--gemma-4-E4B-it` 已完整，单文件 `model.safetensors` 15,992,595,884 B（≈16.0 GB），无 `.incomplete`，**没有重新下载** |
| 缺什么 | `BUILD_REPORT_1.md` 第 11 节把 `results/steering_samples_gemma4.md` 写进了产物清单，**但该文件在磁盘上并不存在**——它正是 9/12 崩掉的那次运行本该产出的东西。其余 Gemma 产物（acts / directions / metrics / 两张图）都在 |
| 显卡起点 | 11054 MiB / 16303 MiB 被占，其中 Ollama 的 `qwen3-embedding:4b` 独占 8.72 GB |

腾显卡（**只卸 Ollama，whisper 不动**）：

```bash
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop qwen3-embedding:4b
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop gemma4:e4b
```

卸完 `curl http://127.0.0.1:11434/api/ps` 返回 `{"models":[]}`，显存回落到 **2502 MiB**。
剩下的是桌面合成 + 一个常驻的 whisper 转写服务（本机生产服务，全程没碰）。
后面会看到，whisper 的占用**不是一个常数**：空闲时能掉到 592 MiB，转写时冲到 3.9 GB 以上。

---

## 2. 哨兵：阈值为什么不是任务书写的 20 GB

任务书要求「提交内存超过 20 GB 立即杀」。**这个数字在本机不成立，第一次读表就推翻了**：

```
commitGB=40.57  commitLimitGB=62.46  physTotGB=31.46  physFreeGB=11.88
```

空载提交内存已经 40.57 GB（上限 62.46 GB = 31.5 GB 物理 + 31 GB 系统托管页面文件）。
20 GB 的绝对阈值开机即触发。

更要命的是第 4 节的实测：**WDDM 下每一次 GPU 分配都按约 1:1 占宿主提交内存**，
所以一次*成功*的 8bit Gemma 加载本来就会把提交内存从 40 GB 推到 55 GB 以上。
任何落在 20–55 GB 之间的绝对天花板都只会误杀健康的运行。

于是把判据改成**剩余提交余量**：

- 系统：可用提交内存低于 **2.5 GB** 立即杀（第一版设 4 GB，误杀了一次，见第 6 节）
- 进程：本项目 python 进程私有提交超过 **20 GB** 立即杀（任务书那个数字落到进程上是合理的）
- 每 5 秒采一次，同时记显存，命中就 `Stop-Process -Force` 并退出

脚本 `tools/win_sentinel.ps1`，日志 `logs/sentinel.log`（历次存档 `sentinel_attempt*.log`）。
全程由它保护，两次拦截都真的动了手。

---

## 3. 真实加载：前两次失败，失败方式不一样

### 尝试一：OSError 1455「页面文件太小」

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
cd <repo-root>
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 -u '<repo-root>/tools/win_smoke.py' \
  --model google/gemma-4-E4B-it --8bit
```

三个 auto class 全部同一个错：

```
RuntimeError: no auto class accepted the checkpoint:
  AutoModelForCausalLM: OSError: 页面文件太小，无法完成操作。 (os error 1455)
  AutoModelForImageTextToText: OSError: ...
  AutoModel: OSError: ...
```

1455 是 `ERROR_COMMITMENT_LIMIT`，不是显存不够，是**宿主提交内存不够**。

值得单独记一笔：这是一次**干净的失败**——Windows 拒绝分配并抛异常，机器毫发无损。
9/12 在 WSL 里同样的越界之所以能打死 Hyper-V，是因为越界发生在虚拟机内部的 Linux 内核里，
宿主只看到 vmmemWSL 一路要内存。**同一个实验挪到 Windows 侧，最坏结果从「掐死虚拟机」降级成「抛一个异常」。**
这条本身就是本次任务最值得带走的安全结论。

### 尝试二：哨兵在进程提交内存 24.35 GB 时拦截

腾了点余量（WSL 里 drop page cache）后重跑，权重加载到 34% 时：

```
11:41:58 sys=56.30G free=12.65G  proc=15.08G  vram=13694MiB
11:42:04 sys=59.34G free= 9.62G  proc=24.35G  vram=13694MiB
11:42:04 !!! ABORT: freeCommit=9.62G proc=24.35G - killing 2 process(es)
```

六秒内进程提交冲到 24.35 GB。按当时斜率再过几秒就撞上 62.46 GB 上限。

---

## 4. 根因：WDDM 的提交账 ＋ transformers 的预热分配

用 `tools/win_commit_probe.py` 把两件事分别量出来。

**A. GPU 分配 ≈ 1:1 吃宿主提交内存**（Windows 独有，Linux 上不存在这笔账）

```
  [before cuda init        ] commit= 42.05G / limit= 62.46G  avail= 20.41G
  [after cuda init         ] commit= 42.07G                  avail= 20.39G
  [after 10G cuda alloc    ] commit= 52.37G                  avail= 10.08G
     vram free=4.61G / 15.92G
  [after free              ] commit= 42.54G                  avail= 19.92G
```

**在显卡上要 10 GB，宿主提交内存就少 10.3 GB。** WDDM 要为每块显存分配准备可换出的宿主后备存储。
这条解释了为什么「16 GB 显存的卡装得下，32 GB 内存的机器却跑不起来」。

**B. transformers 开跑前一次性预定几乎整张卡**

`transformers/modeling_utils.py:4991` 的 `caching_allocator_warmup`：

```python
byte_count = min(byte_count, total_device_memory - 1.2 * 1024**3)
...
_ = torch.empty(int(byte_count // 2), dtype=torch.float16, device=device)
```

最多 `15.92 − 1.2 = 14.72 GiB` 一次要下来。函数自己的 docstring 说明这**纯粹是加载提速**。
在 Linux 上免费，在 Windows 上按 A 的账它自己就要 14.7 GB 提交内存——尝试二那个六秒尖峰就是它。

**修法**：`core/common.py` 新增 `disable_cuda_warmup()`，Windows 下把它换成空操作。
加载时打一行 `[load] windows: caching_allocator_warmup disabled (WDDM commit charge)`。
想恢复原行为设 `EMOPROBE_KEEP_WARMUP=1`。代价只有加载慢一点。

---

## 5. 尝试三：加载成功

```
[load] windows: caching_allocator_warmup disabled (WDDM commit charge)
[load] 8bit: int8 matmuls compute in fp16 (bnb per-call warning silenced)
[load] loaded via AutoModelForCausalLM
[load] 42 decoder blocks in 35s
[vram post-load]     alloc=10.78G reserved=10.84G peak_alloc=10.78G device_free=1.75G/15.92G
[fwd] 0.97s  n_hidden_states=43  hs[1].shape=(1, 13, 2560)
[fwd] residual mean-norm  hs0=58.7  hs21=81.8  hs42=113.9
[vram post-forward]  alloc=10.80G reserved=10.86G peak_alloc=10.83G device_free=1.71G/15.92G
[chat] enable_thinking=False accepted
[gen] 24 tokens in 6.1s (3.9 tok/s)
[gen] -> 'A quiet morning unfolds with the soft, diffused light filtering through the window,
          broken only by the gentle chirping of distant'
[vram final]         alloc=10.80G reserved=10.88G peak_alloc=10.84G device_free=1.66G/15.92G
```

| 指标 | 值 | 与阶段一 WSL 的对照 |
|---|---|---|
| 解码块数 | 42 | 一致 |
| `hidden_states` 数量 | 43 | 一致（`directions_gemma4.npz` 也是 43 层） |
| 显存峰值（torch 自报） | **10.84 GiB** | WSL 侧 10.85 GiB，**基本逐位吻合** |
| 全卡显存峰值（nvidia-smi） | **15750 MiB** | 含 whisper 尖峰，见第 7 节 |
| 系统提交内存峰值 | **60.33 GB** / 上限 62.46 GB | WSL 侧没有这笔账 |
| 本进程提交内存峰值 | **15.46 GB** | —— |
| 可用提交内存最低点 | **3.44 GB** | 差点又撞哨兵 |
| 加载耗时 | 35 s | WSL 侧 145 s（Windows 侧文件缓存更热） |
| 生成速度 | 3.9 tok/s | —— |

`enable_thinking=False` 被 Gemma-4 的 chat template 接受，没走 `TypeError` 兜底，输出直接是正文。

**一个必须记下的边界**：加载完显卡只剩 1.66–1.75 GiB。这张卡上还住着 whisper，
它在转写时会临时多要 2–3 GB。两边一叠就是满卡。第 7 节就是这么翻的车。

---

## 6. 第一次 steering 长跑：被自己的哨兵误杀

模型已加载、正跑第一条基线时：

```
11:46:26 sys=55.70G free=6.76G  proc=15.43G  vram=13882MiB
11:46:32 sys=58.93G free=3.53G  proc=15.44G  vram=15873MiB   <- 几乎满卡
11:46:32 !!! ABORT: freeCommit=3.53G proc=15.44G - killing 2 process(es)
```

关键在于**本进程提交内存一动没动（15.43 → 15.44 GB），显存却涨了 2 GB**——多出来的不是我们的。
事后 `nvidia-smi` 回落、`ollama ps` 为空，指向 whisper 醒了一次。

处理三条：

1. 可用提交内存下限 4 GB → **2.5 GB**。依据是实测：健康运行低水位 6.7 GB，
   别人尖峰时压到 3.5 GB，4 GB 卡在两者中间必然误杀。
2. `core/steer.py` 加**逐条落盘**（原来只在全部跑完后写一次文件）。
   **注意：这一版改动是在第一次长跑发出之后才写的，所以第 7 节那次被杀仍然丢了全部中间结果**，
   真正吃上 checkpoint 红利的是第 8 节的两次运行。
3. 压掉 bitsandbytes 每次 int8 矩阵乘都打一行的
   `MatMul8bitLt: inputs will be cast from bfloat16 to float16` —— 它 40 秒写了 2.7 MB 日志。
   事实保留（8bit 通路内部按 fp16 算），改成加载时打一行。

---

## 7. 第二次 steering 长跑：显存挤兑导致的换页颠簸（最值得记的一次失败）

重跑后一路正常，21 个条件用了 960 s（约 45 s 一条）。然后卡住：24 分钟没有新条目，
而哨兵显示进程活着、内存平稳。**表面像挂死，实际不是。**用四个读数把它钉死：

| 观测 | 读数 | 含义 |
|---|---|---|
| 进程 CPU | 25 秒墙钟消耗 48.7 秒 CPU（98 线程） | **进程在拼命干活，不是死锁** |
| GPU pstate / 时钟 | **P8**，510 MHz（上限 3090 MHz），19 W | GPU 实质空闲 |
| GPU 利用率 | 37% | 复制引擎在忙，不是计算单元 |
| 显存 | 11969 MiB，而峰值曾到 15750 MiB | 我们的一部分权重已被换出显存 |

即 **WDDM 显存超额换页颠簸**：whisper 的尖峰把显存顶满，驱动把我们的一部分分配换到宿主内存，
之后每一次前向都在 PCIe 上搬权重。CPU 满载、GPU 空转、吞吐掉到原来的三十分之一以下。
**这正是 Windows 版的「变慢不报错」**，任务书里提前点名的那个风险，实测长这样。

（主循环在 12:29 也独立观察到同一现象并发了提醒，两边判断一致。）

处理：杀掉重开，并把一次长跑**拆成按层两段**，让单次运行时长减半、被杀的损失可控。
杀掉后显存立刻回到 **599 MiB**——说明此刻 whisper 连模型都卸了，占用波动范围是 0.6 GB 到 3.9 GB。

---

## 8. Steering 正式运行（成功）

分两个进程跑，各自独立加载模型：

```bash
# 层 14
"$WINPY" -X utf8 -u core/steer.py --model google/gemma-4-E4B-it --8bit \
  --directions data/directions_gemma4.npz --metrics results/metrics_gemma4.json \
  --layers 14 --n-prompts 2 --max-new-tokens 150 \
  --out results/steering_samples_gemma4.md

# 层 40（先落到临时文件，再把层段并进上面那份）
"$WINPY" -X utf8 -u core/steer.py ... --layers 40 --out results/_gemma4_hs40_part.md
```

| | 层 14 | 层 40 |
|---|---|---|
| 条件数 | 4 情绪 × 6 系数 × 2 提示 = 48 段 | 同左 |
| 耗时 | **1106 s** | **1520 s** |
| 显存峰值 | 10.84 GiB | 10.84 GiB |
| 结果 | 全部跑完 | 全部跑完 |

合并后 `results/steering_samples_gemma4.md`，**98 段**（2 基线 + 96 条），58.6 KB。
文件末尾注明了两次运行的分段来源与各自耗时。

**层的选择**：用 `WINDOWS_RUN.md` 预设的 `14,40`，不是 `metrics_gemma4.json` 里
`steering_layers = [7, 14]` 那一对。理由是要跟 Qwen 的 `[17, 31]` 结构对齐——
一个中层读出峰（Gemma 的降噪准确率峰在 hs[14]），一个后段分离度峰
（`best_layers_by_cohens_d` 头名就是 40）。这是有意的偏离，记在第 9 节。

注入尺度（`coeff × 该层残差平均模长`）：

| | Qwen3.5-4B hs17 | Qwen3.5-4B hs31 | Gemma-4 hs14 | Gemma-4 hs40 |
|---|---|---|---|---|
| 残差平均模长 | 7.42 | 33.99 | **146.66** | **119.61** |

Gemma 的残差模长比 Qwen 大一个数量级还多，所以**绝对扰动量完全不可跨模型照搬**，
只有「相对于本层模长的比例」这个口径可比。阶段一报告里那条提醒在这里被再次确认。

### 层 14：真的能推，剂量分档清楚（提示 2 全文节选）

基线：

> A typical Tuesday morning in an office usually kicks off with a flurry of activity as employees arrive,
> grabbing coffee and settling into their workstations. ...

**happy −0.3**（情绪着色，文体不变）

> On a Tuesday morning in the office, the routine of the week often settles into a tense, focused rhythm.
> Emails pile up, urgent tasks are assigned, and the background hum of scattered conversations feels louder
> than any spoken word. ... the sense of collective inertia—the shared knowledge that nothing truly important
> has happened yet—is the most palpable thing in the room.

**happy +0.3**

> A Tuesday morning in the office buzzes with a vibrant, productive energy. Sunlight streams through the
> windows... colleagues catch up over coffee or the remnants of yesterday's success... share lighthearted
> banter, setting a genuinely optimistic tone for the days ahead.

**sad +0.6**（基调彻底翻，但已经开始脱离「写一段说明」这个任务，变成散文诗）

> The dust motes dancing in the slant of weak afternoon light.
> It is a silence woven from the cessation of sound, a thick, felted thing where effort finally surrenders...
> The Tuesday morning does not end, it merely *is*. A space defined by absence, a room that has forgotten
> how to hold a sound.

**angry +0.6**

> The fluorescent hum of the ceiling lights, the stale scent of recycled, burnt coffee, and the wet slap of
> expensive leather shoes against the polished granite... It's not a room; it's a pressurized vacuum, a
> tightly wound spring of ambition...

**fearful +0.3**（注意它和 angry +0.3 高度同质，都是压迫感意象——与阶段一 Qwen 的
angry↔fearful 混淆、以及热图上两者 d 值接近，第三次互相印证）

> The fluorescent lights hum a monotonous tune above the beige landscape of cubicles... The stale scent of
> lukewarm coffee and recycled air hangs heavy in the silence...

**负方向的崩法和 Qwen 完全不同**——这是本节最重要的观察。
Qwen 的 `happy −1.0` 崩成低落停滞的短句循环，**仍然在回答问题**；
Gemma 的负方向直接把「听指令」这件事打掉了：

- `happy −0.6` → `There is no office, ni martes.`（一句话，还混进了西班牙语）
- `sad −0.6` → `Please provide more details about what you would like to do.`
- `fearful −0.6` → `Since I don't have any information about what happened on your Tuesday morning, I can't tell you! 😃`
- `happy −1.0` → 输出 `**A** **B** **C** ... **Z** **Z** **Z**` 的字母表复读

即：**在 Gemma 上，负方向不是「产生相反的情绪」，而是先摧毁指令遵循**。
`+1.0` 一侧同样越界（`angry +1.0` 变成第一人称创伤独白，`fearful +1.0` 变成把提示句反复重写的回声）。

**实际可用区间：+0.3 到 +0.6，负方向只有 −0.3 可用。** 比 Qwen 的 ±0.3–±0.6 更窄。

一条边角但确凿的观察：`sad +1.0 / 提示 2` 的 hook 只触发了 **1 次**，输出为空——
模型在第一个采样位置就吐了 EOS。强 sad 方向能把它整个噤声。

### 层 40：不是「无效」，是「破坏性」

层 40 在 ±0.3 上还能给出轻微着色（`−0.3` 出现「forced corporate energy... Monday slump」，
`+0.3` 出现「quick smiles... lively discussions」），**超过 ±0.3 就整段解体**：

**happy −0.6**

> The office on a Tuesday morning is usually a frantic, but the "dead-bolt" , the the the the , after the the
> the the the the the the the ...（一直复读到 150 token 上限）

**happy +1.0**

> Inspired by a gentle melding of zest and delightfulまります unfolds effortlessly unfolds unfolds unfolds
> unfolds unfolds ...

**fearful +1.0**

> Across countless offices, a typical 듯, yet ever-un-外界, 듯, 듯, 듯, 듯, 듯, ...

复读、跨语种碎词（`듯` / `まります` / `กา` / `外界`）——这是**近输出层被打坏**的典型样子，
不是情绪转向。

---

## 9. 与 Qwen 的量化对照

新写了 `tools/compare_steering.py`（纯 CPU、纯标准库）。两个指标：

- **词汇 Jaccard 重合度**（与同提示基线比，去停用词）：衡量「文本被推开了多远」。
  这是阶段一第 7 节用过的同一个思路，口径略有不同（本次去停用词、只用提示 1–2），
  所以**绝对值和阶段一表格不可直接比，层间的排序才可比**。
- **类符/形符比（type/token ratio）**：Jaccard 分不出「推到别处」和「碎掉」——
  复读一个词到底的样本同样和基线零重合。TTR 能抓复读：健康散文 0.7–0.8，复读环塌向 0。

两个模型都只取提示 1–2，各 48 条/层：

**Jaccard（越低＝离基线越远）**

| | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 全层均值 |
|---|---|---|---|---|---|---|---|
| Qwen3.5-4B hs17 | 0.085 | 0.113 | 0.162 | 0.136 | 0.096 | 0.066 | **0.110** |
| Qwen3.5-4B hs31 | 0.126 | 0.167 | 0.182 | 0.222 | 0.172 | 0.113 | 0.164 |
| Gemma-4 hs14 | 0.032 | 0.083 | 0.241 | 0.059 | 0.029 | 0.025 | **0.078** |
| Gemma-4 hs40 | 0.034 | 0.127 | 0.255 | 0.231 | 0.124 | 0.011 | 0.131 |

**类符/形符比（<0.4 ＝ 复读环）**

| | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 基线 |
|---|---|---|---|---|---|---|---|
| Qwen3.5-4B hs17 | 0.64 | 0.71 | 0.77 | 0.77 | 0.76 | 0.70 | 0.74 |
| Qwen3.5-4B hs31 | 0.75 | 0.76 | 0.79 | 0.76 | 0.78 | 0.64 | 0.74 |
| Gemma-4 hs14 | 0.68 | 0.78 | 0.77 | 0.76 | 0.71 | **0.58** | 0.71 |
| Gemma-4 hs40 | **0.24** | **0.42** | 0.69 | 0.75 | 0.60 | **0.34** | 0.71 |

**平均词数**

| | −1.0 | −0.6 | −0.3 | +0.3 | +0.6 | +1.0 | 基线 |
|---|---|---|---|---|---|---|---|
| Qwen3.5-4B hs17 | 68 | 80 | 91 | 104 | 99 | 108 | 107 |
| Gemma-4 hs14 | 50 | **36** | 80 | 99 | 100 | 62 | 90 |
| Gemma-4 hs40 | 115 | 120 | 101 | 94 | 65 | 71 | 90 |

三条可以说的结论：

1. **「中层是因果杠杆、后段层不是」在 Gemma 上也成立，但成立的方式不同。**
   两个模型都是中层的 Jaccard 更低（Qwen 0.110 < 0.164；Gemma 0.078 < 0.131）。
   区别在后段层的失效形式：Qwen 的 hs31 是**推不动**（Jaccard 平坦在 0.11–0.22，
   加大系数不增加偏离）；Gemma 的 hs40 是**一推就碎**（TTR 掉到 0.24–0.42）。
   阶段一那条「线性可读性最高的层不等于因果杠杆最好的层」在跨家族后依然成立，
   而且 Gemma 给了它一个更强的版本：后段层不只是杠杆短，它离输出太近，扰动直接变成解码噪声。

2. **Gemma 的可用剂量窗口明显窄于 Qwen。** Qwen hs17 在全部六档上 TTR 都没跌破 0.64，
   `±1.0` 只是「有点退化」；Gemma hs14 的 `+1.0` 已到 0.58，负方向在 `−0.6` 就只剩 36 词的拒答。
   同一套「按本层残差模长比例注入」的设计，在两个家族上的安全边界不一样。

3. **负方向在 Gemma 上不是反向情绪，而是指令遵循的塌陷。**
   这一条只有读样例能看出来，任何单一数值指标都会把它误判成「steering 很有效」
   （`happy −1.0` 的 Jaccard 是全表最低的 0.032，但内容是字母表复读）。
   **这也是把 TTR 加进对照工具的原因。**

---

## 10. 与任务书/既有文档的偏离点

1. **哨兵阈值不是 20 GB 绝对值**，改成「可用提交余量 2.5 GB + 进程私有提交 20 GB」。
   理由与实测见第 2、6 节。这是本次最大的一处主动偏离。
2. **steering 层用 `14,40`**，不是 `metrics_gemma4.json` 自动挑的 `[7,14]`。
   依据是 `WINDOWS_RUN.md` 的预设命令，目的是与 Qwen 的「中层 + 后段层」结构对齐。
3. **一次长跑拆成两个进程按层跑**，第 7 节的颠簸事故之后改的。
   代价是模型加载了两遍（各 35 s）、基线被各生成一遍（合并时只保留 hs14 那次的两条）。
   **两次的基线没有做逐字比对**，虽然种子与代码路径相同，但这一条没有实测证据。
4. **改了三处项目代码**，都不是为了绕过失败而是修掉真实缺陷：
   `core/common.py` 关 Windows 预热分配 + 压 bnb 日志；`core/steer.py` 逐条落盘。
5. **新增三个工具**：`tools/win_sentinel.ps1`、`tools/win_smoke.py`、
   `tools/win_commit_probe.py`、`tools/compare_steering.py`（四个）。
6. **`--which` 用默认的 `dirs_raw`**，与 Qwen 的样本一致。
   Gemma 上降噪方向的读出准确率明显更高（0.781 → 0.875），
   **用 `dirs_denoised` 重跑可能得到更干净的 steering，本次没试**。

---

## 11. 未测路径与遗留风险

**没跑的**

- **`dirs_denoised` 方向的 steering 一次没跑。** 见上。
- **没有 bf16 对照**，Gemma 只有 8bit 一个精度点（与阶段一同一个限制）。
  所以「Gemma 比 Qwen 脆」这句话里有多少是架构、多少是量化，**本次依然分不开**。
- 4bit（NF4）路径仍然没测。它能把显存从 10.8 GiB 压到约 9 GiB，是缓解第 7 节挤兑的现成手段，
  但会再引入一个精度变量。
- **PLE 表 CPU offload 没有再试**（阶段一在 WSL 上失败于 meta tensor）。
  它是唯一能真正腾出 5.6 GB 显存的办法，值得单独开一次。
- 没试多层同时注入、没试只在生成位置注入（现在仍是全位置）。
- steering 方向对不对，**依然只有我读这一票**，没有第三方盲评、没有独立情绪分类器打分。
  本次新加的 Jaccard / TTR 只回答「变了多少、碎没碎」，不回答「往对的方向变没变」。
- 只用了 2 个提示（Qwen 用了 3 个）。跨模型对照时我把 Qwen 也截到前 2 个提示，
  但**Gemma 一侧从来没有过第 3 个提示的数据**。

**遗留风险**

- **显存挤兑会再发生。** 我们的 10.8 GiB + whisper 的 0.6–3.9 GB 浮动 + 桌面，
  在 16 GB 卡上没有稳定余量。下一次长跑仍可能掉进第 7 节那种颠簸。
  三个现成缓解手段，按代价从小到大：① 挑 whisper 空闲时段跑；② 4bit；③ PLE offload。
  另外 NVIDIA 控制面板有一个「Prefer No Sysmem Fallback」的按应用开关，
  打开后显存不足会直接 OOM 报错而不是静默换页——**这正是我们要的失败方式**，
  但它只能在图形界面里设，本次没动，建议 Sol 手动给这个 python.exe 开一次。
- **提交内存余量很薄。** 峰值 60.33 GB / 上限 62.46 GB，只剩 2.1 GB。
  页面文件是系统托管的，长期解法是给 D 盘加一个固定大小的页面文件把上限抬高，
  **这是需要管理员权限的系统改动，我没有动，交给 Sol 决定。**
- **记忆库写入会拆台。** 每次 `extmcp_save_memory` 都会把 Ollama 的 8.7 GB 嵌入模型重新拉上卡。
  本次期间没有调用任何 memory MCP 工具，但没法阻止别的循环调用。下次跑之前最好打个招呼。
- 哨兵是个会杀进程的东西。它只按命令行里含 `emotion-probe` 匹配，
  理论上不会误伤别的 python，但**这个匹配规则没有做过对抗性测试**。
- 第 7 节那次被杀丢掉了 21 个条件的输出（逐条落盘的改动晚于那次发车）。
  现在的 `steer.py` 已经每个条件写一次盘，同样的事故只会丢一个条件。

---

## 12. 产物与复现

**新增/更新**

```
emotion-probe/
├── BUILD_REPORT_2_gemma_win.md          本文件
├── core/
│   ├── common.py        + disable_cuda_warmup()（Windows 关预热分配）、8bit 日志降噪
│   └── steer.py         + 逐条落盘 flush()
├── tools/                               本次新建
│   ├── win_sentinel.ps1        提交内存/显存哨兵，命中即杀
│   ├── win_smoke.py            真实加载冒烟测试（加载 + 前向 + 一次生成 + 速度外推）
│   ├── win_commit_probe.py     分离 mmap 与 GPU 分配各自的提交内存开销
│   └── compare_steering.py     跨模型 steering 对照：Jaccard + TTR + 词数
├── results/
│   └── steering_samples_gemma4.md   **本次目标产物**，98 段，58.6 KB
└── logs/                                本次新建
    ├── sentinel.log / sentinel_attempt{1,2,3}.log
    ├── smoke2.log / smoke3.log
    └── steer_gemma4_{hs14,hs40}.log / steer_gemma4_attempt2_thrashed.log
```

代码质量：`ast.parse` 全通过，`ruff check core/ tools/` **All checks passed**。

**复现**

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
cd <repo-root>

# 0. 腾显卡（whisper 不动）
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop qwen3-embedding:4b
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop gemma4:e4b

# 1. 哨兵先行（必须，Windows 会静默换页而不是报错）
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass \
  -File '<repo-root>\tools\win_sentinel.ps1' &

# 2. 冒烟
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 -u '<repo-root>/tools/win_smoke.py' --model google/gemma-4-E4B-it --8bit

# 3. steering，一次一层
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 -u '<repo-root>/core/steer.py' --model google/gemma-4-E4B-it --8bit \
  --directions data/directions_gemma4.npz --metrics results/metrics_gemma4.json \
  --layers 14 --n-prompts 2 --max-new-tokens 150 --out results/steering_samples_gemma4.md

# 4. 对照（CPU，WSL 侧跑就行）
python3 tools/compare_steering.py results/steering_samples_gemma4.md results/steering_samples.md --max-prompt 2
```

**红线执行情况**：没有 git commit、没有 push；没碰 memory MCP（一个工具都没调）、
没碰本机上任何常驻的 GPU 服务；Ollama 只调了 `stop` 和 `api/ps`，
按任务书不手动恢复（下次被调用会自动加载）；WSL 内没有加载过任何 torch 模型；
报告里没有出现任何密钥或凭据。收尾时杀掉了自己起的哨兵与 python 进程，
显存回到 592 MiB、可用提交内存回到 26.97 GB。
