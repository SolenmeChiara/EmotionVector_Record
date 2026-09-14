# 在 Windows 侧跑模型（避开 WSL 显存/内存爆炸）

2026-09-13 建立。起因：9/12 夜里在 WSL 内用 `--8bit` 加载 `google/gemma-4-E4B-it`，
vmmemWSL 涨到 34 GB 吃光宿主 commit，Hyper-V 连报两次 Fatal machine check。
结论：模型加载改到 Windows 原生跑，WSL 只当遥控器。

## 环境

- venv：`<repo-root>\.venv-win`（CPython 3.12.11，uv 建）
- 解释器：`<repo-root>/.venv-win/Scripts/python.exe`
- torch 2.11.0+cu128，RTX 5080 Laptop（sm_120）实测 `cuda.is_available() == True`
- 包版本与 WSL 侧 `~/venvs/probe` 完全对齐（transformers 5.17.0 / accelerate 1.15.0 /
  bitsandbytes 0.50.2 / numpy 2.5.3 / scikit-learn 1.9.1 / scipy 1.18.1 / matplotlib 3.11.2）
- HF 缓存两边共用：`core/common.py` 读 `HF_HOME`，没设就退回仓库同级的 `hf-cache/`。
  想让 Windows 和 WSL 共用同一批权重，就把两边的 `HF_HOME` 指到同一个物理目录
  （Windows 写 `<drive>:/hf-cache`，WSL 写对应的 `/mnt/<drive>/hf-cache`），不用重下。

## 环境变量怎么传（已实测三种，只有一种能用）

WSL shell 里 `export` 的变量**不会**进 Windows 的 .exe。实测：

| 写法 | 结果 |
|---|---|
| `HF_HUB_DISABLE_XET=1 python.exe ...` | ✗ 进程里读到 `None` |
| `HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET python.exe ...` | ✓ 读到 `1` |
| `cmd.exe /c "set X=1 && python.exe -c \"...\""` | ✗ 引号被 cmd 吃掉，语法炸 |

**用 WSLENV 那行。** 多个变量用冒号分隔：`WSLENV=HF_HUB_DISABLE_XET:HF_HOME`。

## 调用约定

- 解释器和脚本路径都写 **Windows 式**（`<drive>:/...`），写 WSL 式的 `/mnt/<drive>/...` 会静默失败
- 必须加 `-X utf8`，否则控制台按 GBK 编码，中文/emoji 直接抛异常
- cwd 会自动翻译：从 `<repo-root>` 起步时，
  Windows 进程的 cwd 就是 `<repo-root>`，
  所以 `--out data/xxx.npz` 这种相对路径照常可用（已验证）

## 现成命令

先定义个短名字（每个新 shell 都要重定义，或者写进 ~/.bashrc）：

```bash
WINPY='<repo-root>/.venv-win/Scripts/python.exe'
CORE='<repo-root>/core'
cd <repo-root>
```

### Gemma-4-E4B steering（明天要跑的那一条）

```bash
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 "$CORE/steer.py" \
  --model google/gemma-4-E4B-it --8bit \
  --directions data/directions_gemma4.npz \
  --metrics results/metrics_gemma4.json \
  --layers 14,40 --n-prompts 2 \
  --out results/steering_samples_gemma4.md
```

长跑，建议丢后台再去干别的。

### 激活提取

```bash
HF_HUB_DISABLE_XET=1 WSLENV=HF_HUB_DISABLE_XET \
  "$WINPY" -X utf8 "$CORE/extract.py" \
  --model google/gemma-4-E4B-it --8bit --out data/acts_gemma4.npz
```

### analyze.py 不碰 GPU

纯 CPU + sklearn/matplotlib，WSL 侧 `~/venvs/probe` 跑就行，没必要换边。
真要在 Windows 跑也一样（`"$WINPY" -X utf8 "$CORE/analyze.py" --acts ... --tag ...`，已验证 `--help` 通）。

## 已知坑

- **triton 没有 Windows wheel**，导入 torch 时会打一行
  `triton not found; flop counting will not work`。本项目只用前向 hook，不用
  `torch.compile`，无影响。bitsandbytes 的 8bit 走自带 CUDA kernel，已单测通过
  （随机 `nn.Linear(256,256)` 量化后前向，相对误差 0.008）。
- bitsandbytes 只验了 **8bit（LLM.int8）**，4bit（NF4）路径没测。
- 真实模型加载从没在 Windows 侧跑过（今晚宿主内存紧张，刻意没试）。
  首次跑请盯着任务管理器的「提交」看一眼，不对劲就 Ctrl-C。
- 别往 `C:\Python313` 装东西，那是系统 python；也别动 `~/venvs/probe`。

## 跑前先给显卡腾位（2026-09-13 补）

这台机器上还有别的常驻服务跟探针实验抢同一张 16 GB 卡。其中一个每次被调用都会让 Ollama
把 `qwen3-embedding:4b` 和 `gemma4:e4b` 装进显卡（合计约 14 GB）。9/12 两次 WSL 崩溃就是两份
Gemma 同时上卡、显存溢到宿主内存。在 Windows 侧跑之前先卸掉：

```bash
# Ollama 的默认安装路径里带 Windows 账户名，换成你自己的
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop gemma4:e4b
/mnt/c/Users/<username>/AppData/Local/Programs/Ollama/ollama.exe stop qwen3-embedding:4b
```

跑的期间别去碰那个服务（每次调用都会把模型重新拉上卡）。同一张卡上另有一个常驻服务占着约 1.9 GB 显存。
