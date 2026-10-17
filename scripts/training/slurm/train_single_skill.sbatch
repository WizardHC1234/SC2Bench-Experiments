#!/usr/bin/env bash
#SBATCH --job-name=sc2bench-sft
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=runs/logs/slurm-%j.out

set -euo pipefail

# Edit these values for the target cluster.
PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
CONFIG="${CONFIG:-configs/sft/S2_two_base_tanks_seed1.yaml}"

cd "${PROJECT_ROOT}"
source .venv-sft/bin/activate
python -m sc2bench_experiments sft-preflight --config "${CONFIG}"
llamafactory-cli train "${CONFIG}"

