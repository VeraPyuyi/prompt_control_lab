# Hugging Face 公开演示

Hugging Face Space 是一个受限、无状态的产品体验入口。它让用户在安装本地完整版之前先理解
PromptControlLab 的证据和诊断方式；GitHub 始终是源码、Issue、Pull Request 和 Release 的唯一
上游仓库。

## Space 可以做什么

- 运行离线 Prompt Guard，查看并下载改进后的 Prompt。
- 浏览预置 Quick Analysis、模型漂移、Agent Audit、History、checkpoint 和控制证书 artifact。
- 向当前临时会话上传一个已识别的 PromptControlLab JSON 或 JSONL artifact，单文件不超过 5 MB。
- 切换中英文，并下载当前会话生成的 JSON、文本和报告。

在线演示不会执行任意命令，不会修改 Git 仓库、安装插件、连接外部 Provider、运行 DeepSeek
Harness bridge、训练模型，也不接受 ZIP、pickle、PT 或 NPZ。即使绕过可见按钮直接调用后端，
同样的限制仍然生效。

每个浏览器会话使用 `/tmp/prompt_control_lab/sessions/<random-id>`。预置数据被复制到该目录，
上传文件只能保存在其内部，带标记的过期目录会自动清理。Prompt 原文只在 Streamlit 会话内存中
使用；上传还会受到单会话文件数、累计字节和全局临时容量限制。Prompt 原文不写入服务器 artifact。
Hugging Face Space 的磁盘是临时存储，重启后这些
数据会消失。即使如此，也不要把密钥或私有生产数据上传到公开 Space。

## 从 GitHub 部署

1. 创建公开 Docker Space，通常命名为 `<HF_NAMESPACE>/prompt-control-lab`，使用免费 CPU。
2. 在 GitHub 仓库添加 `HF_SPACE_ID` 和 `HF_TOKEN` 两个 Secret；Token 只授予目标 Space 写权限。
3. 手动运行 `Deploy Hugging Face Space` workflow，或发布 GitHub Release。
4. Workflow 会执行 Python 质量检查、构建 wheel、生成白名单 bundle、上传文件、等待 Space 进入
   Running，检查 Streamlit 健康端点，并确认 `space_manifest.json` 记录了对应 Git commit。

部署不会在每次 `main` 更新时自动触发。

## 本地构建

```bash
python -m pip install -e ".[dev,research,ui]"
python -m build
python scripts/build_hf_space_bundle.py \
  --output .hf-space \
  --wheel dist/promptcontrollab-0.2.0a1-py3-none-any.whl \
  --source-commit "$(git rev-parse HEAD)"
docker build -t prompt-control-lab-hf .hf-space
docker run --rm -p 7860:7860 prompt-control-lab-hf
```

浏览器打开 `http://localhost:7860`。镜像使用非 root 用户运行，只暴露 `7860` 端口。

部署采用 Hugging Face 当前的 [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)
方式；存储行为以官方 [Spaces storage](https://huggingface.co/docs/hub/en/spaces-storage) 文档为准。

## Bundle 边界

`scripts/build_hf_space_bundle.py` 只复制已提交 Space manifest 明确列出的文件，生成不含插件模板的
运行时 wheel，并加入经过筛选的 demo artifact；未声明文件、符号链接、模型权重、pickle 类文件、
NPZ 和视频都会被拒绝。生成的 `space_manifest.json` 会记录包版本、
Git commit、demo 数据版本、wheel 文件名和 wheel digest。测试、插件源码、私有实验、服务器目录和
仓库中的完整媒体文件都不会上传。

后续可以单独建立 `prompt-control-lab-evidence` Dataset，但只发布可公开的汇总、schema、来源引用
和 claim boundary；首版 Space 不依赖这个 Dataset。
