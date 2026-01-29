# PictureAnnotator (YOLO + SAHI 远景人体检测)

给定一个图片目录，检测每张图中的所有 **person**（COCO person），并为每个人输出：

- `bbox(xmin, ymin, xmax, ymax)`（像素坐标，float）
- `score`
- `id`（同一张图内从 0 开始递增；按 `score` 从高到低分配；非跨图追踪 ID）

同时可选输出画框可视化图。

## 目录结构（推荐）

```text
PictureAnnotator/
  config/
    config.toml
    config.example.toml
  data/
    dataset/           # 输入图片（你自己的数据集）
    weights/           # 模型权重（自动下载/手动放置均可）
    output/            # 每张图一个同名 JSON
    visual_output/     # 画框图（可选）
  scripts/
  src/
  docs/
  pyproject.toml
  uv.lock
```

注意：`data/` 默认在 `.gitignore` 中被忽略，用来放大文件（数据集、权重、输出）。

## 快速开始（uv）

1. 安装/同步依赖（生成 `.venv/`）：

```bash
uv sync
```

2. 初始化目录结构（会创建 `data/dataset/`、`data/weights/`、`data/output/`、`data/visual_output/` 等）：

```bash
uv run python scripts/init_project.py
```

如需按其它配置初始化目录结构：

```bash
uv run python scripts/init_project.py --config config/exp1.toml
```

3. 把图片放到 `data/dataset/`（默认配置读取这里）

4. 运行检测（默认读 `config/config.toml`）：

```bash
uv run python scripts/run_detection.py
```

5. 查看输出：

- 结果 JSON：`data/output/`
- 可视化图：`data/visual_output/`

## 配置

- 默认配置文件：`config/config.toml`
- 可参考：`config/config.example.toml`
- 运行时可用 `--config` 指定其它配置文件（应用层仅支持这一项 CLI 参数，不提供更多参数覆盖配置）

```bash
uv run python scripts/run_detection.py --config config/config.toml
```

路径规则：

- 配置里的所有相对路径（如 `input.dir`、`output.dir`、`model.weights`）均相对**项目根目录**解析（含 `pyproject.toml` 的目录）

配置项详细解释见：

- `docs/CONFIG.md`
- `docs/OUTPUT_SCHEMA.md`

## 运行

默认使用 `config/config.toml`：

```bash
uv run python scripts/run_detection.py
```

结果统计（帮助快速调参）：

```bash
uv run python scripts/summarize_results.py
uv run python scripts/summarize_results.py --config config/config.toml
```

关于权重下载：

- `model.weights` 可以写成 `yolov8m.pt` 这种“裸文件名”，程序会把它下载/缓存到 `data/weights/` 再使用（推荐：`yolov8n/s/m/l/x.pt`）
- 也可以直接写成一个路径（如默认的 `data/weights/yolov8m.pt`），文件不存在时会尝试自动下载（仅对 Ultralytics 已知权重名生效）

## 输出

- 标注文件：`output.dir/<相对路径>/<图片同名>.json`（默认 `data/output/`）
- 可视化：`visualization.dir/<相对路径>/<图片同名>.png`（默认 `data/visual_output/`，可配）

输出格式详见 `docs/OUTPUT_SCHEMA.md`。

## 新手调参指南（一步一步）

目标：**召回优先**（尽量少漏人），允许一定误检；后续再通过阈值回调。

### 第 0 步：先把“可见性”拉满

建议先打开可视化与空结果输出，减少盲调：

- `visualization.enabled=true`
- `output.write_empty=true`

### 第 1 步：跑一个基线

```bash
uv run python scripts/run_detection.py
```

然后打开 `data/visual_output/` 看总体漏检/误检趋势。

### 第 2 步：优先调 `model.confidence_threshold`

这是影响召回/误检最直接的旋钮：

- 降低阈值 → **召回更高**、误检更多
- 提高阈值 → 误检更少、漏检更多

远景小人常见起点：`0.10`；漏人多可试 `0.05`。

### 第 3 步：远景小人最关键（SAHI 切片）

远景人物很小，整图推理容易漏。SAHI 切片相当于“局部放大再检”：

- `sahi.enabled=true`：建议保持开启
- `sahi.slice_width/slice_height`：切片越小 → 小人相对更大 → **更容易检到**，但更慢  
  典型：`640 → 512`
- `sahi.overlap_*_ratio`：重叠越大 → 边缘目标更不容易漏，但更慢  
  典型：`0.2 → 0.3`

### 第 4 步：处理重复框（切片合并）

切片推理常见问题：同一个人被多次检测（跨切片重复）。优先调：

- `sahi.postprocess_match_threshold`（NMS IoU 阈值）  
  越小 → 合并更激进（重复框更少，但可能把相邻的人误合并）  
  越大 → 更保守（重复框可能更多）

### 第 5 步：还漏小人？再加“模型能力/分辨率”

- `model.imgsz`：越大通常对小目标更友好，但更慢（SAHI 与非 SAHI 都会使用）
- `model.weights`：模型越大通常更强但更慢  
  可尝试：`yolov8m.pt → yolov8l.pt → yolov8x.pt`

### 第 6 步：用统计脚本辅助“量化”调参

```bash
uv run python scripts/summarize_results.py
```

重点看：

- `Detections/img` 是否在合理范围（过大可能误检多）
- `BBox area/image area` 分布（远景小人通常面积占比很小）

更系统的建议见 `docs/TUNING.md`。

## 使用 uv（本项目）

本项目用 `uv` 管理依赖与虚拟环境（`.venv/`），并用 `uv.lock` 锁定依赖树以保证可复现。

更详细的 uv 使用说明见 `docs/UV.md`。

常用命令：

- 安装/同步环境：`uv sync`
- 运行脚本/命令：`uv run ...`（本项目示例使用 `uv run python ...`）
- 添加依赖（会更新 `pyproject.toml` / `uv.lock`）：`uv add <pkg>`
- 添加开发依赖：`uv add --dev <pkg>`
- 校验锁文件一致性：`uv sync --check`

依赖改动建议工作流：

1. `uv add ...`（或手改 `pyproject.toml`）
2. `uv sync`
3. `uv run pytest` / `uv run ruff check .`
4. 提交 `pyproject.toml` 与 `uv.lock`

## 开发与测试

```bash
uv run pytest
uv run ruff check .
```

## GUI 标注编辑器（PySide6）

用于人工调整检测输出的 per-image JSON（会 **覆盖写回** `output.dir`）。

详细使用说明见：`docs/GUI.md`。

运行：

```bash
uv run python scripts/run_gui.py
```

常用操作：

- 左侧选择图片；切换图片/关闭软件时自动保存
- 右侧列表选中框后按 `D` 删除
- 点击工具栏“新增框(A)”后在画面拖拽创建新框（`score=1.0`，`id=max(id)+1`）
- 选中框为荧光橙，未选中为荧光绿；仅选中时显示角点手柄（拖左上/右下调整）
- `Ctrl + 滚轮` 缩放；拖动画面平移；工具栏“适配窗口”一键适配

打包（Windows，PyInstaller 目录模式）：

```bash
pyinstaller --noconsole --onedir scripts/run_gui.py -n PictureAnnotatorGUI
```

将 `dist/PictureAnnotatorGUI/` 作为“软件根目录”，并确保同目录下存在 `config/config.toml` 以及 `data/`。
