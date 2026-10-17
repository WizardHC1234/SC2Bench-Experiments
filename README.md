# SC2Bench Experiments

这是一个独立的 SC2Bench 实验工程。Teacher 数据采集支持在本机 Windows 运行，
SFT 和 Student 大模型服务仍放在
Linux GPU 服务器。Windows 已配置 DeepSeek-V4-Flash、Python 3.9、StarCraft II、
隔离的 SC2Bench 副本、固定对手风格采集与断点续跑。统一脚本入口见
[scripts/README.md](scripts/README.md)。

Windows 最短流程：

```bash
bash scripts/collection/check.sh
bash scripts/collection/test-one-game.sh
bash scripts/collection/run-teacher.sh --mode all
bash scripts/collection/status.sh
```

正式 Teacher 矩阵固定使用 `rush`、`timing`、`power`、`macro`、`air`
五种对手风格，在 `MediumHard` 和 `Hard` 两个难度下每格运行 20 局。
因此每个条件 200 局，`none` 加三个固定 Skill 共 800 局；四个条件共享同一组
20 个 simulator seeds。正式采集最大并发为 8，`RandomBuild` 不进入主矩阵。

服务器使用两套隔离环境：

- `.venv-sc2`（Python 3.9）：SC2Bench、Teacher + 固定 Skill 对局、轨迹处理；
- `.venv-sft`（Python 3.11）：LlamaFactory v0.9.5、PyTorch 与 Student LoRA SFT。

SC2Bench 由部署脚本克隆到 `platform/SC2Bench/` 并锁定提交。Linux 寻路扩展在临时目录编译，不改动平台源码。

## 服务器快速开始

完整前置条件见 [scripts/README.md](scripts/README.md)。准备 SC2 Linux 客户端和地图后执行：

```bash
cp .env.example .env
# 填写 SC2PATH、LLM_API_KEY、LLM_BASE_URL、LLM_MODEL

TORCH_INDEX_URL=https://download.pytorch.org/whl/<server-cuda> \
  bash scripts/setup/linux-all.sh

bash scripts/collection/check-linux.sh
bash scripts/collection/run-teacher-linux.sh configs/experiments/stage1_teacher_pilot.json --dry-run
```

先执行一个固定 Skill 的实机 smoke run：

```bash
bash scripts/collection/run-teacher-linux.sh \
  configs/experiments/stage1_teacher_pilot.json \
  --condition T1_two_base_tanks --execute
```

确认后执行全部条件并构建数据：

```bash
bash scripts/collection/run-teacher-linux.sh configs/experiments/stage1_teacher_pilot.json --execute
bash scripts/dataset/build-linux.sh
```

数据构建会先按完整 episode 划分，再把每个 tool-call 决策展开成一个有界多轮
上下文窗口。窗口按“环境 observation 到 `advance`”的语义决策周期截取，完整保留
query、普通动作和 `advance`，并固定保留前一个完整周期作为上下文。

复制并填写 SFT 配置，再训练：

```bash
cp configs/sft/single_skill.example.yaml \
  configs/sft/S2_two_base_tanks_seed1.yaml
# 填写 model_name_or_path、template、精度与显存相关字段
bash scripts/training/run-sft.sh configs/sft/S2_two_base_tanks_seed1.yaml
```

`stage1_teacher_pilot.json` 每个条件只有一次对局，只用于服务器链路验证，不能作为
正式 SFT 数据量。正式 Windows 采集由
`teacher_deepseek_v4_flash_fixed_styles_20_per_cell.json` 定义；训练前置检查会拒绝
空数据集或空验证集。

训练完成后，复制推理模板并直接启动 LlamaFactory 的 OpenAI-compatible API：

```bash
cp configs/inference/student_lora.example.yaml \
  configs/inference/S2_two_base_tanks_seed1.yaml
# 填写 model_name_or_path、template、adapter_name_or_path
bash scripts/training/serve-student.sh \
  configs/inference/S2_two_base_tanks_seed1.yaml
```

在同一节点的另一个终端先检查服务，再运行 Student 对局：

```bash
bash scripts/evaluation/check-student-api.sh
bash scripts/evaluation/run-student.sh \
  configs/experiments/stage1_student_pilot.json --dry-run
```

## 实验条件

- `T0`：Teacher，无 Skill；
- `T1_i`：Teacher + 固定 Skill_i；
- `S0`：未训练小模型；
- `S1`：等量无 Skill Teacher 数据训练；
- `S2_i`：Skill_i 数据训练，测试时移除 Skill；
- `S3_i`：S2_i 测试时重新提供完整 Skill；
- `MS1`：后续 Multi-Skill Controlled SFT，暂不引入 Router。

当前第一阶段只做单 Skill 内化，不实现 Skill Router。Student 的 OOD 评估以训练中
未见的难度、地图和对手种族为主，风格作为受控覆盖变量而不是随机扰动。

## 目录

```text
platform/SC2Bench/  服务器自动克隆的只读平台副本，不提交本仓库
platform/LlamaFactory/  锁定 v0.9.5 的训练框架，不提交本仓库
configs/            suite、Teacher 与 SFT 配置
configs/inference/  SFT adapter 与基础模型的 LlamaFactory 服务配置
skills/             实验固定 Skill、来源版本与 SHA256
src/                实验编排、数据清洗与审计代码
src/.../agents/     Teacher/Student 共用 SC2Bench tool-call 协议的封装
scripts/            按 collection、dataset、training、evaluation、setup 组织的 Bash 入口
runs/raw/           Teacher 原始对局记录
data/processed/     移除完整 Skill 文本后的 episode-level JSONL
checkpoints/        SFT checkpoint
analysis/           汇总表格与图形
```

## 数据与复现边界

- `.env`、API key 和请求头不会写入 manifest；
- 数据按完整 episode 划分，`enemy_truth` 不进入 Student 数据；
- Student 数据移除完整 Skill block，并生成 LlamaFactory `openai` 格式注册表；
- SFT 样本以单次决策为监督单位，窗口切分不跨 episode；
- 当前基线蒸馏动作/tool call，不把带 `tool_calls` 消息中的解释文本视为思维链监督；
- 正式批次保存 suite SHA256、平台 commit、Skill SHA256 和模型配置；
- Linux SC2 实机必须先通过 smoke run，fake backend 结果不能作为正式结果。
