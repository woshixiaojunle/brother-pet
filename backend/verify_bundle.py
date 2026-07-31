"""直接读取生成的 exe 内部归档，确认 config.json 与 assets 被打入单文件 exe。"""
import os, sys
from PyInstaller.archive.readers import CArchiveReader

exe = r'D:\workcode\person\brother-pet\gen_tasks\test_out\BrotherPet.exe'
assert os.path.exists(exe), f'exe 不存在: {exe}'

with open(exe, 'rb') as f:
    archive = CArchiveReader(f.read() if False else exe)

# CArchiveReader 支持迭代 (name, typcd, data) ？不同版本 API 不同，做兼容
members = []
try:
    for name, _, _, data in archive:
        members.append(name)
except Exception:
    # 退回到 get 接口
    try:
        for name in archive.toc:
            members.append(name)
    except Exception:
        members = [str(x) for x in dir(archive)]

print('归档内成员数:', len(members))
joined = '\n'.join(str(m) for m in members)
for key in ['config.json', 'pet1_crawl_1.png', 'pet2_sit.png']:
    print(f'  含 {key} ?', key in joined)

assert 'config.json' in joined, 'config.json 未打进 exe！'
assert 'pet1_crawl_1.png' in joined, '素材未打进 exe！'
print('BUNDLE_OK: config.json 与素材均已打包进单文件 exe')
