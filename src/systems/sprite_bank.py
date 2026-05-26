"""Helpers for loading optional external sprites with safe fallbacks."""

from __future__ import annotations

import os

import pygame


class SpriteBank:
    """Loads user-provided sprites and falls back to neutral placeholders."""

    def __init__(self):
        self._cache = {}

    def get(self, path: str, size: tuple[int, int], fallback_color: tuple[int, int, int]):
        key = (path, size)
        if key not in self._cache:
            self._cache[key] = self._load_or_placeholder(path, size, fallback_color)
        return self._cache[key]

    def _load_or_placeholder(
        self,
        path: str,
        size: tuple[int, int],
        fallback_color: tuple[int, int, int],
    ):
        if path and os.path.exists(path):
            try:
                image = pygame.image.load(path).convert_alpha()
                return pygame.transform.smoothscale(image, size)
            except pygame.error:
                pass
        return self._build_placeholder(size, fallback_color)

    def _build_placeholder(self, size: tuple[int, int], color: tuple[int, int, int]):
        width, height = size
        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        outer = pygame.Rect(0, 0, width, height)
        inner = outer.inflate(-8, -8)
        core = inner.inflate(-12, -12)

        pygame.draw.rect(surface, (*color, 54), outer, border_radius=16)
        pygame.draw.rect(surface, (*color, 168), inner, width=2, border_radius=14)
        if core.width > 0 and core.height > 0:
            pygame.draw.rect(surface, (*color, 64), core, border_radius=10)

        step = max(12, min(width, height) // 5)
        for offset in range(-height, width + height, step):
            start = (offset, height)
            end = (offset + height, 0)
            pygame.draw.line(surface, (*color, 62), start, end, 2)

        return surface
