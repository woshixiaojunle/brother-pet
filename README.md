# Brother Pet · 桌面猴子宠物生成器

把真人照片变成「像猴子一样在桌面上爬行玩耍」的桌面宠物，并一键打包成可分享的 `.exe`。
项目提供 **Vue3 前端**（可视化配置）+ **Python/FastAPI 后端**（素材准备 + 打包流水线），前端设置素材与参数后，后端自动生成到指定路径的 `exe` 文件。

---

## 一、功能特性

| 功能 | 说明 |
|------|------|
| 🐵 多宠物桌面爬行 | 透明置顶窗口，多个宠物在全屏范围内自由爬行、跳跃、玩耍 |
| 🪟 窗口边缘感知 | 通过 Win32 API 枚举桌面窗口，把每个窗口的**顶面**当作可站 / 可攀爬的平台 |
| 🎞️ 程序化多帧动画 | 用 PIL 给每张原图生成爬行 / 攀爬 / 坐姿 / 开心 4 套循环帧（上下浮动、摇摆旋转、挤压拉伸） |
| 🖱️ 右键「叫爸爸」 | 点击后最近的宠物弹出对话框，随机播放台词 |
| 💩 右键「投喂」 | 屏幕顶部掉落 💩 图标，砸中宠物后切换开心跳跃动画并弹出「感谢爸爸投喂！」 |
| ⚙️ 可编辑配置 | 宠物名单、素材、动画参数（速度 / 跳跃频率 / 发呆频率）、台词均可前端配置 |
| 📦 一键生成 exe | 后端调用 PyInstaller 把运行时 + 素材 + 配置打包成**单文件免安装 exe** |
| 🔌 可插拔素材生成 | 默认复用示例 / 上传素材（`local`），预留 OpenAI 图像生成接口 |

---

## 二、技术栈

- **前端**：Vue 3 + Vite + 原生 `<script setup>`，Axios（封装于 `src/api.js`）
- **后端**：Python 3.13 + FastAPI + Uvicorn + python-multipart
- **桌面运行时**：`tkinter`（透明置顶窗口）+ `ctypes` 调用 Win32 API（窗口枚举）
- **图像处理**：Pillow（多帧动画生成、透明通道合成）
- **打包**：PyInstaller（`--onefile --windowed`，内置 `config.json` + `assets`）
- **素材生成**：`generators` 抽象层 —— `LocalAssetGenerator`（默认）/ `OpenAIGenerator`（预留）

---

## 三、目录层级

```
brother-pet/
├── README.md                  # 本文件
├── assets/                    # 项目级示例素材（AI 生成的猴子爬行帧 PNG）
│   ├── pet1_crawl_1.png
│   ├── pet1_climb.png
│   ├── pet1_happy.png
│   ├── pet2_crawl.png
│   ├── pet2_sit.png
│   └── pet2_happy.png
├── photo/                     # 原始输入照片
│   ├── pet_001.jpg
│   └── pet_002.jpg
├── brother_pet.py             # 早期单文件版（历史，已被后端架构取代）
├── backend/                   # ★ 后端：生成服务 + 打包流水线
│   ├── server.py              # FastAPI 入口，提供 HTTP API
│   ├── tasks.py               # 任务管理 + PyInstaller 打包流水线
│   ├── pet_runtime.py         # 运行时本体（被打进 exe，从 config.json 读配置）
│   ├── requirements.txt       # 后端依赖
│   ├── generators/            # 素材生成器（可插拔）
│   │   ├── __init__.py
│   │   ├── base.py            # 生成器抽象基类
│   │   ├── local_asset.py     # 本地素材 / 上传素材（默认）
│   │   └── openai_gen.py      # OpenAI 图像生成（预留，需 API key）
│   ├── test_client.py         # HTTP 端到端测试客户端
│   └── _e2e_test.py           # 后端打包流水线无头测试
├── frontend/                  # ★ 前端：Vue3 配置界面
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js         # 含 /api 代理到后端 8996
│   └── src/
│       ├── main.js
│       ├── api.js             # 后端接口封装
│       ├── App.vue            # 主页面（表单 + 进度 + 下载）
│       └── components/
│           └── PetEditor.vue  # 宠物编辑子组件
└── gen_tasks/                 # 生成任务工作区（每次请求一个子目录）
    ├── <task_id>/             # 单次生成任务
    │   ├── config.json        # 本次使用的配置
    │   ├── pet_runtime.py     # 复制的运行时
    │   ├── assets/            # 本次素材
    │   ├── build/             # PyInstaller 工作目录
    │   └── <Name>.spec
    └── http_test/BrotherPet.exe   # 示例成品 exe
```

> 说明：`dist/`、`build*/`、`node_modules/`、`.workbuddy/` 等为构建产物或环境目录，不纳入版本管理。

---

## 四、配置 Schema（config.json）

后端把前端提交的配置写成 `config.json`，运行时 `pet_runtime.py` 在 exe 内读取它：

```jsonc
{
  "pets": [
    {
      "name": "白T眼镜哥",          // 宠物显示名（用于调试/日志）
      "assets": {                 // 各动作对应素材文件名（位于 assets/ 内）
        "crawl": "pet1_crawl_1.png",
        "climb": "pet1_climb.png",
        "sit":   "pet1_crawl_1.png",
        "happy": "pet1_happy.png"
      }
    }
  ],
  "settings": {                  // 动画 / 行为参数
    "crawl_speed": 6,            // 爬行速度（像素/帧）
    "jump_chance": 0.5,          // 主动跳向其他平台的频率
    "sit_chance": 0.0015         // 随机发呆概率
  },
  "dad_quotes": ["叫爸爸！", "爸爸抱抱~"],  // 「叫爸爸」随机台词池
  "feed_text": "感谢爸爸投喂！",            // 「投喂」触发后弹出的文本
  "output_path": "D:\\...\\BrotherPet.exe", // 生成 exe 的目标路径
  "generator": "local"          // 素材生成器：local | openai
}
```

---

## 五、后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health`        | 健康检查 |
| GET  | `/api/samples`       | 返回可用示例素材列表（供前端下拉选择） |
| POST | `/api/generate`      | 提交生成任务。`multipart/form-data`：`config`（JSON 字符串）+ 可选 `files`（上传帧图）。返回 `task_id` |
| GET  | `/api/tasks/{id}`    | 轮询任务状态：`pending / running / done / error`，含实时日志 |
| GET  | `/api/download/{id}` | 下载生成的 exe（仅 `done` 状态可用） |

**生成流程**：`接收配置/上传 → 生成或准备素材 → 写 config.json → 复制 pet_runtime.py → PyInstaller 打包到 output_path`。

---

## 六、快速开始

### 1. 启动后端（默认 127.0.0.1:8996）

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8996
```

### 2. 启动前端（默认 127.0.0.1:5173）

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`：
1. 添加 / 删除宠物，选择示例素材或上传帧图（PNG，透明背景最佳）
2. 调整爬行速度、跳跃频率、发呆频率
3. 填写「叫爸爸」台词池与「投喂」文本
4. 指定输出 exe 路径（如 `D:\brother-pet\BrotherPet.exe`）
5. 点击「生成 exe」，等待进度条完成，下载即可双击运行

---

## 七、素材生成器

`backend/generators/` 是可插拔的素材来源抽象：

- **`local`（默认）**：直接使用 `assets/` 下的示例图，或用户在前端上传的帧图。零额外成本，先把全链路跑通。
- **`openai`（预留）**：在 `openai_gen.py` 中已实现调用 OpenAI 图像 API 从照片生成猴子爬行帧的骨架，需提供 `OPENAI_API_KEY` 与 `base_url` 后，将配置 `generator` 改为 `"openai"` 即可启用。

---

## 八、注意事项 / 已知问题

- **Windows Defender 拦截**：运行时使用 Win32 API 枚举 / 操作窗口，首次运行 exe 可能被拦截，点击「仍要运行」即可。
- **仅支持 Windows**：桌面宠物依赖 `ctypes.windll.user32` 与 tkinter 置顶窗口，暂未适配 macOS / Linux。
- **素材质量**：当前示例素材为 AI 生成卡通版；接入真人或更精细动画可在 `generators` 层扩展。
- **运行退出**：右键菜单提供「退出」选项（无系统托盘图标，纯透明窗口）。

---

## 九、架构概览

```
┌─────────────┐     HTTP /api      ┌──────────────────┐
│  Vue3 前端   │ ───────────────▶ │  FastAPI 后端     │
│  (5173)     │   config + files  │  (8996)          │
└─────────────┘ ◀─────────────── └────────┬─────────┘
                       task + exe          │ build_exe()
                                           ▼
                                  ┌──────────────────┐
                                  │ PyInstaller 打包  │
                                  │ pet_runtime.py   │
                                  │ + assets +       │
                                  │   config.json    │
                                  └────────┬─────────┘
                                           ▼
                                  ┌──────────────────┐
                                  │  BrotherPet.exe  │
                                  │ (透明置顶桌面宠物) │
                                  └──────────────────┘
```
