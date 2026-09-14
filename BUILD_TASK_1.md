# 情绪向量探针 实现任务书 · 阶段一（管线跑通＋热图＋steering 首验）

派发：2026-09-12 19:40，fable5。执行：opus 子代理。Sol 已批准下载模型权重。
必读：`<repo-root>/RECON.md`（论文判定、方法配方、
代码库、不确定项——全文读完再动手）。

## 0. 环境探测（先做，结论写进报告）

- WSL 内 `nvidia-smi` 是否可见 RTX 5080；建 venv（**Linux fs**，如 `~/venvs/probe`，
  drvfs 上建 venv 会炸）装 torch（CUDA 版）+transformers+accelerate+matplotlib+
  scikit-learn，`torch.cuda.is_available()` 实测。
- WSL CUDA 不通则 fallback Windows 侧（`/mnt/c/Python313/python.exe`，pip 装同套；
  注意路径写 Windows 式）。两条路都探，用能通的那条，报告写明用了哪条与判据。
- 显存基线：记录空载 `nvidia-smi` 显存占用（Windows 侧 Ollama/Chrome 可能占着一些）。

## 1. 模型

- 主模型：**Qwen3.5-4B 的 Instruct 版**（Sol 指定用更新的模型；这个尺寸 bf16 约 8GB
  全精度舒适，且与 idhantgulati/j-lens 民间实现同款——为后续 J-lens 阶段直接铺路）。
  开工先上 HF 确认准确 repo 名（搜 Qwen3.5 官方 org 的 4B instruct/chat 变体，
  以 HF 实际存在者为准，报告写明选了哪个）；transformers 用足够新的版本以支持该架构。
  缓存目录设到一块数据盘（`$HF_CACHE`），别塞系统盘。
- 延伸对比（主线全部跑通后才做，时间不够就记账不做）：更大一号的新 dense
  （Qwen3.5-9B 8bit 或 Qwen3-14B 8bit，以 HF 实际可得为准），同管线复跑对比方向质量。
- 若 Qwen3.5 架构与 transformers 兼容性受阻（新模型常见坑），降级链：
  Qwen3-8B bf16-或-8bit → Qwen2.5-7B-Instruct bf16（保底，persona_vectors 验证过），
  每次降级如实记录理由。

## 2. 数据：情绪故事集

- 4 情绪（happy / sad / angry / fearful）＋中性组，每组 **40 篇**短故事（每篇 3–6 句）。
- 生成方式：用本地 Ollama（`http://127.0.0.1:11434`，模型 qwen2.5:14b）批量生成——
  15 个日常主题 × 情绪交叉，prompt 要求「体现该情绪的一段小故事，不出现情绪词本身」
  （防止方向学到的是表面词汇而不是情绪状态）。中性组同主题平实记叙。
- 全部存 `data/stories_{emotion}.jsonl`；抽每组 3 篇人工读一遍核质量（报告贴样例）。
- Ollama 不可用则退化为手写模板组合生成，如实标注。

## 3. 管线（照 RECON「方法配方」节，差分均值主线）

1. 提取：每篇故事跑前向，**全层** hook 残差流（hidden_states 即可，不必手写 hook），
   对故事 token 的后半段做平均池化 → `layer × story` 激活矩阵，存 npz。
2. 方向：每层做差分均值（情绪组均值 − 全组总均值）；可选做论文的中性主成分降噪
   （前 50% PC 投影剔除），做不做都报告。
3. 读出验证：留出每组 8 篇不进方向计算，投影到各情绪方向 → 分类准确率；
   顺手训 sklearn 逻辑回归探针对照。
4. 热图：层 × 情绪的投影信噪比（留出集组间分离度），存 `results/heatmap.png`。
5. Steering：挑信噪最好的 1–2 层，生成时注入方向（系数按该层残差流平均模长的
   ±0.3 / 0.6 / 1.0 三档），固定 3 个中性提示（如「写一段明天的天气预报」），
   每档生成样例存 `results/steering_samples.md`。判断标准：人读得出情绪色彩变化即验收。

## 4. 产物结构

emotion-probe/{core/（脚本）, data/, results/, vendor/}；
vendor 里 clone safety-research/persona_vectors 作**只读参考**（抄结构不抄依赖，
我们的脚本自包含）。

## 5. 红线

- 不 git commit/push；不碰生产服务；Ollama 只调生成接口不动其配置
- 下载/显存/兼容性任何一环卡住：如实记录、走降级链，不许硬编数字凑结果
- 长跑放后台，别占死交互

## 6. 报告（`BUILD_REPORT_1.md`，如实，不许自评完美）

环境结论（哪条路、torch/CUDA 版本、显存峰值）；数据样例与质量说明；分类准确率
（差分均值 vs 逻辑回归）；热图与最佳层；steering 三档样例全文；14B 对比（若做）；
与 RECON/本单的偏离；未测路径；遗留风险。
