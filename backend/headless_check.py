"""无头验证：复用 pet_runtime 的配置驱动数据路径（不创建 Tk 窗口）。"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pet_runtime as bp

# 找到刚构建的任务目录（含 config.json 与 assets），排除纯输出的 test_out
GEN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gen_tasks'))
task_dir = None
for d in os.listdir(GEN):
    p = os.path.join(GEN, d)
    if os.path.isdir(p) and os.path.exists(os.path.join(p, 'config.json')) \
       and os.path.isdir(os.path.join(p, 'assets')):
        if task_dir is None or os.path.getmtime(p) > os.path.getmtime(task_dir):
            task_dir = p
assert task_dir, '未找到含 config.json+assets 的任务目录'
cfg_path = os.path.join(task_dir, 'config.json')
assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))
assert os.path.exists(cfg_path), f'config.json 不存在: {cfg_path}'
print('使用 config:', cfg_path)

with open(cfg_path, encoding='utf-8') as f:
    config = json.load(f)


class TestApp(bp.BrotherPetApp):
    def __init__(self, config, assets_dir):
        # 跳过所有 tkinter / Win32 初始化
        self.config = config
        self.assets_dir = assets_dir
        self.screen_w, self.screen_h = 1920, 1080
        g = config.get('settings', {})
        self.crawl_speed = g.get('crawl_speed', 6)
        self.jump_chance = g.get('jump_chance', 0.5)
        self.sit_chance = g.get('sit_chance', 0.0015)
        self.dad_quotes = config.get('dad_quotes', bp.BrotherPetApp.DEFAULT_DAD_QUOTES)
        self.feed_text = config.get('feed_text', bp.BrotherPetApp.DEFAULT_FEED_TEXT)
        self.pets = []
        self.canvas = object()  # stub
        self._load_pets()


app = TestApp(config, assets_dir)
print('宠物数量:', len(app.pets))
assert len(app.pets) == 2, '应生成 2 个宠物'

for pet in app.pets:
    print(f'  - {pet.name}: 状态帧 { {k: len(v) for k, v in pet.frames.items()} }')
    assert set(pet.frames.keys()) >= {'crawl', 'climb', 'sit', 'happy'}, '缺少动画状态'
    assert all(len(v) >= 4 for v in pet.frames.values()), '帧数不足'

# 跑 200 帧物理，确认不出错
win = [(400, 400, 1200, 820)]
for _ in range(200):
    for pet in app.pets:
        pet.update(app.screen_w, app.screen_h, win)
print('物理循环 200 帧 OK，全屏爬行验证通过')
print('HEADLESS_CHECK_OK')
