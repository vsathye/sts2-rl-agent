"""RNG parity tests for the game's seeded random wrapper."""

import json
from pathlib import Path
import xxhash

VECTORS = json.loads((Path(__file__).parents[1] / "docs/evidence/game_v0_111_0/mega_random_vectors.json").read_text())
MASK64 = (1 << 64) - 1
def reference_seed(seed, name):
    return (seed + xxhash.xxh64_intdigest(name.encode())) & MASK64

from sts2_env.core.rng import Rng, deterministic_hash_code
from sts2_env.events.shared import AromaOfChaos, PunchOff
from sts2_env.run.run_state import RunRngSet
from sts2_env.run.run_state import RunState


def test_rng_seeded_next_matches_csharp_random_sequence():
    rng = Rng(0)
    row = next(row for row in VECTORS if row["seed"] == 0)
    assert [rng.next_int(0, 2_147_483_646) for _ in range(5)] == row["ints"][:5]
    assert rng.counter == 5


def test_named_rng_streams_match_game_seed_derivation():
    seed = deterministic_hash_code("42")

    assert RunRngSet(42).seed == seed
    assert Rng(seed, "up_front").seed == reference_seed(seed, "up_front")
    assert Rng(seed, "shuffle").seed == reference_seed(seed, "shuffle")
    assert Rng(seed, "combat_card_generation").seed == reference_seed(seed, "combat_card_generation")
    assert Rng(seed, "combat_potion_generation").seed == reference_seed(seed, "combat_potion_generation")
    assert Rng(seed, "combat_card_selection").seed == reference_seed(seed, "combat_card_selection")
    assert Rng(seed, "combat_energy_costs").seed == reference_seed(seed, "combat_energy_costs")
    assert Rng(seed, "combat_targets").seed == reference_seed(seed, "combat_targets")
    assert Rng(seed, "monster_ai").seed == reference_seed(seed, "monster_ai")
    assert Rng(seed, "combat_orbs").seed == reference_seed(seed, "combat_orbs")
    assert Rng(seed, "treasure_room_relics").seed == reference_seed(seed, "treasure_room_relics")
    assert Rng(seed + 1, "rewards").seed == reference_seed(seed + 1, "rewards")
    assert Rng(seed + 1, "shops").seed == reference_seed(seed + 1, "shops")
    assert Rng(seed + 1, "transformations").seed == reference_seed(seed + 1, "transformations")
    assert Rng(seed, "act_1_map").seed == reference_seed(seed, "act_1_map")
    assert Rng(seed, "spoils_map").seed == reference_seed(seed, "spoils_map")


def test_run_rng_set_exposes_game_named_streams():
    streams = RunRngSet(42)

    assert streams.up_front.seed == reference_seed(streams.seed, "up_front")
    assert streams.shuffle.seed == reference_seed(streams.seed, "shuffle")
    assert streams.combat_card_generation.seed == reference_seed(streams.seed, "combat_card_generation")
    assert streams.combat_potion_generation.seed == reference_seed(streams.seed, "combat_potion_generation")
    assert streams.combat_card_selection.seed == reference_seed(streams.seed, "combat_card_selection")
    assert streams.combat_energy_costs.seed == reference_seed(streams.seed, "combat_energy_costs")
    assert streams.combat_targets.seed == reference_seed(streams.seed, "combat_targets")
    assert streams.monster_ai.seed == reference_seed(streams.seed, "monster_ai")
    assert streams.combat_orbs.seed == reference_seed(streams.seed, "combat_orbs")
    assert streams.treasure_room.seed == reference_seed(streams.seed, "treasure_room_relics")
    assert streams.rewards.seed == reference_seed(streams.seed + 1, "rewards")
    assert streams.shops.seed == reference_seed(streams.seed + 1, "shops")
    assert streams.transformations.seed == reference_seed(streams.seed + 1, "transformations")


def test_event_rng_seed_matches_game_event_derivation():
    run_state = RunState(seed=42, character_id="Ironclad")

    aroma = AromaOfChaos()
    punch = PunchOff()

    assert aroma.event_entry() == "AROMA_OF_CHAOS"
    assert aroma.create_event_rng(run_state).seed == reference_seed(run_state.rng.seed + run_state.player.player_id, "AROMA_OF_CHAOS")
    assert punch.event_entry() == "PUNCH_OFF"
    assert punch.create_event_rng(run_state).seed == reference_seed(run_state.rng.seed, "PUNCH_OFF")


def test_shuffle_uses_csharp_fisher_yates_sequence():
    values = [1, 2, 3, 4, 5]
    expected = values.copy()
    row = next(row for row in VECTORS if row["seed"] == 42)
    for index, sample in zip(range(4, 0, -1), row["doubles"]):
        swap = int(sample * (index + 1))
        expected[index], expected[swap] = expected[swap], expected[index]
    rng = Rng(42)
    rng.shuffle(values)
    assert values == expected
    assert rng.counter == 4
