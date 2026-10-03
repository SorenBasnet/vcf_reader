"""Small S3 listing helper retained for scripts using the older module path."""
from __future__ import annotations

from typing import Any

import boto3


def list_bucket_objects(
    bucket_name: str,
    *,
    region: str | None = None,
    profile: str | None = None,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """Return object keys and basic metadata using the standard AWS credentials."""
    session = boto3.Session(profile_name=profile or None, region_name=region or None)
    client = session.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    objects: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for item in page.get("Contents", []):
            objects.append({
                "key": item["Key"],
                "size_bytes": item["Size"],
                "last_modified": item["LastModified"].isoformat(),
                "etag": item.get("ETag", "").strip('"'),
            })
    return objects


def view_file(bucket_name: str, region: str | None = None, profile: str | None = None) -> list[dict[str, Any]]:
    """Compatibility alias for older scripts; use list_bucket_objects in new code."""
    return list_bucket_objects(bucket_name, region=region, profile=profile)
