from __future__ import annotations

import glob
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from pipeline_config import PROJECT_ROOT, PYTHON_EXE, build_step_definitions, build_step_map
from stage_config import derived_dearun_result_dir, list_stage_config_names, load_stage_config, resolve_project_path
from step_types import ArtifactBundle, CheckResult, OutputHealth, OutputState, RunPreparation, RunnerType, StepDefinition, StepStatus


STATA_CANDIDATES = (
    Path(r"C:\Program Files\StataNow19\StataMP-64.exe"),
    Path(r"C:\Program Files\Stata18\StataMP-64.exe"),
    Path(r"C:\Program Files\Stata17\StataMP-64.exe"),
    Path(r"C:\Program Files\StataNow19\StataSE-64.exe"),
)

POWERSHELL_CANDIDATES = (
    Path(r"C:\Scoop\shims\pwsh.exe"),
    Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
    Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
)


def list_steps() -> tuple[StepDefinition, ...]:
    return build_step_definitions()


def get_step(step_id: str) -> StepDefinition:
    return build_step_map()[step_id]


def available_stage_configs(stage: str) -> list[str]:
    return list_stage_config_names(stage)


def resolve_stata_executable() -> Path | None:
    for candidate in STATA_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def resolve_powershell_executable() -> Path | None:
    for command in ("pwsh", "powershell"):
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)
    for candidate in POWERSHELL_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _powershell_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _stata_start_process_command(stata_exe: Path, script_path: Path, config_path: Path) -> str:
    argument_list = ", ".join(_powershell_quote(arg) for arg in ("/b", "do", script_path, config_path))
    return (
        "$ErrorActionPreference = 'Stop'; "
        f"$p = Start-Process -FilePath {_powershell_quote(stata_exe)} "
        f"-ArgumentList @({argument_list}) -WindowStyle Hidden -Wait -PassThru; "
        "if ($null -ne $p.ExitCode) { exit $p.ExitCode } else { exit 0 }"
    )


def _glob_paths(patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        for match_text in glob.glob(pattern):
            match = Path(match_text)
            if match.exists():
                paths.append(match)
    unique = sorted(set(paths), key=lambda path: (path.suffix.lower(), -path.stat().st_mtime, str(path)))
    return unique


def _describe_path(path: Path, label: str = "") -> str:
    return label or str(path.relative_to(PROJECT_ROOT))


def _describe_pattern(pattern: str) -> str:
    try:
        return str(Path(pattern).relative_to(PROJECT_ROOT))
    except ValueError:
        return pattern


def _check_requirement(requirement) -> list[str]:
    messages: list[str] = []
    path = requirement.path
    label = _describe_path(path, requirement.label)

    if requirement.kind == "directory":
        if not path.exists() or not path.is_dir():
            messages.append(f"[缺失] 目录不存在: {label}")
        else:
            messages.append(f"[通过] 目录存在: {label}")
        return messages

    if not path.exists():
        messages.append(f"[缺失] 文件不存在: {label}")
        return messages

    messages.append(f"[通过] 文件存在: {label}")
    if requirement.kind == "csv" and requirement.required_columns:
        try:
            columns = list(pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns)
        except Exception as exc:
            messages.append(f"[失败] 无法读取 CSV 头部: {label} | {exc}")
            return messages
        missing = [column for column in requirement.required_columns if column not in columns]
        if missing:
            messages.append(f"[缺失] CSV 字段不足: {label} | 缺少 {missing}")
        else:
            messages.append(f"[通过] CSV 字段齐全: {label}")
    return messages


def check_step(step_id: str) -> CheckResult:
    step = get_step(step_id)
    messages = [f"步骤：{step.stage} / {step.name}"]

    for requirement in step.required_inputs:
        messages.extend(_check_requirement(requirement))

    if step.precheck_mode == "manual_result":
        artifacts = discover_artifacts(step.id)
        matched_outputs = [*artifacts.table_files, *artifacts.image_files, *artifacts.markdown_files]
        if matched_outputs:
            messages.append("[通过] 已发现人工步骤产物。")
        else:
            if step.id == "dearun_manual":
                eff_cfg = load_stage_config("效率测算")
                result_dir = derived_dearun_result_dir(eff_cfg)
                messages.append(f"[待处理] 尚未发现 Dearun 回填结果，请检查目录: {result_dir.relative_to(PROJECT_ROOT)}")
            else:
                messages.append("[待处理] 尚未发现人工步骤产物，请手动完成后再检查。")

    missing_or_failed = [line for line in messages if line.startswith("[缺失]") or line.startswith("[失败]")]
    waiting = [line for line in messages if line.startswith("[待处理]")]
    success = not missing_or_failed and not waiting
    return CheckResult(success=success, messages=messages)


def discover_artifacts(step_id: str) -> ArtifactBundle:
    step = get_step(step_id)
    table_candidates: list[Path] = []
    if step.primary_table and step.primary_table.exists():
        table_candidates.append(step.primary_table)
    image_candidates: list[Path] = []
    if step.primary_image and step.primary_image.exists():
        image_candidates.append(step.primary_image)
    markdown_candidates: list[Path] = []
    if step.primary_markdown and step.primary_markdown.exists():
        markdown_candidates.append(step.primary_markdown)

    table_candidates.extend(_glob_paths(step.table_patterns))
    image_candidates.extend(_glob_paths(step.image_patterns))
    markdown_candidates.extend(_glob_paths(step.markdown_patterns))

    table_unique = _dedupe_paths(table_candidates, primary=step.primary_table)
    image_unique = _dedupe_paths(image_candidates, primary=step.primary_image)
    markdown_unique = _dedupe_paths(markdown_candidates, primary=step.primary_markdown)
    if step.id == "dearun_manual" and not table_unique:
        eff_cfg = load_stage_config("效率测算")
        result_dir = derived_dearun_result_dir(eff_cfg)
        table_unique = _dedupe_paths([path for path in result_dir.rglob("*.xlsx") if path.exists()])
    return ArtifactBundle(table_files=table_unique, image_files=image_unique, markdown_files=markdown_unique)


def _dedupe_paths(paths: list[Path], primary: Path | None = None) -> list[Path]:
    existing = [path for path in paths if path.exists() and path.is_file()]
    unique = list({path.resolve(): path for path in existing}.values())
    unique.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    if primary and primary.exists():
        resolved_primary = primary.resolve()
        unique.sort(key=lambda path: (0 if path.resolve() == resolved_primary else 1, -path.stat().st_mtime))
    return unique


def load_primary_table(step_id: str, index: int = 0) -> pd.DataFrame | None:
    artifacts = discover_artifacts(step_id)
    if not artifacts.table_files:
        return None
    table_path = artifacts.table_files[index]
    try:
        if table_path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(table_path)
        return pd.read_csv(table_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(table_path)


def load_markdown(step_id: str, latest_status: StepStatus = StepStatus.IDLE) -> str:
    step = get_step(step_id)
    artifacts = discover_artifacts(step_id)
    if artifacts.markdown_files:
        return artifacts.markdown_files[0].read_text(encoding="utf-8")

    lines = [
        f"# {step.name}",
        "",
        f"- 阶段：{step.stage}",
        f"- 执行类型：{step.runner_type.value}",
        f"- 当前状态：{latest_status.value}",
        "",
        "## 输入要求",
    ]
    if not step.required_inputs:
        lines.append("- 无显式前置输入检查。")
    else:
        for requirement in step.required_inputs:
            lines.append(f"- `{requirement.path.relative_to(PROJECT_ROOT)}`")

    lines.extend(
        [
            "",
            "## 输出目录",
        ]
    )
    lines.append(f"- `{step.output_dir.relative_to(PROJECT_ROOT)}`")

    lines.extend(["", "## 产物模式"])
    if step.primary_table:
        lines.append(f"- 主表：`{step.primary_table.relative_to(PROJECT_ROOT)}`")
    if step.primary_image:
        lines.append(f"- 主图：`{step.primary_image.relative_to(PROJECT_ROOT)}`")
    if step.primary_markdown:
        lines.append(f"- 主文档：`{step.primary_markdown.relative_to(PROJECT_ROOT)}`")
    for label, patterns in (("表格", step.table_patterns), ("图片", step.image_patterns), ("Markdown", step.markdown_patterns)):
        if patterns:
            for pattern in patterns:
                lines.append(f"- {label}：`{_describe_pattern(pattern)}`")

    if step.notes:
        lines.extend(["", "## 说明"])
        for note in step.notes:
            lines.append(f"- {note}")

    if step.description:
        lines.extend(["", "## 摘要", step.description])
    return "\n".join(lines)


def run_step(step_id: str) -> RunPreparation:
    step = get_step(step_id)
    if step.runner_type == RunnerType.MANUAL:
        if step.command and step.command[0] == "open-path":
            target_path = Path(step.command[1])
            if target_path.exists():
                return RunPreparation(
                    allowed=True,
                    status=StepStatus.MANUAL_PENDING,
                    program="__shell_open__",
                    arguments=[str(target_path)],
                    working_dir=step.working_dir,
                    message=f"已准备打开 Dearun 路径：{target_path}",
                )
            message = f"未找到 Dearun 路径：{target_path}"
            return RunPreparation(allowed=False, status=StepStatus.MANUAL_PENDING, message=message)
        message = "该步骤需在外部软件中手动完成，完成后请点击“检查”回收结果。"
        return RunPreparation(allowed=False, status=StepStatus.MANUAL_PENDING, message=message)

    if step.precheck_mode != "none":
        check = check_step(step_id)
        if not check.success:
            return RunPreparation(
                allowed=False,
                status=StepStatus.BLOCKED,
                message="前置检查未通过，请先修复缺失输入或完成人工步骤。",
            )

    if step.command and step.command[0] == "python":
        script_path = PROJECT_ROOT / step.command[1]
        return RunPreparation(
            allowed=True,
            status=StepStatus.RUNNING,
            program=str(PYTHON_EXE),
            arguments=[str(script_path)],
            working_dir=step.working_dir,
            message=f"启动 Python 脚本：{script_path.relative_to(PROJECT_ROOT)}",
        )

    if step.command and step.command[0] == "stata-do":
        script_path = PROJECT_ROOT / step.command[1]
        stata_exe = resolve_stata_executable()
        if stata_exe is None:
            command_text = f'do "{script_path}"'
            return RunPreparation(
                allowed=False,
                status=StepStatus.MANUAL_PENDING,
                message=f"未找到 Stata 可执行文件。请手动运行：{command_text}",
            )
        powershell_exe = resolve_powershell_executable()
        if powershell_exe is None:
            return RunPreparation(
                allowed=False,
                status=StepStatus.FAILED,
                message="未找到 PowerShell，无法以非批处理方式启动 Stata。",
            )
        stata_config = _write_stata_config(step.id)
        return RunPreparation(
            allowed=True,
            status=StepStatus.RUNNING,
            program=str(powershell_exe),
            arguments=[
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                _stata_start_process_command(stata_exe, script_path, stata_config),
            ],
            working_dir=step.working_dir,
            message=f"启动 Stata 脚本：{script_path.relative_to(PROJECT_ROOT)}",
        )

    return RunPreparation(
        allowed=False,
        status=StepStatus.FAILED,
        message="未识别的执行配置。",
    )


def detect_status(step_id: str) -> StepStatus:
    step = get_step(step_id)
    if step.runner_type == RunnerType.MANUAL:
        return StepStatus.SUCCESS if check_step(step_id).success else StepStatus.MANUAL_PENDING
    if step.precheck_mode == "none":
        return StepStatus.IDLE
    return StepStatus.READY if check_step(step_id).success else StepStatus.BLOCKED


def detect_output_health(step_id: str) -> OutputHealth:
    step = get_step(step_id)
    artifacts = discover_artifacts(step_id)
    artifact_paths = [*artifacts.table_files, *artifacts.image_files, *artifacts.markdown_files]
    if not artifact_paths:
        return OutputHealth(OutputState.MISSING, "● 输出为空")

    source_paths: list[Path] = []
    if step.script_path.exists():
        source_paths.append(step.script_path)

    existing_sources = [path for path in source_paths if path.exists()]
    if not existing_sources:
        return OutputHealth(OutputState.FRESH, "● 输出匹配")

    latest_source_mtime = max(path.stat().st_mtime for path in existing_sources)
    oldest_output_mtime = min(path.stat().st_mtime for path in artifact_paths if path.exists())
    if oldest_output_mtime < latest_source_mtime:
        return OutputHealth(OutputState.STALE, "● 输出不匹配")
    return OutputHealth(OutputState.FRESH, "● 输出匹配")


def executable_summary() -> str:
    stata_exe = resolve_stata_executable()
    stata_text = str(stata_exe) if stata_exe else "未找到"
    return f"Python: {sys.executable}\nStata: {stata_text}"


def open_external_path(path_text: str) -> None:
    os.startfile(path_text)


def _write_stata_config(step_id: str) -> Path:
    spatial_cfg = load_stage_config("空间分析")
    step = get_step(step_id)
    out_dir = step.output_dir
    stata_dir = out_dir / "stata"

    lines = [
        f'global PROJECT_ROOT "{PROJECT_ROOT.as_posix()}"',
        f'global DATA_FILE "{resolve_project_path(spatial_cfg["second_stage_panel"]).as_posix()}"',
        f'global W_ADJ_FILE "{resolve_project_path(spatial_cfg["adjacency_matrix"]).as_posix()}"',
        f'global W_ECO_FILE "{resolve_project_path(spatial_cfg["economic_matrix"]).as_posix()}"',
        f'global W_GEO_INV_FILE "{resolve_project_path(spatial_cfg["geo_inverse_matrix"]).as_posix()}"',
        f'global W_ECO_GEO_NEST_FILE "{resolve_project_path(spatial_cfg["economic_geo_nested_matrix"]).as_posix()}"',
        f'global OUT_DIR "{out_dir.as_posix()}"',
        f'global STATA_DIR "{stata_dir.as_posix()}"',
    ]
    tmp_dir = Path(tempfile.gettempdir())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    config_path = tmp_dir / f"{step_id}_stage_config.do"
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path
