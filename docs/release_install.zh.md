# 发布和安装验证清单

这份清单帮助维护者和早期用户确认 `prompt_control_lab` 可以通过源码、wheel、
`pipx` 或类似 `uvx` 的流程安装和试用。

Python 包名是 `promptcontrollab`。仓库和项目品牌名是 `prompt_control_lab`。

## 源码安装

```bash
git clone https://github.com/VeraPyuyi/prompt_control_lab.git
cd prompt_control_lab
pip install -e .
pcl doctor
```

预期结果：`pcl doctor` 会检查 Python 版本、包导入、CLI parser、guard policy 解析、
插件适配器、demo report 生成和可选依赖状态。

## 本地构建 wheel

```bash
python -m pip install build
python -m build
```

预期结果：`dist/` 中出现类似下面的 wheel：

```text
promptcontrollab-0.1.0-py3-none-any.whl
```

除非正式 release 流程明确要求，不要把 `dist/` 产物提交进仓库。

如果当前环境无法连接 PyPI 去安装隔离构建依赖，可以先在当前环境安装构建后端，
再运行：

```bash
python -m build --wheel --no-isolation
```

这个 fallback 用来验证项目包结构；它适合区分“网络或代理导致拿不到构建依赖”和
“项目本身无法打包”这两类问题。

## wheel 冒烟测试

可以创建临时环境，或用 `pipx`：

```bash
pipx install dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl --help
pcl doctor
pcl install-plugin all --target ./tmp-pcl-templates
pcl import prompt-optimizer --input examples/external/prompt_optimizer_favorites.json --out ./tmp-pcl-prompt-optimizer
pcl scaffold-check --run ./tmp-pcl-prompt-optimizer
```

预期结果：CLI 可用，`pcl doctor` 能运行，模板安装器可以写出 Codex、Cursor、
Claude Code 和 GitHub Action 模板。prompt-optimizer 桥接也能通过 wheel 安装后的包写出
`eval_scaffold/scaffold_check.json` 和 `.html`。

如果当前环境已经安装了 `research` extra，也要用构建出的 wheel 验证论文研究流程：

```bash
python -m pip install --force-reinstall --no-deps dist/promptcontrollab-0.1.0-py3-none-any.whl
pcl research-quickstart --out ./tmp-pcl-research-demo --language zh --open-report
```

预期结果：wheel 安装后的包可以生成 `research_bundle.html`、`research_diagnostics.html`、
`evidence_card.html` 和 `claim_check.html`。

## uv / uvx 说明

开发环境可以用：

```bash
uv pip install -e ".[dev,ui]"
```

本地 wheel 冒烟测试请直接安装 wheel 路径。如果当前环境还没有发布到 PyPI，
不要使用 `uvx prompt_control_lab`。只有包真正发布后，才使用 Python 包名
`promptcontrollab`。

## 模板资源检查

插件模板打包在 `promptcontrollab.template_data` 下。wheel 安装后，建议验证：

```bash
pcl install-plugin codex --target ./tmp-pcl-codex
pcl install-plugin cursor --target ./tmp-pcl-cursor
pcl install-plugin claude-code --target ./tmp-pcl-claude
pcl install-plugin github-action --target ./tmp-pcl-action
```

默认不会覆盖已有文件；只有传入 `--force` 才会覆盖。

## 发布边界

如果本地没有配置 PyPI token，就停在本地构建和 wheel 冒烟测试。文档中只能写
“PyPI-ready”，不要写成“已经发布”。在包真正以 `promptcontrollab` 名称可安装前，
不要声称用户可以直接从 PyPI 安装。
