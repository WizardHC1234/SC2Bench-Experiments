# Data lifecycle

- `runs/raw/`: immutable SC2Bench batch/episode records produced by Teacher conditions.
- `data/processed/<dataset>/`: sanitized episode-level JSONL with the full Skill block removed from Student input.
- `data/manifests/`: optional promoted/frozen dataset manifests.

The dataset builder never reads `*.enemy_truth.json`. Split assignment is deterministic from `episode_id` and happens at episode granularity.

The formal Teacher collection is balanced over five fixed builtin AI styles
(`rush`, `timing`, `power`, `macro`, `air`) and two difficulties. `RandomBuild`
is not part of the primary SFT dataset.

Each processed dataset also contains:

- `dataset_info.json`: LlamaFactory registrations using `formatting: openai`;
- `llamafactory/<skill>/train.jsonl`: one fixed-Skill training set;
- matching `validation.jsonl` and `test.jsonl` files.

SC2Bench's loop emits `assistant -> tool receipt -> next environment observation`.
The LlamaFactory view defines one semantic decision cycle from an environment
observation through the assistant's closing `advance`. It emits one supervised
sample for every assistant tool-call turn inside that cycle. Query calls, staged
actions and every `advance` are retained exactly once. Each sample contains the
current cycle prefix plus a bounded number of complete prior cycles. Episode
splitting happens before window expansion, so windows from one game cannot cross
dataset splits. The original sanitized episode JSONL remains unchanged.

## Baseline semantics

This first baseline distills the Teacher's tool-call decisions. SC2Bench's raw
session remains intact, including assistant content, so later data treatments do
not require recollecting Teacher games.

The one-repetition pilot suite is only a collection and wiring smoke test. A
per-Skill SFT run needs enough successful episodes for non-empty train and
validation splits; `sft-preflight` rejects an empty registered split.

