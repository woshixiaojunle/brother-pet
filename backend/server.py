"""Brother Pet 生成后端（FastAPI）。

提供：
- GET  /api/health            健康检查
- GET  /api/samples           列出可用示例素材文件名（前端选示例用）
- POST /api/generate          接收配置(JSON) + 上传素材文件 → 异步打包 exe
- GET  /api/tasks/{task_id}   轮询任务状态 / 日志 / 结果
- GET  /api/download/{task_id}下载生成的 exe

运行：
    cd backend
    pip install -r requirements.txt
    python server.py
默认监听 http://127.0.0.1:8000
"""
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from tasks import TASKS, start_build

SAMPLE_ASSETS = Path(__file__).parent.parent / 'assets'

app = FastAPI(title='Brother Pet Generator')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_methods=['*'], allow_headers=['*'],
)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/samples')
def list_samples():
    """列出示例素材目录中的文件，供前端「用示例素材」下拉选择。"""
    if not SAMPLE_ASSETS.exists():
        return {'files': []}
    files = sorted(
        f.name for f in SAMPLE_ASSETS.iterdir()
        if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp')
    )
    return {'files': files}


@app.post('/api/generate')
async def generate(
    config: str = Form(..., description='JSON 字符串：{pets, settings, dad_quotes, feed_text, output_path, generator}'),
    files: list[UploadFile] = File(default=[]),
):
    """接收配置 + 可选上传的帧图，启动打包任务。

    约定：config.pets[i].assets[state] 为文件名；若有对应上传文件，
    其 UploadFile.filename 必须等于该文件名，后端会保存到任务 assets/。
    """
    import json
    try:
        cfg = json.loads(config)
    except Exception:
        raise HTTPException(status_code=400, detail='config 不是合法 JSON')

    output_path = cfg.get('output_path')
    if not output_path:
        raise HTTPException(status_code=400, detail='缺少 output_path（exe 输出路径）')
    if not cfg.get('pets'):
        raise HTTPException(status_code=400, detail='至少需要一个宠物')

    # 保存上传文件到临时目录，返回 {filename: saved_path}
    uploaded = {}
    tmp_root = Path(tempfile.mkdtemp(prefix='bp_up_'))
    for uf in files:
        if not uf.filename:
            continue
        saved = tmp_root / uf.filename
        with open(saved, 'wb') as f:
            shutil.copyfileobj(uf.file, f)
        uploaded[uf.filename] = str(saved)

    generator = cfg.get('generator', 'local')
    task_id = start_build(cfg, output_path, uploaded, generator)
    return {'task_id': task_id, 'status': 'running'}


@app.get('/api/tasks/{task_id}')
def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    return {
        'task_id': task.id,
        'status': task.status,
        'logs': task.logs[-200:],
        'result': task.result,
        'error': task.error,
    }


@app.get('/api/download/{task_id}')
def download(task_id: str):
    task = TASKS.get(task_id)
    if not task or task.status != 'done' or not task.result:
        raise HTTPException(status_code=404, detail='exe 尚未生成')
    return FileResponse(task.result, filename=os.path.basename(task.result))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8996)
