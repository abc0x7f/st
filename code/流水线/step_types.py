from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RunnerType(str, Enum):
    PYTHON = "python"
    STATA = "stata"
    MANUAL = "manual"
    HYBRID = "hybrid"


class StepStatus(str, Enum):
    IDLE = "idle"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_PENDING = "manual_pending"


@dataclass(frozen=True)
class InputRequirement:
    path: Path
    kind: str = "file"
    required_columns: tuple[str, ...] = ()
    label: str = ""


@dataclass(frozen=True)
class StepDefinition:
    id: str
    name: str
    stage: str
    runner_type: RunnerType
    command: tuple[str, ...]
    working_dir: Path
    precheck_mode: str
    required_inputs: tuple[InputRequirement, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    primary_csv: Path | None = None
    image_globs: tuple[str, ...] = ()
    markdown_globs: tuple[str, ...] = ()
    console_success_markers: tuple[str, ...] = ()
    description: str = ""
    notes: tuple[str, ...] = ()


@dataclass
class CheckResult:
    success: bool
    messages: list[str]


@dataclass
class ArtifactBundle:
    csv_files: list[Path] = field(default_factory=list)
    image_files: list[Path] = field(default_factory=list)
    markdown_files: list[Path] = field(default_factory=list)


@dataclass
class RunPreparation:
    allowed: bool
    status: StepStatus
    program: str | None = None
    arguments: list[str] = field(default_factory=list)
    working_dir: Path | None = None
    message: str = ""
