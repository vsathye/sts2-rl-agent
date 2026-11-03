"""Reproducible per-character MaskablePPO training and bounded evaluation."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import time

import gymnasium as gym
import numpy as np

from sts2_env.gym_env.character_observation import (
    CHARACTERS, FEATURE_NAMES, OBSERVATION_VERSION, CharacterObservation,
)


@dataclass(frozen=True)
class EnvConfig:
    mode: str = "run"
    character: str = "Ironclad"
    ascension: int = 0
    act_count: int = 1
    observation: str = OBSERVATION_VERSION
    max_steps: int = 10000
    max_turns: int = 200
    starting_relic: bool = False


class SeedSchedule(gym.Wrapper):
    """Cycle a fixed seed set; evaluation resets to the same set each callback."""
    def __init__(self, env: gym.Env, seeds: range | None):
        super().__init__(env)
        self.seeds = seeds
        self.index = 0

    def reset(self, *, seed=None, options=None):
        # SB3 passes model seeds on its first reset. A configured scenario
        # schedule must take precedence to keep train/test splits disjoint.
        if self.seeds is not None:
            seed = self.seeds[self.index % len(self.seeds)]
            self.index += 1
        return self.env.reset(seed=seed, options=options)

    def action_masks(self) -> np.ndarray:
        return self.env.unwrapped.action_masks()


def make_env(config: EnvConfig, seeds: range | None = None):
    """Return a pickleable factory using the same config for train and eval."""
    def factory():
        from sts2_env.gym_env.combat_env import STS2CombatEnv
        from sts2_env.gym_env.run_env import STS2RunEnv
        if config.mode == "combat":
            env = STS2CombatEnv(character_id=config.character,
                                ascension_level=config.ascension,
                                starting_relic=config.starting_relic,
                                max_turns=config.max_turns)
        else:
            env = STS2RunEnv(character_id=config.character,
                            ascension_level=config.ascension,
                            act_count=config.act_count, max_steps=config.max_steps,
                            max_combat_turns=config.max_turns, strict_errors=True)
        if config.observation == OBSERVATION_VERSION:
            env = CharacterObservation(env, config.character)
        elif config.observation != "legacy":
            raise ValueError("Unknown observation version")
        # Bound pending choices as well as turns. Propagate masking explicitly.
        env = gym.wrappers.TimeLimit(env, max_episode_steps=config.max_steps)
        return SeedSchedule(env, seeds)
    return factory


def evaluate(config: EnvConfig, seeds: range, model=None) -> dict:
    """Record each terminal result. Exceptions never become ordinary losses."""
    rows = []
    env = make_env(config)()
    try:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            obs, info = env.reset(seed=seed)
            total_reward = 0.0
            for step in range(1, config.max_steps + 1):
                mask = env.action_masks()
                legal = np.flatnonzero(mask)
                if len(legal) == 0:
                    raise RuntimeError(f"Empty action mask at seed {seed}, step {step}")
                if model is None:
                    action = int(rng.choice(legal))
                else:
                    action, _ = model.predict(obs, action_masks=mask, deterministic=True)
                    action = int(action)
                if not mask[action]:
                    raise RuntimeError("Policy selected an invalid action")
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                if not np.isfinite(obs).all():
                    raise RuntimeError("Non-finite observation")
                if terminated or truncated:
                    rows.append(dict(seed=seed, steps=step, reward=total_reward,
                                     terminated=bool(terminated), truncated=bool(truncated),
                                     combat_win=bool(info.get("combat_win", False) and terminated),
                                     curriculum_win=bool(info.get("curriculum_win", False) and terminated),
                                     full_run_win=bool(info.get("full_run_win", False) and terminated),
                                     floor=info.get("floor"), act=info.get("act")))
                    break
    finally:
        env.close()
    metric = "combat_win" if config.mode == "combat" else "curriculum_win"
    return dict(config=asdict(config), policy="random" if model is None else "ppo",
                episodes=rows, win_metric=metric,
                win_rate=float(np.mean([r[metric] for r in rows])),
                full_run_wins=sum(r["full_run_win"] for r in rows),
                truncations=sum(r["truncated"] for r in rows),
                scientific_status="simulator_only_no_real_game_verdict")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def train(args: argparse.Namespace, config: EnvConfig) -> None:
    import torch
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    class FixedSeedEval(MaskableEvalCallback):
        def _on_step(self):
            if self.eval_freq > 0 and self.n_calls % self.eval_freq == 0:
                for wrapped in self.eval_env.envs:
                    wrapped.env.index = 0  # Monitor -> SeedSchedule
            return super()._on_step()

    torch.set_num_threads(args.threads)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    # Training seeds are finite and disjoint from validation and final test seeds.
    factories = []
    for worker in range(args.n_envs):
        factory = make_env(config, range(worker, args.train_seeds, args.n_envs))
        def monitored(factory=factory):
            return Monitor(factory())
        factories.append(monitored)
    train_env = (SubprocVecEnv if args.n_envs > 1 else DummyVecEnv)(factories)
    eval_env = DummyVecEnv([lambda: Monitor(make_env(
        config, range(1_000_000, 1_000_000 + args.eval_episodes))())])
    try:
        manifest = dict(config=asdict(config), arguments=vars(args),
                        source_commit=subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], text=True).strip(),
                        source_dirty=bool(subprocess.check_output(
                            ["git", "status", "--porcelain"], text=True).strip()),
                        working_diff_sha256=hashlib.sha256(subprocess.check_output(
                            ["git", "diff", "HEAD"])).hexdigest(),
                        observation_shape=list(train_env.observation_space.shape),
                        action_count=int(train_env.action_space.n),
                        appended_feature_names=FEATURE_NAMES if config.observation != "legacy" else [],
                        seed_splits={"train": [0, args.train_seeds],
                                     "validation": [1_000_000, 1_000_000 + args.eval_episodes],
                                     "test": [2_000_000, 2_000_000 + args.test_episodes]},
                        seed_range_end="exclusive", torch_version=torch.__version__)
        write_json(output / "manifest.json", manifest)
        model = MaskablePPO("MlpPolicy", train_env, seed=args.seed, device=args.device,
                            learning_rate=args.lr, n_steps=args.n_steps,
                            batch_size=args.batch_size, n_epochs=args.n_epochs,
                            gamma=args.gamma, gae_lambda=0.95, ent_coef=args.ent_coef,
                            policy_kwargs={"net_arch": {"pi": [256, 256], "vf": [256, 256]}}
                            if config.mode == "run" else None,
                            verbose=1)
        callback = FixedSeedEval(eval_env,
                                best_model_save_path=str(output / "best_model"),
                                log_path=str(output / "eval"),
                                eval_freq=max(args.eval_freq // args.n_envs, 1),
                                n_eval_episodes=args.eval_episodes,
                                deterministic=True)
        start = time.monotonic()
        model.learn(total_timesteps=args.total_timesteps, callback=callback)
        model.save(output / "final_model")
        seeds = range(2_000_000, 2_000_000 + args.test_episodes)
        report = evaluate(config, seeds, model)
        report.update(actual_timesteps=model.num_timesteps,
                      training_seconds=time.monotonic() - start,
                      checkpoint="final_model.zip")
        write_json(output / "test.json", report)
        write_json(output / "random_baseline.json", evaluate(config, seeds))
    finally:
        train_env.close()
        eval_env.close()


def main(mode: str) -> None:
    parser = argparse.ArgumentParser(description=f"Per-character {mode} training")
    parser.add_argument("--character", choices=CHARACTERS, default="Ironclad")
    parser.add_argument("--ascension", type=int, choices=range(11), default=0)
    parser.add_argument("--observation", choices=("legacy", OBSERVATION_VERSION), default=OBSERVATION_VERSION)
    parser.add_argument("--act-count", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--starting-relic", action="store_true", help="Combat only; legacy benchmark omitted relics")
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--total-timesteps", type=int, default=100000)
    parser.add_argument("--n-envs", type=int, default=1)
    parser.add_argument("--n-steps", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.99 if mode == "combat" else 0.995)
    parser.add_argument("--ent-coef", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--train-seeds", type=int, default=10000)
    parser.add_argument("--eval-freq", type=int, default=10000)
    parser.add_argument("--eval-episodes", type=int, default=10)
    parser.add_argument("--test-episodes", type=int, default=100)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output-dir", default=f"output/{mode}_ppo")
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    for name in ("max_steps", "max_turns", "total_timesteps", "n_envs", "n_steps",
                 "batch_size", "n_epochs", "train_seeds", "eval_freq", "eval_episodes",
                 "test_episodes", "threads"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if not args.n_envs <= args.train_seeds <= 1_000_000:
        parser.error("train-seeds must cover all workers and stay below validation seeds")
    if args.eval_episodes > 1_000_000:
        parser.error("validation seeds must not overlap final test seeds")
    if args.n_steps * args.n_envs < 2 or args.batch_size < 2:
        parser.error("PPO requires a rollout and batch size of at least two")
    if mode == "run" and args.starting_relic:
        parser.error("Full runs already include starting relics")
    config = EnvConfig(mode, args.character, args.ascension, args.act_count,
                       args.observation, args.max_steps, args.max_turns, args.starting_relic)
    if args.baseline_only:
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "random_baseline.json", evaluate(
            config, range(2_000_000, 2_000_000 + args.test_episodes)))
    else:
        train(args, config)
