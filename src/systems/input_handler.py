"""Adventure mode input handling."""

from __future__ import annotations

import pygame

from src.core.settings import MAP_HEIGHT, MAP_WIDTH, SNAKE_HEAD_RADIUS


class InputHandler:
    """Collects per-frame actions for the adventure mode."""

    def __init__(self):
        self.quit = False
        self.reset()

    def reset(self):
        self.restart = False
        self.back_to_menu = False
        self.pause_requested = False
        self.activate_skill = False
        self.target_point = None
        self.click_world = None

    def handle_events(self, events, camera):
        self.reset()

        for event in events:
            if event.type == pygame.QUIT:
                self.quit = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit = True
                elif event.key == pygame.K_q:
                    self.pause_requested = True
                elif event.key == pygame.K_r:
                    self.restart = True
                elif event.key == pygame.K_m:
                    self.back_to_menu = True
                elif event.key == pygame.K_SPACE:
                    self.activate_skill = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                world_x = event.pos[0] + camera.offset[0]
                world_y = event.pos[1] + camera.offset[1]
                clamped_x = max(SNAKE_HEAD_RADIUS, min(MAP_WIDTH - SNAKE_HEAD_RADIUS, world_x))
                clamped_y = max(SNAKE_HEAD_RADIUS, min(MAP_HEIGHT - SNAKE_HEAD_RADIUS, world_y))
                self.target_point = (clamped_x, clamped_y)
                self.click_world = (clamped_x, clamped_y)

        return self
