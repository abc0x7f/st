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


class OutputState(str, Enum):
    MISSING = "missing"
    STALE = "stale"
    FRESH = "fresh"


@dataclass(frozen=True)
class InputRequirement:
    path: Path
    kind: str = "file"
    required_columns: tuple[str, ...] = ()
    label: str = ""


@dataclass(frozen=True)
class PipelineEntry:
    id: str
    script: str
    stage: str
    enabled: bool
    order: int
    name_override: str | None = None
    description_override: str | None = None


@dataclass(frozen=True)
class StepDefinition:
    id: str
    script_path: Path
    output_dir: Path
    name: str
    stage: str
    runner_type: RunnerType
    command: tuple[str, ...]
    working_dir: Path
    precheck_mode: str
    required_inputs: tuple[InputRequirement, ...] = ()
    primary_table: Path | None = None
    primary_image: Path | None = None
    primary_markdown: Path | None = None
    table_patterns: tuple[str, ...] = ()
    image_patterns: tuple[str, ...] = ()
    markdown_patterns: tuple[str, ...] = ()
    console_success_markers: tuple[str, ...] = ()
    description: str = ""
    notes: tuple[str, ...] = ()


@dataclass
class CheckResult:
    success: bool
    messages: list[str]


@dataclass
class ArtifactBundle:
    table_files: list[Path] = field(default_factory=list)
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


@dataclass(frozen=True)
class OutputHealth:
    state: OutputState
    text: str
