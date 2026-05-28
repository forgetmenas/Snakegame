"""Helpers for loading optional external sprites with safe fallbacks."""

from __future__ import annotations

import os

import pygame


class SpriteBank:
    """Loads user-provided sprites and falls back to neutral placeholders."""

    def __init__(self):
        self._cache = {}

    def get(
        self,
        path: str,
        size: tuple[int, int],
        fallback_color: tuple[int, int, int],
        *,
        padding_ratio: float = 0.0,
    ):
        key = (path, size, round(padding_ratio, 3))
        if key not in self._cache:
            self._cache[key] = self._load_or_placeholder(path, size, fallback_color, padding_ratio)
        return self._cache[key]

    def _load_or_placeholder(
        self,
        path: str,
        size: tuple[int, int],
        fallback_color: tuple[int, int, int],
        padding_ratio: float,
    ):
        if path and os.path.exists(path):
            try:
                image = pygame.image.load(path).convert_alpha()
                return self._fit_image(image, size, padding_ratio)
            except pygame.error:
                pass
        return self._build_placeholder(size, fallback_color)

    def _fit_image(self, image, size: tuple[int, int], padding_ratio: float):
        width, height = size
        if width <= 0 or height <= 0:
            return pygame.Surface((max(width, 1), max(height, 1)), pygame.SRCALPHA)

        pad_x = max(0, int(width * padding_ratio))
        pad_y = max(0, int(height * padding_ratio))
        target_width = max(1, width - pad_x * 2)
        target_height = max(1, height - pad_y * 2)

        image_width, image_height = image.get_size()
        if image_width <= 0 or image_height <= 0:
            return self._build_placeholder(size, (180, 180, 180))

        scale_ratio = min(target_width / image_width, target_height / image_height)
        scaled_size = (
            max(1, int(image_width * scale_ratio)),
            max(1, int(image_height * scale_ratio)),
        )
        scaled = pygame.transform.smoothscale(image, scaled_size)

        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        draw_x = (width - scaled_size[0]) // 2
        draw_y = (height - scaled_size[1]) // 2
        surface.blit(scaled, (draw_x, draw_y))
        return surface

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
