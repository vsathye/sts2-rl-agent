# Multi-character experiments in this fork

This fork adds per-character experiments for Ironclad, Silent, Defect,
Necrobinder, and Regent. It does not establish trained performance or real-game
parity. Upstream's advertised ~92% result is **single Act 1 combat** performance,
not a full Ascension 1 run. These are distinct metrics.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,train]'
```

Use a fresh output directory for every run; the trainer refuses to overwrite one.
CPU is the default. `--device mps` is optional on Apple Silicon. Set `--threads`
and `--n-envs` explicitly to bound CPU use; both default to one.

## First verify mechanics

```bash
python -m pytest tests/test_multicharacter_training.py -q
python scripts/evaluate_characters.py --mode combat --episodes 10 --output output/combat-smoke.json
python scripts/evaluate_characters.py --mode run --episodes 10 --max-steps 2000 --output output/run-smoke.json
```

These commands use a masked random policy, cover all five characters, and record
every episode, seed, timeout, floor, and result. A simulator exception aborts the
experiment rather than becoming an ordinary loss. They are mechanics checks only.

## Ironclad control and character trials

The legacy observation and no-relic combat setup remain available to attempt an
upstream-style Ironclad reproduction. No upstream checkpoint has been reproduced
by this change. Current upstream content and corrected evaluation may differ from
the original advertised experiment.

```bash
python scripts/train_combat.py --character Ironclad --observation legacy --total-timesteps 500000 --output-dir output/ironclad-legacy
```

For a character-aware combat comparison, give every character the same budget
and the same starting-relic setting. Include Ironclad as the control:

```bash
for character in Ironclad Silent Defect Necrobinder Regent; do
  python scripts/train_combat.py --character "$character" --starting-relic --total-timesteps 100000 --output-dir "output/combat-$character-seed0"
done
```

Starting relics are opt-in for standalone combats to preserve the old benchmark.
Full runs always use the character's normal starting relic. All standalone
combats sample upstream's Act 1 encounter pool with starter decks, not decks
acquired through progression.

Run-level experiments use the same character interface:

```bash
python scripts/train_full_run.py --character Silent --ascension 0 --act-count 1 --total-timesteps 100000 --output-dir output/silent-act1-seed0
```

Repeat for each character with equal budgets and then with `--seed 1` and
`--seed 2` in separate directories before judging learning. Test A1 with
`--ascension 1`; `--act-count 3` targets a full three-act run. These commands are
examples, not evidence that a budget is sufficient. There is no automatic launch
of long experiments.

`--act-count 1` ends successfully after the first boss reward chain transitions
to the next act; `2` similarly caps after two acts. These are `curriculum_win`,
never `full_run_win`. Combat results use `combat_win`. Rewards are sparse +1/-1;
the stale `--reward-shaping` flags were removed rather than silently ignored.

## Evaluation and reproducibility

Training samples only a fixed seed range [0, `--train-seeds`). Validation uses
[1000000, 1000000 + `--eval-episodes`), reset for each mask-aware callback. Final
evaluation and its paired random baseline use [2000000, 2000000 +
`--test-episodes`). The model's `--seed` controls initialization and PPO sampling.
These are environment reset seeds; environments deterministically derive game
seeds from them. Seed ranges do not overlap.

Each output directory contains:

- `manifest.json`: environment, all arguments, code revision/dirty status,
  observation dimensions, feature names, and seed ranges.
- `best_model/best_model.zip`: selected only by validation reward.
- `final_model.zip`: final weights; final test reports explicitly refer to these.
- `test.json` and `random_baseline.json`: paired held-out episode results.

PPO rounds requested timesteps up to a rollout boundary; reports include actual
timesteps. Keep `n_steps * n_envs` equal across comparisons. Timeouts remain
losses and are counted separately. The evaluation reports are descriptive;
small smoke samples are not performance estimates.

Reload a saved model:

```bash
python scripts/evaluate_characters.py --checkpoint output/silent-act1-seed0/final_model.zip --manifest output/silent-act1-seed0/manifest.json --characters Silent --episodes 100 --output output/silent-evaluation.json
```

For checkpoint evaluation, the manifest's environment configuration is
authoritative (including step cap and ascension); `--characters` can explicitly
probe transfer to other characters. The report records the trained character.
Use a new seed range for a fresh test after tuning; don't tune on final seeds.

## Observation contract and remaining gaps

`legacy` keeps upstream observation dimensions and feature order. The trainers
default to `character-v1`, which appends character identity, Focus, orb capacity,
ordered orb types and passive/evoke values (including accumulated Dark charge),
Osty alive/HP/max-HP/block, and per-enemy poison/doom. Existing Stars and hand
card damage features remain in the legacy prefix. Append-only dimensions are
not compatible with old network weights: retrain when changing schemas.

The extension is **simulator-only**. The C# bridge and its state adapter still
emit the legacy format. A character-v1 checkpoint requires corresponding bridge
serialization and parity tests before real-game use. Loading it with a legacy
environment fails the model's shape check.

This is still a compact, partially observed policy. Noncombat option content,
complete deck/relic contents, pending-choice content, and many powers are not
fully represented. Adding four mechanics does not solve those representation
gaps or validate simulator fidelity. Favor a controlled combat comparison first;
use full-run results as diagnostics until those gaps are addressed.

## Recorded validation

[Validation summary](evidence/multicharacter_validation.json) records 4,862
upstream tests and 21 new regressions, ten 32-step PPO trials, a final two-worker
A1 trial, checkpoint reload equality, and 100 A1 random-policy episodes.
The legacy 1,000-combat benchmark produced exactly the same 21,845 steps and
291 wins as the unmodified upstream environment on the same seeds. This checks
compatibility, not the advertised trained policy performance.
