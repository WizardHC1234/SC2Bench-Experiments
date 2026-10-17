# Platform dependency

`server/bootstrap-collection.sh` creates a clean, commit-pinned SC2Bench checkout
at `platform/SC2Bench/`. The checkout is ignored by this repository and treated
as read-only experiment infrastructure.

The Linux native pathfinding extension is compiled in temporary build copies and
installed into `.venv-sc2`; the binary is not written into the platform checkout.
The source path can still be overridden with `SC2EXP_PLATFORM_SOURCE`.

`sc2exp doctor` verifies:

- source path and expected Git commit;
- clean-worktree status (a dirty server checkout fails validation);
- imports for `sc2bench_env` and the repository example `agents.llm_agent`;
- availability of the configured suite and Skill files.

The platform Git commit is locked in `configs/platform.json`. Change that lock
only as a deliberate platform-version experiment, not as part of a normal run.

The SFT bootstrap separately clones LlamaFactory into `platform/LlamaFactory/`
and checks out release `v0.9.5`. It is training infrastructure, not part of the
SC2Bench platform checkout.

