"""Classic grid-based snake mode."""

from __future__ import annotations

import random

import pygame

from src.core.settings import (
    CLASSIC_BOARD_BG,
    CLASSIC_BOARD_LINE,
    CLASSIC_BOARD_MARGIN,
    CLASSIC_FOOD,
    CLASSIC_GRID_COLS,
    CLASSIC_GRID_ROWS,
    CLASSIC_INITIAL_LENGTH,
    CLASSIC_MOVE_INTERVAL,
    CLASSIC_OBSTACLE,
    CLASSIC_OBSTACLE_EDGE,
    CLASSIC_SNAKE_BODY,
    CLASSIC_SNAKE_HEAD,
    CLASSIC_TEXT_SHADOW,
    HUD_ACCENT_COLOR,
    HUD_HINT_COLOR,
    HUD_TEXT_COLOR,
    MENU_HINT_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


class ClassicSnakeGame:
    """Fullscreen classic snake with WASD movement."""

    def __init__(self):
        self.cols = CLASSIC_GRID_COLS
        self.rows = CLASSIC_GRID_ROWS
        available_width = SCREEN_WIDTH - CLASSIC_BOARD_MARGIN * 2
        available_height = SCREEN_HEIGHT - CLASSIC_BOARD_MARGIN * 2
        self.cell_size = min(available_width // self.cols, available_height // self.rows)
        self.board_width = self.cols * self.cell_size
        self.board_height = self.rows * self.cell_size
        self.board_rect = pygame.Rect(
            (SCREEN_WIDTH - self.board_width) // 2,
            (SCREEN_HEIGHT - self.board_height) // 2,
            self.board_width,
            self.board_height,
        )
        self.reset()

    def reset(self):
        center_x = self.cols // 2
        center_y = self.rows // 2
        self.obstacles = self._build_obstacles(center_x, center_y)
        self.snake = [(center_x - offset, center_y) for offset in range(CLASSIC_INITIAL_LENGTH)]
        self.direction = (1, 0)
        self.pending_direction = self.direction
        self.food = self._spawn_food()
        self.score = 0
        self.move_timer = 0.0
        self.alive = True

    @property
    def length(self):
        return len(self.snake)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        direction_map = {
            pygame.K_UP: (0, -1),
            pygame.K_w: (0, -1),
            pygame.K_DOWN: (0, 1),
            pygame.K_s: (0, 1),
            pygame.K_LEFT: (-1, 0),
            pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1, 0),
            pygame.K_d: (1, 0),
        }
        next_direction = direction_map.get(event.key)
        if next_direction is None:
            return

        if next_direction[0] == -self.direction[0] and next_direction[1] == -self.direction[1]:
            return

        self.pending_direction = next_direction

    def update(self, dt):
        if not self.alive:
            return

        self.move_timer += dt
        while self.move_timer >= CLASSIC_MOVE_INTERVAL and self.alive:
            self.move_timer -= CLASSIC_MOVE_INTERVAL
            self._step()

    def _step(self):
        self.direction = self.pending_direction
        head_x, head_y = self.snake[0]
        next_cell = (head_x + self.direction[0], head_y + self.direction[1])
        if not (0 <= next_cell[0] < self.cols and 0 <= next_cell[1] < self.rows):
            self.alive = False
            return

        if next_cell in self.obstacles:
            self.alive = False
            return

        if next_cell in self.snake[:-1]:
            self.alive = False
            return

        self.snake.insert(0, next_cell)
        if next_cell == self.food:
            self.score += 10
            self.food = self._spawn_food()
        else:
            self.snake.pop()

    def _build_obstacles(self, center_x, center_y):
        obstacles = set()
        cluster_count = random.randint(3, 5)

        def can_place(cells):
            for col, row in cells:
                if not (1 <= col < self.cols - 1 and 1 <= row < self.rows - 1):
                    return False
                if abs(col - center_x) <= 5 and abs(row - center_y) <= 4:
                    return False
                if (col, row) in obstacles:
                    return False
            return True

        for _ in range(cluster_count):
            for _ in range(80):
                length = random.randint(2, 3)
                horizontal = random.choice([True, False])
                start_col = random.randint(2, self.cols - 4)
                start_row = random.randint(2, self.rows - 4)
                cells = []
                for index in range(length):
                    cell = (start_col + index, start_row) if horizontal else (start_col, start_row + index)
                    cells.append(cell)
                if can_place(cells):
                    obstacles.update(cells)
                    break

        return obstacles

    def _spawn_food(self):
        available = [
            (col, row)
            for col in range(self.cols)
            for row in range(self.rows)
            if (col, row) not in self.snake and (col, row) not in self.obstacles
        ]
        return random.choice(available) if available else None

    def draw(self, screen, body_font, small_font):
        screen.fill((18, 24, 18))
        pygame.draw.rect(screen, CLASSIC_BOARD_BG, self.board_rect, border_radius=24)
        pygame.draw.rect(screen, CLASSIC_BOARD_LINE, self.board_rect, width=3, border_radius=24)

        for row in range(self.rows):
            for col in range(self.cols):
                cell_rect = self._cell_rect((col, row))
                color = (32, 44, 34) if (row + col) % 2 == 0 else (38, 52, 40)
                pygame.draw.rect(screen, color, cell_rect)

        self._draw_obstacles(screen)
        if self.food is not None:
            self._draw_food(screen)
        self._draw_snake(screen)
        self._draw_corner_text(screen, body_font, small_font)

    def _draw_obstacles(self, screen):
        inset = max(3, self.cell_size // 10)
        for obstacle in self.obstacles:
            cell_rect = self._cell_rect(obstacle).inflate(-inset, -inset)
            pygame.draw.rect(screen, CLASSIC_OBSTACLE, cell_rect, border_radius=max(6, self.cell_size // 4))
            pygame.draw.rect(screen, CLASSIC_OBSTACLE_EDGE, cell_rect, width=2, border_radius=max(6, self.cell_size // 4))

    def _draw_food(self, screen):
        cell = self._cell_rect(self.food)
        radius = max(8, self.cell_size // 3)
        pygame.draw.circle(screen, CLASSIC_FOOD, cell.center, radius)
        pygame.draw.circle(screen, (255, 230, 210), (cell.centerx + radius // 3, cell.centery - radius // 3), max(3, radius // 4))

    def _draw_snake(self, screen):
        padding = max(3, self.cell_size // 10)
        for index, segment in enumerate(self.snake):
            cell = self._cell_rect(segment).inflate(-padding * 2, -padding * 2)
            color = CLASSIC_SNAKE_HEAD if index == 0 else CLASSIC_SNAKE_BODY
            pygame.draw.rect(screen, color, cell, border_radius=max(8, self.cell_size // 4))
            pygame.draw.rect(screen, (24, 34, 18), cell, width=2, border_radius=max(8, self.cell_size // 4))

    def _draw_corner_text(self, screen, body_font, small_font):
        left_lines = [
            ("分数", str(self.score), HUD_ACCENT_COLOR),
            ("长度", str(self.length), HUD_TEXT_COLOR),
        ]
        right_lines = [
            ("经典模式", HUD_TEXT_COLOR),
            ("WASD / 方向键控制", HUD_HINT_COLOR),
            ("R 重开  Q 暂停  M 菜单  ESC 退出", HUD_HINT_COLOR),
        ]

        y = 24
        for label, value, color in left_lines:
            self._draw_shadow_text(screen, body_font, f"{label} {value}", 28, y, color)
            y += 34

        for index, (text, color) in enumerate(right_lines):
            width = small_font.size(text)[0]
            draw_font = body_font if index == 0 else small_font
            width = draw_font.size(text)[0]
            self._draw_shadow_text(screen, draw_font, text, SCREEN_WIDTH - width - 28, 26 + index * 34, color)

        footer_text = "障碍和食物每局随机刷新"
        width = small_font.size(footer_text)[0]
        self._draw_shadow_text(screen, small_font, footer_text, SCREEN_WIDTH - width - 28, SCREEN_HEIGHT - 42, MENU_HINT_COLOR)

    def _draw_shadow_text(self, screen, font, text, x, y, color):
        shadow = font.render(text, True, CLASSIC_TEXT_SHADOW)
        screen.blit(shadow, (x + 2, y + 2))
        surface = font.render(text, True, color)
        screen.blit(surface, (x, y))

    def _cell_rect(self, cell):
        return pygame.Rect(
            self.board_rect.x + cell[0] * self.cell_size,
            self.board_rect.y + cell[1] * self.cell_size,
            self.cell_size,
            self.cell_size,
        )
