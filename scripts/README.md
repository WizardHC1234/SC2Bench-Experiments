# Scripts

所有操作入口按实验阶段组织，不再按 `windows/` 和 `server/` 分成两套目录。

```text
scripts/
├── collection/   Teacher 对局采集、检查和状态
├── dataset/      SFT 数据构建
├── training/     LlamaFactory SFT、Student 服务和 Slurm
├── evaluation/   Student API 检查与对局验证
├── setup/        Windows/Linux 环境安装
└── lib/          脚本共用函数
```

## 当前 Windows Teacher 采集

在项目根目录的 Git Bash 中执行：

```bash
bash scripts/collection/check.sh
bash scripts/collection/test-one-game.sh --condition T1_two_base_tanks --force-rerun
bash scripts/collection/run-teacher.sh --mode all
bash scripts/collection/status.sh
```

正式配置对 `none`、`marine-rush`、`two-base-tanks` 和
`battle-cruisers` 分别运行：

```text
2 个难度（MediumHard、Hard）
× 5 个固定风格（rush、timing、power、macro、air）
× 每格 20 局
= 每个条件 200 局，总计 800 局
```

四个条件共享同一组 20 个 simulator seeds，正式配置最大并发为 8。
`run-teacher.sh` 默认断点续跑，正式采集不要添加 `--force-rerun`。
`RandomBuild` 不进入正式主矩阵。

构建数据：

```bash
bash scripts/dataset/build.sh
```

## Linux 服务器

环境安装：

```bash
TORCH_INDEX_URL=https://download.pytorch.org/whl/<server-cuda> \
  bash scripts/setup/linux-all.sh
```

如果服务器也承担 SC2 采集：

```bash
bash scripts/collection/check-linux.sh
bash scripts/collection/run-teacher-linux.sh \
  configs/experiments/stage1_teacher_pilot.json --dry-run
bash scripts/dataset/build-linux.sh
```

LlamaFactory SFT：

```bash
bash scripts/training/run-sft.sh configs/sft/S2_two_base_tanks_seed1.yaml
```

Student 服务与验证：

```bash
bash scripts/training/serve-student.sh \
  configs/inference/S2_two_base_tanks_seed1.yaml

bash scripts/evaluation/check-student-api.sh
bash scripts/evaluation/run-student.sh \
  configs/experiments/stage1_student_pilot.json --dry-run
```
