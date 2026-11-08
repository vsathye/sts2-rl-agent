# v0.111.0 migration — in progress

The upstream simulator targeted **v0.107.1**. This branch uses the verified
Steam v0.111.0 assembly (build 24724944, commit 41cef1ea). It is **not yet a
validated v0.111.0 simulator** and has not been tested through the real-game bridge.

## Implemented so far

- Replaced the decompiled reference and regenerated card reference/pool data.
- Ported 64-bit xxHash seed hashing and xoshiro256** RNG with state round trips.
- Updated existing card numeric metadata and several reworked effects: Expect a
  Fight, Forgotten Ritual, Expertise, Well-Laid Plans, Outbreak, Haze, Tracking,
  Guiding Star, Eidolon, Sacrifice, Fuel, Hyperbeam, and Rocket Punch.
- Moved player-side Doom checks and Regen to the new end-of-turn phases.
- Added Abundance, Sidestep, Dowsing's five-unknown-room transformation,
  Ambergris, Dowsing Rod, and Neow's Sacrifice implementations. New relics are
  not yet integrated into the complete revised Neow offering logic.
- Implemented all 16 new multiplayer cards and eight supporting powers, with
  behavioral tests for ally targeting, instancing, copied-power choices, shared
  Frost block, exhaust history, and generated-card creator ownership.
- Fixed canonical generation/transform pools for cards in the shared v111 module.
- Changed Regalite, Diamond Diadem, Beautiful Bracelet, Toasty Mittens, and
  several relic/monster scalar values.
- Added simulator identity to training/evaluation artifacts. Checkpoint evaluation
  rejects missing or mismatched versions; old checkpoints must not silently run
  against different card normalization and RNG semantics.

## Evidence

- Complete regression suite: **4,961 passed / 0 failed / 0 skipped**.
  Saved output: `evidence/game_v0_111_0/regression_final.txt`.
- All **145 original failures resolved**, with per-case old-to-current test
  mappings in `regression_resolution.json`. The original failing checkpoint is
  retained in `regression_checkpoint.txt`; removed Grapple reference cases now
  explicitly test legacy IDs and exclusion from current generation.
- `40` focused migration and new multiplayer behavioral cases pass.
- RNG vectors come from compiling the unchanged reference MegaRandom C# source;
  wrapper tests consume those vectors, and integration tests use controlled RNG
  fixtures where a specific reward or encounter is the subject of the test.
- Card static and dynamic audits pass. The mapped monster-stat audit reports
  zero mismatches, with its incomplete mapping coverage recorded below.
- Refreshed random-policy checks: two combat episodes and one bounded run
  episode for each of five characters, with no exceptions or truncations.
- Simulator revision is `v111-migration-2`; checkpoints from earlier simulator
  revisions are rejected rather than silently evaluated with changed behavior.

These are mechanics checks. They do not establish game parity, policy quality,
or a competitive verdict. No long training run has been launched.

## Remaining work before claiming compatibility

1. Finish event/ancient offering changes, remaining monster behaviors, Inky,
   History Course, Scrape, rarity RNG changes, and patch-level bugfix audit.
2. Verify Dowsing quest-completion notifications, save/load persistence, temporary
   Focus interactions, and multiplayer ownership/extra-turn semantics.
3. Extend source audits: the monster audit maps only 69 of 117 reference models;
   its 48 unmapped models cannot be counted as verified.
4. Complete matched-state game/bridge checks before claiming compatibility,
   then retrain and evaluate on held-out seeds. Keep regression and smoke checks
   green as the remaining source audit is completed.

The branch intentionally records `validation_status=migration_in_progress`.
