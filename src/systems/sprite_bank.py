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
        pattern = pygame.Surface((width, height), pygame.SRCALPHA)
        mask = pygame.Surface((width, height), pygame.SRCALPHA)

        radius = min(width, height) // 2
        center = (width // 2, height // 2)
        inner_radius = max(radius - 4, 1)
        core_radius = max(inner_radius - 8, 1)

        pygame.draw.circle(surface, (*color, 54), center, radius)
        pygame.draw.circle(surface, (*color, 168), center, inner_radius, 2)
        pygame.draw.circle(surface, (*color, 72), center, core_radius)

        step = max(10, min(width, height) // 5)
        for offset in range(-height, width + height, step):
            start = (offset, height)
            end = (offset + height, 0)
            pygame.draw.line(pattern, (*color, 62), start, end, 2)

        pygame.draw.circle(mask, (255, 255, 255, 255), center, radius)
        pattern.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(pattern, (0, 0))

        return surface
