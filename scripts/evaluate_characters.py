"""Bounded per-character evaluation; reports retain every episode and seed."""
from dataclasses import replace
import argparse
import json
from pathlib import Path

from sts2_env.gym_env.character_observation import CHARACTERS
from sts2_env.game_version import require_compatible_manifest
from sts2_env.training import EnvConfig, evaluate, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("combat", "run"), default="run")
    parser.add_argument("--characters", nargs="+", choices=CHARACTERS, default=list(CHARACTERS))
    parser.add_argument("--ascension", type=int, choices=range(11), default=0)
    parser.add_argument("--act-count", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=2_000_000)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--manifest", type=Path, help="Required for checkpoints; schema and environment come from this file")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes <= 0 or args.max_steps <= 0 or args.seed_start < 0:
        parser.error("episodes/max-steps must be positive and seed-start nonnegative")
    if bool(args.checkpoint) != bool(args.manifest):
        parser.error("checkpoint and manifest must be supplied together")
    if args.output.exists():
        parser.error("output already exists")
    config = EnvConfig(mode=args.mode, ascension=args.ascension,
                       act_count=args.act_count, max_steps=args.max_steps)
    model = None
    if args.checkpoint:
        from sb3_contrib import MaskablePPO
        manifest = json.loads(args.manifest.read_text())
        require_compatible_manifest(manifest)
        config = EnvConfig(**manifest["config"])
        model = MaskablePPO.load(args.checkpoint, device="cpu")
    reports = [evaluate(replace(config, character=c),
                        range(args.seed_start, args.seed_start + args.episodes), model)
               for c in args.characters]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, dict(checkpoint=str(args.checkpoint) if model else None,
                                trained_character=config.character if model else None,
                                reports=reports))


if __name__ == "__main__":
    main()
