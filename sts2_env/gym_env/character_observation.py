"""Versioned simulator-only character features; legacy observations stay unchanged."""
from __future__ import annotations

import gymnasium as gym
import numpy as np

from sts2_env.core.constants import MAX_ENEMIES
from sts2_env.core.enums import OrbType, PowerId
from sts2_env.orbs.base import OrbQueue

CHARACTERS = ("Ironclad", "Silent", "Defect", "Necrobinder", "Regent")
ORB_TYPES = tuple(OrbType)
FEATURE_NAMES = (
    [f"character.{c}" for c in CHARACTERS]
    + ["focus", "orb_capacity"]
    + [f"orb.{i}.{field}" for i in range(OrbQueue.MAX_CAPACITY)
       for field in [*[t.name for t in ORB_TYPES], "passive", "evoke"]]
    + ["osty.present", "osty.hp", "osty.max_hp", "osty.block"]
    + [f"enemy.{i}.{field}" for i in range(MAX_ENEMIES) for field in ("poison", "doom")]
)
OBSERVATION_VERSION = "character-v1"


def encode_character_features(combat, character: str) -> np.ndarray:
    """Encode public mechanics without peeking at hidden pile order or RNG."""
    values = np.zeros(len(FEATURE_NAMES), dtype=np.float32)
    values[CHARACTERS.index(character)] = 1
    if combat is None:
        return values
    idx = len(CHARACTERS)
    values[idx] = combat.player.get_power_amount(PowerId.FOCUS) / 20
    queue = combat.orb_queue
    values[idx + 1] = queue.capacity / OrbQueue.MAX_CAPACITY if queue else 0
    idx += 2
    orbs = queue.orbs if queue else []
    if len(orbs) > OrbQueue.MAX_CAPACITY:
        raise ValueError("Orb queue exceeds character-v1 capacity")
    for i in range(OrbQueue.MAX_CAPACITY):
        if i < len(orbs):
            orb = orbs[i]
            values[idx + ORB_TYPES.index(orb.orb_type)] = 1
            values[idx + len(ORB_TYPES)] = orb.get_passive_value(combat) / 50
            values[idx + len(ORB_TYPES) + 1] = orb.get_evoke_value(combat) / 50
        idx += len(ORB_TYPES) + 2
    osty = combat.osty
    if osty is not None:
        values[idx:idx + 4] = [float(osty.is_alive), osty.current_hp / 100,
                              osty.max_hp / 100, osty.block / 50]
    idx += 4
    for enemy in combat.enemies[:MAX_ENEMIES]:
        values[idx:idx + 2] = [enemy.get_power_amount(PowerId.POISON) / 50,
                              enemy.get_power_amount(PowerId.DOOM) / 50]
        idx += 2
    return values


class CharacterObservation(gym.ObservationWrapper):
    """Append character-v1 features to either upstream simulator environment.

    This schema is deliberately opt-in. The real-game bridge remains legacy;
    these checkpoints must not be used there without matching serialization.
    """

    def __init__(self, env: gym.Env, character: str):
        super().__init__(env)
        if character not in CHARACTERS:
            raise ValueError(f"Unknown character: {character}")
        self.character = character
        self.observation_space = gym.spaces.Box(
            low=np.concatenate([env.observation_space.low,
                                np.full(len(FEATURE_NAMES), -np.inf, dtype=np.float32)]),
            high=np.concatenate([env.observation_space.high,
                                 np.full(len(FEATURE_NAMES), np.inf, dtype=np.float32)]),
            dtype=np.float32,
        )

    def observation(self, observation: np.ndarray) -> np.ndarray:
        base = self.env.unwrapped
        if hasattr(base, "combat"):
            combat = base.combat
        else:
            combat = base._mgr.get_combat_state() if base._mgr else None
        return np.concatenate([observation, encode_character_features(combat, self.character)])

    def action_masks(self) -> np.ndarray:
        return self.env.unwrapped.action_masks()
