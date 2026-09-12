#!/usr/bin/env python3
"""Assemble the offline Kafka agent import package for the portable build.

The app's "offline import" (import_offline_zip) accepts a ZIP containing:
  agent-registry.json         subset of the official agent registry, with
                              artifact URLs rewritten to offline://<filename>
  drivers/<agent>.jar         the driver JAR extracted from its tar.zst bundle
  jre/<jre>.tar.zst           the platform JRE archive, copied verbatim

Everything (versions, URLs, checksums) is derived from the official
agent-registry.json published on the agents-latest release, so the script
needs no hardcoded driver versions and fails fast if an artifact is missing.
"""

import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.request
import zipfile

import zstandard


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path

REGISTRY_URL = "https://github.com/t8y2/dbx/releases/download/agents-latest/agent-registry.json"
PLATFORM = "windows-x64"


def fail(message: str) -> "None":
    raise SystemExit(f"error: {message}")


def sha256_file(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def fetch(url, destination, expected_sha256=None, expected_size=None):
    print(f"downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "dbx-offline-portable-builder"})
    with urllib.request.urlopen(request) as response, open(destination, "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    actual_sha256, actual_size = sha256_file(destination)
    if expected_sha256 and actual_sha256 != expected_sha256.lower():
        fail(f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual_sha256}")
    if expected_size and actual_size != expected_size:
        fail(f"size mismatch for {url}: expected {expected_size}, got {actual_size}")
    return destination


def extract_driver_jar(tar_zstd_path, work_dir):
    """Extract the agent JAR packed inside a tar.zst driver bundle."""
    with open(tar_zstd_path, "rb") as handle:
        decompressed = zstandard.ZstdDecompressor().stream_reader(handle).read()
    with tarfile.open(fileobj=io.BytesIO(decompressed)) as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        if not members:
            fail("driver tar.zst bundle contains no files")
        # The bundle packs agent-registry.json plus the artifact under drivers/;
        # pick the largest file, which is the JAR itself.
        member = max(members, key=lambda m: m.size)
        if not member.name.startswith("drivers/") or not member.name.endswith(".jar"):
            fail(f"unexpected driver artifact inside bundle: {member.name}")
        # Write the bytes manually: tar members carry 1970 timestamps that zip
        # rejects (ZIP support starts at 1980) and macOS tar metadata differs.
        target = f"{work_dir}/{member.name.rsplit('/', 1)[-1]}"
        ensure_dir(os.path.dirname(target))
        with archive.extractfile(member) as source, open(target, "wb") as out:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    jar_filename = member.name.rsplit("/", 1)[-1]
    print(f"extracted driver jar: {jar_filename} ({member.size} bytes)")
    return jar_filename, target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-type", default="kafka")
    parser.add_argument("--platform", default=PLATFORM)
    parser.add_argument("--output", required=True, help="path of the offline import zip to write")
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    ensure_dir(args.work_dir)

    registry_path = fetch(REGISTRY_URL, f"{args.work_dir}/agent-registry.json")
    with open(registry_path, encoding="utf-8") as handle:
        registry = json.load(handle)

    driver = registry["drivers"].get(args.db_type)
    if not driver:
        fail(f"driver {args.db_type} is missing from the official agent registry")
    jar_artifact = driver.get("jar")
    if not jar_artifact:
        fail(f"driver {args.db_type} has no jar artifact in the official agent registry")
    if jar_artifact.get("format") != "tar_zstd":
        fail(f"driver {args.db_type} jar artifact is not a tar.zst bundle; this script must be extended")

    tar_path = fetch(jar_artifact["url"], f"{args.work_dir}/{args.db_type}-bundle.tar.zst",
                     jar_artifact.get("sha256"), jar_artifact.get("size"))
    jar_filename, jar_path = extract_driver_jar(tar_path, args.work_dir)
    jar_sha256, jar_size = sha256_file(jar_path)

    jre_key = (driver.get("jre") or "").strip()
    if not jre_key:
        fail(f"driver {args.db_type} does not declare a JRE requirement")
    jre_info = (registry.get("jres") or {}).get(jre_key)
    if not jre_info:
        fail(f"JRE {jre_key} is missing from the official agent registry")
    jre_artifact = jre_info["platforms"].get(args.platform)
    if not jre_artifact:
        fail(f"JRE {jre_key} has no artifact for platform {args.platform}")
    if jre_artifact.get("format") != "tar_zstd":
        fail(f"JRE {jre_key} artifact is not a tar.zst archive; this script must be extended")

    jre_filename = jre_artifact["url"].rsplit("/", 1)[-1]
    jre_path = fetch(jre_artifact["url"], f"{args.work_dir}/{jre_filename}",
                     jre_artifact.get("sha256"), jre_artifact.get("size"))

    offline_registry = {
        "jres": {
            jre_key: {
                "version": jre_info["version"],
                "platforms": {
                    args.platform: {
                        "url": f"offline://{jre_filename}",
                        "sha256": jre_artifact["sha256"],
                        "size": jre_artifact["size"],
                        "format": "tar_zstd",
                    }
                },
            }
        },
        "drivers": {
            args.db_type: {
                "version": driver["version"],
                "label": driver["label"],
                "min_app_version": driver["min_app_version"],
                "jre": jre_key,
                "jar": {"url": f"offline://{jar_filename}", "sha256": jar_sha256, "size": jar_size},
            }
        },
    }

    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("agent-registry.json", json.dumps(offline_registry, indent=2))
        archive.write(jar_path, f"drivers/{jar_filename}")
        archive.write(jre_path, f"jre/{jre_filename}")

    output_sha256, output_size = sha256_file(args.output)
    print(f"wrote {args.output} ({output_size} bytes, sha256 {output_sha256})")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - single entry point, fail with context
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
