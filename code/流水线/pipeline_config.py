from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from stage_config import STAGE_DIRS, derived_dearun_result_dir, load_stage_config, resolve_project_path
from step_types import InputRequirement, RunnerType, StepDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_EXE = Path(sys.executable)
LOGO_PATH = PROJECT_ROOT / "releases" / "比赛版" / "图" / "logo.png"
PIPELINE_STEPS_PATH = PROJECT_ROOT / "code" / "流水线" / "pipeline_steps.json"
PIPELINE_VERSION = 1
VALID_PRECHECK_MODES = {"none", "required_inputs", "manual_result"}
VALID_INPUT_KINDS = {"file", "directory", "csv"}
TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")


class PipelineConfigError(ValueError):
    pass


def root_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def stage_names() -> tuple[str, ...]:
    return tuple(STAGE_DIRS.keys())


def load_pipeline_document() -> dict[str, Any]:
    if not PIPELINE_STEPS_PATH.exists():
        raise PipelineConfigError(f"流水线配置不存在：{PIPELINE_STEPS_PATH}")
    try:
        document = json.loads(PIPELINE_STEPS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineConfigError(f"流水线配置 JSON 解析失败：{exc}") from exc
    validate_pipeline_steps(document)
    return document


def save_pipeline_document(document: dict[str, Any]) -> None:
    validate_pipeline_steps(document)
    PIPELINE_STEPS_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_pipeline_step_configs() -> list[dict[str, Any]]:
    return deepcopy(load_pipeline_document()["steps"])


def resolve_pipeline_template(text: str, stage_configs: dict[str, dict[str, Any]]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1).strip()
        if token == "PROJECT_ROOT":
            return PROJECT_ROOT.as_posix()
        if "." not in token:
            raise PipelineConfigError(f"无法解析模板占位符：{token}")

        stage, expression = token.split(".", 1)
        if stage not in stage_configs:
            raise PipelineConfigError(f"模板引用了未知阶段：{stage}")
        value = _resolve_expression(stage_configs[stage], expression, token)
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, (str, int, float)):
            return str(value)
        raise PipelineConfigError(f"模板占位符未解析为字符串：{token}")

    return TEMPLATE_PATTERN.sub(replace, text)


def build_step_definitions() -> tuple[StepDefinition, ...]:
    return load_pipeline_steps()


def build_step_map() -> dict[str, StepDefinition]:
    steps = build_step_definitions()
    return {step.id: step for step in steps}


def load_pipeline_steps(include_disabled: bool = False) -> tuple[StepDefinition, ...]:
    document = load_pipeline_document()
    stage_configs = _load_stage_configs()
    steps: list[StepDefinition] = []
    for raw_step in document["steps"]:
        if not include_disabled and not raw_step.get("enabled", True):
            continue
        steps.append(_build_step_definition(raw_step, stage_configs))
    return tuple(steps)


def validate_pipeline_steps(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise PipelineConfigError("流水线配置顶层必须是对象。")
    if document.get("version") != PIPELINE_VERSION:
        raise PipelineConfigError(f"流水线配置版本必须为 {PIPELINE_VERSION}。")

    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PipelineConfigError("流水线配置 steps 必须是非空数组。")

    stage_configs = _load_stage_configs()
    known_stages = set(stage_names())
    seen_ids: set[str] = set()
    enabled_count = 0

    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict):
            raise PipelineConfigError(f"第 {index + 1} 个步骤不是对象。")

        step_id = raw_step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise PipelineConfigError(f"第 {index + 1} 个步骤缺少有效 id。")
        if step_id in seen_ids:
            raise PipelineConfigError(f"步骤 id 重复：{step_id}")
        seen_ids.add(step_id)

        stage = raw_step.get("stage")
        if stage not in known_stages:
            raise PipelineConfigError(f"步骤 {step_id} 的 stage 非法：{stage}")

        runner_type = raw_step.get("runner_type")
        if runner_type not in {member.value for member in RunnerType}:
            raise PipelineConfigError(f"步骤 {step_id} 的 runner_type 非法：{runner_type}")

        precheck_mode = raw_step.get("precheck_mode")
        if precheck_mode not in VALID_PRECHECK_MODES:
            raise PipelineConfigError(f"步骤 {step_id} 的 precheck_mode 非法：{precheck_mode}")

        enabled = raw_step.get("enabled", True)
        if not isinstance(enabled, bool):
            raise PipelineConfigError(f"步骤 {step_id} 的 enabled 必须是布尔值。")
        if enabled:
            enabled_count += 1

        command = raw_step.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            raise PipelineConfigError(f"步骤 {step_id} 的 command 必须是非空字符串数组。")
        if runner_type == RunnerType.PYTHON.value and command[0] != "python":
            raise PipelineConfigError(f"步骤 {step_id} 的 python 步骤命令必须以 'python' 开头。")
        if runner_type == RunnerType.HYBRID.value and command[0] != "stata-do":
            raise PipelineConfigError(f"步骤 {step_id} 的 hybrid 步骤命令必须以 'stata-do' 开头。")
        if runner_type == RunnerType.MANUAL.value and command[0] != "open-path":
            raise PipelineConfigError(f"步骤 {step_id} 的 manual 步骤命令必须以 'open-path' 开头。")

        _validate_string_field(raw_step, "name", step_id)
        _validate_string_field(raw_step, "working_dir", step_id)
        _validate_optional_string_field(raw_step, "description", step_id)
        _validate_sequence_field(raw_step, "expected_outputs", step_id)
        _validate_sequence_field(raw_step, "image_globs", step_id)
        _validate_sequence_field(raw_step, "markdown_globs", step_id)
        _validate_sequence_field(raw_step, "notes", step_id)
        _validate_sequence_field(raw_step, "console_success_markers", step_id)

        primary_csv = raw_step.get("primary_csv")
        if primary_csv is not None and not isinstance(primary_csv, str):
            raise PipelineConfigError(f"步骤 {step_id} 的 primary_csv 必须是字符串或 null。")

        required_inputs = raw_step.get("required_inputs", [])
        if not isinstance(required_inputs, list):
            raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs 必须是数组。")
        for req_index, requirement in enumerate(required_inputs):
            if not isinstance(requirement, dict):
                raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs[{req_index}] 必须是对象。")
            path_text = requirement.get("path")
            if not isinstance(path_text, str) or not path_text:
                raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs[{req_index}].path 缺失。")
            kind = requirement.get("kind", "file")
            if kind not in VALID_INPUT_KINDS:
                raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs[{req_index}].kind 非法：{kind}")
            columns = requirement.get("required_columns", [])
            if not isinstance(columns, list) or not all(isinstance(column, str) for column in columns):
                raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs[{req_index}].required_columns 必须是字符串数组。")
            label = requirement.get("label", "")
            if not isinstance(label, str):
                raise PipelineConfigError(f"步骤 {step_id} 的 required_inputs[{req_index}].label 必须是字符串。")
            resolve_pipeline_template(path_text, stage_configs)

        resolve_pipeline_template(raw_step["working_dir"], stage_configs)
        for key in ("expected_outputs", "image_globs", "markdown_globs", "notes", "console_success_markers"):
            for value in raw_step.get(key, []):
                if not isinstance(value, str):
                    raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是字符串数组。")
                if key in {"expected_outputs", "image_globs", "markdown_globs"}:
                    resolve_pipeline_template(value, stage_configs)
        if primary_csv:
            resolve_pipeline_template(primary_csv, stage_configs)
        for command_part in command:
            if "{" in command_part:
                resolve_pipeline_template(command_part, stage_configs)

    if enabled_count == 0:
        raise PipelineConfigError("至少需要保留一个启用的流水线步骤。")


def _validate_string_field(raw_step: dict[str, Any], key: str, step_id: str) -> None:
    value = raw_step.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是非空字符串。")


def _validate_optional_string_field(raw_step: dict[str, Any], key: str, step_id: str) -> None:
    value = raw_step.get(key, "")
    if not isinstance(value, str):
        raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是字符串。")


def _validate_sequence_field(raw_step: dict[str, Any], key: str, step_id: str) -> None:
    value = raw_step.get(key, [])
    if not isinstance(value, list):
        raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是数组。")
    if not all(isinstance(item, str) for item in value):
        raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是字符串数组。")


def _load_stage_configs() -> dict[str, dict[str, Any]]:
    configs = {stage: load_stage_config(stage) for stage in stage_names()}
    efficiency_cfg = dict(configs["效率测算"])
    efficiency_cfg["dearun_result_dir"] = str(derived_dearun_result_dir(efficiency_cfg).relative_to(PROJECT_ROOT).as_posix())
    configs["效率测算"] = efficiency_cfg
    return configs


def _resolve_expression(payload: Any, expression: str, token: str) -> Any:
    current = payload
    for part in expression.split("."):
        current = _apply_segment(current, part, token)
    return current


def _apply_segment(current: Any, segment: str, token: str) -> Any:
    cursor = 0
    while cursor < len(segment):
        bracket_index = segment.find("[", cursor)
        chunk = segment[cursor:] if bracket_index == -1 else segment[cursor:bracket_index]
        if chunk:
            if not isinstance(current, dict) or chunk not in current:
                raise PipelineConfigError(f"模板占位符不存在：{token}")
            current = current[chunk]
        if bracket_index == -1:
            break
        end_index = segment.find("]", bracket_index)
        if end_index == -1:
            raise PipelineConfigError(f"模板占位符数组语法错误：{token}")
        index_text = segment[bracket_index + 1:end_index]
        if not index_text.isdigit():
            raise PipelineConfigError(f"模板占位符数组下标非法：{token}")
        index = int(index_text)
        if not isinstance(current, list) or index >= len(current):
            raise PipelineConfigError(f"模板占位符数组越界：{token}")
        current = current[index]
        cursor = end_index + 1
    return current


def _build_step_definition(raw_step: dict[str, Any], stage_configs: dict[str, dict[str, Any]]) -> StepDefinition:
    required_inputs = tuple(
        InputRequirement(
            path=resolve_project_path(resolve_pipeline_template(requirement["path"], stage_configs)),
            kind=requirement.get("kind", "file"),
            required_columns=tuple(requirement.get("required_columns", [])),
            label=requirement.get("label", ""),
        )
        for requirement in raw_step.get("required_inputs", [])
    )
    command = tuple(resolve_pipeline_template(part, stage_configs) if "{" in part else part for part in raw_step["command"])
    expected_outputs = tuple(resolve_pipeline_template(pattern, stage_configs) for pattern in raw_step.get("expected_outputs", []))
    image_globs = tuple(resolve_pipeline_template(pattern, stage_configs) for pattern in raw_step.get("image_globs", []))
    markdown_globs = tuple(resolve_pipeline_template(pattern, stage_configs) for pattern in raw_step.get("markdown_globs", []))
    primary_csv_text = raw_step.get("primary_csv")
    primary_csv = resolve_project_path(resolve_pipeline_template(primary_csv_text, stage_configs)) if primary_csv_text else None
    working_dir = resolve_project_path(resolve_pipeline_template(raw_step["working_dir"], stage_configs))

    return StepDefinition(
        id=raw_step["id"],
        name=raw_step["name"],
        stage=raw_step["stage"],
        runner_type=RunnerType(raw_step["runner_type"]),
        command=command,
        working_dir=working_dir,
        precheck_mode=raw_step["precheck_mode"],
        required_inputs=required_inputs,
        expected_outputs=expected_outputs,
        primary_csv=primary_csv,
        image_globs=image_globs,
        markdown_globs=markdown_globs,
        console_success_markers=tuple(raw_step.get("console_success_markers", [])),
        description=raw_step.get("description", ""),
        notes=tuple(raw_step.get("notes", [])),
    )
