"""Fog of war rendering for the adventure mode."""

from __future__ import annotations

import pygame

from src.core.settings import FOG_COLOR, FOG_COOKIE_QUALITY, FOG_EDGE_FEATHER


class FogOfWar:
    """Builds a head-centered light mask and multiplies it onto the scene."""

    def __init__(self, screen_width, screen_height, camera):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.camera = camera
        self.light_mask = pygame.Surface((screen_width, screen_height))
        self.cookie_cache = {}

    def _create_cookie(self, radius):
        diameter = radius * 2
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))

        feather = max(1, min(FOG_EDGE_FEATHER, radius))
        solid_radius = radius - feather

        if solid_radius > 0:
            pygame.draw.circle(surface, (255, 255, 255, 255), (radius, radius), solid_radius)

        ring_count = min(feather, FOG_COOKIE_QUALITY)
        step = feather / max(ring_count, 1)
        for index in range(ring_count):
            ring_radius = solid_radius + (index + 1) * step
            fraction = (ring_radius - solid_radius) / feather
            smooth = fraction * fraction * (3.0 - 2.0 * fraction)
            alpha = max(0, min(255, int(255 * (1.0 - smooth))))
            pygame.draw.circle(
                surface,
                (255, 255, 255, alpha),
                (radius, radius),
                int(ring_radius),
            )

        return surface

    def _get_cookie(self, radius):
        radius = max(16, int(radius))
        if radius not in self.cookie_cache:
            self.cookie_cache[radius] = self._create_cookie(radius)
        return self.cookie_cache[radius]

    def update(self, head_pos, vision_radius=None):
        self.light_mask.fill(FOG_COLOR)
        if vision_radius is None:
            sources = list(head_pos)
        else:
            sources = [(head_pos, vision_radius)]

        for point, radius in sources:
            cookie = self._get_cookie(radius)
            screen_x, screen_y = self.camera.world_to_screen(point[0], point[1])
            size = cookie.get_width()
            self.light_mask.blit(
                cookie,
                (screen_x - size // 2, screen_y - size // 2),
                special_flags=pygame.BLEND_RGBA_MAX,
            )

    def apply(self, screen):
        screen.blit(self.light_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
