"""OpenAI 图像生成器（可插拔，默认不启用）。

当用户配置 generator='openai' 且设置了 OPENAI_API_KEY 时启用：
从上传的原始照片自动生成「猴子爬行」各状态帧图。

接入说明：
1. pip install openai
2. 环境变量 OPENAI_API_KEY=sk-xxx（可选 OPENAI_BASE_URL 走代理/兼容端点）
3. 前端上传每张照片（字段 photo），config.pets[i].photo 指向该文件

下面给出可运行的调用骨架（基于 openai >= 1.0 的 images.edit）。
未配置 key 时 client 为 None，prepare_assets 会抛错，由 server 自动回退 local。
"""
import os

from .base import ImageGenerator

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


STATES = ['crawl', 'climb', 'sit', 'happy']

PROMPTS = {
    'crawl': 'cute cartoon mascot crawling on all fours like a monkey, transparent background, '
             'keep the person\'s face/hair/outfit, playful expression',
    'climb': 'cute cartoon mascot climbing upward like a monkey, transparent background, '
             'keep the person\'s face/hair/outfit',
    'sit': 'cute cartoon mascot sitting relaxed like a monkey, transparent background, '
           'keep the person\'s face/hair/outfit',
    'happy': 'cute cartoon mascot jumping with joy, arms raised, transparent background, '
             'keep the person\'s face/hair/outfit',
}


class OpenAIGenerator(ImageGenerator):
    name = 'openai'

    def __init__(self, search_dirs):
        if isinstance(search_dirs, str):
            search_dirs = [search_dirs]
        self.sample_dir = search_dirs[0] if search_dirs else ''
        self.key = os.environ.get('OPENAI_API_KEY')
        self.base_url = os.environ.get('OPENAI_BASE_URL')
        self.client = OpenAI(api_key=self.key, base_url=self.base_url) if (OpenAI and self.key) else None

    def prepare_assets(self, pet_cfg: dict, assets_dir: str) -> dict:
        if self.client is None:
            raise RuntimeError('OPENAI_API_KEY 未配置，无法使用 openai 生成器（已回退 local）')
        photo = pet_cfg.get('photo')
        if not photo or not os.path.exists(photo):
            raise RuntimeError('缺少原始照片，无法用 openai 生成（已回退 local）')

        result = {}
        for state in STATES:
            # 调用 images.edit（图生图）。模型名按你的账户可用模型调整，如 'gpt-image-1' / 'dall-e-3'。
            resp = self.client.images.edit(
                model=os.environ.get('OPENAI_IMAGE_MODEL', 'gpt-image-1'),
                image=open(photo, 'rb'),
                prompt=PROMPTS[state],
                size='512x512',
                n=1,
            )
            # 保存：gpt-image-1 返回 b64_json；dall-e 返回 url。这里按 b64 处理。
            data = resp.data[0]
            fname = f"{pet_cfg.get('id', 'pet')}_{state}.png"
            out = os.path.join(assets_dir, fname)
            if getattr(data, 'b64_json', None):
                import base64
                with open(out, 'wb') as f:
                    f.write(base64.b64decode(data.b64_json))
            elif getattr(data, 'url', None):
                import urllib.request
                urllib.request.urlretrieve(data.url, out)
            result[state] = fname
        return result
