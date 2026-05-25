"""
迷雾系统 - 使用 light mask + BLEND_RGBA_MULT 实现迷雾效果
变更：
- 使用 HEAD_VISION_RADIUS / BODY_VISION_WIDTH 新常量
- Cookie 渐变改用 smoothstep 实现类高斯模糊的羽化效果（中心全可见，边缘平滑过渡到迷雾）
- 增大可见半径（200px 头 / 70px 身）

原理：BLEND_RGBA_MULT 公式: dst = dst * (src / 255)
light_surface 白色处场景完全可见，深色处被压暗形成迷雾。
"""

import pygame
from src.core.settings import *


class FogOfWar:
    """迷雾系统，管理可见区域遮罩"""

    def __init__(self, screen_width, screen_height, camera):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.camera = camera

        # RGB 表面（无 alpha），白色=可见，深色=迷雾
        self.light_mask = pygame.Surface((screen_width, screen_height))

        # 预渲染头部 cookie（大圆，宽羽化）
        self.head_cookie = self._create_cookie(
            HEAD_VISION_RADIUS, FOG_EDGE_FEATHER)
        # 预渲染身体 cookie（小圆）
        trail_half = BODY_VISION_WIDTH // 2
        self.body_cookie = self._create_cookie(
            trail_half, FOG_EDGE_FEATHER // 2)

    def _create_cookie(self, radius, feather):
        """创建径向渐变圆形贴图（smoothstep 类高斯羽化）。
        白色中心 → 透明边缘，使用 smoothstep 使过渡更接近高斯模糊。
        仅在初始化时调用一次，运行时直接 blit。
        """
        d = radius * 2
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        feather = max(1, min(feather, radius))
        solid_r = radius - feather

        # 实心白色核心
        if solid_r > 0:
            pygame.draw.circle(surf, (255, 255, 255, 255),
                               (radius, radius), solid_r)

        # Smoothstep 渐变羽化环
        rings = min(feather, FOG_COOKIE_QUALITY)
        step = feather / max(rings, 1)
        for i in range(rings):
            r = solid_r + (i + 1) * step
            fraction = (r - solid_r) / feather  # 0..1
            # smoothstep: 3t² - 2t³，S 曲线过渡，更接近高斯模糊
            t = fraction * fraction * (3.0 - 2.0 * fraction)
            alpha = int(255 * (1.0 - t))
            alpha = max(0, min(255, alpha))
            pygame.draw.circle(surf, (255, 255, 255, alpha),
                               (radius, radius), int(r))

        return surf

    def _draw_cookie_on_mask(self, cookie, world_x, world_y):
        """将预渲染 cookie 以 BLEND_RGBA_MAX 绘制到 light_mask 上。
        cookie 白色处覆盖迷雾，半透明边缘产生平滑羽化。"""
        sx, sy = self.camera.world_to_screen(world_x, world_y)
        cookie_size = cookie.get_width()
        blit_x = sx - cookie_size // 2
        blit_y = sy - cookie_size // 2
        self.light_mask.blit(cookie, (blit_x, blit_y),
                             special_flags=pygame.BLEND_RGBA_MAX)

    def update(self, head_pos, body_segments):
        """重建本帧的 light mask。
        head_pos: (x, y) 蛇头世界坐标
        body_segments: [[x, y], ...] 所有身体段世界坐标
        """
        self.light_mask.fill(FOG_COLOR)

        # 身体可见区域
        self._reveal_body(body_segments)

        # 头部可见区域（后绘制，覆盖在身体上）
        self._draw_cookie_on_mask(self.head_cookie, head_pos[0], head_pos[1])

    def _reveal_body(self, body_segments):
        """沿蛇身绘制可见条带"""
        if not body_segments:
            return

        for seg in body_segments:
            self._draw_cookie_on_mask(self.body_cookie, seg[0], seg[1])

        # 用白色宽线连接相邻段，填补空隙
        if FOG_BODY_CONNECT_SEGMENTS and len(body_segments) >= 2:
            line_width = BODY_VISION_WIDTH
            screen_pts = [
                self.camera.world_to_screen(seg[0], seg[1])
                for seg in body_segments
            ]
            for i in range(len(screen_pts) - 1):
                pygame.draw.line(self.light_mask, (255, 255, 255),
                                 screen_pts[i], screen_pts[i + 1], line_width)

    def apply(self, screen):
        """将迷雾叠加到已渲染场景上。BLEND_RGBA_MULT 使暗区变暗，亮区保持可见。"""
        screen.blit(self.light_mask, (0, 0),
                    special_flags=pygame.BLEND_RGBA_MULT)
