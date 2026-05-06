from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from pipeline_config import PROJECT_ROOT, PYTHON_EXE, STEP_BY_ID, STEP_DEFINITIONS
from step_types import ArtifactBundle, CheckResult, RunPreparation, RunnerType, StepDefinition, StepStatus


STATA_CANDIDATES = (
    Path(r"C:\Program Files\StataNow19\StataMP-64.exe"),
    Path(r"C:\Program Files\Stata18\StataMP-64.exe"),
    Path(r"C:\Program Files\Stata17\StataMP-64.exe"),
    Path(r"C:\Program Files\StataNow19\StataSE-64.exe"),
)


def list_steps() -> tuple[StepDefinition, ...]:
    return STEP_DEFINITIONS


def get_step(step_id: str) -> StepDefinition:
    return STEP_BY_ID[step_id]


def resolve_stata_executable() -> Path | None:
    for candidate in STATA_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _glob_paths(patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        for match in PROJECT_ROOT.glob(pattern):
            if match.exists():
                paths.append(match)
    unique = sorted(set(paths), key=lambda path: (path.suffix.lower(), -path.stat().st_mtime, str(path)))
    return unique


def _expand_image_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for pattern in patterns:
        expanded.append(pattern)
        if pattern.endswith(".png"):
            expanded.append(pattern[:-4] + ".svg")
        elif pattern.endswith(".jpg"):
            expanded.append(pattern[:-4] + ".svg")
        elif pattern.endswith(".jpeg"):
            expanded.append(pattern[:-5] + ".svg")
        elif pattern.endswith(".bmp"):
            expanded.append(pattern[:-4] + ".svg")
    return tuple(dict.fromkeys(expanded))


def _describe_path(path: Path, label: str = "") -> str:
    return label or str(path.relative_to(PROJECT_ROOT))


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
        matched_outputs = _glob_paths(step.expected_outputs)
        if matched_outputs:
            messages.append("[通过] 已发现人工步骤产物。")
        else:
            messages.append("[待处理] 尚未发现 Dearun 回填结果，请手动完成后再检查。")

    missing_or_failed = [line for line in messages if line.startswith("[缺失]") or line.startswith("[失败]")]
    waiting = [line for line in messages if line.startswith("[待处理]")]
    success = not missing_or_failed and not waiting
    return CheckResult(success=success, messages=messages)


def discover_artifacts(step_id: str) -> ArtifactBundle:
    step = get_step(step_id)
    csv_candidates: list[Path] = []
    if step.primary_csv and step.primary_csv.exists():
        csv_candidates.append(step.primary_csv)

    expected = _glob_paths(step.expected_outputs)
    image_paths = [path for path in expected if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".svg"}]
    markdown_paths = [path for path in expected if path.suffix.lower() == ".md"]
    csv_paths = [path for path in expected if path.suffix.lower() == ".csv"]

    if step.image_globs:
        image_paths.extend(_glob_paths(_expand_image_patterns(step.image_globs)))
    if step.markdown_globs:
        markdown_paths.extend(_glob_paths(step.markdown_globs))

    csv_candidates.extend(csv_paths)
    csv_unique = _dedupe_paths(csv_candidates, primary=step.primary_csv)
    image_unique = _dedupe_paths(image_paths, prefer_svg=True)
    markdown_unique = _dedupe_paths(markdown_paths)
    return ArtifactBundle(csv_files=csv_unique, image_files=image_unique, markdown_files=markdown_unique)


def _dedupe_paths(paths: list[Path], primary: Path | None = None, prefer_svg: bool = False) -> list[Path]:
    existing = [path for path in paths if path.exists() and path.is_file()]
    unique = list({path.resolve(): path for path in existing}.values())
    unique.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    if primary and primary.exists():
        resolved_primary = primary.resolve()
        unique.sort(key=lambda path: (0 if path.resolve() == resolved_primary else 1, -path.stat().st_mtime))
    if prefer_svg:
        preferred_by_stem: dict[str, Path] = {}
        for path in unique:
            key = str(path.with_suffix("")).lower()
            current = preferred_by_stem.get(key)
            if current is None:
                preferred_by_stem[key] = path
                continue
            if current.suffix.lower() != ".svg" and path.suffix.lower() == ".svg":
                preferred_by_stem[key] = path
        unique = list(preferred_by_stem.values())
        unique.sort(key=lambda path: (path.stem.lower(), -path.stat().st_mtime))
    return unique


def load_primary_table(step_id: str, index: int = 0) -> pd.DataFrame | None:
    artifacts = discover_artifacts(step_id)
    if not artifacts.csv_files:
        return None
    try:
        return pd.read_csv(artifacts.csv_files[index], encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(artifacts.csv_files[index])


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
            "## 预计输出",
        ]
    )
    if not step.expected_outputs:
        lines.append("- 暂无显式输出模式。")
    else:
        for pattern in step.expected_outputs:
            lines.append(f"- `{pattern}`")

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
        return RunPreparation(
            allowed=True,
            status=StepStatus.RUNNING,
            program=str(stata_exe),
            arguments=["/e", "do", str(script_path)],
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


def executable_summary() -> str:
    stata_exe = resolve_stata_executable()
    stata_text = str(stata_exe) if stata_exe else "未找到"
    return f"Python: {sys.executable}\nStata: {stata_text}"


def open_external_path(path_text: str) -> None:
    os.startfile(path_text)
