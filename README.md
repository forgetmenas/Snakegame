# 迷雾贪吃蛇 - Fog of War Snake

在迷雾中探索、捕食、生存的贪吃蛇游戏。

## 运行方式

```
pip install -r requirements.txt
python run.py
```

## 操作

| 操作 | 按键 |
|------|------|
| 设置方向 | 鼠标右键点击目标位置 |
| 移动 | 按住空格 |
| 暂停/开始 | 空格 |
| 重新开始(R) | R |
| 返回菜单(M) | M |
| 退出 | ESC |

## 项目结构

```
src/
├── core/       # 入口与配置
├── entities/   # 蛇、猎物、野兽、指引
└── systems/    # 相机、迷雾、输入、音效
assets/         # 静态资源
docs/           # 项目文档
```
