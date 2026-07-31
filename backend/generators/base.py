"""图像生成器抽象基类。

不同素材来源实现同一接口，使后端可插拔：
- LocalAssetGenerator：复用示例素材 / 用户上传的帧图（无需外部 API）
- OpenAIGenerator：接入 OpenAI 图像 API，从照片自动生成（需 key）
"""
from abc import ABC, abstractmethod
import os
import shutil


class ImageGenerator(ABC):
    name = 'base'

    @abstractmethod
    def prepare_assets(self, pet_cfg: dict, assets_dir: str) -> dict:
        """确保 assets_dir 中具备 pet_cfg['assets'] 引用的素材文件。

        Args:
            pet_cfg: 单个宠物的配置，含 'assets': {state: filename}
            assets_dir: 本次任务素材目录（已包含用户上传的文件）
        Returns:
            实际可用的素材映射 {state: filename}
        """
        raise NotImplementedError
