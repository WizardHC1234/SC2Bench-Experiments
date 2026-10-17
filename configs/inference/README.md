# Student inference configuration

Copy `student_lora.example.yaml` to a run-specific file after SFT. Keep
`model_name_or_path` and `template` identical to the training configuration,
and set `adapter_name_or_path` to that run's LoRA output directory.

```bash
cp configs/inference/student_lora.example.yaml \
  configs/inference/S2_two_base_tanks_seed1.yaml
```

For the untrained `S0` base-model condition, make a separate copy and remove
`adapter_name_or_path`. Do not overwrite an SFT serving config to switch
conditions; separate files make the evaluated checkpoint explicit.

The default `huggingface` backend works with the base LlamaFactory installation.
`vllm` can be selected later, but it requires its own compatible installation
and should be treated as a server-specific optimization rather than part of the
baseline recipe.
