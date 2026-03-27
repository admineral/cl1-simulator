#!/usr/bin/env python3
"""Lightweight LRU cache for reusable CL1 stimulation designs."""

from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V], OrderedDict[K, V]):
    def __init__(self, maxsize: int = 256):
        super().__init__()
        self.maxsize = maxsize

    def get_or_set(self, key: K, factory: Callable[[], V]) -> V:
        if key in self:
            self.move_to_end(key)
            return self[key]
        value = factory()
        self[key] = value
        if len(self) > self.maxsize:
            self.popitem(last=False)
        return value

    def clear_all(self) -> None:
        self.clear()


if __name__ == "__main__":
    cache: LRUCache[str, int] = LRUCache(maxsize=2)
    print(cache.get_or_set("a", lambda: 1))
    print(cache.get_or_set("b", lambda: 2))
    print(cache.get_or_set("a", lambda: 99))
    print(cache.get_or_set("c", lambda: 3))
    print(list(cache.items()))
