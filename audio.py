"""
音效管理器 - 提供吃、死亡、指引三种音效
若 WAV 文件不存在则静默跳过，不崩溃
"""

import os
import pygame


class AudioManager:
    """管理游戏音效的加载与播放"""

    def __init__(self):
        self.sounds = {}
        self._load("eat", "eat.wav")
        self._load("death", "death.wav")
        self._load("guide", "guide.wav")

    def _load(self, key, filename):
        """尝试加载 WAV 文件，失败则设为 None"""
        try:
            if os.path.exists(filename):
                self.sounds[key] = pygame.mixer.Sound(filename)
            else:
                print(f"[Audio] 音效文件缺失: {filename}（将静默跳过）")
                self.sounds[key] = None
        except Exception as e:
            print(f"[Audio] 加载 {filename} 失败: {e}")
            self.sounds[key] = None

    def _play(self, key):
        """播放指定音效"""
        snd = self.sounds.get(key)
        if snd is not None:
            snd.play()

    def play_eat(self):
        """播放进食音效"""
        self._play("eat")

    def play_death(self):
        """播放死亡音效"""
        self._play("death")

    def play_guide(self):
        """播放指引发现音效"""
        self._play("guide")
