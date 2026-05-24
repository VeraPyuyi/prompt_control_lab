"""Build bilingual narrated demo videos from the docs demo manifest.

This is a documentation utility, not a package runtime dependency. It reads
``docs/demo/video_manifest.json`` plus ``docs/assets/tutorial_*.png`` and writes:

* ``docs/assets/demo/prompt_control_lab_demo.en.mp4``
* ``docs/assets/demo/prompt_control_lab_demo.zh.mp4``
* matching ``.srt`` subtitles
* matching poster ``.png`` files

Optional dependencies:
    pip install pillow imageio-ffmpeg edge-tts

On Windows, the script falls back to SAPI voices through PowerShell's
System.Speech APIs when neural TTS is not available.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "demo" / "video_manifest.json"
ASSET_DIR = ROOT / "docs" / "assets"
OUTPUT_DIR = ASSET_DIR / "demo"

BASE_VIDEO_SIZE = (1280, 720)
VIDEO_SIZE = (3840, 2160)
FPS = 12
TARGET_MB = 95
MAX_VIDEO_BITRATE_K = 1600
AUDIO_BITRATE_K = 48
MIN_SLIDE_SECONDS = 2.8
SLIDE_PAD_SECONDS = 0.55
OPERATION_FRAMES = 5

LANGUAGES = ("en", "zh")
LANG_LABELS = {"en": "English", "zh": "中文"}
EDGE_PROFILES = {
    "en": {
        "voice": "en-US-JennyNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "pause_ms": 0,
        "chunked": False,
    },
    "zh": {
        "voice": "zh-CN-YunyangNeural",
        "rate": "+7%",
        "pitch": "-2Hz",
        "pause_ms": 220,
        "chunked": True,
    },
}
SAPI_VOICES = {
    "en": (
        "Microsoft Zira Desktop",
        "Microsoft David Desktop",
        "Microsoft Zira",
        "Microsoft David",
    ),
    "zh": ("Microsoft Huihui Desktop", "Microsoft Huihui"),
}


def scale_px(value: int | float) -> int:
    return round(float(value) * VIDEO_SIZE[0] / BASE_VIDEO_SIZE[0])


class BuildError(RuntimeError):
    """User-facing build error."""


@dataclass(frozen=True)
class Scene:
    key: str
    image: Path
    title: str
    subtitle: str
    narration: str
    command_snippets: list[str]
    output_filenames: list[str]
    operation_steps: list[dict[str, Any]]
    duration: float | None = None


@dataclass(frozen=True)
class LanguageVideo:
    language: str
    title: str
    subtitle: str
    scenes: list[Scene]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build bilingual prompt_control_lab demo videos.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="Path to video_manifest.json.",
    )
    parser.add_argument(
        "--assets",
        type=Path,
        default=ASSET_DIR,
        help="Directory containing tutorial_*.png.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for videos/assets.",
    )
    parser.add_argument("--langs", nargs="+", choices=LANGUAGES, default=list(LANGUAGES))
    parser.add_argument("--tts", choices=("auto", "edge", "sapi", "silent"), default="auto")
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep intermediate files for debugging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print planned outputs only.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        ffmpeg = None if args.dry_run else find_ffmpeg()
        videos = [build_language_video(manifest, lang, args.assets) for lang in args.langs]
        if args.dry_run:
            for video in videos:
                stem = output_stem(video.language, args.out)
                print(f"{video.language}: {len(video.scenes)} scenes -> {stem}")
            return 0
        args.out.mkdir(parents=True, exist_ok=True)
        for video in videos:
            render_language_video(
                video,
                args.out,
                ffmpeg=ffmpeg,
                tts_mode=args.tts,
                keep_temp=args.keep_temp,
            )
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BuildError(
            f"Missing manifest: {path}. "
            "Create docs/demo/video_manifest.json before running this builder."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BuildError(f"Manifest must be a JSON object: {path}")
    return data


def build_language_video(
    manifest: dict[str, Any],
    language: str,
    assets_dir: Path,
) -> LanguageVideo:
    localized = localized_manifest(manifest, language)
    title = (
        pick_text(localized, language, ("title", "video_title", "name"))
        or default_title(language)
    )
    subtitle = pick_text(localized, language, ("subtitle", "tagline", "description")) or ""
    raw_scenes = extract_scenes(localized, manifest, language)
    if not raw_scenes:
        raise BuildError(
            "Manifest must define at least one scene in 'scenes', 'slides', "
            "or per-language videos."
        )

    scenes: list[Scene] = []
    for index, raw_scene in enumerate(raw_scenes, start=1):
        if not isinstance(raw_scene, dict):
            raise BuildError(f"Scene {index} for {language} must be an object.")
        scene = normalize_scene(raw_scene, language, assets_dir, index)
        scenes.append(scene)
    return LanguageVideo(language=language, title=title, subtitle=subtitle, scenes=scenes)


def localized_manifest(manifest: dict[str, Any], language: str) -> dict[str, Any]:
    videos = manifest.get("videos")
    if isinstance(videos, dict) and isinstance(videos.get(language), dict):
        merged = dict(manifest)
        merged.update(videos[language])
        return merged
    languages = manifest.get("languages")
    if isinstance(languages, dict) and isinstance(languages.get(language), dict):
        merged = dict(manifest)
        merged.update(languages[language])
        return merged
    return manifest


def extract_scenes(localized: dict[str, Any], manifest: dict[str, Any], language: str) -> list[Any]:
    for key in ("scenes", "slides", "steps"):
        value = localized.get(key)
        if isinstance(value, list):
            return value
    videos = manifest.get("videos")
    if isinstance(videos, dict) and isinstance(videos.get(language), list):
        return videos[language]
    raise BuildError(f"No scenes found for language '{language}'.")


def normalize_scene(raw: dict[str, Any], language: str, assets_dir: Path, index: int) -> Scene:
    key = str(raw.get("id") or raw.get("key") or raw.get("name") or f"scene_{index:02d}")
    title = pick_text(raw, language, ("title", "heading", "label")) or key.replace("_", " ").title()
    subtitle = pick_text(raw, language, ("subtitle", "caption", "body", "description")) or ""
    narration = pick_text(raw, language, ("narration", "voiceover", "script", "text"))
    if not narration:
        narration = " ".join(part for part in (title, subtitle) if part).strip()
    if not narration:
        raise BuildError(f"Scene '{key}' is missing narration/text for {language}.")
    image = resolve_scene_image(raw, language, assets_dir, key)
    command_snippets = coerce_str_list(raw.get("command_snippets") or raw.get("commands"))
    output_filenames = coerce_str_list(raw.get("output_filenames") or raw.get("outputs"))
    operation_steps = coerce_operation_steps(raw.get("operation_steps") or raw.get("operations"))
    duration = coerce_duration(raw.get("duration") or raw.get("seconds"))
    return Scene(
        key=key,
        image=image,
        title=title,
        subtitle=subtitle,
        narration=narration,
        command_snippets=command_snippets,
        output_filenames=output_filenames,
        operation_steps=operation_steps,
        duration=duration,
    )


def coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def coerce_operation_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    steps: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            steps.append(item)
        elif isinstance(item, str) and item.strip():
            steps.append({"label": item.strip()})
    return steps


def pick_text(source: dict[str, Any], language: str, names: Iterable[str]) -> str:
    for name in names:
        value = source.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            localized = value.get(language)
            if isinstance(localized, str) and localized.strip():
                return localized.strip()
    suffixes = (f"_{language}", f".{language}")
    for name in names:
        for suffix in suffixes:
            value = source.get(f"{name}{suffix}")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def resolve_scene_image(raw: dict[str, Any], language: str, assets_dir: Path, key: str) -> Path:
    image_value = raw.get("image") or raw.get("screenshot") or raw.get("asset")
    if isinstance(image_value, dict):
        image_value = image_value.get(language) or image_value.get("default")
    candidates: list[Path] = []
    if isinstance(image_value, str) and image_value.strip():
        image_path = Path(image_value)
        candidates.append(image_path if image_path.is_absolute() else ROOT / image_path)
        candidates.append(assets_dir / image_value)
    safe_key = re.sub(r"^tutorial[_-]?", "", key, flags=re.IGNORECASE).replace("-", "_")
    candidates.extend(
        [
            assets_dir / f"tutorial_{safe_key}.{language}.png",
            assets_dir / f"tutorial_{key}.{language}.png",
            assets_dir / f"{key}.{language}.png",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    tried = ", ".join(str(path) for path in candidates[:5])
    raise BuildError(f"Could not find screenshot for scene '{key}' ({language}). Tried: {tried}")


def coerce_duration(value: Any) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds > 0 else None


def render_language_video(
    video: LanguageVideo,
    out_dir: Path,
    *,
    ffmpeg: Path,
    tts_mode: str,
    keep_temp: bool,
) -> None:
    stem = output_stem(video.language, out_dir)
    poster_path = out_dir / f"poster.{video.language}.png"
    srt_path = Path(f"{stem}.srt")
    mp4_path = Path(f"{stem}.mp4")

    temp_context = tempfile.TemporaryDirectory(prefix=f"pcl_demo_{video.language}_")
    temp_dir = Path(temp_context.name)
    try:
        rendered: list[tuple[Scene, list[Path], Path, float]] = []
        for index, scene in enumerate(video.scenes, start=1):
            audio_path = temp_dir / f"audio_{index:02d}.wav"
            synthesize_narration(scene.narration, audio_path, video.language, tts_mode, ffmpeg)
            audio_seconds = wav_duration(audio_path)
            seconds = max(
                scene.duration or 0.0,
                audio_seconds + SLIDE_PAD_SECONDS,
                MIN_SLIDE_SECONDS,
            )
            frame_dir = temp_dir / f"frames_{index:02d}"
            frame_paths = render_scene_frames(video, scene, index, frame_dir)
            rendered.append((scene, frame_paths, audio_path, seconds))
            if index == 1:
                shutil.copyfile(frame_paths[0], poster_path)
        write_srt(rendered, srt_path)
        encode_video(rendered, mp4_path, ffmpeg)
        size_mb = mp4_path.stat().st_size / (1024 * 1024)
        if size_mb > TARGET_MB:
            raise BuildError(
                f"{mp4_path} is {size_mb:.1f} MB, above the {TARGET_MB} MB target. "
                "Reduce scene count/durations or lower MAX_VIDEO_BITRATE_K."
            )
        print(f"wrote {mp4_path} ({size_mb:.1f} MB)")
        print(f"wrote {srt_path}")
        print(f"wrote {poster_path}")
    finally:
        if keep_temp:
            print(f"kept temp directory: {temp_dir}")
        else:
            temp_context.cleanup()


def output_stem(language: str, out_dir: Path) -> Path:
    return out_dir / f"prompt_control_lab_demo.{language}"


def render_scene_frames(
    video: LanguageVideo,
    scene: Scene,
    index: int,
    out_dir: Path,
) -> list[Path]:
    steps = scene.operation_steps or default_operation_steps(scene, video.language)
    if len(steps) < OPERATION_FRAMES:
        steps = [*steps, *default_operation_steps(scene, video.language)][0:OPERATION_FRAMES]
    else:
        steps = steps[:OPERATION_FRAMES]

    out_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: list[Path] = []
    for frame_index, step in enumerate(steps):
        frame_path = out_dir / f"frame_{frame_index:02d}.png"
        render_slide(video, scene, index, frame_index, len(steps), step, frame_path)
        frame_paths.append(frame_path)
    return frame_paths


def default_operation_steps(scene: Scene, language: str) -> list[dict[str, Any]]:
    labels = {
        "en": [
            "Open the local workflow",
            "Type or select the prompt",
            "Click the action button",
            "Inspect the result",
            "Save the artifact",
        ],
        "zh": [
            "打开本地工作流",
            "输入或选择 prompt",
            "点击运行按钮",
            "查看检测结果",
            "保存可复核文件",
        ],
    }[language]
    if "guard" in scene.key or "improve" in scene.key:
        labels = {
            "en": [
                "Open Guard Prompt",
                "Paste the coding-agent prompt",
                "Run policy preflight",
                "Read risk and violations",
                "Copy or save the improved prompt",
            ],
            "zh": [
                "打开 Guard Prompt",
                "粘贴编程 Agent 指令",
                "运行策略预检",
                "查看风险和违规项",
                "复制或保存改写后的 prompt",
            ],
        }[language]
    elif "analyze" in scene.key or "gate" in scene.key or "report" in scene.key:
        labels = {
            "en": [
                "Create demo artifacts",
                "Run analyze",
                "Run the gate policy",
                "Open the report",
                "Check score, CI, and p-value",
            ],
            "zh": [
                "创建演示数据",
                "运行 analyze",
                "运行 gate policy",
                "打开报告页",
                "检查分数、区间和 p-value",
            ],
        }[language]
    elif "model" in scene.key:
        labels = {
            "en": [
                "Open Model Drift",
                "Select the current run",
                "Compare provider and model",
                "Read alias or unknown warnings",
                "Decide if comparison is clean",
            ],
            "zh": [
                "打开模型漂移页",
                "选择当前 run",
                "比较 provider 和 model",
                "查看 alias 或未知模型警告",
                "判断是否是干净比较",
            ],
        }[language]
    elif "audit" in scene.key:
        labels = {
            "en": [
                "Run audit-diff",
                "Review touched files",
                "Open changed-lines table",
                "Inspect dangerous findings",
                "Decide if review is required",
            ],
            "zh": [
                "运行 audit-diff",
                "查看改动文件",
                "打开 changed-lines 表",
                "检查危险发现",
                "判断是否需要人工复核",
            ],
        }[language]
    elif "history" in scene.key:
        labels = {
            "en": [
                "Build history index",
                "Open History",
                "Filter risky runs",
                "Check model and gate trends",
                "Compare the next run",
            ],
            "zh": [
                "构建历史索引",
                "打开 History 页",
                "过滤高风险 run",
                "查看模型和 gate 趋势",
                "对比下一次运行",
            ],
        }[language]
    return [{"label": label} for label in labels]


def render_slide(
    video: LanguageVideo,
    scene: Scene,
    index: int,
    frame_index: int,
    frame_count: int,
    step: dict[str, Any],
    out_path: Path,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError as exc:
        raise BuildError(
            "Missing dependency: pillow. Install with: python -m pip install pillow"
        ) from exc

    width, height = VIDEO_SIZE
    canvas = Image.new("RGB", VIDEO_SIZE, "#f7f8fb")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, height), fill="#f7f8fb")
    draw.rectangle((0, 0, width, scale_px(86)), fill="#102033")
    draw.rectangle((0, height - scale_px(58), width, height), fill="#102033")

    title_font = load_font(scale_px(34), bold=True)
    body_font = load_font(scale_px(21))
    meta_font = load_font(scale_px(22))
    small_font = load_font(scale_px(18))
    mono_font = load_mono_font(scale_px(16))

    draw.text((scale_px(48), scale_px(25)), video.title, fill="#ffffff", font=meta_font)
    draw.text(
        (width - scale_px(166), scale_px(25)),
        f"{LANG_LABELS[video.language]}  {index}/{len(video.scenes)}",
        fill="#dce6f2",
        font=small_font,
    )

    left_x = scale_px(42)
    content_top = scale_px(128)
    left_panel_w = scale_px(292)
    text_width_limit = left_panel_w
    title_lines = wrap_text(scene.title, title_font, text_width_limit)
    y = content_top
    for line in title_lines[:3]:
        draw.text((left_x, y), line, fill="#102033", font=title_font)
        y += scale_px(43)
    y += scale_px(8)

    step_label = str(step.get("label") or "").strip()
    if step_label:
        draw.rounded_rectangle(
            (
                left_x,
                y,
                left_x + left_panel_w,
                y + scale_px(74),
            ),
            radius=scale_px(16),
            fill="#e8f5ff",
            outline="#38a6e8",
            width=scale_px(2),
        )
        step_y = y + scale_px(11)
        for line in wrap_text(
            f"{frame_index + 1}. {step_label}",
            body_font,
            left_panel_w - scale_px(30),
        )[:2]:
            draw.text((left_x + scale_px(16), step_y), line, fill="#075985", font=body_font)
            step_y += scale_px(27)
        y += scale_px(94)

    summary = compact_scene_summary(scene, video.language)
    for line in wrap_text(summary, body_font, text_width_limit)[:4]:
        draw.text((left_x, y), line, fill="#31465c", font=body_font)
        y += scale_px(29)
    y += scale_px(16)

    command = command_for_frame(scene, frame_index)
    if command:
        command_font = load_font(scale_px(16)) if contains_cjk(command) else mono_font
        y = draw_command_card(draw, left_x, y, left_panel_w, command, command_font)

    output = output_for_frame(scene, frame_index)
    if output:
        y += scale_px(12)
        draw_artifact_pill(draw, left_x, y, left_panel_w, output, small_font)

    draw_progress_dots(draw, left_x, height - scale_px(106), frame_count, frame_index)

    screenshot = Image.open(scene.image).convert("RGB")
    screenshot = resize_to_fit(
        screenshot,
        width - scale_px(380) - scale_px(108),
        height - scale_px(238),
    )
    shot_x = width - screenshot.width - scale_px(48)
    shot_y = scale_px(126) + max(0, (height - scale_px(210) - screenshot.height) // 2)
    shadow = Image.new(
        "RGBA",
        (screenshot.width + scale_px(32), screenshot.height + scale_px(32)),
        (0, 0, 0, 0),
    )
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (
            scale_px(16),
            scale_px(16),
            screenshot.width + scale_px(16),
            screenshot.height + scale_px(16),
        ),
        radius=scale_px(18),
        fill=(0, 0, 0, 55),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(scale_px(10)))
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(shadow, (shot_x - scale_px(16), shot_y - scale_px(10)))
    canvas = canvas_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    canvas.paste(screenshot, (shot_x, shot_y))
    draw.rounded_rectangle(
        (shot_x, shot_y, shot_x + screenshot.width, shot_y + screenshot.height),
        radius=scale_px(14),
        outline="#c9d4e3",
        width=scale_px(2),
    )
    draw_operation_overlay(
        draw,
        shot_x,
        shot_y,
        screenshot.width,
        screenshot.height,
        frame_index,
        scene.key,
    )
    draw.text(
        (scale_px(48), height - scale_px(39)),
        "prompt_control_lab",
        fill="#dce6f2",
        font=small_font,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, optimize=True)


def resize_to_fit(image: Any, max_width: int, max_height: int) -> Any:
    try:
        from PIL import Image
    except ImportError as exc:
        raise BuildError(
            "Missing dependency: pillow. Install with: python -m pip install pillow"
        ) from exc
    scale = min(max_width / image.width, max_height / image.height)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def compact_scene_summary(scene: Scene, language: str) -> str:
    summaries = {
        "en": {
            "why": "Goal: check prompt risk before the agent spends tokens or edits files.",
            "guard": "Action: paste the prompt, run policy preflight, then inspect risk and fixes.",
            "improve": "Action: rewrite a vague prompt into a clearer, cheaper, more stable one.",
            "ui": "Action: use the local dashboard to run the same workflow from the browser.",
            "analyze": "Action: build splits, metrics, statistics, explanations, and reports.",
            "gate": "Action: turn the report into pass, needs review, or fail.",
            "model": "Action: check whether the model record makes the comparison clean.",
            "audit": "Action: inspect what files the agent changed after it ran.",
            "history": "Action: compare runs over time and filter risky changes.",
            "plugins": "Action: connect guard to IDEs, CLI wrappers, and CI.",
            "research": "Action: open advanced diagnostics only when you need research detail.",
            "review": "Action: keep a reviewable trail from prompt to diff audit.",
        },
        "zh": {
            "why": "目标: 在 agent 花 token 或改文件之前, 先检查 prompt 风险。",
            "guard": "操作: 粘贴 prompt, 运行策略预检, 再查看风险和改写建议。",
            "improve": "操作: 把模糊 prompt 改写成更清楚、更省 token 的版本。",
            "ui": "操作: 用本地仪表盘在浏览器里完成同一套流程。",
            "analyze": "操作: 生成切分、指标、统计、解释和报告。",
            "gate": "操作: 把报告转成通过、需复核或失败的门禁结论。",
            "model": "操作: 检查模型记录, 判断比较是否干净。",
            "audit": "操作: agent 运行后, 审计它到底改了哪些文件。",
            "history": "操作: 按时间比较 run, 并过滤高风险变化。",
            "plugins": "操作: 把 guard 接进 IDE、CLI wrapper 和 CI。",
            "research": "操作: 需要研究细节时, 再打开高级诊断命令。",
            "review": "操作: 从 prompt 到 diff audit, 都留下可复核证据。",
        },
    }
    key = scene.key.lower()
    for marker, summary in summaries[language].items():
        if marker in key:
            return summary
    return scene.subtitle or summaries[language]["review"]


def command_for_frame(scene: Scene, frame_index: int) -> str:
    if not scene.command_snippets:
        return ""
    if len(scene.command_snippets) == 1:
        return scene.command_snippets[0]
    index = min(frame_index, len(scene.command_snippets) - 1)
    return scene.command_snippets[index]


def output_for_frame(scene: Scene, frame_index: int) -> str:
    if not scene.output_filenames or frame_index < 3:
        return ""
    index = min(max(frame_index - 3, 0), len(scene.output_filenames) - 1)
    return scene.output_filenames[index]


def draw_command_card(draw: Any, x: int, y: int, width: int, command: str, font: Any) -> int:
    card_h = scale_px(112)
    draw.rounded_rectangle(
        (x, y, x + width, y + card_h),
        radius=scale_px(14),
        fill="#0f172a",
        outline="#1e293b",
        width=scale_px(1),
    )
    draw.text((x + scale_px(14), y + scale_px(12)), "$", fill="#38bdf8", font=font)
    text_x = x + scale_px(38)
    text_y = y + scale_px(12)
    for line in wrap_text(command, font, width - scale_px(56))[:4]:
        draw.text((text_x, text_y), line, fill="#e2e8f0", font=font)
        text_y += scale_px(22)
    return y + card_h


def draw_artifact_pill(draw: Any, x: int, y: int, width: int, text: str, font: Any) -> None:
    draw.rounded_rectangle(
        (x, y, x + width, y + scale_px(42)),
        radius=scale_px(16),
        fill="#ecfdf3",
        outline="#22c55e",
        width=scale_px(1),
    )
    draw.text(
        (x + scale_px(14), y + scale_px(11)),
        f"artifact: {text}",
        fill="#166534",
        font=font,
    )


def draw_progress_dots(draw: Any, x: int, y: int, count: int, active: int) -> None:
    for index in range(count):
        dot_x = x + index * scale_px(28)
        fill = "#38bdf8" if index <= active else "#cbd5e1"
        draw.ellipse((dot_x, y, dot_x + scale_px(13), y + scale_px(13)), fill=fill)


def draw_operation_overlay(
    draw: Any,
    shot_x: int,
    shot_y: int,
    shot_w: int,
    shot_h: int,
    frame_index: int,
    scene_key: str,
) -> None:
    regions = operation_regions(scene_key)
    rx, ry, rw, rh = regions[min(frame_index, len(regions) - 1)]
    x1 = shot_x + int(rx * shot_w)
    y1 = shot_y + int(ry * shot_h)
    x2 = x1 + int(rw * shot_w)
    y2 = y1 + int(rh * shot_h)
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=scale_px(12),
        outline="#f97316",
        width=scale_px(5),
    )
    label = f"{frame_index + 1}"
    draw.ellipse(
        (x1 - scale_px(18), y1 - scale_px(18), x1 + scale_px(26), y1 + scale_px(26)),
        fill="#f97316",
    )
    draw.text(
        (x1 - scale_px(3), y1 - scale_px(12)),
        label,
        fill="#ffffff",
        font=load_font(scale_px(18), bold=True),
    )
    cursor_x = min(x2 - scale_px(16), x1 + int(0.78 * (x2 - x1)))
    cursor_y = min(y2 - scale_px(12), y1 + int(0.60 * (y2 - y1)))
    draw_cursor(draw, cursor_x, cursor_y)
    if frame_index in (2, 4):
        ring = scale_px(30)
        draw.ellipse(
            (cursor_x - ring, cursor_y - ring, cursor_x + ring, cursor_y + ring),
            outline="#0ea5e9",
            width=scale_px(4),
        )


def operation_regions(scene_key: str) -> list[tuple[float, float, float, float]]:
    key = scene_key.lower()
    if "model" in key:
        return [
            (0.03, 0.10, 0.24, 0.20),
            (0.23, 0.20, 0.52, 0.16),
            (0.22, 0.32, 0.70, 0.18),
            (0.22, 0.34, 0.70, 0.18),
            (0.22, 0.34, 0.70, 0.18),
        ]
    if "history" in key:
        return [
            (0.03, 0.10, 0.24, 0.20),
            (0.20, 0.22, 0.70, 0.18),
            (0.22, 0.40, 0.68, 0.18),
            (0.22, 0.55, 0.68, 0.20),
            (0.15, 0.74, 0.72, 0.15),
        ]
    if "audit" in key:
        return [
            (0.03, 0.10, 0.24, 0.20),
            (0.22, 0.20, 0.65, 0.16),
            (0.22, 0.38, 0.66, 0.18),
            (0.22, 0.52, 0.66, 0.20),
            (0.18, 0.72, 0.70, 0.18),
        ]
    return [
        (0.03, 0.10, 0.24, 0.20),
        (0.25, 0.22, 0.52, 0.22),
        (0.70, 0.24, 0.20, 0.12),
        (0.24, 0.45, 0.62, 0.30),
        (0.18, 0.72, 0.68, 0.16),
    ]


def draw_cursor(draw: Any, x: int, y: int) -> None:
    points = [
        (x, y),
        (x + scale_px(18), y + scale_px(52)),
        (x + scale_px(30), y + scale_px(30)),
        (x + scale_px(55), y + scale_px(28)),
    ]
    draw.polygon(points, fill="#ffffff", outline="#0f172a")
    draw.line(
        (x + scale_px(22), y + scale_px(32), x + scale_px(40), y + scale_px(62)),
        fill="#0f172a",
        width=scale_px(4),
    )


def load_font(size: int, *, bold: bool = False) -> Any:
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise BuildError(
            "Missing dependency: pillow. Install with: python -m pip install pillow"
        ) from exc
    names = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_mono_font(size: int) -> Any:
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise BuildError(
            "Missing dependency: pillow. Install with: python -m pip install pillow"
        ) from exc
    names = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "DejaVuSansMono.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return load_font(size)


def quoted_concat_path(path: Path) -> str:
    return path.as_posix().replace("'", "'\\''")


def write_frame_concat(frame_paths: list[Path], seconds: float, out_path: Path) -> None:
    if not frame_paths:
        raise BuildError("Cannot encode a scene without rendered operation frames.")
    per_frame = max(0.12, seconds / len(frame_paths))
    lines: list[str] = []
    for frame_path in frame_paths:
        lines.append(f"file '{quoted_concat_path(frame_path)}'")
        lines.append(f"duration {per_frame:.4f}")
    lines.append(f"file '{quoted_concat_path(frame_paths[-1])}'")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scene_filter() -> str:
    return (
        f"scale={VIDEO_SIZE[0]}:{VIDEO_SIZE[1]}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_SIZE[0]}:{VIDEO_SIZE[1]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )


def validate_video_dimensions(path: Path, ffmpeg: Path) -> None:
    ffprobe = ffmpeg.with_name("ffprobe.exe" if ffmpeg.name.endswith(".exe") else "ffprobe")
    if not ffprobe.exists():
        return
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip() != f"{VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}":
        raise BuildError(
            f"{path} is {result.stdout.strip()}, expected {VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}."
        )

def wrap_text(text: str, font: Any, max_width: int) -> list[str]:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise BuildError(
            "Missing dependency: pillow. Install with: python -m pip install pillow"
        ) from exc
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        if contains_cjk(paragraph):
            lines.extend(wrap_cjk(paragraph, draw, font, max_width))
        else:
            lines.extend(textwrap.wrap(paragraph, width=42) or [paragraph])
    fitted: list[str] = []
    for line in lines:
        if text_width(draw, line, font) <= max_width:
            fitted.append(line)
            continue
        fitted.extend(wrap_cjk(line, draw, font, max_width))
    return fitted


def wrap_cjk(text: str, draw: Any, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    tokens = re.findall(r"[A-Za-z0-9_./:-]+|[ \t]+|.", text)
    no_line_start = (
        "\u3001\u3002\uff0c\uff1b\uff1a\uff1f\uff01"
        "\uff09\u3011\u300b\u300d\u300f.,;:!?)]}"
    )
    for token in tokens:
        trial = current + token
        if current and text_width(draw, trial, font) > max_width:
            if token in no_line_start:
                current = trial
                continue
            lines.append(current.rstrip())
            current = token.lstrip()
        else:
            current = trial
    if current:
        lines.append(current.rstrip())
    return lines


def text_width(draw: Any, text: str, font: Any) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0])


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def synthesize_narration(text: str, wav_path: Path, language: str, mode: str, ffmpeg: Path) -> None:
    if mode in ("auto", "edge"):
        try:
            synthesize_edge_tts(text, wav_path, language, ffmpeg)
            return
        except Exception as exc:
            if mode == "edge":
                raise BuildError(f"Neural TTS failed for {language}: {exc}") from exc
            print(f"warning: neural TTS unavailable for {language}; falling back to SAPI ({exc})")
    if mode in ("auto", "sapi"):
        try:
            synthesize_sapi(text, wav_path, language)
            return
        except Exception as exc:
            if mode == "sapi":
                raise BuildError(f"SAPI TTS failed for {language}: {exc}") from exc
            print(f"warning: SAPI TTS unavailable for {language}; using silent audio ({exc})")
    synthesize_silence(wav_path, estimate_duration(text, language))


def synthesize_edge_tts(text: str, wav_path: Path, language: str, ffmpeg: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise BuildError("edge-tts is not installed") from exc

    profile = EDGE_PROFILES[language]
    chunks = chunk_narration(text, language) if profile["chunked"] else [text]
    if len(chunks) > 1:
        synthesize_edge_tts_chunks(chunks, wav_path, language, ffmpeg, edge_tts, profile)
        return

    mp3_path = wav_path.with_suffix(".mp3")

    async def run() -> None:
        communicate = edge_tts.Communicate(
            text,
            profile["voice"],
            rate=profile["rate"],
            pitch=profile["pitch"],
        )
        await communicate.save(str(mp3_path))

    asyncio.run(run())
    run_command(
        [
            str(ffmpeg),
            "-y",
            "-i",
            str(mp3_path),
            "-ar",
            "44100",
            "-ac",
            "2",
            str(wav_path),
        ],
        "convert neural TTS audio",
    )


def chunk_narration(text: str, language: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if language != "zh" or not normalized:
        return [normalized] if normalized else []
    sentence_end = "\u3002\uff01\uff1f\uff1b.!?"
    pieces = [
        match.group(0).strip()
        for match in re.finditer(rf".+?(?:[{sentence_end}]|$)", normalized)
        if match.group(0).strip()
    ]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) <= 44:
            current += piece
            continue
        if current:
            chunks.append(current)
        current = piece
    if current:
        chunks.append(current)
    return chunks or [normalized]


def synthesize_edge_tts_chunks(
    chunks: list[str],
    wav_path: Path,
    language: str,
    ffmpeg: Path,
    edge_tts: Any,
    profile: dict[str, Any],
) -> None:
    temp_context = tempfile.TemporaryDirectory(prefix=f"pcl_tts_{language}_")
    temp_dir = Path(temp_context.name)
    try:
        wav_parts: list[Path] = []
        for index, chunk in enumerate(chunks, start=1):
            mp3_part = temp_dir / f"part_{index:02d}.mp3"
            wav_part = temp_dir / f"part_{index:02d}.wav"

            async def run(text_chunk: str = chunk, mp3_output: Path = mp3_part) -> None:
                communicate = edge_tts.Communicate(
                    text_chunk,
                    profile["voice"],
                    rate=profile["rate"],
                    pitch=profile["pitch"],
                )
                await communicate.save(str(mp3_output))

            asyncio.run(run())
            run_command(
                [
                    str(ffmpeg),
                    "-y",
                    "-i",
                    str(mp3_part),
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    str(wav_part),
                ],
                "convert chunked neural TTS audio",
            )
            wav_parts.append(wav_part)
        concatenate_wavs(wav_parts, wav_path, pause_ms=int(profile["pause_ms"]))
    finally:
        temp_context.cleanup()


def concatenate_wavs(parts: list[Path], out_path: Path, *, pause_ms: int) -> None:
    if not parts:
        synthesize_silence(out_path, MIN_SLIDE_SECONDS)
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()
    pause_frames = int(params.framerate * (pause_ms / 1000))
    silence_frame = b"\x00" * params.sampwidth * params.nchannels
    with wave.open(str(out_path), "wb") as output:
        output.setparams(params)
        for index, part in enumerate(parts):
            if index:
                output.writeframes(silence_frame * pause_frames)
            with wave.open(str(part), "rb") as source:
                if source.getparams()[:3] != params[:3]:
                    raise BuildError("Chunked TTS wav files have incompatible audio parameters.")
                output.writeframes(source.readframes(source.getnframes()))


def synthesize_sapi(text: str, wav_path: Path, language: str) -> None:
    if platform.system().lower() != "windows":
        raise BuildError("Windows SAPI fallback requires Windows.")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise BuildError("PowerShell was not found for Windows SAPI fallback.")

    voice_literals = ", ".join(to_ps_literal(voice) for voice in SAPI_VOICES[language])
    text_literal = to_ps_literal(text)
    path_literal = to_ps_literal(str(wav_path))
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @({voice_literals})
$installed = $synth.GetInstalledVoices() | ForEach-Object {{ $_.VoiceInfo.Name }}
$selected = $voices | Where-Object {{ $installed -contains $_ }} | Select-Object -First 1
if (-not $selected) {{
  throw "None of the requested SAPI voices are installed: $($voices -join ', ')"
}}
$synth.SelectVoice($selected)
$synth.Rate = 0
$synth.Volume = 100
$synth.SetOutputToWaveFile({path_literal})
$synth.Speak({text_literal})
$synth.Dispose()
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        run_command(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            "synthesize Windows SAPI narration",
        )
    finally:
        script_path.unlink(missing_ok=True)


def to_ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def synthesize_silence(wav_path: Path, seconds: float) -> None:
    sample_rate = 44100
    frames = math.ceil(seconds * sample_rate)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        chunk = b"\x00\x00\x00\x00" * 4096
        remaining = frames
        while remaining > 0:
            count = min(remaining, 4096)
            handle.writeframes(chunk[: count * 4])
            remaining -= count


def estimate_duration(text: str, language: str) -> float:
    if language == "zh":
        return max(MIN_SLIDE_SECONDS, len(text) / 5.5)
    words = max(1, len(re.findall(r"\w+", text)))
    return max(MIN_SLIDE_SECONDS, words / 2.4)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(rendered: list[tuple[Scene, list[Path], Path, float]], srt_path: Path) -> None:
    lines: list[str] = []
    start = 0.0
    for index, (scene, _frames, _audio, seconds) in enumerate(rendered, start=1):
        end = start + seconds
        lines.extend(
            [
                str(index),
                f"{srt_time(start)} --> {srt_time(end)}",
                scene.narration,
                "",
            ]
        )
        start = end
    srt_path.write_text("\n".join(lines), encoding="utf-8")


def encode_video(
    rendered: list[tuple[Scene, list[Path], Path, float]],
    mp4_path: Path,
    ffmpeg: Path,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pcl_ffmpeg_concat_") as temp_name:
        temp_dir = Path(temp_name)
        part_paths: list[Path] = []
        for index, (_scene, frame_paths, audio_path, seconds) in enumerate(rendered, start=1):
            part_path = temp_dir / f"part_{index:02d}.mp4"
            frames_concat = temp_dir / f"frames_{index:02d}.txt"
            write_frame_concat(frame_paths, seconds, frames_concat)
            bitrate = bitrate_for_duration(total_duration(rendered))
            run_command(
                [
                    str(ffmpeg),
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(frames_concat),
                    "-i",
                    str(audio_path),
                    "-t",
                    f"{seconds:.3f}",
                    "-vf",
                    scene_filter(),
                    "-r",
                    str(FPS),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-profile:v",
                    "main",
                    "-b:v",
                    f"{bitrate}k",
                    "-maxrate",
                    f"{bitrate}k",
                    "-bufsize",
                    f"{bitrate * 2}k",
                    "-c:a",
                    "aac",
                    "-b:a",
                    f"{AUDIO_BITRATE_K}k",
                    "-movflags",
                    "+faststart",
                    str(part_path),
                ],
                "encode slide segment",
            )
            part_paths.append(part_path)
        concat_file = temp_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in part_paths),
            encoding="utf-8",
        )
        run_command(
            [
                str(ffmpeg),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(mp4_path),
            ],
            "concatenate video segments",
        )
        validate_video_dimensions(mp4_path, ffmpeg)


def total_duration(rendered: list[tuple[Scene, list[Path], Path, float]]) -> float:
    return sum(seconds for _scene, _frames, _audio, seconds in rendered)


def bitrate_for_duration(seconds: float) -> int:
    budget_kbits = TARGET_MB * 1024 * 8 * 0.86
    video_k = int((budget_kbits / max(seconds, 1.0)) - AUDIO_BITRATE_K)
    return max(120, min(MAX_VIDEO_BITRATE_K, video_k))


def find_ffmpeg() -> Path:
    try:
        import imageio_ffmpeg

        path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if path.exists():
            return path
    except ImportError:
        pass
    system = shutil.which("ffmpeg")
    if system:
        return Path(system)
    raise BuildError(
        "ffmpeg was not found. Install imageio-ffmpeg with "
        "'python -m pip install imageio-ffmpeg' or put ffmpeg on PATH."
    )


def run_command(command: list[str], action: str) -> None:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    result = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise BuildError(f"Failed to {action}: {detail}")


def default_title(language: str) -> str:
    if language == "zh":
        return "prompt_control_lab 双语演示"
    return "prompt_control_lab Demo"


if __name__ == "__main__":
    raise SystemExit(main())
