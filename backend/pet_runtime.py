"""
Brother Pet - 桌面猴子宠物运行时（由后端打包进 exe）
配置驱动：读取同目录 config.json + assets/ 素材，动态加载宠物。
前端/后端只负责生成 config.json 与素材，本程序不依赖网络。
"""

import tkinter as tk
from tkinter import Canvas
import random
import math
import time
import os
import sys
import json
import ctypes
from ctypes import wintypes
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
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 50 or height < 50:
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        classname = buf.value
        skip_classes = {
            'Shell_TrayWnd', 'WorkerW', 'Progman', 'Button',
            'SysListView32', 'IME', 'Chrome_WidgetWin_1', 'MozillaWindowClass',
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
    """单个桌面宠物（配置驱动）"""

    STATE_CRAWL = 'crawl'
    STATE_CLIMB = 'climb'
    STATE_SIT = 'sit'
    STATE_HAPPY = 'happy'
    GRAVITY = 0.45
    PET_W = 108
    PET_H = 108

    def __init__(self, canvas, name, frames_dict, start_x, start_y,
                 crawl_speed=6, jump_chance=0.5, sit_chance=0.0015):
        self.canvas = canvas
        self.name = name
        self.frames = frames_dict
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
        self.platform = None
        self.action_timer = random.randint(40, 120)
        self._target_platform = None
        # 可调参数
        self.crawl_speed = crawl_speed
        self.jump_chance = jump_chance
        self.sit_chance = sit_chance

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

        if not self.in_air and self.state == self.STATE_CRAWL and random.random() < self.sit_chance:
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
            self.x += self.vx
            _, px1, py, px2 = self.platform
            left_limit = px1
            right_limit = px2 - self.PET_W
            if self.x <= left_limit:
                self.x = left_limit
                self.vx = abs(self.vx)
                self.facing_right = True
                if random.random() < self.jump_chance:
                    self._jump_to_random_platform(platforms, screen_w, screen_h)
            elif self.x >= right_limit:
                self.x = right_limit
                self.vx = -abs(self.vx)
                self.facing_right = False
                if random.random() < self.jump_chance:
                    self._jump_to_random_platform(platforms, screen_w, screen_h)

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
        ax1, ay1, ax2, ay2 = r1
        bx1, by1, bx2, by2 = r2
        h_overlap = not (ax2 < bx1 - threshold or ax1 > bx2 + threshold)
        v_overlap = not (ay2 < by1 - threshold or ay1 > by2 + threshold)
        return h_overlap and v_overlap

    def _advance_frame(self):
        frames = self.current_frames
        if len(frames) > 1:
            speed = max(3, self.crawl_speed // 2) if self.state == self.STATE_HAPPY else self.crawl_speed
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
            else:
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
        H = y0 - ty
        if H <= 0:
            vy = -random.uniform(7, 11)
        else:
            vy = -math.sqrt(2 * self.GRAVITY * (H + 30))
        t = 2 * abs(vy) / self.GRAVITY
        vx = max(-9, min(9, (tx - cx) / max(t, 1)))
        self.in_air = True
        self.platform = None
        self.state = self.STATE_CRAWL
        self.vx = vx
        self.vy = vy

    def _decide_action(self, platforms, screen_w, screen_h):
        if random.random() < self.jump_chance:
            self._jump_to_random_platform(platforms, screen_w, screen_h)
        else:
            self.vx = random.choice([-1, 1]) * random.uniform(1.5, 3.5)

    def draw(self):
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
        if self.dialog_timer <= 0:
            return
        if self.dialog_id:
            self.canvas.delete(self.dialog_id)
        cx = self.x + self.PET_W / 2
        cy = self.y - 15
        bubble_w = max(len(self.dialog_text) * 14 + 30, 80)
        bubble_h = 36
        self.dialog_id = self.canvas.create_oval(
            cx - bubble_w // 2, cy - bubble_h,
            cx + bubble_w // 2, cy,
            fill='#ffffff', outline='#333333', width=2
        )
        tri_points = [cx - 8, cy, cx + 8, cy, cx, cy + 12]
        self.canvas.create_polygon(tri_points, fill='#ffffff', outline='#333333')
        self.canvas.create_text(
            cx, cy - bubble_h // 2,
            text=self.dialog_text,
            font=('Microsoft YaHei', 11, 'bold'),
            fill='#333333'
        )

    def show_dialog(self, text, duration=180):
        self.dialog_text = text
        self.dialog_timer = duration

    def _hide_dialog(self):
        if self.dialog_id:
            self.canvas.delete(self.dialog_id)
            self.dialog_id = None
        self.dialog_text = ''
        self.dialog_timer = 0

    def set_happy(self, duration=240, text='\u611f\u8c22\u7238\u7238\u6295\u5582\uff01'):
        self.state = self.STATE_HAPPY
        self.happy_timer = duration
        self.show_dialog(text, duration)


# ─── 💩 掉落物类 ────────────────────────────────────────────────
class PoopDrop:
    def __init__(self, canvas, x, y, target_pet, feed_text):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.target_pet = target_pet
        self.feed_text = feed_text
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
            self.vy += self.gravity
            self.y += self.vy
            pet_cx = self.target_pet.x + self.target_pet.width * self.target_pet.scale / 2
            pet_cy = self.target_pet.y + self.target_pet.height * self.target_pet.scale / 2
            if self.y >= pet_cy - 20 and abs(self.x - pet_cx) < 60:
                self.landed = True
                self.y = pet_cy - 10
                self.land_timer = 90
                self.target_pet.set_happy(text=self.feed_text)
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
        self.text_id = self.canvas.create_text(
            self.x, self.y,
            text='\U0001f4a9',
            font=('Segoe UI Emoji', self.size),
            anchor='center'
        )


# ─── 主应用类 ────────────────────────────────────────────────────
class BrotherPetApp:
    DEFAULT_DAD_QUOTES = [
        '\u53eb\u7238\u7238\uff01', '\u7238\u7238~\u7238\u7238~',
        '\u7238\u7238\u6211\u5728\u8fd9\u91cc\uff01', '\u7238\u7238\u62b1\u62b1~',
        '\u7238\u7238\u662f\u5927\u82f1\u96c4\uff01', '\u7238\u7238\u7ed9\u6211\u4e70\u7cd6~',
    ]
    DEFAULT_FEED_TEXT = '\u611f\u8c22\u7238\u7238\u6295\u5582\uff01'

    def __init__(self):
        self.running = True
        self.root = tk.Tk()
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        self.root.overrideredirect(True)
        self.root.attributes('-transparentcolor', '#000001')
        self.root.attributes('-topmost', True)

        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

        self.root.geometry(f'{self.screen_w}x{self.screen_h}+0+0')
        self.root.configure(bg='#000001')

        self.canvas = Canvas(
            self.root, width=self.screen_w, height=self.screen_h,
            bg='#000001', highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Button-3>', self._on_right_click)

        # 配置驱动
        self._load_config()
        self.pets = []
        self.poops = []
        self._load_pets()

        self.window_rects = []
        self._refresh_window_rects()
        self._game_loop()

    # ── 配置加载 ──
    def _base_dir(self):
        """返回可能的配置/素材目录候选列表，兼容性更强。"""
        candidates = []
        if hasattr(sys, '_MEIPASS'):
            candidates.append(sys._MEIPASS)
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'executable', None):
            candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
        candidates.append(os.getcwd())
        # 去重并保持顺序
        seen, out = set(), []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _load_config(self):
        self.config = {}
        cfg_path = None
        for d in self._base_dir():
            p = os.path.join(d, 'config.json')
            if os.path.exists(p):
                cfg_path = p
                break
        if cfg_path:
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f'[WARN] config.json 解析失败，使用默认: {e}')
        g = self.config.get('settings', {})
        self.dad_quotes = self.config.get('dad_quotes', self.DEFAULT_DAD_QUOTES)
        self.feed_text = self.config.get('feed_text', self.DEFAULT_FEED_TEXT)
        self.crawl_speed = g.get('crawl_speed', 6)
        self.jump_chance = g.get('jump_chance', 0.5)
        self.sit_chance = g.get('sit_chance', 0.0015)
        self.assets_dir = os.path.join(self._base_dir()[0], 'assets')

    def _load_image(self, path):
        if os.path.exists(path):
            return Image.open(path).convert('RGBA')
        print(f'[WARN] 图片找不到: {path}')
        return None

    def _load_pets(self):
        pets_cfg = self.config.get('pets', [])
        if not pets_cfg:
            pets_cfg = self._default_pets_cfg()
        W, H = Pet.PET_W, Pet.PET_H
        for idx, pc in enumerate(pets_cfg):
            assets = pc.get('assets', {})
            frames = {}
            for st in ['crawl', 'climb', 'sit', 'happy']:
                fn = assets.get(st) or pc.get(st)
                if not fn:
                    continue
                base = self._load_image(os.path.join(self.assets_dir, fn))
                n = (pc.get('frames', {}) or {}).get(st, 6 if st != 'sit' else 4)
                variants = Pet._gen_variants(base, W, H, st, n)
                if variants:
                    frames[st] = variants
            if not frames:
                continue
            start_x = pc.get('start_x', int(self.screen_w * (idx + 1) / (len(pets_cfg) + 1)))
            start_y = pc.get('start_y', self.screen_h - 160)
            pet = Pet(
                self.canvas, pc.get('name', f'pet{idx+1}'), frames,
                start_x, start_y,
                crawl_speed=pc.get('crawl_speed', self.crawl_speed),
                jump_chance=pc.get('jump_chance', self.jump_chance),
                sit_chance=pc.get('sit_chance', self.sit_chance),
            )
            self.pets.append(pet)

    def _default_pets_cfg(self):
        return [
            {'name': '\u767dT\u773c\u955c\u54e5', 'assets': {
                'crawl': 'pet1_crawl_1.png', 'climb': 'pet1_climb.png',
                'sit': 'pet1_crawl_1.png', 'happy': 'pet1_happy.png'}},
            {'name': '\u9ed1T\u6064\u5144\u5f1f', 'assets': {
                'crawl': 'pet2_crawl.png', 'climb': 'pet2_crawl.png',
                'sit': 'pet2_sit.png', 'happy': 'pet2_happy.png'}},
        ]

    # ── 右键菜单 ──
    def _on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='\u53eb\u7238\u7238 \U0001f478',
                         command=lambda: self._call_dad(event.x, event.y))
        menu.add_command(label='\u6295\u5582 \U0001f4a9',
                         command=lambda: self._feed_pets(event.x, event.y))
        menu.add_separator()
        menu.add_command(label='\u9000\u51fa', command=self._quit)
        menu.tk_popup(event.x_root, event.y_root)

    def _call_dad(self, x, y):
        nearest = None
        min_dist = float('inf')
        for pet in self.pets:
            dist = math.sqrt((pet.x - x) ** 2 + (pet.y - y) ** 2)
            if dist < min_dist:
                min_dist = dist
                nearest = pet
        if nearest:
            quote = random.choice(self.dad_quotes)
            nearest.show_dialog(quote, duration=180)

    def _feed_pets(self, x, y):
        num_poops = random.randint(3, 6)
        for i in range(num_poops):
            px = random.randint(max(50, x - 150), min(self.screen_w - 50, x + 150))
            py = 10 + random.randint(0, 30)
            target = random.choice(self.pets)
            poop = PoopDrop(self.canvas, px, py, target, self.feed_text)
            self.poops.append(poop)

    def _refresh_window_rects(self):
        if hasattr(self, '_hwnd'):
            self.window_rects = get_visible_windows_rects(exclude_hwnd=self._hwnd)
        else:
            self.window_rects = get_visible_windows_rects()
        if self.running:
            self.root.after(2000, self._refresh_window_rects)

    def _game_loop(self):
        if not self.running:
            return
        self.canvas.delete('all')
        for pet in self.pets:
            pet.update(self.screen_w, self.screen_h, self.window_rects)
            pet.draw()
        active_poops = []
        for poop in self.poops:
            poop.update()
            poop.draw()
            if poop.active:
                active_poops.append(poop)
        self.poops = active_poops
        if not hasattr(self, '_hwnd'):
            self._hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        self.root.after(16, self._game_loop)

    def _quit(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = BrotherPetApp()
    app.run()
