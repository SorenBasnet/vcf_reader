"""Git-like command line for local research snapshots and private S3 remotes."""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
from cintern.vcf.reader import get_vcf_header
from cintern.vcf.samples import get_samples
from cintern.vcf.query import query_region
from cintern.vcf.stats import calc_allele_freq
from cintern.hpc.slurm import generate_slurm_script, submit_slurm_job
from cintern.hpc.htcondor import generate_condor_submit, submit_condor_job
from cintern.publish.manifest import create_gwas_repository
from cintern.publish.report import generate_web_report
from cintern.mock_gwas.mock import generate_mock_gwas


def main():

    parser = argparse.ArgumentParser(prog="genome", description="C-Intern Platform v0.0.1")
    subparsers = parser.add_subparsers(dest = "subcommand", required = True)

    init = commands.add_parser("init", help="Initialize a local research repository")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--name")

    config = commands.add_parser("config", help="Set or read your name, email, and defaults")
    config.add_argument("key", nargs="?")
    config.add_argument("value", nargs="?")
    config.add_argument("--global", dest="global_scope", action="store_true", help="Use your user-wide config")
    config.add_argument("--list", action="store_true", help="Show effective configuration")

    auth = commands.add_parser("auth", help="Check AWS access used by S3 remotes")
    auth.add_argument("action", choices=["status"], nargs="?", default="status")
    auth.add_argument("--profile")
    auth.add_argument("--region")

    repo = commands.add_parser("repo", help="Create or list remote repositories")
    repo_commands = repo.add_subparsers(dest="repo_command", required=True)
    create = repo_commands.add_parser("create", help="Create a private S3-backed repository")
    create.add_argument("name")
    create.add_argument("--bucket", required=True)
    create.add_argument("--prefix", default="vcfr/repositories")
    create.add_argument("--directory")
    create.add_argument("--profile")
    create.add_argument("--region")
    listing = repo_commands.add_parser("list", help="List repositories visible in an S3 prefix")
    listing.add_argument("--bucket", required=True)
    listing.add_argument("--prefix", default="vcfr/repositories")
    listing.add_argument("--profile")
    listing.add_argument("--region")

    clone = commands.add_parser("clone", help="Clone a repository or fetch only its data summary")
    clone.add_argument("remote", help="S3 URI such as s3://bucket/vcfr/repositories/study-a")
    clone.add_argument("directory", nargs="?")
    clone.add_argument("--summary-only", action="store_true", help="Fetch the manifest without large data files")
    _add_transfer_options(clone)

    # --- HPC SUBCOMMANDS ---
    hpc_parser = subparsers.add_parser("hpc", help="Submit platform workloads to HPC schedulers")
    hpc_subparsers = hpc_parser.add_subparsers(dest="hpc_command", required=True)

    # genome hpc submit --scheduler slurm --job-name my_stats --cmd "genome vcf stats sample.vcf.gz -o out.vcf.gz"
    submit_p = hpc_subparsers.add_parser("submit", help="Submit a job to SLURM or HTCondor")
    submit_p.add_argument("--scheduler", choices=["slurm", "condor"], default="slurm", help="HPC Scheduler type")
    submit_p.add_argument("--job-name", required=True, help="Name for the HPC job")
    submit_p.add_argument("--cmd", required=True, help="Command string to run on worker node")
    submit_p.add_argument("--cpus", type=int, default=4, help="CPUs to request")
    submit_p.add_argument("--mem", type=int, default=16, help="RAM in GB to request")

    publish_p = subparsers.add_parser("publish", help="Publish GWAS analysis into a web repository")
    publish_p.add_argument("--dir", required=True, help="Target repository directory")
    publish_p.add_argument("--title", required=True, help="Dataset Title")
    publish_p.add_argument("--author", required=True, help="Author Name")
    publish_p.add_argument("--gwas", required=True, help="Path to GWAS output file")
    publish_p.add_argument("--trait", required=True, help="Trait analyzed")
    publish_p.add_argument("--n-samples", type=int, required=True, help="Sample size")

    # Subcommand parser for GWAS
    gwas_parser = subparsers.add_parser("gwas", help="GWAS analysis and utilities")
    gwas_subparsers = gwas_parser.add_subparsers(dest="gwas_command", required=True)

    mock_p = gwas_subparsers.add_parser("mock", help="Generate mock summary stats for testing")
    mock_p.add_argument("-o", "--output", default="mock_gwas.tsv", help="Output file path")
    mock_p.add_argument("-n", "--num-variants", type=int, default=5000, help="Number of variants")


    args = parser.parse_args()

    add = commands.add_parser("add", help="Stage files for the next snapshot")
    add.add_argument("paths", nargs="+")
    rm = commands.add_parser("rm", help="Stage a tracked file for removal")
    rm.add_argument("paths", nargs="+")
    status = commands.add_parser("status", help="Show staged and working-tree changes")
    status.add_argument("--porcelain", action="store_true")
    commit = commands.add_parser("commit", help="Create a versioned snapshot")
    commit.add_argument("-m", "--message", required=True)
    log = commands.add_parser("log", help="Show snapshot history")
    log.add_argument("--limit", type=int, default=10)
    summary = commands.add_parser("summary", help="Write or print the current data summary")
    summary.add_argument("--output", "-o")
    push = commands.add_parser("push", help="Upload new content and publish the current snapshot")
    _add_transfer_options(push)
    pull = commands.add_parser("pull", help="Fetch a newer remote snapshot")
    _add_transfer_options(pull)

    vcf = commands.add_parser("vcf", help="Inspect and query local VCF/BCF files")
    vcf_commands = vcf.add_subparsers(dest="vcf_command", required=True)
    info = vcf_commands.add_parser("info", help="Print a VCF header")
    info.add_argument("file")
    samples = vcf_commands.add_parser("samples", help="List sample names")
    samples.add_argument("file")
    query = vcf_commands.add_parser("query", help="Query one genomic region")
    query.add_argument("file")
    query.add_argument("--region", "-r", required=True)
    stats = vcf_commands.add_parser("stats", help="Calculate allele-frequency tags")
    stats.add_argument("file")
    stats.add_argument("--output", "-o")
    inspect = vcf_commands.add_parser("inspect", help="Print file metadata as JSON")
    inspect.add_argument("file")
    return parser


def _add_transfer_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", help="AWS profile name; defaults to the standard AWS credential chain")
    parser.add_argument("--region", help="AWS region; defaults to your AWS profile/SDK configuration")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel file transfers (1-16, default: 4)")
    parser.add_argument("--part-size-mib", type=int, default=32, help="Multipart chunk size in MiB (8-512, default: 32)")


def _s3(profile: str | None, region: str | None, jobs: int = 4):
    from cintern.storage.s3 import s3_client
    try:
        config = load_config(find_workspace())
    except WorkspaceError:
        config = load_config(None)
    profile = profile or config_value(config, "aws.profile") or None
    region = region or config_value(config, "aws.region") or None
    return s3_client(profile=profile, region=region, jobs=jobs)


def _print_json(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _config_command(args) -> None:
    if args.list:
        try:
            workspace = None if args.global_scope else find_workspace()
        except WorkspaceError:
            workspace = None
        config = load_config(workspace)
        for section in config.sections():
            for key, value in config.items(section, raw=True):
                print(f"{section}.{key}={value}")
        return
    if not args.key:
        raise WorkspaceError("Use 'vcfr config user.email name@lab.edu' or 'vcfr config --list'.")
    if args.value is None:
        try:
            workspace = None if args.global_scope else find_workspace()
        except WorkspaceError:
            workspace = None
        config = load_config(workspace)
        value = config_value(config, args.key)
        if not value:
            raise WorkspaceError(f"No value configured for {args.key}.")
        print(value)
        return
    save_config_value(args.key, args.value, global_scope=args.global_scope or not _inside_repository())
    print(f"Set {args.key}.")


def _inside_repository() -> bool:
    try:
        find_workspace()
        return True
    except WorkspaceError:
        return False


def _init(args) -> None:
    root = Path(args.directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = load_config(None)
    name = args.name or config_value(config, "user.name") or root.name or "research-data"
    create_local_repository(root, name=name)
    print(f"Initialized vcfr repository in {root}")


def _auth(args) -> None:
    config = load_config(None)
    email = config_value(config, "user.email") or "(not configured; use vcfr config user.email name@lab.edu --global)"
    import boto3
    profile = args.profile or config_value(config, "aws.profile") or None
    region = args.region or config_value(config, "aws.region") or None
    identity = boto3.Session(profile_name=profile, region_name=region).client("sts").get_caller_identity()
    print(f"Commit email: {email}")
    print(f"AWS account: {identity.get('Account')}")
    print(f"AWS identity: {identity.get('Arn')}")
    print("AWS credential check: passed (bucket permissions are checked by repository commands)")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    if not slug:
        raise WorkspaceError("Repository name must include at least one letter or number.")
    return slug


def _repo_create(args) -> None:
    config = load_config(None)
    email = config_value(config, "user.email")
    if not email:
        raise WorkspaceError("Set your commit email first: vcfr config user.email you@lab.edu --global")
    slug = _slug(args.name)
    prefix = "/".join(piece.strip("/") for piece in (args.prefix, slug) if piece.strip("/"))
    uri = f"s3://{args.bucket}/{prefix}"
    root = Path(args.directory or args.name).expanduser().resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise WorkspaceError(f"Destination directory is not empty: {root}")
    client = _s3(args.profile, args.region)
    from cintern.storage.s3 import create_remote_repository
    metadata, initial_commit = create_remote_repository(uri=uri, name=args.name, email=email, client=client)
    root.mkdir(parents=True, exist_ok=True)
    create_local_repository(root, name=args.name, remote=uri)
    state = repository_state(root)
    # Use the exact initial commit created remotely as the local base snapshot.
    local_initial = read_head(root)
    if local_initial and local_initial != initial_commit["commit_id"]:
        commit_path(root, local_initial).unlink(missing_ok=True)
    write_json(commit_path(root, initial_commit["commit_id"]), initial_commit)
    (state / "HEAD").write_text(initial_commit["commit_id"] + "\n", encoding="utf-8")
    (state / "REMOTE_HEAD").write_text(initial_commit["commit_id"] + "\n", encoding="utf-8")
    _print_json({"repository": metadata["name"], "remote": uri, "directory": str(root)})


def _repo_list(args) -> None:
    client = _s3(args.profile, args.region)
    from cintern.storage.s3 import list_remote_repositories
    repos = list_remote_repositories(bucket=args.bucket, prefix=args.prefix, client=client)
    if not repos:
        print("No repositories found in that S3 prefix.")
        return
    for item in repos:
        print(f"{item.get('name', '(unnamed)')}\t{item.get('owner_email', '')}\t{item.get('remote', '')}")


def _clone(args) -> None:
    from cintern.storage.s3 import clone_repository
    name = Path(args.remote.rstrip("/")).name or "repository"
    target = Path(args.directory).expanduser().resolve() if args.directory else Path(name).expanduser().resolve()
    metadata = clone_repository(
        uri=args.remote,
        target=target,
        client=_s3(args.profile, args.region, args.jobs),
        jobs=args.jobs,
        part_size_mib=args.part_size_mib,
        summary_only=args.summary_only,
    )
    mode = "summary only" if args.summary_only else "full data"
    print(f"Cloned {metadata.get('name', name)} ({mode}) into {target}")

    # Route HPC
    elif args.subcommand == "hpc":
        if args.hpc_command == "submit":
            if args.scheduler == "slurm":
                script = generate_slurm_script(
                    job_name=args.job_name,
                    command=args.cmd,
                    cpus=args.cpus,
                    mem_gb=args.mem
                )
                print(f"Generated SLURM script: {script}")
                submit_slurm_job(script)
            elif args.scheduler == "condor":
                sub_file = generate_condor_submit(
                    job_name=args.job_name,
                    command=args.cmd,
                    cpus=args.cpus,
                    mem_gb=args.mem
                )
                print(f"Generated HTCondor submit file: {sub_file}")
                submit_condor_job(sub_file)

    elif args.subcommand == "publish": 
        manifest = create_gwas_repository(
                repo_dir = args.dir, 
                title = args.title, 
                description = "GWAS results platform deployment", 
                author = args.author, 
                gwas_file = args.gwas,
                trait = args.trait, 
                sample_size = args.n_samples
                )

        report_file = generate_web_report(args.dir, args.gwas)
   
        print(f"Repository initialized successfully at: {args.dir}")
        print(f"Manifest written to: {args.dir}/cintern_repo.json")
        print(f"Web viewer created: {report_file}")

    elif args.subcommand == "gwas":
        if args.gwas_command == "mock":
            out = generate_mock_gwas(args.output, args.num_variants)
            print(f"Generated test GWAS summary stats: {out}")

if __name__ == "__main__":
    main()

def _remote_add(args) -> None:
    root = find_workspace()
    state = repository_state(root)
    config_file = state / "config.ini"
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_file, encoding="utf-8")
    section = f'remote "{args.name}"'
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, "url", args.url)
    with config_file.open("w", encoding="utf-8") as stream:
        config.write(stream)
    repo = read_json(state / "repository.json", {})
    repo["remote"] = args.url
    write_json(state / "repository.json", repo)
    print(f"Remote '{args.name}' set to {args.url}")


def _add(args) -> None:
    root = find_workspace()
    from pathspec import PathSpec
    ignore_file = root / ".vcfrignore"
    patterns = [".vcfr/", ".git/", ".venv/", "__pycache__/", "*.pyc", ".DS_Store"]
    if ignore_file.exists():
        patterns += ignore_file.read_text(encoding="utf-8").splitlines()
    spec = PathSpec.from_lines("gitwildmatch", patterns)
    added = []
    for raw in args.paths:
        item = Path(raw)
        full = item.resolve()
        if full.is_dir():
            candidates = []
            for current, directories, filenames in os.walk(full):
                current_path = Path(current)
                kept_directories = []
                for directory in directories:
                    candidate_directory = current_path / directory
                    relative_directory = candidate_directory.relative_to(root).as_posix() + "/"
                    if not spec.match_file(relative_directory):
                        kept_directories.append(directory)
                directories[:] = kept_directories
                candidates.extend(current_path / filename for filename in filenames)
            candidates.sort()
        else:
            candidates = [full]
        for candidate in candidates:
            try:
                relative = candidate.relative_to(root).as_posix()
            except ValueError as exc:
                raise WorkspaceError(f"Files must be inside the repository: {candidate}") from exc
            if spec.match_file(relative):
                continue
            added.append(stage_file(root, candidate))
    if added:
        print("Staged " + ", ".join(added))
    else:
        print("No files staged (all paths may be ignored).")


def _rm(args) -> None:
    root = find_workspace()
    for raw in args.paths:
        candidate = Path(raw)
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise WorkspaceError(f"Path is outside the repository: {raw}") from exc
        stage_remove(root, relative)
        print(f"Staged removal: {relative}")


def _status(args) -> None:
    root = find_workspace()
    changes = working_tree_changes(root)
    from pathspec import PathSpec
    ignore_file = root / ".vcfrignore"
    patterns = [".vcfr/", ".git/", ".venv/", "__pycache__/", "*.pyc", ".DS_Store"]
    if ignore_file.exists():
        patterns += ignore_file.read_text(encoding="utf-8").splitlines()
    ignored = PathSpec.from_lines("gitwildmatch", patterns)
    known = set(index_files(root)) | set(current_commit(root).get("files", {}))
    for current, directories, filenames in os.walk(root):
        current_path = Path(current)
        directories[:] = [
            directory for directory in directories
            if not ignored.match_file((current_path / directory).relative_to(root).as_posix() + "/")
        ]
        for filename in filenames:
            candidate = current_path / filename
            if candidate.is_symlink():
                continue
            relative = candidate.relative_to(root).as_posix()
            if relative not in known and not ignored.match_file(relative):
                changes.append(("untracked", relative))
    if not changes:
        print("Working tree clean")
        return
    for kind, path in changes:
        if args.porcelain:
            print(f"{kind[:1].upper()} {path}")
        else:
            print(f"{kind}: {path}")


def _commit(args) -> None:
    root = find_workspace()
    if (repository_state(root) / "SUMMARY_ONLY").exists():
        raise WorkspaceError("This is a summary-only clone. Make a full clone before committing data.")
    config = load_config(root)
    email = config_value(config, "user.email")
    name = config_value(config, "user.name")
    if not email:
        raise WorkspaceError("Commit email is required. Set it with 'vcfr config user.email you@lab.edu --global'.")
    index = index_files(root)
    previous = current_commit(root)
    if normalized_files(index) == normalized_files(previous.get("files", {})):
        raise WorkspaceError("Nothing staged. Use 'vcfr add <path>' or 'vcfr rm <path>' first.")
    commit = make_commit(parent=previous["commit_id"], files=index, name=name, email=email, message=args.message)
    write_json(commit_path(root, commit["commit_id"]), commit)
    (repository_state(root) / "HEAD").write_text(commit["commit_id"] + "\n", encoding="utf-8")
    _print_json({"commit": commit["commit_id"], "files": len(index), "message": args.message})


def _log(args) -> None:
    if args.limit < 1:
        raise WorkspaceError("--limit must be at least 1.")
    root = find_workspace()
    cursor = read_head(root)
    count = 0
    while cursor and count < args.limit:
        commit = read_json(commit_path(root, cursor))
        if not commit:
            raise WorkspaceError(f"Commit history is incomplete at {cursor}.")
        author = commit.get("author", {})
        print(f"commit {commit['commit_id']}\nAuthor: {author.get('name', '')} <{author.get('email', '')}>\nDate:   {commit.get('created_at', '')}\n\n    {commit.get('message', '')}\n")
        cursor = commit.get("parent")
        count += 1


def _summary(args) -> None:
    root = find_workspace()
    commit = current_commit(root)
    summary = {"repository": read_json(repository_state(root) / "repository.json", {}).get("name"), "commit_id": commit["commit_id"], **commit.get("summary", {})}
    if args.output:
        output = Path(args.output).expanduser()
        write_json(output, summary)
        print(f"Wrote data summary to {output.resolve()}")
    else:
        _print_json(summary)


def _push(args) -> None:
    from cintern.storage.s3 import push_repository
    root = find_workspace()
    uploaded, commits = push_repository(root=root, client=_s3(args.profile, args.region, args.jobs), jobs=args.jobs, part_size_mib=args.part_size_mib)
    if not commits:
        print("Everything is up to date.")
    else:
        print(f"Pushed {commits} snapshot(s); uploaded {uploaded} new content object(s).")


def _pull(args) -> None:
    from cintern.storage.s3 import pull_repository
    root = find_workspace()
    count = pull_repository(root=root, client=_s3(args.profile, args.region, args.jobs), jobs=args.jobs, part_size_mib=args.part_size_mib)
    if count is None:
        print("Updated the repository summary; this summary-only clone has no data files.")
    else:
        print("Already up to date." if count == 0 else f"Updated to the remote snapshot ({count} files).")


def _vcf(args) -> None:
    if args.vcf_command == "info":
        from cintern.vcf.reader import get_vcf_header
        print(get_vcf_header(args.file), end="")
    elif args.vcf_command == "samples":
        from cintern.vcf.samples import get_samples
        samples = get_samples(args.file)
        print(f"{len(samples)} samples")
        for sample in samples:
            print(sample)
    elif args.vcf_command == "query":
        from cintern.vcf.query import query_region
        print(query_region(args.file, args.region), end="")
    elif args.vcf_command == "stats":
        from cintern.vcf.stats import calc_allele_freq
        result = calc_allele_freq(args.file, args.output)
        if result:
            print(result, end="")
    elif args.vcf_command == "inspect":
        from cintern.vcf.inspect import inspect_variant_file
        _print_json(inspect_variant_file(args.file))


def _dispatch(args) -> None:
    handlers = {
        "init": _init,
        "config": _config_command,
        "auth": _auth,
        "clone": _clone,
        "add": _add,
        "rm": _rm,
        "status": _status,
        "commit": _commit,
        "log": _log,
        "summary": _summary,
        "push": _push,
        "pull": _pull,
        "vcf": _vcf,
    }
    if args.command == "repo":
        return _repo_create(args) if args.repo_command == "create" else _repo_list(args)
    if args.command == "remote":
        return _remote_add(args)
    return handlers[args.command](args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _dispatch(args)
    except WorkspaceError as exc:
        print(f"vcfr: error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # boto3's ClientError is rendered without credentials or request internals.
        try:
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:
            raise
        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {})
            message = error.get("Message", str(exc))
            print(f"vcfr: AWS {error.get('Code', 'error')}: {message}", file=sys.stderr)
            return 2
        if isinstance(exc, BotoCoreError):
            print(f"vcfr: AWS connection error: {exc}", file=sys.stderr)
            return 2
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
