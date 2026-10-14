#!/usr/bin/env python3
"""Prints REPOSITORY<TAB>PULLS for every Docker Hub repository in the image
lists given, so the command map can rank them. The list of the most pulled
images already has its counts. This adds the official ones, which that list
leaves to their own.

Run: ./pulls.py lists/official.txt > pulls.tsv
"""
import json
import subprocess
import sys
import time


def get(url):
    for _ in range(8):
        out = subprocess.run(["curl", "-s", "--max-time", "60", "-w", "\n%{http_code}", url],
                             capture_output=True, text=True)
        body, _, code = out.stdout.rpartition("\n")
        if code == "200":
            try:
                return json.loads(body)
            except ValueError:
                pass
        if code == "404":
            return None
        if code == "429":
            print("rate limited, waiting a minute", file=sys.stderr)
            time.sleep(60)
        time.sleep(0.4)
    print(f"gave up on {url}", file=sys.stderr)
    return None


def repositories(paths):
    seen = []
    for path in paths:
        for line in open(path):
            image = line.split("#")[0].split("|")[0].strip()
            if not image:
                continue
            name = image.split("@")[0]
            if ":" in name.rsplit("/", 1)[-1]:
                name = name.rsplit(":", 1)[0]
            # Docker Hub only: a registry host has a dot or a port.
            if "." in name.split("/")[0] or ":" in name.split("/")[0]:
                continue
            if name not in seen:
                seen.append(name)
    return seen


def main():
    for name in repositories(sys.argv[1:]):
        path = name if "/" in name else "library/" + name
        repo = get(f"https://hub.docker.com/v2/repositories/{path}/")
        if repo and repo.get("pull_count"):
            print(f"{name}\t{repo['pull_count']}", flush=True)
        time.sleep(0.4)


if __name__ == "__main__":
    main()
