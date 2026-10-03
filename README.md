# vcfr — versioned research data, from the command line

`vcfr` is a developing command-line tool for preparing, summarizing, versioning, and transferring research datasets. Its first remote backend stores immutable content objects and commit manifests in a **private Amazon S3 bucket**. The email configured in `vcfr` is commit attribution, like Git; AWS credentials separately determine which S3 repositories the user may read or write.

This release is an very early prototype. It does not yet connect to the C-Intern website, Google accounts, or website access requests. S3 permissions are enforced by the AWS bucket/IAM policy.

**Do not make the bucket public.**

## Install

Python 3.10 or newer is required. Install the package in editable mode:

```bash
cd vcf_reader
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The console command is `vcfr`. `python -m cintern` also works.
The old `genome` command remains as a compatibility alias for now but will be deprecated in the later versions.

VCF operations call `bcftools`, which must be installed separately (future packages are planned to be containerized) and available on `PATH`. The VCF inspection command uses `pysam`, installed with `vcfr`.

## Configure identity and AWS access

Set the name and email written on your commits. These values are not AWS or website login credentials.

```bash
vcfr config user.name "Name" --global
vcfr config user.email name@provider.com --global
vcfr config aws.profile lab --global
vcfr config aws.region us-east-2 --global
```

Configure AWS credentials outside `vcfr`. For an AWS IAM Identity Center profile, use your normal AWS CLI setup and login:

```bash
aws configure sso --profile lab
aws sso login --profile lab
vcfr auth status
```

The tool uses the AWS SDK credential chain and never saves access keys in repository configuration. Grant the profile only the required S3 permissions for the repository prefix. `auth status` confirms AWS credentials resolve; it does not prove that a particular bucket grants access.

## Create, version, and upload a repository

Create a private S3-backed repository. The bucket must already exist, and the AWS profile must have permission to list/read/write the selected prefix.

```bash
vcfr repo create "Study A results" \
  --bucket my-private-research-bucket \
  --prefix vcfr/repositories \
  --directory study-a \
  --profile lab \
  --region us-east-2

cd study-a
vcfr add results/cohort.vcf.gz results/summary.tsv
vcfr status
vcfr commit -m "Add filtered cohort outputs"
vcfr push --profile lab --jobs 4
```

`vcfr add` computes a SHA-256 digest and stores a local content-addressed copy. Commits are immutable JSON manifests with the configured author, message, parent, file names, sizes, hashes, and a machine-readable data summary. Identical file content is stored once per repository. A push uploads missing content objects using parallel S3 transfers, then writes the commit and advances `HEAD` last. Large objects use S3 multipart upload, allowing parts to transfer concurrently and be retried independently. Use `--jobs` to control transfer concurrency and `--part-size-mib` to tune large transfers.

Useful local commands:

```bash
vcfr init my-analysis             # Start a local-only repository
vcfr add results/                 # Stage files (honors .vcfrignore)
vcfr rm old-results.tsv           # Stage a tracked file removal
vcfr commit -m "Describe snapshot"
vcfr log                          # Show local snapshot history
vcfr summary -o data-summary.json # Export the current file summary
vcfr remote add origin s3://bucket/prefix/repository
```

For this early release, create new remote repositories with `vcfr repo create`; a local-only repository cannot yet bootstrap an empty remote using `vcfr push`.

## List and clone repositories

```bash
vcfr repo list --bucket my-private-research-bucket \
  --prefix vcfr/repositories --profile lab --region us-east-2

vcfr clone s3://my-private-research-bucket/vcfr/repositories/study-a \
  study-a-summary --summary-only
cd study-a-summary
vcfr summary
```

`--summary-only` downloads the manifest and summary without the large data objects. Omit it to clone the complete working tree. Use `vcfr pull` to fetch a newer remote snapshot and `vcfr push` to publish local commits. Push refuses when the remote has moved since the last pull; pull refuses to overwrite local edits or unpushed commits. Resolve changes deliberately, then retry.

## Local VCF operations

```bash
vcfr vcf info cohort.vcf.gz
vcfr vcf samples cohort.vcf.gz
vcfr vcf query cohort.vcf.gz --region chr1:100000-200000
vcfr vcf stats cohort.vcf.gz --output cohort.with-af.vcf.gz
vcfr vcf inspect cohort.vcf.gz
```

`query` checks for an index and asks `bcftools` to create one when needed. The stats command uses the `+fill-tags` plugin to add allele-frequency tags. These commands process local files; `vcfr` does not run variant searches against S3. Fast remote genomic search is a later feature.

## Data and cost safeguards

- Keep S3 Block Public Access enabled. `vcfr` does not change bucket ACLs or make uploaded objects public.
- Prefer short-lived AWS SSO/role credentials and narrowly scoped IAM policies over long-lived access keys.
- Multipart uploads use multiple requests and network transfer. S3 storage, requests, and data transfer can incur charges even during a trial; check AWS billing and configure an S3 lifecycle rule to abort incomplete multipart uploads.
- Enable S3 bucket versioning for additional recovery from accidental object deletion. `vcfr` itself versions repository manifests and preserves prior content-addressed commits until objects are deleted.
- Do not place human genomic data in this trial bucket unless your institution has approved the account, region, access policy, retention, and data handling requirements.
- The web portal still uses its own Django database and local file storage. `vcfr` S3 repositories will not show up there yet; a secure API/storage integration is the next bridge to build.

## Roadmap

The current foundation provides local `add`/`commit`/`log` snapshots, S3 `repo create`/`list`/`clone`/`pull`/`push`, SHA-256 content addressing, checksum verification on downloads, per-part SDK retries, and metadata-only clones. Next steps are a portal API with user tokens and owner-granted access, resumable upload state across interrupted CLI sessions, and richer VCF summaries. Search/indexing of genomic records is deliberately out of scope for this version.
