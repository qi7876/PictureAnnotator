# 调参指南（远景小人，召回优先）

本项目的目标是检测远景小人，默认建议开启 SAHI 切片推理以提升召回。

如果你没有标注数据，推荐用“可视化 + 统计”进行快速迭代：每次只改 1~2 个参数，跑一遍，观察变化并记录在新的 config 文件里（便于回滚/对比）。

## 快速迭代闭环（推荐）

1) 打开可视化与空结果输出（避免盲调）：

- `visualization.enabled=true`
- `output.write_empty=true`

2) 跑一遍：

```bash
uv run python scripts/run_detection.py
```

3) 看可视化（主观判断漏检/误检/重复框）：

- `data/visual_output/`

4) 看统计（量化趋势）：

```bash
uv run python scripts/summarize_results.py
```

## 推荐调参顺序（影响最大优先）

### 1) `model.confidence_threshold`：召回/误检最直接旋钮

- 降低阈值 → 召回更高、误检更多
- 提高阈值 → 误检更少、漏检更多

远景小人常见起点：`0.10`。漏人多可试 `0.05`。

### 2) SAHI 切片：远景小人最关键

开启 SAHI 后，相当于“局部放大再检”。常用旋钮：

- `sahi.slice_width / sahi.slice_height`：切片越小越“放大”，小人更容易检到，但更慢  
  典型：`640 → 512`
- `sahi.overlap_width_ratio / sahi.overlap_height_ratio`：重叠越大，越不容易漏边缘目标，但更慢  
  典型：`0.2 → 0.3`

经验：如果你看到“很多小人漏掉”，优先调小切片并适当增加 overlap。

### 3) SAHI 合并：减少重复框

切片推理常见重复框（同一人跨切片多次检测），优先调：

- `sahi.postprocess_match_threshold`（NMS IoU 阈值）  
  越小 → 合并更激进（重复框更少，但可能把相邻人误合并）  
  越大 → 更保守（重复框可能更多）

### 4) `model.imgsz`：给模型更多像素

`imgsz` 越大通常对小目标更友好，但更慢。

- 非 SAHI：直接作为 Ultralytics `predict(imgsz=...)`
- SAHI：作为 SAHI 后端模型的 `image_size`

典型：`1280 → 1536`（更慢但可能更稳）

### 5) `model.weights`：更大模型通常更强

在不追求速度时，可尝试更大权重：

- `yolov8m.pt → yolov8l.pt → yolov8x.pt`

注意：更大模型也可能带来更多误检，需要结合 `confidence_threshold` 回调。

### 6) 其它常用项

- `model.max_det`：每张图最多输出多少个框。召回优先可适当调大，避免被截断。
- `output.overwrite=false`：断点续跑/对比不同 config 时很有用（配合不同输出目录）。

## 常见问题与排查

### 1) 输出全空/非常少

检查：

- `input.dir` 是否指向正确目录，`extensions` 是否匹配
- `model.weights` 文件是否存在（或是否为可自动下载的权重名）
- `model.device` 是否可用（例如某些环境没有 CUDA）

### 2) 重复框很多

- 先调小 `sahi.postprocess_match_threshold`
- 然后再看是否需要降低 overlap（太大 overlap 可能加剧重复）

### 3) 误检很多（但你又想保召回）

- 适当上调 `model.confidence_threshold`
- 或增大模型并同时上调阈值（更强的模型 + 更严格阈值，有时比弱模型 + 很低阈值更干净）

## 建议的起步配置（1920×1080 远景小人）

这是一个“召回优先”的常见起点（仅供参考，需结合你的数据分布）：

- `model.confidence_threshold=0.10`
- `model.imgsz=1280`
- `sahi.slice_width=sahi.slice_height=640`
- `sahi.overlap_*_ratio=0.2`
- `sahi.postprocess_match_threshold=0.5`

更详细参数含义见 `docs/CONFIG.md`，输出格式见 `docs/OUTPUT_SCHEMA.md`。
