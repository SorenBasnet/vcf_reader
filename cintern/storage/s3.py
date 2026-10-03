"""Private S3 object storage for vcfr's content-addressed repositories."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.config import Config as BotocoreConfig
    from botocore.exceptions import ClientError
except ImportError as exc:  # pragma: no cover - depends on optional install
    raise RuntimeError("S3 support requires boto3. Install this project with `python -m pip install -e .`.") from exc

from cintern.workspace import (
    WorkspaceError,
    commit_path,
    current_commit,
    make_commit,
    read_json,
    read_head,
    repository_state,
    safe_target_path,
    safe_relative_path,
    validate_commit,
    validate_digest,
    write_json,
)

REPOSITORY_SCHEMA = 1
DEFAULT_PART_SIZE_MIB = 32


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    bucket = parsed.netloc
    prefix_parts = [part for part in parsed.path.split("/") if part]
    if any(part in {".", ".."} for part in prefix_parts) or "\\" in parsed.path:
        raise WorkspaceError("S3 repository prefixes cannot contain relative path components.")
    prefix = "/".join(prefix_parts)
    if parsed.scheme != "s3" or not bucket or parsed.query or parsed.fragment:
        raise WorkspaceError("S3 remotes must look like s3://bucket/repository-prefix.")
    return bucket, prefix


def s3_uri(bucket: str, prefix: str = "") -> str:
    suffix = prefix.strip("/")
    return f"s3://{bucket}/{suffix}" if suffix else f"s3://{bucket}"


def s3_client(*, profile: str | None = None, region: str | None = None, jobs: int = 4):
    """Use the standard AWS credential chain; never load keys from vcfr config."""
    session = boto3.Session(profile_name=profile or None, region_name=region or None)
    return session.client(
        "s3",
        config=BotocoreConfig(
            retries={"max_attempts": 8, "mode": "adaptive"},
            max_pool_connections=max(10, jobs * 4),
        ),
    )


def transfer_config(*, jobs: int = 4, part_size_mib: int = DEFAULT_PART_SIZE_MIB) -> TransferConfig:
    if jobs < 1 or jobs > 16:
        raise WorkspaceError("--jobs must be between 1 and 16 to keep transfer concurrency controlled.")
    if part_size_mib < 8 or part_size_mib > 512:
        raise WorkspaceError("--part-size-mib must be between 8 and 512.")
    return TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=part_size_mib * 1024 * 1024,
        # Object workers are also parallelized by the caller. Keeping each
        # transfer at four part workers caps aggregate concurrency to 64.
        max_concurrency=min(jobs, 4),
        use_threads=True,
    )


def transfer_config_for_size(config: TransferConfig, size_bytes: int) -> TransferConfig:
    """Increase chunk size for very large objects to stay below S3's 10k-part limit."""
    max_parts = 10_000
    mib = 1024 * 1024
    required_chunk = ((max(size_bytes, 1) + max_parts - 1) // max_parts + mib - 1) // mib * mib
    chunk_size = max(config.multipart_chunksize, required_chunk)
    if chunk_size > 5 * 1024**3:
        raise WorkspaceError("This file is larger than the S3 multipart upload limits supported by vcfr.")
    return TransferConfig(
        multipart_threshold=config.multipart_threshold,
        multipart_chunksize=chunk_size,
        max_concurrency=config.max_concurrency,
        use_threads=config.use_threads,
    )


def _key(prefix: str, path: str) -> str:
    joined = "/".join(piece for piece in (prefix.strip("/"), path.strip("/")) if piece)
    return joined


def get_json(client, bucket: str, key: str) -> tuple[dict[str, Any], str]:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NotFound"}:
            raise WorkspaceError(f"Remote repository metadata is missing: s3://{bucket}/{key}") from exc
        raise
    try:
        data = json.loads(response["Body"].read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"Invalid JSON stored at s3://{bucket}/{key}") from exc
    if not isinstance(data, dict):
        raise WorkspaceError(f"Expected a JSON object at s3://{bucket}/{key}")
    return data, response.get("ETag", "").strip('"')


def put_json(client, bucket: str, key: str, data: dict[str, Any], **conditions: Any):
    body = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", **conditions)


def create_remote_repository(*, uri: str, name: str, email: str, client) -> tuple[dict[str, Any], dict[str, Any]]:
    bucket, prefix = parse_s3_uri(uri)
    if not prefix:
        raise WorkspaceError("Choose a repository prefix below the bucket, for example s3://my-bucket/vcfr/repositories/study-a.")
    normalized_name = name.strip()
    if not normalized_name:
        raise WorkspaceError("Repository name cannot be empty.")
    metadata = {
        "schema_version": REPOSITORY_SCHEMA,
        "name": normalized_name,
        "owner_email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage": "s3",
        "visibility": "private",
    }
    root_commit = make_commit(parent=None, files={}, name="", email="", message="Initialize repository")
    try:
        put_json(client, bucket, _key(prefix, "repository.json"), metadata, IfNoneMatch="*")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict", "412"}:
            raise WorkspaceError(f"A repository already exists at {uri}.") from exc
        raise
    put_json(client, bucket, _key(prefix, f"commits/{root_commit['commit_id']}.json"), root_commit, IfNoneMatch="*")
    put_json(client, bucket, _key(prefix, "HEAD.json"), {"commit_id": root_commit["commit_id"]}, IfNoneMatch="*")
    return metadata, root_commit


def list_remote_repositories(*, bucket: str, prefix: str, client) -> list[dict[str, Any]]:
    root = prefix.strip("/")
    if root:
        root += "/"
    paginator = client.get_paginator("list_objects_v2")
    results = []
    for page in paginator.paginate(Bucket=bucket, Prefix=root, Delimiter="/"):
        for common in page.get("CommonPrefixes", []):
            repo_prefix = common["Prefix"].rstrip("/")
            try:
                item, _ = get_json(client, bucket, _key(repo_prefix, "repository.json"))
            except WorkspaceError:
                continue
            item["remote"] = s3_uri(bucket, repo_prefix)
            results.append(item)
    return sorted(results, key=lambda item: item.get("name", "").casefold())


def _remote_head(client, bucket: str, prefix: str) -> tuple[str | None, str | None]:
    try:
        value, etag = get_json(client, bucket, _key(prefix, "HEAD.json"))
        return value.get("commit_id"), etag
    except WorkspaceError as exc:
        if "metadata is missing" in str(exc):
            return None, None
        raise


def _load_remote_commit(client, bucket: str, prefix: str, commit_id: str) -> dict[str, Any]:
    validate_digest(commit_id)
    commit, _ = get_json(client, bucket, _key(prefix, f"commits/{commit_id}.json"))
    commit = validate_commit(commit)
    if commit["commit_id"] != commit_id:
        raise WorkspaceError(f"Remote commit hash does not match its object key: {commit_id}")
    return commit


def _load_local_commit(root: Path, commit_id: str) -> dict[str, Any]:
    validate_digest(commit_id)
    commit = read_json(commit_path(root, commit_id))
    if not commit:
        raise WorkspaceError(f"Local commit {commit_id} is missing.")
    commit = validate_commit(commit)
    if commit["commit_id"] != commit_id:
        raise WorkspaceError(f"Local commit hash does not match its file name: {commit_id}")
    return commit


def _upload_object(client, bucket: str, prefix: str, root: Path, digest: str, cfg: TransferConfig) -> bool:
    validate_digest(digest)
    key = _key(prefix, f"objects/{digest[:2]}/{digest[2:]}")
    try:
        client.head_object(Bucket=bucket, Key=key)
        return False
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
            raise
    source = repository_state(root) / "objects" / digest[:2] / digest[2:]
    if not source.is_file():
        raise WorkspaceError(f"Local content object is missing: {digest}")
    object_cfg = transfer_config_for_size(cfg, source.stat().st_size)
    from cintern.workspace import sha256_file
    if sha256_file(source) != digest:
        raise WorkspaceError(f"Local object failed its SHA-256 check: {digest}")
    client.upload_file(str(source), bucket, key, Config=object_cfg, ExtraArgs={"Metadata": {"sha256": digest}})
    return True


def _download_object(client, bucket: str, prefix: str, digest: str, target: Path, cfg: TransferConfig, size_bytes: int = 0) -> None:
    validate_digest(digest)
    key = _key(prefix, f"objects/{digest[:2]}/{digest[2:]}")
    target.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket, key, str(target), Config=transfer_config_for_size(cfg, size_bytes))
    from cintern.workspace import sha256_file
    if sha256_file(target) != digest:
        target.unlink(missing_ok=True)
        raise WorkspaceError(f"Checksum mismatch while downloading object {digest}; removed the incomplete file.")


def _put_immutable_json(client, bucket: str, key: str, data: dict[str, Any]) -> None:
    """Write an immutable object once; make retries safe after partial pushes."""
    try:
        existing, _ = get_json(client, bucket, key)
    except WorkspaceError as exc:
        if "metadata is missing" not in str(exc):
            raise
    else:
        if existing != data:
            raise WorkspaceError(f"Remote immutable object already exists with different content: s3://{bucket}/{key}")
        return
    try:
        put_json(client, bucket, key, data, IfNoneMatch="*")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"PreconditionFailed", "ConditionalRequestConflict", "412"}:
            raise
        existing, _ = get_json(client, bucket, key)
        if existing != data:
            raise WorkspaceError(f"Remote immutable object already exists with different content: s3://{bucket}/{key}") from exc


def clone_repository(*, uri: str, target: Path, client, jobs: int = 4, part_size_mib: int = DEFAULT_PART_SIZE_MIB, summary_only: bool = False) -> dict[str, Any]:
    bucket, prefix = parse_s3_uri(uri)
    if target.exists() and any(target.iterdir()):
        raise WorkspaceError(f"Destination directory is not empty: {target}")
    metadata, _ = get_json(client, bucket, _key(prefix, "repository.json"))
    head, _ = _remote_head(client, bucket, prefix)
    if not head:
        raise WorkspaceError("Remote repository has no HEAD commit.")
    commit = _load_remote_commit(client, bucket, prefix, head)
    for path in commit.get("files", {}):
        safe_relative_path(path)
    target.mkdir(parents=True, exist_ok=True)
    from cintern.workspace import create_local_repository
    create_local_repository(target, name=metadata["name"], remote=uri)
    state = repository_state(target)
    generated_initial = read_head(target)
    if generated_initial and generated_initial != head:
        commit_path(target, generated_initial).unlink(missing_ok=True)
    write_json(commit_path(target, head), commit)
    (state / "HEAD").write_text(head + "\n", encoding="utf-8")
    (state / "REMOTE_HEAD").write_text(head + "\n", encoding="utf-8")
    write_json(state / "index.json", {"files": commit.get("files", {})})
    write_json(state / "repository.json", {**metadata, "remote": uri})
    write_json(state / "summary.json", {"repository": metadata["name"], "remote": uri, "commit_id": head, **commit.get("summary", {})})
    if summary_only:
        (state / "SUMMARY_ONLY").write_text("1\n", encoding="utf-8")
    else:
        cfg = transfer_config(jobs=jobs, part_size_mib=part_size_mib)
        def download_one(path: str, item: dict[str, Any]) -> None:
            relative = safe_relative_path(path)
            target_path = safe_target_path(target, path)
            digest = item["sha256"]
            _download_object(client, bucket, prefix, digest, target_path, cfg, item["size_bytes"])
            object_path = state / "objects" / digest[:2] / digest[2:]
            object_path.parent.mkdir(parents=True, exist_ok=True)
            if not object_path.exists():
                import shutil
                shutil.copyfile(target_path, object_path)
        entries = list(commit.get("files", {}).items())
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(download_one, path, item) for path, item in entries]
            for future in as_completed(futures):
                future.result()
        local_index = {}
        for path, item in commit.get("files", {}).items():
            stat = target.joinpath(*safe_relative_path(path).parts).stat()
            local_index[path] = {**item, "mtime_ns": stat.st_mtime_ns}
        write_json(state / "index.json", {"files": local_index})
    return metadata


def push_repository(*, root: Path, client, jobs: int = 4, part_size_mib: int = DEFAULT_PART_SIZE_MIB) -> tuple[int, int]:
    state = repository_state(root)
    if (state / "SUMMARY_ONLY").exists():
        raise WorkspaceError("This is a summary-only clone. Run 'vcfr clone <remote>' in another folder to get data before editing or pushing.")
    config = read_json(state / "repository.json", {})
    uri = config.get("remote", "")
    if not uri:
        raise WorkspaceError("No remote is configured. Add one with 'vcfr remote add origin s3://bucket/prefix'.")
    bucket, prefix = parse_s3_uri(uri)
    remote_head, remote_etag = _remote_head(client, bucket, prefix)
    expected_remote = (state / "REMOTE_HEAD").read_text(encoding="utf-8").strip() if (state / "REMOTE_HEAD").exists() else ""
    if remote_head != (expected_remote or None):
        raise WorkspaceError("The remote has commits you do not have locally. Run 'vcfr pull' before pushing.")
    local_head = read_head(root)
    if not local_head:
        raise WorkspaceError("Local repository has no commit.")
    if local_head == remote_head:
        return 0, 0
    chain: list[dict[str, Any]] = []
    cursor: str | None = local_head
    while cursor and cursor != remote_head:
        commit = _load_local_commit(root, cursor)
        chain.append(commit)
        cursor = commit.get("parent")
    if cursor != remote_head:
        raise WorkspaceError("Local history does not descend from the remote. Clone the remote into a separate folder to avoid overwriting it.")
    chain.reverse()
    latest = chain[-1]
    cfg = transfer_config(jobs=jobs, part_size_mib=part_size_mib)
    objects = sorted({entry["sha256"] for entry in latest.get("files", {}).values()})
    uploaded_objects = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_upload_object, client, bucket, prefix, root, digest, cfg) for digest in objects]
        for future in as_completed(futures):
            uploaded_objects += int(future.result())
    for commit in chain:
        key = _key(prefix, f"commits/{commit['commit_id']}.json")
        _put_immutable_json(client, bucket, key, commit)
    conditions = {"IfMatch": f'"{remote_etag}"'} if remote_etag else {"IfNoneMatch": "*"}
    try:
        put_json(client, bucket, _key(prefix, "HEAD.json"), {"commit_id": local_head}, **conditions)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict", "412"}:
            raise WorkspaceError("Another writer updated this repository during push. Run 'vcfr pull', review the change, then retry.") from exc
        raise
    (state / "REMOTE_HEAD").write_text(local_head + "\n", encoding="utf-8")
    return uploaded_objects, len(chain)


def pull_repository(*, root: Path, client, jobs: int = 4, part_size_mib: int = DEFAULT_PART_SIZE_MIB) -> int | None:
    state = repository_state(root)
    config = read_json(state / "repository.json", {})
    bucket, prefix = parse_s3_uri(config.get("remote", ""))
    remote_head, _ = _remote_head(client, bucket, prefix)
    if not remote_head:
        raise WorkspaceError("Remote repository has no HEAD commit.")
    remote_base = (state / "REMOTE_HEAD").read_text(encoding="utf-8").strip() if (state / "REMOTE_HEAD").exists() else ""
    local_head = read_head(root)
    if local_head != remote_base:
        raise WorkspaceError("You have local commits that have not been pushed. Push them or clone the remote into another folder before pulling.")
    if remote_head == local_head:
        return 0
    from cintern.workspace import working_tree_changes
    if working_tree_changes(root):
        raise WorkspaceError("Working files differ from the last commit. Commit or restore them before pulling.")
    commit = _load_remote_commit(client, bucket, prefix, remote_head)
    prior_files = set(current_commit(root).get("files", {}))
    for path in commit.get("files", {}):
        target = safe_target_path(root, path)
        if target.exists() and path not in prior_files:
            raise WorkspaceError(f"Pull would overwrite an untracked local file: {path}. Move it or choose another clone directory.")
    summary_only = (state / "SUMMARY_ONLY").exists()
    if summary_only:
        write_json(commit_path(root, remote_head), commit)
        (state / "HEAD").write_text(remote_head + "\n", encoding="utf-8")
        (state / "REMOTE_HEAD").write_text(remote_head + "\n", encoding="utf-8")
        write_json(state / "index.json", {"files": commit.get("files", {})})
        write_json(state / "summary.json", {"repository": config.get("name"), "remote": config.get("remote"), "commit_id": remote_head, **commit.get("summary", {})})
        return None
    cfg = transfer_config(jobs=jobs, part_size_mib=part_size_mib)
    # Download files in parallel; workers write to distinct object paths.
    state_objects = state / "objects"
    def fetch(path: str, item: dict[str, Any]) -> None:
        safe_relative_path(path)
        digest = item["sha256"]
        object_path = state_objects / digest[:2] / digest[2:]
        if not object_path.exists():
            _download_object(client, bucket, prefix, digest, object_path, cfg, item["size_bytes"])
        target = safe_target_path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        import tempfile
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.vcfr-", dir=target.parent)
        import os
        os.close(fd)
        try:
            shutil.copyfile(object_path, temp_name)
            Path(temp_name).replace(target)
        finally:
            Path(temp_name).unlink(missing_ok=True)
    entries = list(commit.get("files", {}).items())
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(fetch, path, item) for path, item in entries]
        for future in as_completed(futures):
            future.result()
    prior = current_commit(root)
    write_json(commit_path(root, remote_head), commit)
    (state / "HEAD").write_text(remote_head + "\n", encoding="utf-8")
    (state / "REMOTE_HEAD").write_text(remote_head + "\n", encoding="utf-8")
    local_index = {}
    for path, item in commit.get("files", {}).items():
        stat = root.joinpath(*safe_relative_path(path).parts).stat()
        local_index[path] = {**item, "mtime_ns": stat.st_mtime_ns}
    write_json(state / "index.json", {"files": local_index})
    write_json(state / "summary.json", {"repository": config.get("name"), "remote": config.get("remote"), "commit_id": remote_head, **commit.get("summary", {})})
    (state / "SUMMARY_ONLY").unlink(missing_ok=True)
    # Remove files tracked in the previous commit but absent from the remote snapshot.
    for path in set(prior.get("files", {})) - set(commit.get("files", {})):
        target = safe_target_path(root, path)
        if target.is_file():
            target.unlink()
    return len(entries)
