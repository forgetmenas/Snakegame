"""输入处理 - 支持菜单/游戏/结束三种状态的输入"""

import pygame
import math
from settings import *


class InputHandler:
    """处理玩家输入，支持状态机（menu / playing / gameover）"""

    def __init__(self):
        self.target_angle = 0.0
        self.angle_set = False
        self.quit = False

    def reset(self):
        """重置输入状态（用于重新开始游戏）"""
        self.target_angle = 0.0
        self.angle_set = False
        self.quit = False

    def handle_events(self, events, snake_head_x, snake_head_y, camera):
        """处理 playing 状态下的输入。
        返回 is_moving (bool)
        """
        for event in events:
            if event.type == pygame.QUIT:
                self.quit = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # 右键设置方向
                    mouse_sx, mouse_sy = pygame.mouse.get_pos()
                    world_x = mouse_sx + camera.offset[0]
                    world_y = mouse_sy + camera.offset[1]
                    dx = world_x - snake_head_x
                    dy = world_y - snake_head_y
                    self.target_angle = math.atan2(dy, dx)
                    self.angle_set = True

        keys = pygame.key.get_pressed()
        is_moving = keys[pygame.K_SPACE] and self.angle_set
        return is_moving
