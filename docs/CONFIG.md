# 配置说明（config/config.toml）

本项目通过 TOML 配置控制输入目录、输出目录、模型/切片参数等。

## 选择配置文件

默认使用 `config/config.toml`，也可以运行时指定：

```bash
uv run python scripts/run_detection.py --config config/config.toml
```

> 应用层仅支持 `--config` 这一项 CLI 参数，不提供更多命令行覆盖配置。

## 路径规则

配置里的所有相对路径（如 `input.dir`、`output.dir`、`model.weights`）均相对 **项目根目录**（含 `pyproject.toml` 的目录）解析，而不是相对 config 文件所在目录解析。

推荐目录约定：

- `data/dataset/`：原始图片数据集（输入）
- `data/weights/`：模型权重（自动下载/缓存）
- `data/output/`：检测结果 JSON
- `data/visual_output/`：画框可视化输出

## 完整示例

参考 `config/config.example.toml`。

## 参数详解

### [input]

- `dir`（string，默认：`data/dataset`）  
  输入目录。支持绝对路径/相对路径。
- `recursive`（bool，默认：`false`）  
  是否递归读取子目录。
- `extensions`（string[]，默认：`[".png",".jpg",".jpeg"]`）  
  允许的图片扩展名（大小写不敏感）。建议统一小写并带点。

### [output]

- `dir`（string，默认：`data/output`）  
  输出标注文件目录。
- `overwrite`（bool，默认：`true`）  
  已存在输出文件时是否覆盖。  
  - `true`：重新跑会覆盖旧结果  
  - `false`：已存在则跳过该图片（适合断点续跑）
- `write_empty`（bool，默认：`true`）  
  没有检测结果时是否也写空 JSON。建议调参阶段保持 `true`，方便排查“完全漏检”的图片。

输出路径会保留相对结构：`output.dir/<相对路径>/<图片同名>.json`

### [visualization]

用于输出画框图（依赖 `Pillow`）。

- `enabled`（bool，默认：`true`）  
  是否输出画框图。
- `dir`（string，默认：`data/visual_output`）  
  可视化输出目录。
- `box_color`（int[3]，默认：`[0,255,0]`）  
  RGB 颜色。
- `line_width`（int，默认：`2`）  
  线宽（像素）。
- `write_label`（bool，默认：`true`）  
  是否在框左上角写 `id:score`。

### [model]

注意：本项目只输出 **person** 类别（COCO person）。

- `weights`（string，默认：`data/weights/yolov8x.pt`）  
  YOLO 权重文件。
  - 可写成“裸文件名”（如 `yolov8m.pt`），程序会把它下载/缓存到 `data/weights/` 再使用
  - 也可写成路径（绝对/相对项目根）
  - 若文件不存在：会尝试下载 Ultralytics 已知权重名；否则报错提示你检查路径
  - 本项目推荐使用 COCO 检测权重（person 类别齐全）：`yolov8n.pt` / `yolov8s.pt` / `yolov8m.pt` / `yolov8l.pt` / `yolov8x.pt`
  - 如需查看当前环境可自动下载的官方权重名列表，可运行：`uv run python -c "from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES; print('\\n'.join(GITHUB_ASSETS_NAMES))"`
- `device`（string，默认：`cpu`）  
  推理设备：`cpu` / `cuda` / `cuda:0`。  
  若你配置了 `cuda` 但当前环境不可用（驱动/运行环境限制等），可能会回退到 CPU 或报错。
- `confidence_threshold`（float，默认：`0.10`）  
  置信度阈值。召回优先可降低（例如 `0.05`），但误检会增加。
- `iou_threshold`（float，默认：`0.5`）  
  仅在关闭 SAHI（`sahi.enabled=false`）时，用于 YOLO 原生 NMS 的 IoU 阈值。
- `imgsz`（int，默认：`1280`）  
  推理尺寸。通常越大对小目标更友好，但更慢。  
  - SAHI 模式：作为 `image_size` 传给 SAHI/Ultralytics 后端模型  
  - 非 SAHI：作为 `imgsz` 传给 Ultralytics `predict`
- `max_det`（int，默认：`300`）  
  每张图最多输出多少个框（按分数降序截断）。召回优先时可适当调大。

### [sahi]

用于远景小目标（小人）检测。开启后会对图片进行切片推理，再把切片结果合并。

- `enabled`（bool，默认：`true`）  
  是否启用切片推理。远景小人强烈建议开启。
- `slice_height / slice_width`（int，默认：`640/640`）  
  切片大小。越小越“放大”，召回更好但更慢。
- `overlap_height_ratio / overlap_width_ratio`（float，默认：`0.2/0.2`）  
  切片重叠比例。越大越不容易漏边缘目标，但更慢。
- `postprocess_type`（string，默认：`NMS`）  
  合并策略，通常使用 `NMS`。
- `postprocess_match_metric`（string，默认：`IOU`）  
  合并度量，通常使用 `IOU`。
- `postprocess_match_threshold`（float，默认：`0.5`）  
  合并阈值（NMS IoU 阈值）。越小合并越激进（重复框更少，但可能误合并邻近人）。
