"""Version identity for simulator artifacts; not a claim of complete game parity."""
GAME_VERSION = "0.111.0"
GAME_BUILD = "24724944"
SIMULATOR_REVISION = "v111-migration-2"
VALIDATION_STATUS = "migration_in_progress"


def simulator_identity():
    return dict(game_version=GAME_VERSION, game_build=GAME_BUILD,
                simulator_revision=SIMULATOR_REVISION, validation_status=VALIDATION_STATUS)


def require_compatible_manifest(manifest):
    expected = simulator_identity()
    recorded = manifest.get("simulator", {})
    for key in ("game_version", "simulator_revision"):
        if recorded.get(key) != expected[key]:
            raise ValueError(f"Checkpoint {key} {recorded.get(key)!r} does not match {expected[key]!r}; "
                             "old observation IDs and RNG semantics are incompatible")
