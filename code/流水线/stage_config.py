from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "code" / "流水线" / "config_state.json"

STAGE_DIRS = {
    "数据处理": PROJECT_ROOT / "code" / "数据处理" / "config",
    "效率测算": PROJECT_ROOT / "code" / "效率测算" / "config",
    "回归分析": PROJECT_ROOT / "code" / "回归分析" / "config",
    "空间分析": PROJECT_ROOT / "code" / "空间分析" / "config",
}

SCRIPT_STAGE_SEGMENTS = {
    "数据处理": "数据处理",
    "效率测算": "效率测算",
    "回归分析": "回归分析",
    "空间分析": "空间分析",
}


@dataclass(frozen=True)
class ScriptStageContext:
    stage: str
    config_name: str
    config: dict[str, Any]
    project_root: Path


def resolve_project_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def list_stage_config_names(stage: str) -> list[str]:
    config_dir = STAGE_DIRS[stage]
    if not config_dir.exists():
        return []
    return sorted(path.stem for path in config_dir.glob("*.json"))


def _default_config_name(stage: str) -> str:
    names = list_stage_config_names(stage)
    if not names:
        raise FileNotFoundError(f"{stage} 未找到任何配置文件。")
    if "default" in names:
        return "default"
    if "baseline" in names:
        return "baseline"
    return names[0]


def _load_state() -> dict[str, str]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict[str, str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_config_name(stage: str) -> str:
    state = _load_state()
    active = state.get(stage)
    if active and active in list_stage_config_names(stage):
        return active
    fallback = _default_config_name(stage)
    state[stage] = fallback
    _save_state(state)
    return fallback


def set_active_config_name(stage: str, config_name: str) -> None:
    names = list_stage_config_names(stage)
    if config_name not in names:
        raise ValueError(f"{stage} 不存在配置 {config_name!r}。可选值：{names}")
    state = _load_state()
    state[stage] = config_name
    _save_state(state)


def load_stage_config(stage: str, explicit_name: str | None = None) -> dict[str, Any]:
    config_name = explicit_name or get_active_config_name(stage)
    config_path = STAGE_DIRS[stage] / f"{config_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"{stage} 配置不存在：{config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if stage == "效率测算" and "first_stage_panel" in config:
        config.setdefault("dearun_input_panel", config["first_stage_panel"])
    config.setdefault("config_name", config_name)
    config.setdefault("output_root", f"outputs/{stage}/{config_name}")
    return config


def detect_stage_from_script(script_path: Path) -> str:
    normalized = script_path.resolve()
    parts = set(normalized.parts)
    for stage, segment in SCRIPT_STAGE_SEGMENTS.items():
        if segment in parts:
            return stage
    raise ValueError(f"无法根据脚本路径识别阶段：{script_path}")


def parse_config_argument(argv: list[str] | None = None) -> str | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", dest="config_name")
    args, _ = parser.parse_known_args(argv)
    return args.config_name


def load_script_context(script_path: Path, argv: list[str] | None = None) -> ScriptStageContext:
    stage = detect_stage_from_script(script_path)
    explicit_name = parse_config_argument(argv)
    config = load_stage_config(stage, explicit_name=explicit_name)
    return ScriptStageContext(
        stage=stage,
        config_name=str(config["config_name"]),
        config=config,
        project_root=PROJECT_ROOT,
    )


def stage_output_dir(config: dict[str, Any], leaf_dir: str) -> Path:
    return resolve_project_path(config["output_root"]) / leaf_dir


def derived_dearun_result_dir(efficiency_config: dict[str, Any]) -> Path:
    panel_path = resolve_project_path(efficiency_config["dearun_input_panel"])
    return panel_path.parent / f"结果_{panel_path.stem}"
