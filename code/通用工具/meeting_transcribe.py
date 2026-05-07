from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import av
import numpy as np
from faster_whisper import WhisperModel
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score


TERMS_PROMPT = (
    "专业术语包括：SBM、SBM-DEA、DEA、超效率SBM、Malmquist、"
    "面板回归、双固定效应、随机效应、Hausman检验、Pooled OLS、"
    "空间计量、空间相关性、莫兰指数、Moran's I、LISA、"
    "空间杜宾模型、SDM、SAR、SEM、LM检验、Wald检验、LR检验、"
    "Driscoll-Kraay标准误、夜间灯光聚合度、碳排放效率。"
)

TERM_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bs[\s-]*b[\s-]*m\b", re.I), "SBM"),
    (re.compile(r"\bd[\s-]*e[\s-]*a\b", re.I), "DEA"),
    (re.compile(r"\bsbm\s*[-/]\s*dea\b", re.I), "SBM-DEA"),
    (re.compile(r"\bs[\s-]*d[\s-]*m\b", re.I), "SDM"),
    (re.compile(r"\bs[\s-]*a[\s-]*r\b", re.I), "SAR"),
    (re.compile(r"\bs[\s-]*e[\s-]*m\b", re.I), "SEM"),
    (re.compile(r"\bl[\s-]*m\b", re.I), "LM"),
    (re.compile(r"\bv[\s-]*i[\s-]*f\b", re.I), "VIF"),
    (re.compile(r"\bl[\s-]*i[\s-]*s[\s-]*a\b", re.I), "LISA"),
    (re.compile(r"\bhausman\b", re.I), "Hausman"),
    (re.compile(r"\bmoran('?s)?\s*i\b", re.I), "Moran's I"),
    (re.compile(r"莫兰\s*[iI１1]"), "莫兰 I"),
    (re.compile(r"\bdea\s*run\b", re.I), "DEARUN"),
    (re.compile(r"\bdearun\b", re.I), "DEARUN"),
    (re.compile(r"空间杜宾"), "空间杜宾"),
    (re.compile(r"双固定效[益应]"), "双固定效应"),
    (re.compile(r"面版回归"), "面板回归"),
]


@dataclass
class SegmentRecord:
    start: float
    end: float
    speaker: str
    text: str


def format_ts(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    for pattern, repl in TERM_REPLACEMENTS:
        text = pattern.sub(repl, text)
    return text


def is_low_value_text(text: str) -> bool:
    stripped = re.sub(r"[，。、“”‘’？！：；,.!?;:\-\s]", "", text)
    if not stripped:
        return True
    tokens = re.findall(r"[嗯啊呃哦唉欸诶]", stripped)
    if stripped and len("".join(tokens)) / max(len(stripped), 1) > 0.85:
        return True
    return False


def extract_feature(y: np.ndarray, sr: int) -> np.ndarray:
    if y.size == 0:
        return np.zeros(40, dtype=np.float32)
    if np.max(np.abs(y)) > 0:
        y = y / np.max(np.abs(y))
    frame = max(256, int(sr * 0.025))
    hop = max(128, int(sr * 0.010))
    if y.size < frame:
        y = np.pad(y, (0, frame - y.size))
    n_frames = 1 + max(0, (len(y) - frame) // hop)
    windows = np.lib.stride_tricks.sliding_window_view(y, frame)[::hop][:n_frames]
    win = np.hanning(frame).astype(np.float32)
    windows = windows * win
    spec = np.abs(np.fft.rfft(windows, axis=1)) + 1e-8
    freqs = np.fft.rfftfreq(frame, d=1.0 / sr)
    power = spec**2
    power_sum = np.sum(power, axis=1) + 1e-8
    centroid = np.sum(power * freqs[None, :], axis=1) / power_sum
    spread = np.sqrt(np.sum(power * (freqs[None, :] - centroid[:, None]) ** 2, axis=1) / power_sum)
    flatness = np.exp(np.mean(np.log(spec), axis=1)) / np.mean(spec, axis=1)
    rolloff_threshold = 0.85 * power_sum
    cumulative = np.cumsum(power, axis=1)
    rolloff_idx = np.argmax(cumulative >= rolloff_threshold[:, None], axis=1)
    rolloff = freqs[rolloff_idx]
    zcr = np.mean(np.abs(np.diff(np.signbit(windows), axis=1)), axis=1)
    rms = np.sqrt(np.mean(windows**2, axis=1))
    log_spec = np.log(spec)
    low_bands = np.array_split(log_spec, 8, axis=1)
    band_means = np.array([band.mean(axis=1) for band in low_bands])
    feats = np.concatenate(
        [
            np.array(
                [
                    centroid.mean(),
                    centroid.std(),
                    spread.mean(),
                    spread.std(),
                    flatness.mean(),
                    flatness.std(),
                    rolloff.mean(),
                    rolloff.std(),
                    zcr.mean(),
                    zcr.std(),
                    rms.mean(),
                    rms.std(),
                ],
                dtype=np.float32,
            ),
            band_means.mean(axis=1).astype(np.float32),
            band_means.std(axis=1).astype(np.float32),
        ]
    )
    return np.nan_to_num(feats.astype(np.float32))


def load_audio_for_diarization(path: Path, sr: int = 16000) -> tuple[np.ndarray, int]:
    container = av.open(str(path))
    stream = next(s for s in container.streams if s.type == "audio")
    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=sr)
    chunks: list[np.ndarray] = []
    for frame in container.decode(stream):
        mono = resampler.resample(frame)
        frames = mono if isinstance(mono, list) else [mono]
        for out_frame in frames:
            arr = out_frame.to_ndarray()
            if arr.ndim > 1:
                arr = arr[0]
            chunks.append(arr.astype(np.float32) / 32768.0)
    if not chunks:
        return np.zeros(1, dtype=np.float32), sr
    return np.concatenate(chunks), sr


def choose_cluster_count(features: np.ndarray) -> int:
    n_samples = len(features)
    if n_samples < 4:
        return 1
    best_k = 1
    best_score = -1.0
    upper = min(4, n_samples - 1)
    for k in range(2, upper + 1):
        model = AgglomerativeClustering(n_clusters=k)
        labels = model.fit_predict(features)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(features, labels)
        if score > best_score:
            best_score = score
            best_k = k
    return best_k


def diarize_segments(
    audio: np.ndarray, sr: int, raw_segments: list[dict[str, float | str]]
) -> list[str]:
    valid_indexes: list[int] = []
    valid_features: list[np.ndarray] = []
    for idx, seg in enumerate(raw_segments):
        start = max(0, int(float(seg["start"]) * sr))
        end = min(len(audio), int(float(seg["end"]) * sr))
        clip = audio[start:end]
        duration = (end - start) / sr
        if duration < 1.2:
            continue
        valid_indexes.append(idx)
        valid_features.append(extract_feature(clip, sr))

    speakers = ["发言人1"] * len(raw_segments)
    if len(valid_features) < 4:
        return speakers

    feature_matrix = np.vstack(valid_features)
    k = choose_cluster_count(feature_matrix)
    if k <= 1:
        return speakers

    model = AgglomerativeClustering(n_clusters=k)
    labels = model.fit_predict(feature_matrix)

    for idx, label in zip(valid_indexes, labels, strict=False):
        speakers[idx] = f"发言人{int(label) + 1}"

    for idx in range(1, len(speakers)):
        if speakers[idx] == "发言人1" and idx not in valid_indexes:
            speakers[idx] = speakers[idx - 1]

    return speakers


def merge_segments(records: Iterable[SegmentRecord]) -> list[SegmentRecord]:
    merged: list[SegmentRecord] = []
    for rec in records:
        if not rec.text:
            continue
        if not merged:
            merged.append(rec)
            continue
        prev = merged[-1]
        if rec.speaker == prev.speaker and rec.start - prev.end <= 1.0:
            prev.end = rec.end
            prev.text = f"{prev.text} {rec.text}".strip()
        else:
            merged.append(rec)
    return merged


def render_markdown(
    video_path: Path,
    model_name: str,
    language: str,
    records: list[SegmentRecord],
) -> str:
    lines = [
        f"# 会议转写：{video_path.name}",
        "",
        f"- 模型：`{model_name}`",
        f"- 语言：`{language}`",
        "- 说明：发言人为本地聚类得到的暂定标签，适合速读与后续人工校对。",
        "- 术语已按项目主题做过一次自动纠偏，重点覆盖 `SBM-DEA`、面板回归、空间计量相关表述。",
        "",
        "## 转写正文",
        "",
    ]
    for i, rec in enumerate(records, start=1):
        lines.extend(
            [
                f"### {i}. {format_ts(rec.start)} - {format_ts(rec.end)} | {rec.speaker}",
                "",
                rec.text,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--model",
        default="large-v3",
        help="Whisper model name, for example: small, medium, large-v3",
    )
    parser.add_argument("--language", default="zh")
    parser.add_argument("--compute-type", default="int8")
    args = parser.parse_args()

    video_path = args.video.resolve()
    out_md = video_path.with_name(f"{video_path.stem}_转写稿.md")
    out_json = video_path.with_name(f"{video_path.stem}_segments.json")

    model = WhisperModel(args.model, device="cpu", compute_type=args.compute_type)
    segments, info = model.transcribe(
        str(video_path),
        language=args.language,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=True,
        initial_prompt=TERMS_PROMPT,
        hotwords="SBM, SBM-DEA, DEA, Moran's I, LISA, SDM, SAR, SEM, Hausman",
        temperature=0,
        beam_size=5,
    )

    raw_segments: list[dict[str, float | str]] = []
    for seg in segments:
        text = normalize_text(seg.text)
        if not text or is_low_value_text(text):
            continue
        raw_segments.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text,
            }
        )

    audio, sr = load_audio_for_diarization(video_path, sr=16000)
    speaker_tags = diarize_segments(audio, sr, raw_segments)

    records = [
        SegmentRecord(
            start=float(seg["start"]),
            end=float(seg["end"]),
            speaker=speaker,
            text=str(seg["text"]),
        )
        for seg, speaker in zip(raw_segments, speaker_tags, strict=False)
    ]
    merged_records = merge_segments(records)

    out_json.write_text(
        json.dumps(
            {
                "video": str(video_path),
                "model": args.model,
                "language": info.language,
                "duration_seconds": getattr(info, "duration", math.nan),
                "segments": [asdict(r) for r in merged_records],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    out_md.write_text(
        render_markdown(video_path, args.model, info.language, merged_records),
        encoding="utf-8",
    )

    print(f"markdown={out_md}")
    print(f"json={out_json}")
    print(f"segments={len(merged_records)}")
    print(f"duration_seconds={getattr(info, 'duration', math.nan)}")


if __name__ == "__main__":
    main()
