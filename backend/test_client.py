"""HTTP 端到端测试客户端：POST 配置 -> 轮询 -> 下载 exe。

用法：
    python test_client.py
依赖：仅标准库（urllib）。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:8996'

CFG = {
    "pets": [
        {"name": "白T眼镜哥", "assets": {"crawl": "pet1_crawl_1.png", "climb": "pet1_climb.png",
                                         "sit": "pet1_crawl_1.png", "happy": "pet1_happy.png"}},
        {"name": "黑T恤兄弟", "assets": {"crawl": "pet2_crawl.png", "climb": "pet2_crawl.png",
                                         "sit": "pet2_sit.png", "happy": "pet2_happy.png"}},
    ],
    "settings": {"crawl_speed": 6, "jump_chance": 0.5, "sit_chance": 0.0015},
    "dad_quotes": ["叫爸爸！", "爸爸抱抱~"],
    "feed_text": "感谢爸爸投喂！",
    "output_path": r"D:\workcode\person\brother-pet\gen_tasks\http_test\BrotherPet.exe",
    "generator": "local",
}


def _post_multipart(url, fields):
    boundary = '----bptestboundary'
    body = b''
    for name, value in fields:
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += value.encode('utf-8') + b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')


def main():
    print('=== POST /api/generate ===')
    resp = _post_multipart(f'{BASE}/api/generate', [('config', json.dumps(CFG, ensure_ascii=False))])
    print(resp)
    data = json.loads(resp)
    tid = data.get('task_id')
    if not tid:
        print('未返回 task_id，退出'); sys.exit(1)

    print('=== poll ===')
    for i in range(60):
        try:
            with urllib.request.urlopen(f'{BASE}/api/tasks/{tid}', timeout=10) as r:
                task = json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print('  轮询错误', e); break
        st = task.get('status')
        print(f'  [{i+1}] {st}')
        if st in ('done', 'error'):
            if task.get('error'):
                print('  ERROR:', task['error'])
            if task.get('logs'):
                print('  --- 末 6 行日志 ---')
                for line in task['logs'][-6:]:
                    print('   ', line)
            break
        time.sleep(3)

    print('=== download ===')
    out = r'D:\workcode\person\brother-pet\gen_tasks\http_test\BrotherPet_http.exe'
    try:
        urllib.request.urlretrieve(f'{BASE}/api/download/{tid}', out)
        size = os.path.getsize(out)
        print(f'下载成功: {out}  ({size} bytes)')
        print('HTTP_E2E_OK')
    except Exception as e:
        print('下载失败:', e)


if __name__ == '__main__':
    main()
