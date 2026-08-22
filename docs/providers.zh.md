# Provider Adapter 与模型溯源

English: [providers.en.md](providers.en.md)

PromptControlLab provider adapter 服务于本地控制闭环中显式授权的 `model` 分支。它们是小型、无额外依赖的 HTTP adapter：每次调用都要求用户给出公开 model id，从环境变量读取凭证，归一化公开 response metadata，并写出脱敏 provenance artifact。

工具不选择默认模型：所有 adapter 都要求显式 model id。请求失败时，PromptControlLab 也不会静默切换到另一个 provider。

## 支持的 Adapter

| Provider id | Protocol | 凭证环境变量 | Base URL 行为 |
|---|---|---|---|
| `openai` | OpenAI chat completions | `OPENAI_API_KEY` | 默认 `https://api.openai.com/v1`；可用 `OPENAI_BASE_URL` 覆盖。 |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` | 默认 `https://api.anthropic.com`；可用 `ANTHROPIC_BASE_URL` 覆盖。 |
| `gemini` | Gemini generateContent | `GEMINI_API_KEY` | 默认 `https://generativelanguage.googleapis.com/v1beta`；可用 `GEMINI_BASE_URL` 覆盖。 |
| `deepseek` | OpenAI-compatible chat completions | `DEEPSEEK_API_KEY` | 默认 `https://api.deepseek.com`；可用 `DEEPSEEK_BASE_URL` 覆盖。 |
| `qwen` | DashScope OpenAI-compatible endpoint | `DASHSCOPE_API_KEY` | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`；可用 `DASHSCOPE_BASE_URL` 覆盖。 |
| `kimi` | Moonshot OpenAI-compatible endpoint | `MOONSHOT_API_KEY` | 没有默认 base URL；设置 `MOONSHOT_BASE_URL` 或显式传入 URL。 |
| `openai-compatible` | OpenAI chat completions | `OPENAI_COMPATIBLE_API_KEY` | 没有默认 base URL；设置 `OPENAI_COMPATIBLE_BASE_URL` 或显式传入 URL。 |

不需要凭证就能读取 provider metadata 与文档 URL：

```bash
pcl providers list --json
```

## 离线 Inspect

```bash
pcl providers inspect deepseek --json
pcl providers inspect openai-compatible \
  --base-url http://127.0.0.1:8000/v1 \
  --api-key-env LOCAL_MODEL_API_KEY \
  --json
```

`inspect` 会报告 protocol、所选环境变量名、解析后的 base URL、变量是否存在以及配置 warning。它不会显示凭证，也不会发出网络请求。

`--api-key-env` override 必须是环境变量名，不能直接填写 secret。远程 endpoint 必须使用 HTTPS；只有 `localhost`、`127.0.0.1`、`::1` 可以使用明文 HTTP。包含嵌入式凭证、query string 或 fragment 的 URL 会被拒绝。

## Doctor 默认离线

```bash
pcl providers doctor deepseek --json
```

默认 doctor 完全离线，只检查所选凭证变量与 base URL 是否已配置。`status: ready` 只表示本地配置存在，不能确认 quota、model access、endpoint 行为或 transport。

Live check 必须显式选择，并提供公开 model id：

```bash
pcl providers doctor deepseek --live --model deepseek-chat --json
```

Live check 会发送一个要求回复 `OK` 的极小请求，把输出限制到四个 token，并记录 observed public model id、request id、latency 与 provenance evidence。它会消耗 provider 资源，也可能因为 access、quota、policy 或 network state 失败。

## 显式 Model 授权

```bash
pcl control \
  --prompt "返回一个三项检查表。" \
  --authorization model \
  --provider deepseek \
  --model deepseek-chat \
  --out runs/deepseek-control \
  --json
```

`--provider` 与 `--model` 都是必需项。Preflight 为 blocking 或 required-review 时不会发出请求。调用成功后，会先写 `provider_result.json` 与公开 provider event，再生成 attribution、stability 和最终 decision。

## 归一化 Result

Provider result 会记录：

- adapter id 与 observed 或 declared public model id；
- 获得授权的本地 run 的 output text；
- provider 暴露时的 request id；
- 公开 usage count 与 latency；
- 序列化 request/response 的 SHA-256 identity；
- 有界公开 response metadata；
- provenance evidence 与 warning。

凭证不会写入 result。Redirect 会被拒绝，避免 authorization header 被转发到另一个 URL。超过 10 MiB 的 response、非 UTF-8、非标准 JSON、空输出、error envelope 和可见 refusal/block state 都会显式失败。

## 诚实的公开模型溯源

Response 报告 `response.model` 或 Gemini `response.modelVersion` 时，PromptControlLab 把它记录为 `observed_model_field`。Response 缺少该字段时，只记录 request 中的 id 为 `declared_model`，并添加 warning。

这些证据只标识 endpoint 报告的公开模型标签，不能证明隐藏权重、未公开 build revision、provider 内部 routing choice 或实际服务模型的字节身份。Alias 与 gateway 可以把一个公开 id 映射到不断变化的 backend。Request/response hash 标识观察到的 payload byte，不是模型参数。

模型溯源只是比较中的一个因素。要形成干净的 prompt-only comparison，还需要 provider、公开 model id、request setting、data、metric 与 split 保持一致。若要执行 Agent，而不是直接调用一次模型，请使用显式 adapter，例如 [DeepSeek Harness](deepseek_harness.zh.md)。
