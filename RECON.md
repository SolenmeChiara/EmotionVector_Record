# 情绪向量探针 · 侦查档案

2026-09-12 18:11，sonnet 侦查兵交付，fable5 整理归档。
起因：Sol 提议「跑一个情绪向量探针，Anthropic 发的，可能是 j space 那篇或情绪向量那篇」。

## 论文判定（两篇都真实存在，Sol 记混的是同一作者的两篇）

**正主：《Emotion Concepts and their Function in a Large Language Model》**
Anthropic interpretability，2026-04，Transformer Circuits ＋ arXiv 2604.07729。
对 Claude Sonnet 4.5 找到 171 个情绪概念方向，验证因果影响行为
（偏好 Elo：blissful +212 / hostile −303；也影响 blackmail/reward hacking/sycophancy 发生率）。
- https://transformer-circuits.pub/2026/emotions/index.html
- https://arxiv.org/abs/2604.07729

**J space：《Verbalizable Representations Form a Global Workspace in Language Models》**
Anthropic 2026-07。「即将被言语表达」的特征子空间，靠 Jacobian（J-lens）跨大语料平均算出。
- https://transformer-circuits.pub/2026/workspace/

**⚠️ 修正（9/12 18:33，Sol 提供线索后二次查证）**：初版侦查称「家用复现不可行」——
仅对「复现 Claude 上的原始结果」成立。方法本身已被移植到开源模型，且官方发了配套代码：
- anthropics/jacobian-lens —— **官方 companion code**（初版侦查漏抓）
- idhantgulati/j-lens —— qwen3.5-4B 上的最小实现＋可视化（尺寸对 5080 友好）
- WeZZard/jlens-qwen36 —— Qwen3.6-27B 4bit（Apple MLX 移植）
- LessWrong 复现帖：多人在 Qwen3.6-27B 复刻 verbal report / CKA 层带 / directed modulation
成本注意：J-lens 要梯度反传＋大语料平均，比情绪探针的纯前向 hook 重；4B 尺寸本机现实。

同源方法学谱系：Persona Vectors（Anthropic 2025, arXiv 2507.21509，人格特质版，
官方代码 github.com/safety-research/persona_vectors，已在 Qwen2.5-7B-Instruct 验证）；
Representation Engineering（Zou 2023, arXiv 2310.01405，奠基作，LAT 情绪实验在 LLaMA-2-13B）。

## 方法配方（情绪论文原文，五步）

1. 171 个情绪词 × 100 主题 × 12 篇短故事 ≈ 20,400 篇（模型自产，抽样人工核验）
2. 激活：约 2/3 深度层的残差流，故事第 50 token 起全 token 平均池化
3. 方向：**差分均值**（该情绪激活均值 − 跨情绪总均值），再投影减掉中性集前 50% 主成分降噪。
   另训逻辑回归线性探针仅作对照
4. 读出：目标位置残差流对方向投影，强度按「相对残差流平均模长比例」表示
5. Steering：同批中间层注入 0.5×平均模长（该系数为 Sonnet 4.5 尺度，小模型须重扫）

## 本地方案（RTX 5080 16GB / 32GB RAM）

- **Ollama 确认不暴露激活**，只能当聊天出口；正路 HF transformers ＋ pytorch forward hooks
  （或 TransformerLens，但对 Qwen2.5/3、gpt-oss 的验证程度未确认，须实测）
- 首选 **Qwen2.5-7B-Instruct bf16**（权重 ~14GB 恰好塞进 16GB；persona_vectors 官方代码
  就在它上面跑过，骨架直接可抄）
- 备选 Qwen3-8B / Qwen2.5-14B（int4/8，量化噪声非首选）；gemma、deepseek-r1:8b 留作跨模型对比
- **gpt-oss-20b 排最后**：MoE（21B 总/3.6B 激活）＋MXFP4 新格式，激活语义不干净、
  toolchain 风险最高

## 可抄代码

- safety-research/persona_vectors —— 官方，工程质量最高，换情绪词表即用
- drgzkr/EmoVecLLM —— 与论文流程最贴的社区复现（TransformerLens，10 个 notebook）
- Aurora-cx/EmotionCircuits-LLM —— 纯 torch，16GB 推荐配置，quick_start.py 一键，最易跑通
- ewernn/traitinterp —— 覆盖模型最广（含 GPT-OSS），默认配置按 70B 写，须砍小

## 最小实验设计

4 情绪（happy/sad/angry/fearful）＋中性基线，各 ~40 条故事；**全层扫描**画
层×情绪投影热图（勿直接锁 2/3 层）；差分均值为主、sklearn 逻辑回归对照；
挑信噪比最好的 1–2 层做 steering（±0.3/0.6/1.0 档人工读输出）。
工作量：抄骨架 1–2 天出第一版热图＋steering；从零手写 3–5 天。

## 不确定项（侦查兵如实申报）

- 主方法是否含 SAE：二手博客说 SAE，arXiv 原文写差分均值——倾向信原文，动手前翻原文 2.2 节
- blackmail 具体百分比（22%→72% 之类）是二手转述，未直接核图
- TransformerLens 对 Qwen 各代/gpt-oss 支持程度未权威确认
- gpt-oss-20b 16GB 激活提取无实测报告（最高风险项）
- steering 系数 0.5 是 Sonnet 尺度，7B 须重新扫
- 论文效果在开源小模型上无官方验证，社区复现 r=0.63（vs 原文 0.85），预期打折
