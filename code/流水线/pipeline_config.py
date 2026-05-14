from __future__ import annotations

import ast
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from stage_config import STAGE_DIRS, derived_dearun_result_dir, load_stage_config, resolve_project_path
from step_types import InputRequirement, PipelineEntry, RunnerType, StepDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_EXE = Path(sys.executable)
LOGO_PATH = PROJECT_ROOT / "releases" / "比赛版" / "图" / "logo.png"
PIPELINE_STEPS_PATH = PROJECT_ROOT / "code" / "流水线" / "pipeline_steps.json"
PIPELINE_VERSION = 2
VALID_PRECHECK_MODES = {"none", "required_inputs", "manual_result"}
VALID_INPUT_KINDS = {"file", "directory", "csv"}
TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")
DO_STEP_SPEC_BEGIN = "STEP_SPEC_BEGIN"
DO_STEP_SPEC_END = "STEP_SPEC_END"
FORBIDDEN_MANIFEST_FIELDS = {
    "command",
    "required_inputs",
    "expected_outputs",
    "primary_csv",
    "image_globs",
    "markdown_globs",
    "runner_type",
    "working_dir",
    "precheck_mode",
    "console_success_markers",
    "notes",
    "description",
    "name",
}
FORBIDDEN_STEP_SPEC_FIELDS = {
    "expected_outputs",
    "primary_csv",
    "image_globs",
    "markdown_globs",
}
ALLOWED_MANIFEST_FIELDS = {
    "id",
    "script",
    "stage",
    "enabled",
    "order",
    "name_override",
    "description_override",
}
ALLOWED_STEP_SPEC_FIELDS = {
    "name",
    "runner_type",
    "command",
    "working_dir",
    "precheck_mode",
    "required_inputs",
    "artifacts",
    "console_success_markers",
    "description",
    "notes",
}
ARTIFACT_SECTIONS = ("tables", "images", "markdown")


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
    ordered_steps = sorted(document["steps"], key=lambda item: (item["order"], item["id"]))
    normalized = {"version": PIPELINE_VERSION, "steps": ordered_steps}
    PIPELINE_STEPS_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_pipeline_step_configs() -> list[dict[str, Any]]:
    return deepcopy(load_pipeline_document()["steps"])


def load_pipeline_manifest() -> tuple[PipelineEntry, ...]:
    document = load_pipeline_document()
    entries = [_build_pipeline_entry(raw_step) for raw_step in document["steps"]]
    entries.sort(key=lambda item: (item.order, item.id))
    return tuple(entries)


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
    entries = load_pipeline_manifest()
    stage_configs = _load_stage_configs()
    steps: list[StepDefinition] = []
    for entry in entries:
        if not include_disabled and not entry.enabled:
            continue
        step_spec = load_step_spec_from_script(PROJECT_ROOT / entry.script)
        steps.append(build_step_definition(entry, step_spec, stage_configs))
    return tuple(steps)


def validate_pipeline_steps(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise PipelineConfigError("流水线配置顶层必须是对象。")
    if document.get("version") != PIPELINE_VERSION:
        raise PipelineConfigError(f"流水线配置版本必须为 {PIPELINE_VERSION}。")

    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PipelineConfigError("流水线配置 steps 必须是非空数组。")

    known_stages = set(stage_names())
    seen_ids: set[str] = set()
    enabled_count = 0

    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict):
            raise PipelineConfigError(f"第 {index + 1} 个步骤不是对象。")
        extra_keys = set(raw_step) - ALLOWED_MANIFEST_FIELDS
        forbidden_keys = FORBIDDEN_MANIFEST_FIELDS & set(raw_step)
        if forbidden_keys:
            raise PipelineConfigError(f"步骤 {raw_step.get('id', index + 1)} 在编排层包含已废弃字段：{sorted(forbidden_keys)}")
        if extra_keys:
            raise PipelineConfigError(f"步骤 {raw_step.get('id', index + 1)} 在编排层包含未知字段：{sorted(extra_keys)}")

        step_id = raw_step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise PipelineConfigError(f"第 {index + 1} 个步骤缺少有效 id。")
        if step_id in seen_ids:
            raise PipelineConfigError(f"步骤 id 重复：{step_id}")
        seen_ids.add(step_id)

        script_text = raw_step.get("script")
        if not isinstance(script_text, str) or not script_text.strip():
            raise PipelineConfigError(f"步骤 {step_id} 的 script 必须是非空字符串。")
        script_path = resolve_project_path(script_text)
        if not script_path.exists():
            raise PipelineConfigError(f"步骤 {step_id} 的 script 不存在：{script_text}")

        stage = raw_step.get("stage")
        if stage not in known_stages:
            raise PipelineConfigError(f"步骤 {step_id} 的 stage 非法：{stage}")

        enabled = raw_step.get("enabled", True)
        if not isinstance(enabled, bool):
            raise PipelineConfigError(f"步骤 {step_id} 的 enabled 必须是布尔值。")
        if enabled:
            enabled_count += 1

        order = raw_step.get("order")
        if not isinstance(order, int):
            raise PipelineConfigError(f"步骤 {step_id} 的 order 必须是整数。")

        for key in ("name_override", "description_override"):
            value = raw_step.get(key)
            if value is not None and not isinstance(value, str):
                raise PipelineConfigError(f"步骤 {step_id} 的 {key} 必须是字符串或 null。")

        load_step_spec_from_script(script_path)

    if enabled_count == 0:
        raise PipelineConfigError("至少需要保留一个启用的流水线步骤。")


def load_step_spec_from_script(script_path: Path) -> dict[str, Any]:
    if not script_path.exists():
        raise PipelineConfigError(f"脚本不存在：{script_path}")

    if script_path.suffix == ".py":
        step_spec = _load_python_step_spec(script_path)
    elif script_path.suffix == ".do":
        step_spec = _load_stata_step_spec(script_path)
    elif script_path.suffixes[-2:] == [".step", ".json"]:
        step_spec = _load_sidecar_step_spec(script_path)
    else:
        raise PipelineConfigError(f"不支持的步骤脚本类型：{script_path}")

    validate_step_spec(step_spec, script_path)
    return step_spec


def resolve_output_dir(stage: str, script_path: Path) -> Path:
    stage_config = load_stage_config(stage)
    output_root = resolve_project_path(stage_config["output_root"])
    return output_root / _derive_script_stem(script_path)


def build_step_definition(
    entry: PipelineEntry,
    step_spec: dict[str, Any],
    stage_configs: dict[str, dict[str, Any]] | None = None,
) -> StepDefinition:
    stage_configs = stage_configs or _load_stage_configs()
    script_path = resolve_project_path(entry.script)
    output_dir = resolve_output_dir(entry.stage, script_path)
    required_inputs = tuple(
        InputRequirement(
            path=resolve_project_path(resolve_pipeline_template(requirement["path"], stage_configs)),
            kind=requirement.get("kind", "file"),
            required_columns=tuple(requirement.get("required_columns", [])),
            label=requirement.get("label", ""),
        )
        for requirement in step_spec.get("required_inputs", [])
    )
    command = tuple(resolve_pipeline_template(part, stage_configs) if "{" in part else part for part in step_spec["command"])
    working_dir = resolve_project_path(resolve_pipeline_template(step_spec["working_dir"], stage_configs))

    artifacts = step_spec.get("artifacts", {})
    table_primary, table_patterns = _resolve_artifact_category(output_dir, artifacts.get("tables", {}))
    image_primary, image_patterns = _resolve_artifact_category(output_dir, artifacts.get("images", {}))
    markdown_primary, markdown_patterns = _resolve_artifact_category(output_dir, artifacts.get("markdown", {}))

    return StepDefinition(
        id=entry.id,
        script_path=script_path,
        output_dir=output_dir,
        name=entry.name_override or step_spec["name"],
        stage=entry.stage,
        runner_type=RunnerType(step_spec["runner_type"]),
        command=command,
        working_dir=working_dir,
        precheck_mode=step_spec["precheck_mode"],
        required_inputs=required_inputs,
        primary_table=table_primary,
        primary_image=image_primary,
        primary_markdown=markdown_primary,
        table_patterns=table_patterns,
        image_patterns=image_patterns,
        markdown_patterns=markdown_patterns,
        console_success_markers=tuple(step_spec.get("console_success_markers", [])),
        description=entry.description_override or step_spec.get("description", ""),
        notes=tuple(step_spec.get("notes", [])),
    )


def validate_step_spec(step_spec: dict[str, Any], script_path: Path) -> None:
    if not isinstance(step_spec, dict):
        raise PipelineConfigError(f"步骤元数据必须是对象：{script_path}")
    forbidden_keys = FORBIDDEN_STEP_SPEC_FIELDS & set(step_spec)
    if forbidden_keys:
        raise PipelineConfigError(f"步骤元数据包含已废弃字段 {sorted(forbidden_keys)}：{script_path}")
    extra_keys = set(step_spec) - ALLOWED_STEP_SPEC_FIELDS
    if extra_keys:
        raise PipelineConfigError(f"步骤元数据包含未知字段 {sorted(extra_keys)}：{script_path}")

    for key in ("name", "working_dir", "precheck_mode", "description"):
        value = step_spec.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PipelineConfigError(f"步骤元数据字段 {key} 必须是非空字符串：{script_path}")

    runner_type = step_spec.get("runner_type")
    if runner_type not in {member.value for member in RunnerType}:
        raise PipelineConfigError(f"步骤元数据 runner_type 非法：{script_path}")

    if step_spec["precheck_mode"] not in VALID_PRECHECK_MODES:
        raise PipelineConfigError(f"步骤元数据 precheck_mode 非法：{script_path}")

    command = step_spec.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part.strip() for part in command):
        raise PipelineConfigError(f"步骤元数据 command 必须是非空字符串数组：{script_path}")
    if runner_type == RunnerType.PYTHON.value and command[0] != "python":
        raise PipelineConfigError(f"python 步骤命令必须以 python 开头：{script_path}")
    if runner_type in {RunnerType.STATA.value, RunnerType.HYBRID.value} and command[0] != "stata-do":
        raise PipelineConfigError(f"stata 步骤命令必须以 stata-do 开头：{script_path}")
    if runner_type == RunnerType.MANUAL.value and command[0] != "open-path":
        raise PipelineConfigError(f"manual 步骤命令必须以 open-path 开头：{script_path}")

    required_inputs = step_spec.get("required_inputs", [])
    if not isinstance(required_inputs, list):
        raise PipelineConfigError(f"步骤元数据 required_inputs 必须是数组：{script_path}")
    stage_configs = _load_stage_configs()
    for req_index, requirement in enumerate(required_inputs):
        if not isinstance(requirement, dict):
            raise PipelineConfigError(f"required_inputs[{req_index}] 必须是对象：{script_path}")
        path_text = requirement.get("path")
        if not isinstance(path_text, str) or not path_text.strip():
            raise PipelineConfigError(f"required_inputs[{req_index}].path 缺失：{script_path}")
        kind = requirement.get("kind", "file")
        if kind not in VALID_INPUT_KINDS:
            raise PipelineConfigError(f"required_inputs[{req_index}].kind 非法：{script_path}")
        columns = requirement.get("required_columns", [])
        if not isinstance(columns, list) or not all(isinstance(column, str) for column in columns):
            raise PipelineConfigError(f"required_inputs[{req_index}].required_columns 必须是字符串数组：{script_path}")
        label = requirement.get("label", "")
        if not isinstance(label, str):
            raise PipelineConfigError(f"required_inputs[{req_index}].label 必须是字符串：{script_path}")
        resolve_pipeline_template(path_text, stage_configs)

    resolve_pipeline_template(step_spec["working_dir"], stage_configs)
    for command_part in command:
        if "{" in command_part:
            resolve_pipeline_template(command_part, stage_configs)

    console_markers = step_spec.get("console_success_markers", [])
    if not isinstance(console_markers, list) or not all(isinstance(item, str) for item in console_markers):
        raise PipelineConfigError(f"console_success_markers 必须是字符串数组：{script_path}")

    notes = step_spec.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        raise PipelineConfigError(f"notes 必须是字符串数组：{script_path}")

    artifacts = step_spec.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PipelineConfigError(f"artifacts 必须是对象：{script_path}")
    extra_sections = set(artifacts) - set(ARTIFACT_SECTIONS)
    if extra_sections:
        raise PipelineConfigError(f"artifacts 包含未知分组 {sorted(extra_sections)}：{script_path}")
    for section in ARTIFACT_SECTIONS:
        _validate_artifact_category(artifacts.get(section, {}), script_path, section)


def _load_stage_configs() -> dict[str, dict[str, Any]]:
    configs = {stage: load_stage_config(stage) for stage in stage_names()}
    efficiency_cfg = dict(configs["效率测算"])
    efficiency_cfg["dearun_result_dir"] = str(derived_dearun_result_dir(efficiency_cfg).relative_to(PROJECT_ROOT).as_posix())
    configs["效率测算"] = efficiency_cfg
    return configs


def _build_pipeline_entry(raw_step: dict[str, Any]) -> PipelineEntry:
    return PipelineEntry(
        id=raw_step["id"],
        script=raw_step["script"],
        stage=raw_step["stage"],
        enabled=raw_step["enabled"],
        order=raw_step["order"],
        name_override=raw_step.get("name_override"),
        description_override=raw_step.get("description_override"),
    )


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


def _load_python_step_spec(script_path: Path) -> dict[str, Any]:
    try:
        module = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except SyntaxError as exc:
        raise PipelineConfigError(f"脚本语法解析失败：{script_path} | {exc}") from exc

    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STEP_SPEC":
                    return _literal_eval_step_spec(node.value, script_path)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "STEP_SPEC":
            return _literal_eval_step_spec(node.value, script_path)
    raise PipelineConfigError(f"脚本缺少顶层静态 STEP_SPEC：{script_path}")


def _load_stata_step_spec(script_path: Path) -> dict[str, Any]:
    lines = script_path.read_text(encoding="utf-8").splitlines()
    begin_index = next((idx for idx, line in enumerate(lines) if DO_STEP_SPEC_BEGIN in line), -1)
    end_index = next((idx for idx, line in enumerate(lines) if DO_STEP_SPEC_END in line), -1)
    if begin_index < 0 or end_index <= begin_index:
        raise PipelineConfigError(f".do 文件缺少 STEP_SPEC 注释块：{script_path}")
    json_lines: list[str] = []
    for line in lines[begin_index + 1:end_index]:
        stripped = line.lstrip()
        if stripped.startswith("*"):
            stripped = stripped[1:]
        json_lines.append(stripped.lstrip())
    try:
        return json.loads("\n".join(json_lines))
    except json.JSONDecodeError as exc:
        raise PipelineConfigError(f".do 文件 STEP_SPEC JSON 解析失败：{script_path} | {exc}") from exc


def _load_sidecar_step_spec(script_path: Path) -> dict[str, Any]:
    try:
        return json.loads(script_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineConfigError(f"sidecar STEP_SPEC JSON 解析失败：{script_path} | {exc}") from exc


def _literal_eval_step_spec(node: ast.AST, script_path: Path) -> dict[str, Any]:
    try:
        value = ast.literal_eval(node)
    except Exception as exc:
        raise PipelineConfigError(f"STEP_SPEC 必须是顶层静态字面量：{script_path}") from exc
    if not isinstance(value, dict):
        raise PipelineConfigError(f"STEP_SPEC 必须是对象：{script_path}")
    return value


def _validate_artifact_category(category: Any, script_path: Path, section: str) -> None:
    if category in ({}, None):
        return
    if not isinstance(category, dict):
        raise PipelineConfigError(f"artifacts.{section} 必须是对象：{script_path}")
    extra_keys = set(category) - {"primary", "patterns"}
    if extra_keys:
        raise PipelineConfigError(f"artifacts.{section} 包含未知字段 {sorted(extra_keys)}：{script_path}")
    primary = category.get("primary")
    if primary is not None:
        if not isinstance(primary, str) or not primary.strip():
            raise PipelineConfigError(f"artifacts.{section}.primary 必须是字符串或 null：{script_path}")
        _validate_artifact_token(primary, script_path, f"artifacts.{section}.primary")
    patterns = category.get("patterns", [])
    if not isinstance(patterns, list) or not all(isinstance(item, str) and item.strip() for item in patterns):
        raise PipelineConfigError(f"artifacts.{section}.patterns 必须是字符串数组：{script_path}")
    for pattern in patterns:
        _validate_artifact_token(pattern, script_path, f"artifacts.{section}.patterns")


def _validate_artifact_token(token: str, script_path: Path, label: str) -> None:
    if "{" in token or "}" in token:
        raise PipelineConfigError(f"{label} 不允许包含模板占位符：{script_path}")
    normalized = token.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute():
        raise PipelineConfigError(f"{label} 不允许使用绝对路径：{script_path}")
    if any(part in {"..", "."} for part in candidate.parts):
        raise PipelineConfigError(f"{label} 不允许使用相对目录跳转：{script_path}")
    if len(candidate.parts) != 1:
        raise PipelineConfigError(f"{label} 只能写输出目录内的文件名或通配符：{script_path}")


def _resolve_artifact_category(output_dir: Path, category: dict[str, Any]) -> tuple[Path | None, tuple[str, ...]]:
    if not category:
        return None, ()
    primary_text = category.get("primary")
    primary = output_dir / primary_text if primary_text else None
    patterns = tuple(str((output_dir / pattern).as_posix()) for pattern in category.get("patterns", []))
    return primary, patterns


def _derive_script_stem(script_path: Path) -> str:
    if script_path.suffixes[-2:] == [".step", ".json"]:
        return script_path.name[: -len(".step.json")]
    return script_path.stem
