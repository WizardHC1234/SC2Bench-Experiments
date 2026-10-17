# Skills

Stage 1 first reads fixed Terran Skills from this directory. Each experiment
manifest stores the canonical Skill id, source revision and SHA256 of its text.

The initial three files are text-identical snapshots from the pinned SC2Bench
commit recorded in `manifest.json`. They make collection reproducible even when
the platform checkout is installed later on the server.

Do not edit the platform Skill files for an experiment. If a new or revised
Skill is required, place it here, give it a new experiment-visible id/revision,
and update its SHA256 in `manifest.json`. The registry uses experiment Skills
first and falls back to the pinned platform for other built-in names.

