"""相机系统 - 平滑跟随蛇头，提供世界坐标到屏幕坐标的转换"""

from settings import *


class Camera:
    """2D 相机，通过 lerp 平滑跟随目标"""

    def __init__(self, map_width, map_height, screen_width, screen_height):
        self.offset = [0.0, 0.0]
        self.map_width = map_width
        self.map_height = map_height
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.lerp_factor = CAMERA_LERP

    def reset(self):
        """重置相机位置到蛇出生点"""
        self.offset[0] = INITIAL_WORLD_X - self.screen_width / 2
        self.offset[1] = INITIAL_WORLD_Y - self.screen_height / 2

    def update(self, target_x, target_y, dt):
        desired_x = target_x - self.screen_width / 2
        desired_y = target_y - self.screen_height / 2
        desired_x = max(0, min(desired_x, self.map_width - self.screen_width))
        desired_y = max(0, min(desired_y, self.map_height - self.screen_height))
        self.offset[0] += (desired_x - self.offset[0]) * self.lerp_factor
        self.offset[1] += (desired_y - self.offset[1]) * self.lerp_factor

    def world_to_screen(self, wx, wy):
        sx = int(wx - self.offset[0])
        sy = int(wy - self.offset[1])
        return (sx, sy)
