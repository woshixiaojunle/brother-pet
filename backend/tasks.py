"""任务管理与 exe 打包流水线。

- BuildTask：保存单个生成任务的状态 / 日志 / 结果
- build_exe()：在后台线程中执行
    1) 准备任务目录与 assets/
    2) 调用图像生成器准备素材
    3) 写入 config.json
    4) 复制 pet_runtime.py
    5) 调用 PyInstaller 打包到用户指定路径
"""
import os
import sys
import json
import uuid
import shutil
import subprocess
import threading
from pathlib import Path

from generators.local_asset import LocalAssetGenerator
from generators.openai_gen import OpenAIGenerator

BACKEND_DIR = Path(__file__).parent
PET_RUNTIME = BACKEND_DIR / 'pet_runtime.py'
SAMPLE_ASSETS = BACKEND_DIR.parent / 'assets'        # 项目级示例素材
GEN_GIFS = BACKEND_DIR.parent / 'generated-gifs'     # AI 生成的 GIF 动画素材
GEN_ROOT = BACKEND_DIR.parent / 'gen_tasks'          # 任务工作区

TASKS = {}  # task_id -> BuildTask


class BuildTask:
    def __init__(self, task_id: str):
        self.id = task_id
        self.status = 'pending'      # pending | running | done | error
        self.logs = []
        self.result = None           # 生成的 exe 路径
        self.error = None
        self.dir = GEN_ROOT / task_id

    def log(self, msg: str):
        self.logs.append(msg)
        print(f'[{self.id}] {msg}', flush=True)


def _make_generator(name: str):
    search = [str(SAMPLE_ASSETS), str(GEN_GIFS)]
    if name == 'openai':
        try:
            return OpenAIGenerator(search)
        except Exception:
            return LocalAssetGenerator(search)
    return LocalAssetGenerator(search)


def build_exe(task_id: str, config: dict, output_path: str,
              uploaded_files: dict, generator_name: str = 'local'):
    """在后台线程执行打包。uploaded_files: {filename: local_saved_path}"""
    task = TASKS.get(task_id)
    if task is None:
        return
    task.status = 'running'
    try:
        task.dir.mkdir(parents=True, exist_ok=True)
        assets_dir = task.dir / 'assets'
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 1) 保存上传的素材文件
        for fname, saved in uploaded_files.items():
            dst = assets_dir / fname
            if os.path.exists(saved):
                shutil.copy(saved, dst)
                task.log(f'已接收上传素材: {fname}')

        # 2) 生成/准备每个宠物的素材
        generator = _make_generator(generator_name)
        pets_out = []
        for idx, pc in enumerate(config.get('pets', [])):
            pc = dict(pc)
            pc.setdefault('id', f'pet{idx+1}')
            try:
                assets = generator.prepare_assets(pc, str(assets_dir))
            except Exception as e:
                task.log(f'[warn] 生成器失败，回退 local: {e}')
                assets = LocalAssetGenerator([str(SAMPLE_ASSETS), str(GEN_GIFS)]).prepare_assets(pc, str(assets_dir))
            pc['assets'] = assets
            if not assets:
                task.log(
                    f'[warn] 宠物「{pc.get("name")}」未匹配到任何素材，将不会出现在 exe 中！'
                    f'请检查所选示例素材名是否存在、或上传文件是否成功。'
                )
            pets_out.append(pc)
        config['pets'] = pets_out

        # 3) 写 config.json
        cfg_path = task.dir / 'config.json'
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        task.log('已写入 config.json')

        # 4) 复制运行时
        shutil.copy(PET_RUNTIME, task.dir / 'pet_runtime.py')
        task.log('已复制 pet_runtime.py')

        # 5) PyInstaller 打包
        out = Path(output_path)
        out_dir = out.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        name = out.stem
        # 若已存在同名（旧产物），尝试先删除
        if out.exists():
            try:
                out.unlink()
            except Exception as e:
                task.log(f'[warn] 无法删除旧 exe: {e}')

        sep = os.pathsep
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--noconfirm', '--onefile', '--windowed',
            '--name', name,
            '--distpath', str(out_dir),
            '--workpath', str(task.dir / 'build'),
            '--specpath', str(task.dir),
            '--add-data', f'assets{sep}assets',
            # 注意：config.json 是「文件」，目标目录必须是根目录 '.'，
            # 若写成 'config.json' 会被当成目录，导致打包成 config.json/config.json 而读不到
            '--add-data', f'config.json{sep}.',
            'pet_runtime.py',
        ]
        task.log('开始打包（PyInstaller）...')
        proc = subprocess.Popen(
            cmd, cwd=str(task.dir),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip('\n')
            if line:
                task.log(line)
        proc.wait()

        expected = out_dir / f'{name}.exe'
        if proc.returncode == 0 and expected.exists():
            task.result = str(expected)
            task.status = 'done'
            task.log(f'打包成功: {expected}')
        else:
            task.status = 'error'
            task.error = f'PyInstaller 返回码 {proc.returncode}，未生成 exe'
            task.log(task.error)
    except Exception as e:
        task.status = 'error'
        task.error = str(e)
        task.log(f'[ERROR] {e}')


def start_build(config: dict, output_path: str, uploaded_files: dict,
                generator_name: str = 'local') -> str:
    task_id = uuid.uuid4().hex[:12]
    task = BuildTask(task_id)
    TASKS[task_id] = task
    t = threading.Thread(
        target=build_exe,
        args=(task_id, config, output_path, uploaded_files, generator_name),
        daemon=True,
    )
    t.start()
    return task_id
