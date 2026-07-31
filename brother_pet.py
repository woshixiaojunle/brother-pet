"""
Brother Pet - 桌面猴子宠物应用
两位兄弟在桌面上像猴子一样爬行玩耍
功能：透明置顶窗口、窗口边缘感知、右键菜单（叫爸爸/投喂）、投喂掉💩动画
"""

import tkinter as tk
from tkinter import Canvas
import random
import math
import time
import os
import ctypes
from ctypes import wintypes
import threading
from PIL import Image, ImageTk

# ─── Win32 API 常量 ──────────────────────────────────────────────
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_TOPMOST = 0x8
WS_EX_NOACTIVATE = 0x08000000

LWA_ALPHA = 0x2
LWA_COLORKEY = 0x1

# 窗口枚举回调类型
WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    wintypes.HWND,
    wintypes.LPARAM,
)

# ─── 获取屏幕上其他窗口的矩形区域 ───────────────────────────────
def get_visible_windows_rects(exclude_hwnd=None):
    """获取屏幕上所有可见窗口的矩形区域（排除自身和任务栏等系统窗口）"""
    rects = []
    hwnds = []

    def enum_callback(hwnd, lParam):
        if hwnd == exclude_hwnd:
            return True
        # 跳过不可见窗口
        if not user32.IsWindowVisible(hwnd):
            return True
        # 跳过最小化窗口
        if user32.IsIconic(hwnd):
            return True
        # 获取窗口矩形
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        # 过滤太小的窗口（可能是隐藏控件）
        if width < 50 or height < 50:
            return True
        # 获取窗口类名（跳过特殊系统窗口）
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        classname = buf.value
        skip_classes = {
            'Shell_TrayWnd',      # 任务栏
            'WorkerW',           # 桌面工作区
            'Progman',           # 程序管理器
            'Button',            # 按钮
            'SysListView32',     # 列表视图
            'IME',               # 输入法
            'Chrome_WidgetWin_1', # Chrome 内部
            'MozillaWindowClass',
        }
        if classname in skip_classes:
            return True
        rects.append((rect.left, rect.top, rect.right, rect.bottom))
        hwnds.append(hwnd)
        return True

    callback = WNDENUMPROC(enum_callback)
    user32.EnumWindows(callback, 0)
    return rects


# ─── 宠物类 ──────────────────────────────────────────────────────
class Pet:
    """单个桌面宠物"""

    # 状态常量
    STATE_CRAWL = 'crawl'       # 爬行
    STATE_CLIMB = 'climb'       # 攀爬
    STATE_SIT = 'sit'           # 坐着发呆
    STATE_HAPPY = 'happy'       # 开心（投喂后）
    GRAVITY = 0.45              # 重力加速度
    PET_W = 108                 # 显示宽度（= 120 * 0.9）
    PET_H = 108                 # 显示高度

    def __init__(self, canvas, name, frames_dict, start_x, start_y):
        self.canvas = canvas
        self.name = name
        self.frames = frames_dict   # {'crawl': [img], 'climb': [img], 'sit': [img], 'happy': [img]}
        self.state = self.STATE_CRAWL
        self.frame_index = 0
        self.x = start_x
        self.y = start_y
        self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.0)
        self.vy = 0
        self.width = 120
        self.height = 120
        self.scale = 0.9
        self.facing_right = self.vx > 0
        self.image_id = None
        self.dialog_id = None
        self.dialog_text = ''
        self.dialog_timer = 0
        self.happy_timer = 0
        self.sit_timer = random.randint(100, 300)
        # 平台物理系统
        self.in_air = False
        self.platform = None        # ('ground'|'window', x1, y_top, x2)
        self.action_timer = random.randint(40, 120)
        self._target_platform = None

    @property
    def current_frames(self):
        return self.frames.get(self.state, self.frames.get('crawl', []))

    def get_current_image(self):
        frames = self.current_frames
        if not frames:
            return None
        idx = self.frame_index % len(frames)
        return frames[idx]

    def update(self, screen_w, screen_h, window_rects):
        """更新宠物状态与平台物理（全屏爬行 + 生动动画）"""
        # 平台兜底：首次确保落在地面平台上
        if self.platform is None and not self.in_air:
            gy = screen_h - 40
            self.platform = ('ground', 0, gy, screen_w)
            self.y = gy - self.PET_H

        # ── 开心状态：原地弹跳 ──
        if self.happy_timer > 0:
            self.happy_timer -= 1
            if self.happy_timer <= 0:
                self.state = self.STATE_CRAWL
                self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.0)
            base_y = self.platform[2] - self.PET_H if self.platform else self.y
            self.y = base_y - abs(math.sin(time.time() * 12)) * 14
            self._advance_frame()
            return

        # ── 对话框计时 ──
        if self.dialog_timer > 0:
            self.dialog_timer -= 1
            if self.dialog_timer <= 0:
                self._hide_dialog()

        # ── 发呆状态 ──
        if self.state == self.STATE_SIT:
            self.sit_timer -= 1
            if self.platform:
                self.y = self.platform[2] - self.PET_H
            if self.sit_timer <= 0:
                self.state = self.STATE_CRAWL
                self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.0)
                self.sit_timer = random.randint(200, 500)
            self._advance_frame()
            return

        platforms = self._build_platforms(screen_w, screen_h, window_rects)

        # ── 行为决策（定时） ──
        self.action_timer -= 1
        if self.action_timer <= 0 and not self.in_air:
            self._decide_action(platforms, screen_w, screen_h)
            self.action_timer = random.randint(80, 200)

        # 随机发呆
        if not self.in_air and self.state == self.STATE_CRAWL and random.random() < 0.0015:
            self.state = self.STATE_SIT
            self.vx = 0
            self.vy = 0
            self.sit_timer = random.randint(80, 220)
            return

        # ── 物理 ──
        if self.in_air:
            self.vy += self.GRAVITY
            self.x += self.vx
            self.y += self.vy
            foot_y = self.y + self.PET_H
            landed = False
            for p in platforms:
                _, px1, py, px2 = p
                cx = self.x + self.PET_W / 2
                if px1 - 25 <= cx <= px2 + 25 and self.vy > 0:
                    if foot_y >= py and foot_y - self.vy <= py + 20:
                        self.y = py - self.PET_H
                        self.vy = 0
                        self.in_air = False
                        self.platform = p
                        self.state = self.STATE_CRAWL
                        self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.0)
                        landed = True
                        break
            if not landed and foot_y > screen_h + 60:
                gy = screen_h - 40
                self.y = gy - self.PET_H
                self.in_air = False
                self.platform = ('ground', 0, gy, screen_w)
                self.vy = 0
                self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.0)
        else:
            # 在平台上爬行
            self.x += self.vx
            _, px1, py, px2 = self.platform
            left_limit = px1
            right_limit = px2 - self.PET_W
            if self.x <= left_limit:
                self.x = left_limit
                self.vx = abs(self.vx)
                self.facing_right = True
                if random.random() < 0.5:
                    self._jump_to_random_platform(platforms, screen_w, screen_h)
            elif self.x >= right_limit:
                self.x = right_limit
                self.vx = -abs(self.vx)
                self.facing_right = False
                if random.random() < 0.5:
                    self._jump_to_random_platform(platforms, screen_w, screen_h)

        # 全局水平边界
        margin = 5
        if self.x < margin:
            self.x = margin
            self.vx = abs(self.vx)
            self.facing_right = True
        elif self.x > screen_w - self.PET_W - margin:
            self.x = screen_w - self.PET_W - margin
            self.vx = -abs(self.vx)
            self.facing_right = False

        if self.vx != 0:
            self.facing_right = self.vx > 0

        self._advance_frame()

    def _rects_near(self, r1, r2, threshold=30):
        """判断两个矩形是否足够接近"""
        ax1, ay1, ax2, ay2 = r1
        bx1, by1, bx2, by2 = r2
        # 检查水平方向是否有重叠或接近
        h_overlap = not (ax2 < bx1 - threshold or ax1 > bx2 + threshold)
        v_overlap = not (ay2 < by1 - threshold or ay1 > by2 + threshold)
        return h_overlap and v_overlap

    def _advance_frame(self):
        """推进到下一帧"""
        frames = self.current_frames
        if len(frames) > 1:
            speed = 3 if self.state == self.STATE_HAPPY else 6
            if int(time.time() * speed) % speed == 0:
                self.frame_index = (self.frame_index + 1) % len(frames)

    # ── 程序化动画：单帧 → 生动多帧循环 ──
    @staticmethod
    def _gen_variants(base, w, h, kind='crawl', n=6):
        if base is None:
            return []
        out = []
        for i in range(n):
            t = i / n * 2 * math.pi
            if kind == 'crawl':
                angle = math.sin(t) * 7
                dy = -abs(math.sin(t)) * 5 + 2
                sx = 1 + math.sin(t + math.pi / 2) * 0.04
                sy = 1 - math.sin(t + math.pi / 2) * 0.04
            elif kind == 'climb':
                angle = -14 + math.sin(t) * 14
                dy = math.sin(t) * 4
                sx = sy = 1.0
            elif kind == 'sit':
                angle = 0
                s = 1 + math.sin(t) * 0.02
                sx = sy = s
                dy = math.sin(t) * 1.5
            else:  # happy
                angle = math.sin(t) * 14
                dy = -abs(math.sin(t)) * 12
                s = 1 + math.sin(t) * 0.07
                sx = sy = s
            out.append(Pet._transform(base, w, h, angle, sx, sy, dy))
        return out

    @staticmethod
    def _transform(base, w, h, angle, sx, sy, dy):
        img = base.resize((w, h), Image.Resampling.LANCZOS)
        nw = max(1, int(w * sx))
        nh = max(1, int(h * sy))
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        img = img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        canvas_img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        cw, ch = img.size
        ox = (w - cw) // 2
        oy = (h - ch) // 2 + int(dy)
        canvas_img.paste(img, (ox, oy), img)
        return canvas_img

    def _build_platforms(self, screen_w, screen_h, window_rects):
        """地面 + 各可见窗口顶面 = 可站立/攀爬的平台"""
        gy = screen_h - 40
        platforms = [('ground', 0, gy, screen_w)]
        for wr in window_rects:
            wx1, wy1, wx2, wy2 = wr
            ww = wx2 - wx1
            wh = wy2 - wy1
            if ww > 90 and wh > 90 and 40 < wy1 < screen_h - 120:
                platforms.append(('window', wx1 + 8, wy1 + 6, wx2 - 8))
        return platforms

    def _jump_to_random_platform(self, platforms, screen_w, screen_h):
        if not platforms:
            return
        target = random.choice(platforms)
        _, tx1, ty, tx2 = target
        tx = random.uniform(tx1, max(tx1 + 1, tx2 - self.PET_W))
        cx = self.x + self.PET_W / 2
        y0 = self.y + self.PET_H
        H = y0 - ty  # 需要上升的量（目标更高时为正）
        if H <= 0:
            vy = -random.uniform(7, 11)                      # 目标更低：普通抛物线跳
        else:
            vy = -math.sqrt(2 * self.GRAVITY * (H + 30))    # 精准抛物到目标高度
        t = 2 * abs(vy) / self.GRAVITY
        vx = max(-9, min(9, (tx - cx) / max(t, 1)))
        self.in_air = True
        self.platform = None
        self.state = self.STATE_CRAWL
        self.vx = vx
        self.vy = vy

    def _decide_action(self, platforms, screen_w, screen_h):
        if random.random() < 0.5:
            self._jump_to_random_platform(platforms, screen_w, screen_h)
        else:
            self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.5)

    def draw(self):
        """绘制宠物（帧已为最终尺寸，仅按朝向翻转）"""
        img = self.get_current_image()
        if img is None:
            return

        if not self.facing_right:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        self.photo_img = ImageTk.PhotoImage(img)

        if self.image_id:
            self.canvas.delete(self.image_id)

        self.image_id = self.canvas.create_image(
            self.x + self.PET_W // 2, self.y + self.PET_H // 2,
            image=self.photo_img, anchor='center'
        )

        self._draw_dialog()

    def _draw_dialog(self):
        """绘制对话气泡"""
        if self.dialog_timer <= 0:
            return

        if self.dialog_id:
            self.canvas.delete(self.dialog_id)

        cx = self.x + self.PET_W / 2
        cy = self.y - 15

        # 气泡背景
        bubble_w = max(len(self.dialog_text) * 14 + 30, 80)
        bubble_h = 36

        self.dialog_id = self.canvas.create_oval(
            cx - bubble_w // 2, cy - bubble_h,
            cx + bubble_w // 2, cy,
            fill='#ffffff', outline='#333333', width=2
        )

        # 小三角指向宠物
        tri_points = [
            cx - 8, cy,
            cx + 8, cy,
            cx, cy + 12,
        ]
        self.canvas.create_polygon(tri_points, fill='#ffffff', outline='#333333')

        # 文字
        self.canvas.create_text(
            cx, cy - bubble_h // 2,
            text=self.dialog_text,
            font=('Microsoft YaHei', 11, 'bold'),
            fill='#333333'
        )

    def show_dialog(self, text, duration=180):
        """显示对话框"""
        self.dialog_text = text
        self.dialog_timer = duration

    def _hide_dialog(self):
        """隐藏对话框"""
        if self.dialog_id:
            self.canvas.delete(self.dialog_id)
            self.dialog_id = None
        self.dialog_text = ''
        self.dialog_timer = 0

    def set_happy(self, duration=240):
        """设置开心状态"""
        self.state = self.STATE_HAPPY
        self.happy_timer = duration
        self.show_dialog('\u611f\u8c22\u7238\u7236\u6295\u5582\uff01', duration)


# ─── 💩 掉落物类 ────────────────────────────────────────────────
class PoopDrop:
    """投喂时掉落的粪便图标"""

    def __init__(self, canvas, x, y, target_pet):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.target_pet = target_pet
        self.vy = 0
        self.gravity = 0.4
        self.active = True
        self.landed = False
        self.land_timer = 0
        self.text_id = None
        self.size = 28

    def update(self):
        if not self.active:
            return

        if not self.landed:
            # 下落物理
            self.vy += self.gravity
            self.y += self.vy

            # 检测是否到达目标宠物位置
            pet_cx = self.target_pet.x + self.target_pet.width * self.target_pet.scale / 2
            pet_cy = self.target_pet.y + self.target_pet.height * self.target_pet.scale / 2

            if self.y >= pet_cy - 20 and abs(self.x - pet_cx) < 60:
                self.landed = True
                self.y = pet_cy - 10
                self.land_timer = 90  # 显示1.5秒后消失
                # 命中！让宠物开心
                self.target_pet.set_happy()
        else:
            self.land_timer -= 1
            if self.land_timer <= 0:
                self.active = False
                if self.text_id:
                    self.canvas.delete(self.text_id)
                    self.text_id = None

    def draw(self):
        if not self.active:
            return

        if self.text_id:
            self.canvas.delete(self.text_id)

        # 绘制💩 emoji 作为文本
        self.text_id = self.canvas.create_text(
            self.x, self.y,
            text='\U0001f4a9',  # 💩
            font=('Segoe UI Emoji', self.size),
            anchor='center'
        )


# ─── 主应用类 ────────────────────────────────────────────────────
class BrotherPetApp:
    """桌面宠物主应用"""

    DAD_QUOTES = [
        '\u53eb\u7238\u7238\uff01',
        '\u7238\u7238~\u7238\u7238~',
        '\u7238\u7238\u6211\u5728\u8fd9\u91cc\uff01',
        '\u7238\u7238\u62b1\u62b1~',
        '\u7238\u7238\u662f\u5927\u82f1\u96c4\uff01',
        '\u7238\u7238\u7ed9\u6211\u4e70\u7cd6~',
    ]

    def __init__(self):
        self.running = True
        self.root = tk.Tk()
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # 设置窗口属性：透明、置顶、穿透点击、无任务栏图标
        self.root.overrideredirect(True)
        self.root.attributes('-transparentcolor', '#000001')
        self.root.attributes('-topmost', True)

        # Win32 扩展样式：穿透鼠标事件 + 不激活
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

        # 全屏窗口
        self.root.geometry(f'{self.screen_w}x{self.screen_h}+0+0')
        self.root.configure(bg='#000001')

        # 画布
        self.canvas = Canvas(
            self.root,
            width=self.screen_w,
            height=self.screen_h,
            bg='#000001',
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)

        # 绑定右键菜单
        self.canvas.bind('<Button-3>', self._on_right_click)

        # 加载宠物素材
        self.pets = []
        self._load_pets()

        # 掉落物列表
        self.poops = []

        # 窗口矩形缓存（每秒刷新一次）
        self.window_rects = []
        self._refresh_window_rects()

        # 启动主循环
        self._game_loop()

    def _load_pets(self):
        """加载宠物素材并生成生动动画帧"""
        import sys
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS  # PyInstaller 打包后的临时解压目录
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(base_dir, 'assets')
        W, H = Pet.PET_W, Pet.PET_H

        # Pet 1: 白T眼镜哥
        pet1_frames = {
            'crawl': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet1_crawl_1.png')), W, H, 'crawl', 6),
            'climb': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet1_climb.png')), W, H, 'climb', 4),
            'sit':   Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet1_crawl_1.png')), W, H, 'sit', 4),
            'happy': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet1_happy.png')), W, H, 'happy', 6),
        }
        pet1 = Pet(
            self.canvas, '\u767dT\u773c\u955c\u54e5', pet1_frames,
            self.screen_w // 3, self.screen_h - 160
        )
        self.pets.append(pet1)

        # Pet 2: 黑T恤兄弟
        pet2_frames = {
            'crawl': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet2_crawl.png')), W, H, 'crawl', 6),
            'climb': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet2_crawl.png')), W, H, 'climb', 4),
            'sit':   Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet2_sit.png')), W, H, 'sit', 4),
            'happy': Pet._gen_variants(self._load_image(os.path.join(assets_dir, 'pet2_happy.png')), W, H, 'happy', 6),
        }
        pet2 = Pet(
            self.canvas, '\u9ed1T\u6064\u5144\u5f1f', pet2_frames,
            self.screen_w * 2 // 3, self.screen_h - 160
        )
        self.pets.append(pet2)

    def _load_image(self, path):
        """加载单张图片（RGBA），找不到返回 None"""
        if os.path.exists(path):
            return Image.open(path).convert('RGBA')
        print(f'[WARN] \u56fe\u7247\u627e\u4e0d\u5230: {path}')
        return None

    def _on_right_click(self, event):
        """右键菜单"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label='\u53eb\u7238\u7238 \U0001f478',
            command=lambda: self._call_dad(event.x, event.y)
        )
        menu.add_command(
            label='\u6295\u5582 \U0001f4a9',
            command=lambda: self._feed_pets(event.x, event.y)
        )
        menu.add_separator()
        menu.add_command(label='\u9000\u51fa', command=self._quit)
        menu.tk_popup(event.x_root, event.y_root)

    def _call_dad(self, x, y):
        """叫爸爸功能"""
        # 找最近的宠物说话
        nearest = None
        min_dist = float('inf')
        for pet in self.pets:
            dist = math.sqrt((pet.x - x) ** 2 + (pet.y - y) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest = pet

        if nearest:
            quote = random.choice(self.DAD_QUOTES)
            nearest.show_dialog(quote, duration=180)

    def _feed_pets(self, x, y):
        """投喂功能 - 掉落💩"""
        num_poops = random.randint(3, 6)
        for i in range(num_poops):
            px = random.randint(max(50, x - 150), min(self.screen_w - 50, x + 150))
            py = 10 + random.randint(0, 30)
            target = random.choice(self.pets)
            poop = PoopDrop(self.canvas, px, py, target)
            self.poops.append(poop)

    def _refresh_window_rects(self):
        """刷新窗口矩形缓存"""
        if hasattr(self, '_hwnd'):
            self.window_rects = get_visible_windows_rects(exclude_hwnd=self._hwnd)
        else:
            self.window_rects = get_visible_windows_rects()
        # 每2秒刷新一次
        if self.running:
            self.root.after(2000, self._refresh_window_rects)

    def _game_loop(self):
        """游戏主循环"""
        if not self.running:
            return

        # 清空画布
        self.canvas.delete('all')

        # 更新并绘制所有宠物
        for pet in self.pets:
            pet.update(self.screen_w, self.screen_h, self.window_rects)
            pet.draw()

        # 更新并绘制掉落物
        active_poops = []
        for poop in self.poops:
            poop.update()
            poop.draw()
            if poop.active:
                active_poops.append(poop)
        self.poops = active_poops

        # 获取 hwnd（首次循环后）
        if not hasattr(self, '_hwnd'):
            self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

        # ~60fps
        self.root.after(16, self._game_loop)

    def _quit(self):
        """退出"""
        self.running = False
        self.root.destroy()

    def run(self):
        """启动应用"""
        self.root.mainloop()


# ─── 入口 ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = BrotherPetApp()
    app.run()
