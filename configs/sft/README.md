# SFT configuration

Do not edit `single_skill.example.yaml` into a machine-specific config. Copy it
to a run-specific name, for example:

```bash
cp configs/sft/single_skill.example.yaml \
  configs/sft/S2_two_base_tanks_seed1.yaml
```

Resolve these fields on the training server before launching:

- `model_name_or_path`: local model path or model identifier;
- `template`: the matching LlamaFactory chat/tool template;
- `dataset` and `eval_dataset`: one fixed-Skill pair registered by
  `data/processed/<dataset>/dataset_info.json`;
- `bf16`/`fp16`: select the precision supported by the server GPU;
- `lora_target`: start with `all`, or specify verified module names;
- batch size, accumulation and maximum length according to available VRAM.

Keep `train_on_prompt: false` and `mask_history: true`. The dataset builder emits
one window per assistant tool-call target; earlier turns are context and only the
final target is supervised. Windows use one fixed policy: the current semantic
observation-to-`advance` cycle prefix plus one complete prior cycle. No
`advance` target is downsampled.

Do not train from the one-repetition pilot alone. It exists to validate SC2,
trajectory collection and the data path; collect enough successful episodes per
Skill to populate both the registered training and validation datasets.

The example starts at `cutoff_len: 8192`. This is not a universal safe value:
after selecting the Student model, audit lengths with its actual tokenizer and
template before treating the recipe as final.

Run the preflight before every new model/config combination:

```bash
python -m sc2bench_experiments sft-preflight \
  --config configs/sft/S2_two_base_tanks_seed1.yaml
```

Training is launched with `llamafactory-cli train <config.yaml>`. The example
intentionally contains `TBD` values so it cannot be mistaken for a validated
model-specific recipe.
