"""Local, content-addressed working copies for vcfr repositories."""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

STATE_DIR = ".vcfr"
SCHEMA_VERSION = 1


class WorkspaceError(RuntimeError):
    """A user-correctable repository or configuration error."""


def config_home() -> Path:
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "vcfr"


def find_workspace(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / STATE_DIR / "repository.json").is_file():
            return directory
    raise WorkspaceError("This folder is not a vcfr repository. Run 'vcfr init' or 'vcfr clone'.")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"Could not read {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    # Atomic replacement prevents interrupted writes from corrupting repository state.
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise WorkspaceError(f"Invalid SHA-256 digest in repository metadata: {value!r}")


def validate_commit(commit: dict[str, Any]) -> dict[str, Any]:
    commit_id = commit.get("commit_id", "")
    validate_digest(commit_id)
    payload = {key: value for key, value in commit.items() if key != "commit_id"}
    calculated = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if calculated != commit_id:
        raise WorkspaceError(f"Commit manifest checksum mismatch: {commit_id}")
    files = commit.get("files")
    if not isinstance(files, dict):
        raise WorkspaceError(f"Commit manifest has no valid file table: {commit_id}")
    for path, item in files.items():
        safe_relative_path(path)
        if not isinstance(item, dict):
            raise WorkspaceError(f"Invalid file metadata for {path!r} in commit {commit_id}")
        validate_digest(item.get("sha256", ""))
        if not isinstance(item.get("size_bytes"), int) or item["size_bytes"] < 0:
            raise WorkspaceError(f"Invalid file size for {path!r} in commit {commit_id}")
    return commit


def safe_relative_path(path: str) -> PurePosixPath:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise WorkspaceError(f"Unsafe repository path: {path!r}")
    if "\\" in path or "\x00" in path:
        raise WorkspaceError(f"Unsafe repository path: {path!r}")
    return candidate


def safe_target_path(root: Path, relative: str) -> Path:
    """Resolve a repository path without allowing symlinks to escape its root."""
    parts = safe_relative_path(relative).parts
    root_resolved = root.resolve()
    target = root.joinpath(*parts)
    parent_resolved = target.parent.resolve()
    try:
        parent_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise WorkspaceError(f"Repository path escapes through a symlink: {relative!r}") from exc
    if target.is_symlink():
        raise WorkspaceError(f"Refusing to overwrite a symbolic link: {relative!r}")
    return target


def local_config_path(workspace: Path | None = None) -> Path:
    return (workspace or find_workspace()) / STATE_DIR / "config.ini"


def load_config(workspace: Path | None = None) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    global_file = config_home() / "config.ini"
    local_file = local_config_path(workspace) if workspace else None
    for path in (global_file, local_file):
        if path and path.is_file():
            config.read(path, encoding="utf-8")
    return config


def save_config_value(key: str, value: str, *, global_scope: bool = False) -> None:
    if "." not in key:
        raise WorkspaceError("Config keys use section.name form, for example user.email.")
    section, name = key.split(".", 1)
    path = config_home() / "config.ini" if global_scope else local_config_path()
    config = configparser.ConfigParser(interpolation=None)
    if path.exists():
        config.read(path, encoding="utf-8")
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, name, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"[{s}]\n" + "".join(f"{k} = {v}\n" for k, v in config.items(s, raw=True)) + "\n" for s in config.sections()), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def config_value(config: configparser.ConfigParser, key: str, default: str = "") -> str:
    if "." not in key:
        return default
    section, name = key.split(".", 1)
    return config.get(section, name, fallback=default)


def repository_state(root: Path) -> Path:
    return root / STATE_DIR


def read_head(root: Path) -> str | None:
    head_path = repository_state(root) / "HEAD"
    if not head_path.exists():
        return None
    value = head_path.read_text(encoding="utf-8").strip() or None
    if value:
        validate_digest(value)
    return value


def commit_path(root: Path, commit_id: str) -> Path:
    validate_digest(commit_id)
    return repository_state(root) / "commits" / f"{commit_id}.json"


def make_commit(*, parent: str | None, files: dict[str, dict[str, Any]], name: str, email: str, message: str) -> dict[str, Any]:
    ordered = {
        key: {"sha256": files[key]["sha256"], "size_bytes": files[key]["size_bytes"]}
        for key in sorted(files)
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "parent": parent,
        "author": {"name": name, "email": email},
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": ordered,
        "summary": summarize_files(ordered),
    }
    commit_id = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"commit_id": commit_id, **payload}


def summarize_files(files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for path, item in sorted(files.items()):
        lower_path = path.casefold()
        if lower_path.endswith(".vcf.gz"):
            suffix = "vcf.gz"
        elif lower_path.endswith(".vcf.bgz"):
            suffix = "vcf.bgz"
        else:
            suffix = Path(path).suffix.lower().lstrip(".") or "unknown"
        rows.append({"path": path, "size_bytes": item["size_bytes"], "sha256": item["sha256"], "format": suffix})
    return {
        "schema_version": SCHEMA_VERSION,
        "file_count": len(rows),
        "total_bytes": sum(row["size_bytes"] for row in rows),
        "files": rows,
    }


def create_local_repository(root: Path, *, name: str, remote: str = "") -> None:
    state = repository_state(root)
    if state.exists():
        raise WorkspaceError(f"A vcfr repository already exists at {root}.")
    state.mkdir(parents=True)
    config = configparser.ConfigParser(interpolation=None)
    config["core"] = {"name": name, "schema_version": str(SCHEMA_VERSION)}
    if remote:
        config["remote \"origin\""] = {"url": remote}
    with (state / "config.ini").open("w", encoding="utf-8") as stream:
        config.write(stream)
    write_json(state / "repository.json", {"schema_version": SCHEMA_VERSION, "name": name, "remote": remote})
    write_json(state / "index.json", {"files": {}})
    commit = make_commit(parent=None, files={}, name="", email="", message="Initialize repository")
    write_json(commit_path(root, commit["commit_id"]), commit)
    (state / "HEAD").write_text(commit["commit_id"] + "\n", encoding="utf-8")
    (state / "REMOTE_HEAD").write_text(commit["commit_id"] + "\n", encoding="utf-8")
    (state / "objects").mkdir()


def index_files(root: Path) -> dict[str, dict[str, Any]]:
    index = read_json(repository_state(root) / "index.json", {"files": {}})
    return index.get("files", {})


def normalized_files(files: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {path: {"sha256": item["sha256"], "size_bytes": item["size_bytes"]} for path, item in sorted(files.items())}


def current_commit(root: Path) -> dict[str, Any]:
    commit_id = read_head(root)
    if not commit_id:
        raise WorkspaceError("Repository HEAD is missing; run 'vcfr init' again in a clean folder.")
    commit = read_json(commit_path(root, commit_id))
    if not commit:
        raise WorkspaceError(f"Local commit {commit_id} is missing.")
    return validate_commit(commit)


def stage_file(root: Path, source: Path) -> str:
    absolute = source.resolve()
    try:
        relative = absolute.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise WorkspaceError(f"Files must be inside the repository: {source}") from exc
    safe_relative_path(relative)
    if not absolute.is_file() or absolute.is_symlink():
        raise WorkspaceError(f"Not a regular file: {source}")
    digest = sha256_file(absolute)
    size = absolute.stat().st_size
    object_path = repository_state(root) / "objects" / digest[:2] / digest[2:]
    object_path.parent.mkdir(parents=True, exist_ok=True)
    if not object_path.exists():
        shutil.copyfile(absolute, object_path)
        if sha256_file(object_path) != digest:
            object_path.unlink(missing_ok=True)
            raise WorkspaceError(f"{source} changed while it was being staged; run 'vcfr add' again.")
    files = index_files(root)
    files[relative] = {"sha256": digest, "size_bytes": size, "mtime_ns": absolute.stat().st_mtime_ns}
    write_json(repository_state(root) / "index.json", {"files": files})
    return relative


def stage_remove(root: Path, relative: str) -> None:
    path = safe_relative_path(relative).as_posix()
    files = index_files(root)
    if path not in files:
        raise WorkspaceError(f"Path is not tracked: {path}")
    del files[path]
    write_json(repository_state(root) / "index.json", {"files": files})


def working_tree_changes(root: Path) -> list[tuple[str, str]]:
    committed = current_commit(root).get("files", {})
    staged = index_files(root)
    summary_only = (repository_state(root) / "SUMMARY_ONLY").exists()
    changes: list[tuple[str, str]] = []
    for path in sorted(set(committed) | set(staged)):
        if path not in staged:
            changes.append(("staged deletion", path))
        elif path not in committed:
            changes.append(("staged addition", path))
        elif staged[path]["sha256"] != committed[path]["sha256"]:
            changes.append(("staged modification", path))
        source = safe_target_path(root, path)
        if path in staged and source.exists():
            stat = source.stat()
            changed_stat = stat.st_size != staged[path]["size_bytes"] or (
                staged[path].get("mtime_ns") is not None and stat.st_mtime_ns != staged[path]["mtime_ns"]
            )
            if changed_stat and sha256_file(source) != staged[path]["sha256"]:
                changes.append(("unstaged modification", path))
        elif path in staged and path in committed and not summary_only:
            changes.append(("unstaged deletion", path))
    return changes
