# Provider Adapters and Model Provenance

Chinese: [providers.zh.md](providers.zh.md)

PromptControlLab provider adapters support the explicitly authorized `model` branch of the local control loop. They are small, dependency-free HTTP adapters: each requires a public model id, reads credentials from an environment variable, normalizes public response metadata, and writes redacted provenance artifacts.

There is no default model: every adapter requires an explicit model id. PromptControlLab also does not route to a different provider when the requested one fails.

## Supported Adapters

| Provider id | Protocol | Credential variable | Base URL behavior |
|---|---|---|---|
| `openai` | OpenAI chat completions | `OPENAI_API_KEY` | Defaults to `https://api.openai.com/v1`; override with `OPENAI_BASE_URL`. |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` | Defaults to `https://api.anthropic.com`; override with `ANTHROPIC_BASE_URL`. |
| `gemini` | Gemini generateContent | `GEMINI_API_KEY` | Defaults to `https://generativelanguage.googleapis.com/v1beta`; override with `GEMINI_BASE_URL`. |
| `deepseek` | OpenAI-compatible chat completions | `DEEPSEEK_API_KEY` | Defaults to `https://api.deepseek.com`; override with `DEEPSEEK_BASE_URL`. |
| `qwen` | DashScope OpenAI-compatible endpoint | `DASHSCOPE_API_KEY` | Defaults to `https://dashscope.aliyuncs.com/compatible-mode/v1`; override with `DASHSCOPE_BASE_URL`. |
| `kimi` | Moonshot OpenAI-compatible endpoint | `MOONSHOT_API_KEY` | No default base URL; set `MOONSHOT_BASE_URL` or pass an explicit URL. |
| `openai-compatible` | OpenAI chat completions | `OPENAI_COMPATIBLE_API_KEY` | No default base URL; set `OPENAI_COMPATIBLE_BASE_URL` or pass an explicit URL. |

Provider metadata and documentation URLs are available without credentials:

```bash
pcl providers list --json
```

## Inspect Without Network Access

```bash
pcl providers inspect deepseek --json
pcl providers inspect openai-compatible \
  --base-url http://127.0.0.1:8000/v1 \
  --api-key-env LOCAL_MODEL_API_KEY \
  --json
```

`inspect` reports the protocol, selected environment-variable name, resolved base URL, whether the variable is present, and configuration warnings. It does not reveal the credential and makes no request.

An `--api-key-env` override must be an environment-variable name, not a secret value. Remote endpoints must use HTTPS. Plain HTTP is accepted only for `localhost`, `127.0.0.1`, or `::1`. URLs containing embedded credentials, query strings, or fragments are rejected.

## Doctor: Offline by Default

```bash
pcl providers doctor deepseek --json
```

The default doctor is offline. It checks whether the selected credential variable and base URL are configured. `status: ready` means local configuration is present; it does not confirm quota, model access, endpoint behavior, or transport.

A live check is opt-in and requires an explicit public model id:

```bash
pcl providers doctor deepseek --live --model deepseek-chat --json
```

The live check sends a tiny request asking for `OK`, limits output to four tokens, and records the observed public model id, request id, latency, and provenance evidence. It spends provider resources and can still be rejected by access, quota, policy, or network state.

## Explicit Model Authorization

```bash
pcl control \
  --prompt "Return a three-item checklist." \
  --authorization model \
  --provider deepseek \
  --model deepseek-chat \
  --out runs/deepseek-control \
  --json
```

Both `--provider` and `--model` are required. A blocking or review-required preflight prevents the request. A successful call writes `provider_result.json` and public provider events before attribution, stability, and the final decision are generated.

## Normalized Result

The provider result records:

- adapter id and observed or declared public model id;
- output text for the authorized local run;
- provider request id when exposed;
- public usage counts and latency;
- SHA-256 identities for the serialized request and response;
- bounded public response metadata;
- provenance evidence and warnings.

Credentials are never written to the result. Redirects are rejected so an authorization header cannot be forwarded to another URL. Responses larger than 10 MiB, non-UTF-8 or non-standard JSON, empty outputs, error envelopes, and visible refusal/block states fail explicitly.

## Honest Public-Model Provenance

When a response reports `response.model` or Gemini `response.modelVersion`, PromptControlLab records it as `observed_model_field`. If the response omits that field, it records the requested id as `declared_model` and adds a warning.

This evidence identifies a public model label reported by the endpoint. It does not prove hidden weights, an unpublished build revision, a provider's internal routing choice, or byte identity of the served model. Aliases and gateways may map one public id to changing backends. Request and response hashes identify the observed payload bytes, not model parameters.

Use model provenance as one factor in a comparison. A clean prompt-only comparison still requires consistent provider, public model id, request settings, data, metric, and split. For Agent execution rather than one direct model call, use an explicit adapter such as [DeepSeek Harness](deepseek_harness.en.md).
