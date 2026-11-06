"""Deterministic RNG matching the game's seeded RNG wrapper."""

from __future__ import annotations

import math


INT_MAX = 2_147_483_647
INT_MIN = -2_147_483_648
INT_MAX_EXCLUSIVE = INT_MAX + 1
UINT_MASK = 0xFFFFFFFF


def _to_int32(value: int) -> int:
    value &= UINT_MASK
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _to_uint32(value: int) -> int:
    return value & UINT_MASK


UINT64_MASK = (1 << 64) - 1


def deterministic_hash_code(text: str) -> int:
    """v0.111.0 StringHelper: xxHash64 of UTF-8, seed zero."""
    import xxhash
    return xxhash.xxh64_intdigest(text.encode("utf-8"), seed=0)


class _MegaRandom:
    """v0.111.0 Xoshiro256** with SplitMix64 initialization."""
    def __init__(self, seed: int):
        self.state = []
        for _ in range(4):
            seed = (seed + 0x9E3779B97F4A7C15) & UINT64_MASK
            z = seed
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & UINT64_MASK
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & UINT64_MASK
            self.state.append((z ^ (z >> 31)) & UINT64_MASK)

    @staticmethod
    def _rotl(x: int, k: int) -> int:
        return ((x << k) | (x >> (64 - k))) & UINT64_MASK

    def internal_sample(self) -> int:
        s0, s1, s2, s3 = self.state
        result = (self._rotl((s1 * 5) & UINT64_MASK, 7) * 9) & UINT64_MASK
        t = (s1 << 17) & UINT64_MASK
        s2 ^= s0
        s3 ^= s1
        s1 ^= s2
        s0 ^= s3
        s2 ^= t
        s3 = self._rotl(s3, 45)
        self.state = [s0, s1, s2, s3]
        return result

    def sample(self) -> float:
        return (self.internal_sample() >> 11) * (2.0 ** -53)

    def get_sample_for_large_range(self) -> float:
        return self.sample()


class Rng:
    """Seeded random number generator compatible with the game's Rng class.

    The public ``next_int(low, high)`` API keeps this project's inclusive
    upper bound convention, while the underlying sequence uses C#'s seeded
    ``MegaRandom`` xoshiro256** implementation.
    """

    def __init__(self, seed: int = 0, name: str | None = None, counter: int = 0):
        self._base_seed = seed & UINT64_MASK
        if name is None:
            self._seed = self._base_seed
        else:
            self._seed = (self._base_seed + deterministic_hash_code(name)) & UINT64_MASK
        self._rng = _MegaRandom(self._seed)
        self._counter = 0
        self.fast_forward_counter(counter)

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def counter(self) -> int:
        return self._counter

    def fast_forward_counter(self, target_count: int) -> None:
        if self._counter > target_count:
            raise ValueError(
                f"Cannot fast-forward an Rng counter to a lower number "
                f"(current = {self._counter}, target = {target_count})"
            )
        while self._counter < target_count:
            self._counter += 1
            self._rng.internal_sample()

    def next_int(self, low: int, high: int) -> int:
        """Return random int in [low, high] inclusive."""
        if low > high:
            raise ValueError("low must be <= high")
        self._counter += 1
        exclusive_high = high + 1
        range_size = exclusive_high - low
        if range_size <= INT_MAX:
            return int(self._rng.sample() * range_size) + low
        return int(self._rng.get_sample_for_large_range() * range_size) + low

    def next_int_exclusive(self, low: int, high: int) -> int:
        """Return random int in [low, high), matching C# Random.Next(min, max)."""
        if low >= high:
            raise ValueError("low must be < high")
        return self.next_int(low, high - 1)

    def next_bool(self) -> bool:
        """Return random bool matching the game's Rng.NextBool."""
        return self.next_int(0, 1) == 0

    def random_int(self, low: int, high: int) -> int:
        """Backward-compatible alias for ``next_int``."""
        return self.next_int(low, high)

    def next_float(self, upper: float = 1.0) -> float:
        """Return random float in [0, upper)."""
        return self.next_float_range(0.0, upper)

    def shuffle(self, lst: list) -> None:
        """In-place shuffle."""
        for index in range(len(lst) - 1, 0, -1):
            swap_index = self.next_int(0, index)
            lst[index], lst[swap_index] = lst[swap_index], lst[index]

    def choice(self, lst: list):
        """Pick a random element."""
        if not lst:
            raise IndexError("Cannot choose from an empty list")
        return lst[self.next_int(0, len(lst) - 1)]

    def sample(self, lst: list, k: int) -> list:
        """Pick k distinct elements."""
        if k < 0 or k > len(lst):
            raise ValueError("Sample larger than population or is negative")
        pool = list(lst)
        result = []
        for _ in range(k):
            index = self.next_int(0, len(pool) - 1)
            result.append(pool.pop(index))
        return result

    def next_float_range(self, low: float, high: float) -> float:
        """Return random float in [low, high)."""
        if low > high:
            raise ValueError("low must be <= high")
        self._counter += 1
        import struct
        return struct.unpack("f", struct.pack("f", low + self._rng.sample() * (high - low)))[0]

    def next_gaussian_int(self, mean: float, stddev: float, min_val: int, max_val: int) -> int:
        """Return a gaussian-distributed int in [min_val, max_val].

        Matches C# Rng.NextGaussianInt: uses rejection sampling (re-rolls
        until the result is within range) rather than clamping.
        """
        while True:
            u1 = 1.0 - self.next_double()
            u2 = 1.0 - self.next_double()
            z = math.sqrt(-2.0 * math.log(u1)) * math.sin(2.0 * math.pi * u2)
            val = round(mean + stddev * z)
            if min_val <= val <= max_val:
                return val

    def fork(self) -> Rng:
        """Create a child RNG with a derived seed."""
        return Rng(self.next_int(0, INT_MAX_EXCLUSIVE))

    def next_double(self) -> float:
        self._counter += 1
        return self._rng.sample()

    def next_unsigned_long(self) -> int:
        self._counter += 1
        return self._rng.internal_sample()

    def to_serializable(self) -> dict:
        return {"counter": self._counter, **{f"state{i}": n for i, n in enumerate(self._rng.state)}}

    def load_from_serializable(self, saved: dict) -> None:
        state = [int(saved[f"state{i}"]) for i in range(4)]
        if any(n < 0 or n > UINT64_MASK for n in state) or not any(state):
            raise ValueError("Invalid Xoshiro256 state")
        self._rng.state = state
        self._counter = int(saved["counter"])
