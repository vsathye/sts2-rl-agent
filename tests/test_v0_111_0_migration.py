"""v0.111.0 regression cases; vectors come from the compiled C# reference."""
import json
from pathlib import Path
import pytest
from sts2_env.cards.factory import create_card
from sts2_env.core.enums import CardId, PowerId, CombatSide, CardType
from sts2_env.core.rng import Rng
from sts2_env.core.hooks import fire_after_turn_end
from tests.test_necrobinder_parity import _make_combat

VECTORS = json.loads((Path(__file__).parents[1] / "docs/evidence/game_v0_111_0/mega_random_vectors.json").read_text())

@pytest.mark.parametrize("row", VECTORS, ids=lambda row: str(row["seed"]))
def test_mega_random_matches_compiled_reference(row):
    rng = Rng(row["seed"])
    assert [rng.next_int_exclusive(0, 2147483647) for _ in range(8)] == row["ints"]
    rng = Rng(row["seed"])
    assert [rng.next_double() for _ in range(8)] == row["doubles"]
    rng = Rng(row["seed"])
    assert [rng.next_unsigned_long() for _ in range(8)] == row["ulongs"]
    saved = rng.to_serializable()
    resumed = Rng(0)
    resumed.load_from_serializable(saved)
    assert [resumed.next_unsigned_long() for _ in range(20)] == [rng.next_unsigned_long() for _ in range(20)]
    assert resumed.counter == rng.counter == 28


def play(combat, card_id, upgraded=False):
    card = create_card(card_id, upgraded)
    card.owner = combat.player
    combat.hand = [card]
    combat.energy = 10
    assert combat.play_card(0)
    return card


def test_sidestep_defers_energy_to_next_turn():
    combat = _make_combat()
    play(combat, CardId.SIDESTEP, True)
    assert combat.energy == 10
    assert combat.player.get_power_amount(PowerId.ENERGY_NEXT_TURN) == 2


def test_expect_a_fight_scales_block_with_strength():
    combat = _make_combat()
    combat.player.apply_power(PowerId.STRENGTH, 3)
    card = create_card(CardId.EXPECT_A_FIGHT)
    play(combat, CardId.EXPECT_A_FIGHT)
    assert combat.player.block == card.effect_vars["calc_base"] + 3 * card.effect_vars["calc_extra"]
    assert combat.player.get_power_amount(PowerId.NO_ENERGY_GAIN) == 0


def test_fuel_no_longer_draws():
    combat = _make_combat()
    before = list(combat.draw_pile)
    play(combat, CardId.FUEL)
    assert combat.draw_pile == before
    assert not combat.hand


def test_hyperbeam_focus_penalty_expires():
    combat = _make_combat()
    combat.enemies[0].current_hp = combat.enemies[0].max_hp = 1000
    combat.player.apply_power(PowerId.FOCUS, 5)
    play(combat, CardId.HYPERBEAM)
    assert combat.player.get_power_amount(PowerId.FOCUS) == 2
    fire_after_turn_end(CombatSide.PLAYER, combat)
    assert combat.player.get_power_amount(PowerId.FOCUS) == 5


def test_abundance_offers_three_upgraded_powers():
    combat = _make_combat()
    play(combat, CardId.ABUNDANCE)
    choice = combat.pending_choice
    assert choice is not None
    assert len(choice.options) == 3
    assert all(c.card_type is CardType.POWER and c.upgraded for c in [o.card for o in choice.options])


def test_old_checkpoints_are_not_silently_accepted():
    from sts2_env.game_version import require_compatible_manifest, simulator_identity
    with pytest.raises(ValueError, match="Checkpoint"):
        require_compatible_manifest({"config": {}})
    with pytest.raises(ValueError, match="Checkpoint"):
        require_compatible_manifest({"simulator": {"game_version": "0.107.1"}})
    require_compatible_manifest({"simulator": simulator_identity()})


def test_dowsing_transforms_after_five_unknown_visits():
    from sts2_env.cards.v111 import advance_dowsing
    from sts2_env.run.run_state import RunState
    player = RunState(seed=42, character_id="Silent").player
    player.add_card_to_deck("Dowsing")
    quest = next(c for c in player.deck if c.card_id is CardId.DOWSING)
    for _ in range(4):
        advance_dowsing(player)
    assert quest.card_id is CardId.DOWSING
    assert quest.effect_vars["rooms"] == 1
    advance_dowsing(player)
    assert quest.card_id is CardId.ABUNDANCE


def test_ambergris_heals_and_consumes_one_extra_turn():
    from sts2_env.potions.base import create_potion
    from sts2_env.core.hooks import should_take_extra_turn, fire_after_taking_extra_turn
    combat = _make_combat()
    combat.player.current_hp = 10
    create_potion("Ambergris").use(combat, combat.player)
    assert combat.player.current_hp == 45
    assert should_take_extra_turn(combat)
    fire_after_taking_extra_turn(combat)
    assert not should_take_extra_turn(combat)


def test_regalite_triggers_once_until_owner_turn_start():
    from sts2_env.relics.registry import create_relic
    from sts2_env.relics.base import RelicId
    combat = _make_combat()
    relic = create_relic(RelicId.REGALITE)
    card = create_card(CardId.SOUL)
    card.owner = combat.player
    for _ in range(3):
        relic.after_card_generated_for_combat(combat.player, card, True, combat)
    assert combat.player.block == 4
    relic.before_side_turn_start(combat.player, CombatSide.PLAYER, combat)
    relic.after_card_generated_for_combat(combat.player, card, True, combat)
    assert combat.player.block == 8


@pytest.mark.parametrize("upgraded,poison,weak", [(False, 4, 1), (True, 6, 2)])
def test_haze_applies_both_reference_debuffs(upgraded, poison, weak):
    combat = _make_combat()
    enemy = combat.enemies[0]
    play(combat, CardId.HAZE, upgraded)
    assert enemy.get_power_amount(PowerId.POISON) == poison
    assert enemy.get_power_amount(PowerId.WEAK) == weak


@pytest.mark.parametrize("upgraded,poison", [(False, 9), (True, 12)])
def test_outbreak_applies_and_triggers_poison(upgraded, poison):
    combat = _make_combat()
    enemy = combat.enemies[0]
    enemy.max_hp = enemy.current_hp = 1000
    play(combat, CardId.OUTBREAK_CARD, upgraded)
    assert enemy.current_hp == 1000 - poison
    assert enemy.get_power_amount(PowerId.POISON) == poison - 1


def test_eidolon_plays_only_ethereal_cards_from_exhaust():
    combat = _make_combat()
    enemy = combat.enemies[0]
    enemy.max_hp = enemy.current_hp = 1000
    ethereal = create_card(CardId.STRIKE_NECROBINDER)
    ethereal.owner = combat.player
    ethereal.keywords = frozenset({"ethereal"})
    ordinary = create_card(CardId.STRIKE_NECROBINDER)
    ordinary.owner = combat.player
    state = combat.combat_player_state_for(combat.player)
    state.exhaust[:] = [ethereal, ordinary]
    play(combat, CardId.EIDOLON)
    assert enemy.current_hp == 1000 - ethereal.base_damage
    assert ordinary in state.exhaust
    assert ethereal not in state.exhaust
