# 使用 uv（项目依赖与环境管理）

本项目使用 `uv`：

- 管理依赖（写入 `pyproject.toml`）
- 锁定依赖树（写入 `uv.lock`）
- 创建/同步虚拟环境（默认 `.venv/`）
- 运行命令（在虚拟环境里执行）

## 1) 初次安装 / 同步环境

在项目根目录执行：

```bash
uv sync
```

如果你只想安装运行所需依赖（不装开发工具 pytest/ruff）：

```bash
uv sync --no-dev
```

校验当前环境是否与 `uv.lock` 一致（不做修改）：

```bash
uv sync --check
```

## 2) 运行脚本/命令

在虚拟环境中运行任意命令：

```bash
uv run <command>
```

运行 Python 脚本（本项目文档示例）：

```bash
uv run python scripts/run_detection.py
uv run python scripts/run_detection.py --config config/config.toml
```

## 3) 添加/移除依赖（会更新 pyproject 与锁文件）

添加运行依赖：

```bash
uv add <package>
```

添加开发依赖（写入 `[dependency-groups].dev`）：

```bash
uv add --dev <package>
```

移除依赖：

```bash
uv remove <package>
```

一般工作流（推荐）：

1. `uv add ...` / `uv add --dev ...`
2. `uv sync`
3. `uv run pytest` / `uv run ruff check .`
4. 提交 `pyproject.toml` 与 `uv.lock`

## 4) 常见问题

### 4.1 缓存目录权限问题

可临时指定缓存目录：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

### 4.2 torch/torchvision (CPU/CUDA) 安装策略

`torch/torchvision` 体积较大，且 CPU/CUDA wheel 的选择与平台/驱动/索引源有关。

建议：

- 推理设备通过 `config` 里的 `model.device` 控制（`cpu` / `cuda` / `cuda:0`）
- 若你需要特定 CUDA 版本或希望 CPU-only，请优先参考 PyTorch 官方安装指引，然后用 `uv add`/版本约束把最终结果固化到项目中
