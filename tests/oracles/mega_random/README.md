# Generate RNG fixtures from the game source

Copy this directory to a temporary directory. Copy
`decompiled/MegaCrit.Sts2.Core.Random/MegaRandom.cs` into it unchanged. Run
`dotnet run --project oracle.csproj` with .NET 8. Its JSON output is
`docs/evidence/game_v0_111_0/mega_random_vectors.json`.

The save-record stub removes networking dependencies; the RNG code itself is
unmodified. Vectors cover seeds 0, 1, 42, 2^32 and 2^64-1, with eight integer,
double and unsigned 64-bit outputs each. This validates the underlying stream,
not all game call ordering or all RNG wrapper methods.
