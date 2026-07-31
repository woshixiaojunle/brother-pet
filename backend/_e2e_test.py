import sys, time, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasks import TASKS, start_build

cfg = {
  'pets': [
    {'name':'白T眼镜哥','assets':{'crawl':'pet1_crawl_1.png','climb':'pet1_climb.png','sit':'pet1_crawl_1.png','happy':'pet1_happy.png'}},
    {'name':'黑T恤兄弟','assets':{'crawl':'pet2_crawl.png','climb':'pet2_crawl.png','sit':'pet2_sit.png','happy':'pet2_happy.png'}},
  ],
  'settings': {'crawl_speed':6,'jump_chance':0.5,'sit_chance':0.0015},
  'dad_quotes':['叫爸爸！','爸爸抱抱~'], 'feed_text':'感谢爸爸投喂！',
  'output_path': r'D:\workcode\person\brother-pet\gen_tasks\test_out\BrotherPet.exe',
  'generator':'local',
}
try:
    tid = start_build(cfg, cfg['output_path'], {}, 'local')
    print('task started:', tid)
    for _ in range(180):
        t = TASKS[tid]
        if t.status in ('done','error'): break
        time.sleep(1)
    t = TASKS[tid]
    print('STATUS:', t.status)
    print('ERROR:', t.error)
    print('RESULT:', t.result)
    print('--- last 15 logs ---')
    for l in t.logs[-15:]: print(l)
    out = t.result if isinstance(t.result, str) else None
    if out and os.path.exists(out):
        print('EXE_EXISTS_SIZE:', os.path.getsize(out))
    else:
        print('EXE_MISSING')
except Exception:
    traceback.print_exc()
