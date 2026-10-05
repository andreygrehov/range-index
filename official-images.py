#!/usr/bin/env python3
"""Prints every image Docker's official images build for Linux amd64 or arm64,
one tag per image, as lines of images.txt.

docker-library/official-images lists, for each official repository, every
image it builds and all the tags that name it: python:3.12, 3.12.7 and
3.12-bookworm are one image. The catalog is keyed by digest, so one tag per
image covers all of its names. A repository that images.txt gives a command,
such as "python | python3 -c pass", gets that command on every one of its tags.

    ./official-images.py images.txt > official.txt
"""
import io
import os
import re
import sys
import tarfile
import urllib.request

SOURCE = "https://codeload.github.com/docker-library/official-images/tar.gz/refs/heads/master"


def entries(text):
    """The header and the entries of one library file, as dicts."""
    blocks = []
    for block in re.split(r"\n\s*\n", text):
        fields, key = {}, None
        for line in block.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if line[0] in " \t" and key:
                fields[key] += " " + line.strip()
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        if fields:
            blocks.append(fields)
    return blocks


def commands(path):
    """The command images.txt gives a bare repository name, if any."""
    out = {}
    for line in open(path):
        line = line.split("#")[0]
        if "|" not in line:
            continue
        image, command = (part.strip() for part in line.split("|", 1))
        if image and ":" not in image and "/" not in image and command:
            out[image] = command
    return out


def main():
    given = commands(sys.argv[1]) if len(sys.argv) > 1 else {}
    data = urllib.request.urlopen(SOURCE, timeout=120).read()
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            parts = member.name.split("/")
            if len(parts) != 3 or parts[1] != "library" or not member.isfile():
                continue
            repo = parts[2]
            blocks = entries(tar.extractfile(member).read().decode())
            default = blocks[0].get("Architectures", "amd64") if blocks else "amd64"
            for entry in blocks:
                tags = [t.strip() for t in entry.get("Tags", "").split(",") if t.strip()]
                if not tags:
                    continue
                arches = {a.strip() for a in entry.get("Architectures", default).split(",")}
                if not arches & {"amd64", "arm64v8"}:
                    continue
                if "windows" in entry.get("Constraints", "") or "nanoserver" in entry.get("Constraints", ""):
                    continue
                line = f"{repo}:{tags[0]}"
                if repo in given:
                    line += f" | {given[repo]}"
                print(line)
                count += 1
    print(f"{count} images", file=sys.stderr)


if __name__ == "__main__":
    main()
