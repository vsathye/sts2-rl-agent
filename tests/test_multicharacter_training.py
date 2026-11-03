"""Regression coverage for character mechanics and honest experiment boundaries."""
from dataclasses import replace

import numpy as np
import pytest

from sts2_env.characters import create_starting_deck, get_character
from sts2_env.core.enums import OrbType, PowerId
from sts2_env.gym_env.character_observation import (
    CHARACTERS, FEATURE_NAMES, encode_character_features,
)
from sts2_env.gym_env.combat_env import STS2CombatEnv
from sts2_env.gym_env.observation import encode_observation
from sts2_env.gym_env.run_env import STS2RunEnv, _BOSS_RELIC_START
from sts2_env.training import EnvConfig, evaluate, make_env


@pytest.mark.parametrize("character", CHARACTERS)
def test_character_starter_and_reproducible_reset(character):
    env = STS2CombatEnv(character_id=character, ascension_level=1)
    a, _ = env.reset(seed=9)
    assert env.combat.player.max_hp == get_character(character).starting_hp
    assert env.combat.ascension_level == 1
    actual = env.combat.hand + env.combat.draw_pile + env.combat.discard_pile
    assert sorted(c.card_id.name for c in actual) == sorted(
        c.card_id.name for c in create_starting_deck(character))
    b, _ = env.reset(seed=9)
    np.testing.assert_array_equal(a, b)


def test_character_features_react_to_mechanics_without_changing_legacy():
    env = STS2CombatEnv(character_id="Defect")
    env.reset(seed=8)
    combat = env.combat
    before = encode_character_features(combat, "Defect")
    legacy = encode_observation(combat)
    combat.orb_queue.channel(OrbType.DARK, combat)
    combat.player.apply_power(PowerId.FOCUS, 2)
    combat.enemies[0].apply_power(PowerId.POISON, 4)
    combat.enemies[0].apply_power(PowerId.DOOM, 7)
    after = encode_character_features(combat, "Defect")
    assert not np.array_equal(before, after)
    assert after[FEATURE_NAMES.index("focus")] == pytest.approx(0.1)
    assert after[FEATURE_NAMES.index("enemy.0.poison")] == pytest.approx(0.08)
    assert after[FEATURE_NAMES.index("enemy.0.doom")] == pytest.approx(0.14)
    idx = FEATURE_NAMES.index("orb.0.evoke")
    combat.orb_queue.orbs[0].on_passive(combat)
    assert encode_character_features(combat, "Defect")[idx] > after[idx]
    np.testing.assert_array_equal(legacy, encode_observation(combat))


def test_osty_and_orb_order_visible():
    env = STS2CombatEnv(character_id="Necrobinder")
    env.reset(seed=2)
    combat = env.combat
    before = encode_character_features(combat, "Necrobinder")
    combat.summon_osty(combat.player, 5)
    after = encode_character_features(combat, "Necrobinder")
    assert not np.array_equal(before, after)
    assert after[FEATURE_NAMES.index("osty.hp")] > 0
    defect = STS2CombatEnv(character_id="Defect")
    defect.reset(seed=2)
    combat = defect.combat
    combat.orb_queue.channel(OrbType.FROST, combat)
    combat.orb_queue.channel(OrbType.LIGHTNING, combat)
    before = encode_character_features(combat, "Defect")
    combat.orb_queue.orbs.reverse()
    assert not np.array_equal(before, encode_character_features(combat, "Defect"))


@pytest.mark.parametrize("mode", ("combat", "run"))
@pytest.mark.parametrize("character", CHARACTERS)
def test_character_wrapper_and_seed_split(mode, character):
    config = EnvConfig(mode=mode, character=character)
    env = make_env(config, range(5, 7))()
    legacy = make_env(replace(config, observation="legacy"))()
    obs, _ = env.reset()
    old, _ = legacy.reset(seed=5)
    np.testing.assert_array_equal(obs[:len(old)], old)
    assert env.observation_space.contains(obs)
    assert env.action_masks().any()
    second, _ = env.reset()
    expected, _ = legacy.reset(seed=6)
    np.testing.assert_array_equal(second[:len(expected)], expected)
    assert env.index == 2


def test_act_one_win_is_not_full_run_win():
    env = STS2RunEnv(act_count=1, strict_errors=True)
    env.reset(seed=2)
    env._mgr._enter_boss_relic()
    env._mgr._boss_relics = ["BLACK_STAR"]
    _, reward, terminated, truncated, info = env.step(_BOSS_RELIC_START)
    assert reward == 1 and terminated and not truncated
    assert info["curriculum_win"] and not info["full_run_win"]
    with pytest.raises(Exception, match="episode has ended"):
        env.step(0)


def test_simulation_exception_is_not_a_loss_in_strict_mode(monkeypatch):
    env = STS2RunEnv(strict_errors=True)
    env.reset(seed=3)
    env._mgr._enter_boss_relic()
    def fail(*args):
        raise RuntimeError("injected simulator error")
    monkeypatch.setattr(env, "_step_boss_relic", fail)
    with pytest.raises(RuntimeError, match="injected"):
        env.step(_BOSS_RELIC_START)


def test_timeouts_never_count_as_wins():
    report = evaluate(EnvConfig(max_steps=1), range(3))
    assert report["truncations"] == 3
    assert report["win_rate"] == 0
    assert report["full_run_wins"] == 0


def test_model_seed_cannot_escape_training_seed_split():
    config = EnvConfig(mode="combat")
    scheduled = make_env(config, range(5, 7))()
    reference = make_env(config)()
    obs, _ = scheduled.reset(seed=2_000_000)
    expected, _ = reference.reset(seed=5)
    np.testing.assert_array_equal(obs, expected)
