"""Dataset provenance, data-version manifests and pipeline run records.

Three separate records exist (none of them is the software CHANGELOG):

* dataset metadata  - config/datasets.yaml (publication / retrieval dates, source, ...)
* data manifests    - data/manifests/<mode>_datasets.json: checksums of the exact input files,
                      written on request with ``--record-manifest``
* run records       - logs/runs/<run_id>.json: what one pipeline execution read and wrote
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bess_catalonia import __version__
from bess_catalonia.config import Config, DatasetSpec
from bess_catalonia.io import write_text

PROVENANCE_FIELDS = (
    "dataset_id", "dataset_name", "provider", "source_url", "publication_date",
    "retrieval_date", "observation_period", "version", "format", "source_crs",
    "spatial_resolution", "temporal_resolution", "units", "file_path", "checksum", "owner",
    "processing_method", "known_limitations", "verification_status",
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def code_fingerprint() -> str:
    """Hash of the package source, so that code changes invalidate cached stage outputs."""
    pkg = Path(__file__).parent
    h = hashlib.sha256(__version__.encode())
    for py in sorted(pkg.rglob("*.py")):
        h.update(py.relative_to(pkg).as_posix().encode())
        h.update(py.read_bytes())
    return h.hexdigest()[:16]


def dataset_record(spec: DatasetSpec, root: Path, with_checksum: bool = True) -> dict[str, Any]:
    """Provenance record for one dataset, combining config metadata and file facts."""
    meta = spec.metadata
    rec: dict[str, Any] = {k: meta.get(k) for k in PROVENANCE_FIELDS}
    rec.update(
        dataset_id=meta.get("dataset_id") or spec.key,
        format=spec.format,
        source_crs=spec.source_crs,
        units=spec.units or None,
        owner=spec.owner,
        layer=spec.layer,
        file_path=(spec.path.relative_to(root).as_posix() if spec.path else None),
        available=spec.available,
    )
    if spec.available and with_checksum:
        rec["checksum"] = "sha256:" + sha256_file(spec.path)
        rec["size_bytes"] = spec.path.stat().st_size
    return rec


def manifest_path(cfg: Config, mode: str) -> Path:
    return cfg.manifests_dir / f"{mode}_datasets.json"


def write_manifest(cfg: Config, mode: str) -> Path:
    """Record the exact versions (checksums) of all available input files for a mode."""
    records = {k: dataset_record(cfg.dataset(mode, k), cfg.root) for k in cfg.dataset_keys(mode)}
    payload = {"mode": mode, "recorded_at": now_iso(), "datasets": records}
    path = manifest_path(cfg, mode)
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))
    return path


def compare_manifest(cfg: Config, mode: str) -> list[str]:
    """Differences between the current input files and the recorded manifest."""
    path = manifest_path(cfg, mode)
    if not path.exists():
        return [f"No data manifest recorded yet ({path.relative_to(cfg.root)}); "
                f"run --mode {mode} --record-manifest after adding datasets"]
    recorded = json.loads(path.read_text(encoding="utf-8"))["datasets"]
    notes = []
    for key in cfg.dataset_keys(mode):
        spec = cfg.dataset(mode, key)
        old = recorded.get(key, {}).get("checksum")
        new = ("sha256:" + sha256_file(spec.path)) if spec.available else None
        if old != new:
            notes.append(f"{key}: input file changed since manifest "
                         f"({(old or 'none')[:19]} -> {(new or 'none')[:19]})")
    return notes


@dataclass
class StageRecord:
    stage: str
    status: str  # ran | up_to_date | skipped | failed | blocked | planned
    reason: str = ""
    outputs: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunRecord:
    run_id: str
    mode: str
    stages: list[str]
    start_time: str = field(default_factory=now_iso)
    end_time: str | None = None
    package_version: str = __version__
    dry_run: bool = False
    input_versions: dict[str, Any] = field(default_factory=dict)
    input_checksums: dict[str, str] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)
    stage_results: list[StageRecord] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "running"

    def add_input(self, spec: DatasetSpec, root: Path) -> None:
        if spec.key in self.input_checksums or not spec.available:
            return
        rec = dataset_record(spec, root)
        self.input_checksums[spec.key] = rec["checksum"]
        self.input_versions[spec.key] = {
            k: rec.get(k) for k in ("file_path", "version", "publication_date",
                                    "retrieval_date", "verification_status")
        }

    def finish(self, status: str) -> None:
        self.status = status
        self.end_time = now_iso()

    def write(self, logs_dir: Path) -> Path:
        path = logs_dir / "runs" / f"{self.run_id}.json"
        write_text(path, json.dumps(asdict(self), indent=2, default=str, ensure_ascii=False))
        return path
