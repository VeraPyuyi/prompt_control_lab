"""HuggingFace hidden-state extraction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from promptcontrollab.core.files import JsonDict, ensure_dir, read_jsonl, write_json
from promptcontrollab.core.optional import require_module


def load_prompt_texts(path: Path, *, max_items: int | None) -> list[str]:
    """Load prompts from JSONL objects or a plain text file."""

    if path.suffix.lower() == ".jsonl":
        prompts: list[str] = []
        for record in read_jsonl(path):
            prompt = _prompt_from_record(record, path)
            if prompt:
                prompts.append(prompt)
            if max_items is not None and len(prompts) >= max_items:
                break
        if not prompts:
            msg = f"No prompts found in {path}"
            raise ValueError(msg)
        return prompts

    prompts = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()]
    prompts = [line for line in prompts if line]
    if max_items is not None:
        prompts = prompts[:max_items]
    if not prompts:
        msg = f"No prompts found in {path}"
        raise ValueError(msg)
    return prompts


def extract_hidden_states(
    *,
    model_id: str,
    prompts_path: Path,
    out_path: Path,
    layer: int = -1,
    pool: str = "last-token",
    max_items: int | None = None,
    max_length: int = 512,
    device: str = "auto",
    trust_remote_code: bool = False,
) -> JsonDict:
    """Extract HuggingFace hidden states into a ``states`` NPZ artifact."""

    if pool not in {"last-token", "mean", "token-trajectory"}:
        msg = "pool must be one of: last-token, mean, token-trajectory"
        raise ValueError(msg)
    if max_length <= 0:
        msg = "max_length must be positive"
        raise ValueError(msg)
    prompts = load_prompt_texts(prompts_path, max_items=max_items)

    np = cast(Any, require_module("numpy", feature="hidden-state extraction", extra="hf"))
    torch = cast(Any, require_module("torch", feature="hidden-state extraction", extra="hf"))
    transformers = require_module("transformers", feature="hidden-state extraction", extra="hf")

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=trust_remote_code,
    )
    if getattr(tokenizer, "pad_token", None) is None and getattr(tokenizer, "eos_token", None):
        tokenizer.pad_token = tokenizer.eos_token
    model = _load_model(transformers, model_id, trust_remote_code=trust_remote_code)
    resolved_device = _resolve_device(torch, device)
    model.to(resolved_device)
    model.eval()

    rows: list[Any] = []
    with torch.no_grad():
        for prompt in prompts:
            encoded = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
            )
            encoded = {
                key: value.to(resolved_device) if hasattr(value, "to") else value
                for key, value in encoded.items()
            }
            outputs = model(**encoded, output_hidden_states=True)
            hidden_states = getattr(outputs, "hidden_states", None)
            if hidden_states is None:
                msg = "Model output did not include hidden_states"
                raise ValueError(msg)
            hidden = hidden_states[layer]
            attention_mask = encoded.get("attention_mask")
            rows.extend(_pool_hidden(torch, hidden, attention_mask, pool=pool))

    states = np.stack([_to_numpy(row) for row in rows], axis=0)
    ensure_dir(out_path.parent)
    np.savez(out_path, states=states)
    payload: JsonDict = {
        "kind": "hidden_state_extraction",
        "model_id": model_id,
        "prompts_path": str(prompts_path),
        "out_path": str(out_path),
        "states_shape": [int(states.shape[0]), int(states.shape[1])],
        "prompt_count": len(prompts),
        "layer": layer,
        "pool": pool,
        "max_length": max_length,
        "device": resolved_device,
        "trust_remote_code": trust_remote_code,
        "next_steps": [
            f"pcl trajectory --states {out_path} --out {out_path.parent / 'diagnostics'}",
            f"pcl riccati --trajectory {out_path} --out {out_path.parent / 'diagnostics'}",
        ],
        "boundary": (
            "This records hidden states from the selected HuggingFace model and layer. It is an "
            "input artifact for trajectory/Riccati diagnostics, not a proof of full model "
            "stability."
        ),
    }
    write_json(Path(str(out_path) + ".metadata.json"), payload)
    return payload


def _prompt_from_record(record: JsonDict, path: Path) -> str:
    for key in ["input", "prompt", "text"]:
        value = record.get(key)
        if isinstance(value, str):
            return value.strip()
    msg = f"JSONL prompt records in {path} must contain one of: input, prompt, text"
    raise ValueError(msg)


def _load_model(transformers: Any, model_id: str, *, trust_remote_code: bool) -> Any:
    try:
        return transformers.AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=trust_remote_code,
        )
    except Exception:
        return transformers.AutoModel.from_pretrained(
            model_id,
            trust_remote_code=trust_remote_code,
        )


def _resolve_device(torch: Any, device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def _pool_hidden(torch: Any, hidden: Any, attention_mask: Any, *, pool: str) -> list[Any]:
    token_count = _token_count(attention_mask, hidden)
    token_hidden = hidden[0, :token_count, :]
    if pool == "token-trajectory":
        return [token_hidden[index, :] for index in range(token_count)]
    if pool == "mean":
        return [token_hidden.mean(dim=0)]
    return [token_hidden[token_count - 1, :]]


def _token_count(attention_mask: Any, hidden: Any) -> int:
    if attention_mask is None:
        return int(hidden.shape[1])
    count = int(attention_mask[0].sum().item())
    return max(1, count)


def _to_numpy(value: Any) -> Any:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    return value
