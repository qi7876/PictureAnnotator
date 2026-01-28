# 输出 JSON 格式（每张图一个文件）

本项目的输出是“每张图片一个 JSON 文件”。

## 文件位置与命名

- 文件名与图片同名（扩展名改为 `.json`）
- 路径结构与输入目录保持一致（保留相对路径）

示例（默认配置）：

- 输入：`data/dataset/sub/a.png`
- 输出：`data/output/sub/a.json`

## 版本

- `format_version`：用于区分 schema 版本，当前为 `"1.0"`

示例：

```json
{
  "format_version": "1.0",
  "image": {
    "file_name": "test_0000.png",
    "relative_path": "test_0000.png",
    "width": 1920,
    "height": 1080
  },
  "detections": [
    {
      "id": 0,
      "bbox": [100.5, 200.0, 140.3, 280.8],
      "score": 0.92
    }
  ]
}
```

## 字段说明

### image

- `image.file_name`：图片文件名（不含目录）
- `image.relative_path`：相对输入目录的路径（统一使用 `/` 分隔）
- `image.width / image.height`：图片尺寸（像素）

### detections

`detections` 是一个列表，每个元素表示一个 **person** 检测结果（仅输出 COCO person）。

- `detections[*].id`：同一张图内从 0 开始递增，按 `score` 从高到低分配  
  说明：这是“同一张图内的编号”，不是跨图追踪 ID。
- `detections[*].score`：置信度分数（0~1）
- `detections[*].bbox`：`[xmin, ymin, xmax, ymax]`（像素坐标，float）  
  坐标系约定：
  - 原点在图片左上角
  - x 轴向右，y 轴向下

注意事项：

- `bbox` 可能包含小数，也可能出现略微越界（例如 -0.2 或略大于宽高），这是检测模型的常见行为；如需严格像素裁剪，可在下游进行 clamp。

## 扩展字段（可选）

输出 JSON 允许额外扩展字段（例如未来加入运行参数、耗时等），建议使用顶层 `extra` 字段承载，不影响既有解析逻辑。
