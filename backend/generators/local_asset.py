"""本地素材生成器（默认）。

直接复用示例素材目录中已有的帧图，或以用户上传的帧图为准。
无需任何外部 API，即可跑通「前端配置 → 打包 exe」完整链路。
"""
import os
import shutil

from .base import ImageGenerator


class LocalAssetGenerator(ImageGenerator):
    name = 'local'

    def __init__(self, search_dirs):
        if isinstance(search_dirs, str):
            search_dirs = [search_dirs]
        self.search_dirs = [d for d in search_dirs if d]

    def prepare_assets(self, pet_cfg: dict, assets_dir: str) -> dict:
        result = {}
        assets = pet_cfg.get('assets') or {}
        for state, fname in assets.items():
            if not fname:
                continue
            dst = os.path.join(assets_dir, fname)
            # 已上传的文件优先
            if os.path.exists(dst):
                result[state] = fname
                continue
            # 否则从搜索目录复制（支持 assets/ 与 generated-gifs/，含 GIF）
            src = None
            for d in self.search_dirs:
                cand = os.path.join(d, fname)
                if os.path.exists(cand):
                    src = cand
                    break
            if src:
                shutil.copy(src, dst)
                result[state] = fname
            else:
                # 缺失时尝试用 crawl 帧兜底
                crawl = assets.get('crawl')
                if crawl and crawl != fname and os.path.exists(os.path.join(assets_dir, crawl)):
                    result[state] = crawl
        return result
