#!/usr/bin/env python3
"""Prints the most pulled Docker Hub images that have a Linux amd64 or arm64
build and were pushed in the last two years, one per line, most pulled first,
with the pull count after a tab. An image whose latest tag has no Linux build
is printed with its most recently pushed stable tag that has one.

Signed in (DOCKERHUB_USERNAME and DOCKERHUB_TOKEN set), Docker Hub's search
lists the 2500 most pulled repositories in order, which reaches well below the
thousandth image pushed in two years. Without them, search pages only 200
results, so this asks many narrower questions and ranks what they turn up by
exact pull count, and may miss a few.

    ./top-images.py 1000 > top.txt
"""
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time

SEARCH = "https://hub.docker.com/api/search/v3/catalog/search?type=image&sort=pull_count&order=desc&size=100"
CATEGORIES = [
    "networking", "security", "languages-and-frameworks", "integration-and-delivery",
    "message-queues", "api-management", "internet-of-things", "machine-learning-and-ai",
    "developer-tools", "data-science", "web-servers", "operating-systems",
    "content-management-system", "databases-and-storage", "monitoring-and-observability",
    "web-analytics",
]
ARCHITECTURES = ["amd64", "arm64", "arm", "386", "ppc64le", "s390x", "riscv64"]
SOURCES = ["", "source=store", "source=community"]


# Docker Hub answers 180 requests a minute from one address.
lock = threading.Lock()
last = [0.0]


def get(url, headers=()):
    for _ in range(8):
        with lock:
            time.sleep(max(0, last[0] + 0.4 - time.monotonic()))
            last[0] = time.monotonic()
        out = subprocess.run(["curl", "-s", "--max-time", "60", "-w", "\n%{http_code}", *headers, url],
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
    print(f"gave up on {url}", file=sys.stderr)
    return None


BUCKETS = {"1B+": 10**9, "500M+": 5 * 10**8, "100M+": 10**8, "50M+": 5 * 10**7,
           "10M+": 10**7, "5M+": 5 * 10**6, "1M+": 10**6, "500K+": 5 * 10**5,
           "100K+": 10**5, "50K+": 5 * 10**4, "10K+": 10**4}


def bucket(result):
    try:
        return BUCKETS.get(result["rate_plans"][0]["repositories"][0]["pull_count"], 0)
    except (KeyError, IndexError):
        return 0


def search(query):
    found = {}
    for start in (0, 100):
        data = get(f"{SEARCH}&from={start}&{query}")
        if not data:
            break
        found.update((r["name"], bucket(r)) for r in data.get("results", []))
    return found


def namespace(ns):
    data = get(f"https://hub.docker.com/v2/namespaces/{ns}/repositories?page_size=100&ordering=pull_count")
    if not data:
        return []
    return [r for r in data.get("results", []) if r.get("repository_type") in (None, "image")]


# Words that mark a tag as a preview, a branch build or not for Linux.
UNSTABLE = {"rc", "alpha", "beta", "dev", "nightly", "snapshot", "test", "sha256", "debug", "windows",
            "nanoserver", "ltsc", "ea", "head", "sha", "sig", "att", "sbom", "merge", "main", "master", "edge", "canary", "pr", "pre", "preview"}
# A release: v1, 1.2, 1.2.3, optionally with one suffix such as -alpine.
VERSION = re.compile(r"^v?\d+(\.\d+)*(-[a-z][a-z0-9.]*)?$")


def stable(tag):
    return not any(w.rstrip("0123456789") in UNSTABLE for w in re.split(r"[-_.]", tag.lower()))


def linux(tag):
    return any(i.get("os") == "linux" and i.get("architecture") in ("amd64", "arm64")
               for i in tag.get("images") or [])


def reference(name):
    """The image reference to index: the name alone when its latest tag has a
    Linux build, else the most recently pushed stable tag that has one."""
    repo = name if "/" in name else f"library/{name}"
    latest = get(f"https://hub.docker.com/v2/repositories/{repo}/tags/latest")
    if latest and linux(latest):
        return name
    data = get(f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=50&ordering=last_updated")
    tags = [t for t in (data or {}).get("results", []) if linux(t) and stable(t["name"])]
    # Prefer the newest release, then the newest tag that is not a commit hash.
    for tag in tags:
        if VERSION.match(tag["name"]):
            return f"{name}:{tag['name']}"
    for tag in tags:
        if not re.fullmatch(r"[0-9a-f]{7,64}", tag["name"]):
            return f"{name}:{tag['name']}"
    return None


def login():
    """A Docker Hub session for DOCKERHUB_USERNAME and DOCKERHUB_TOKEN, a
    personal access token, or None. Hub takes a token only after exchanging
    it for a JWT."""
    user, token = os.environ.get("DOCKERHUB_USERNAME"), os.environ.get("DOCKERHUB_TOKEN")
    if not user or not token:
        return None
    out = subprocess.run(["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "@-",
                          "https://hub.docker.com/v2/auth/token"],
                         input=json.dumps({"identifier": user, "secret": token}), capture_output=True, text=True)
    try:
        return json.loads(out.stdout)["access_token"]
    except (ValueError, KeyError):
        sys.exit("top-images: Docker Hub refused DOCKERHUB_USERNAME and DOCKERHUB_TOKEN")


def ranked(jwt):
    """Repositories in order of exact pull count, as signed-in search returns
    them: the first 2500, the most it pages to. Pull counts show only as
    buckets, so each gets its bucket."""
    headers = ["-H", f"Authorization: Bearer {jwt}"]
    repos = {}
    for start in range(0, 2500, 100):
        data = get(f"{SEARCH}&from={start}", headers)
        for r in (data or {}).get("results", []):
            # "name" is a display name for some images ("Python" for
            # dhi/python); the repository record has the real one.
            repo = (r.get("rate_plans") or [{}])[0].get("repositories", [{}])[0]
            if r.get("archived") or not repo.get("name"):
                continue
            ns = repo.get("namespace", "library")
            name = repo["name"] if ns == "library" else f"{ns}/{repo['name']}"
            repos[name] = {"pull_count": bucket(r), "last_updated": repo.get("last_pushed_at") or r.get("updated_at")}
    return repos


def discovered():
    """Repositories with exact pull counts, found without signing in: search
    pages only 200 results to an anonymous client, so this asks many
    narrower questions and lists every namespace they turn up. It can miss a
    namespace that no narrow search shows."""
    queries = list(SOURCES)
    queries += [f"{s}&categories={c}" for s in SOURCES for c in CATEGORIES]
    queries += [f"{s}&architectures={a}" for s in SOURCES for a in ARCHITECTURES]
    queries += [f"categories={c}&architectures={a}" for c in CATEGORIES for a in ("amd64", "arm64")]
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        found = {}
        for names in pool.map(search, [q.strip("&") for q in queries]):
            found.update(names)
        # Only namespaces with a repository pulled 10 million times or more
        # can place one in the top thousand.
        namespaces = {n.split("/")[0] if "/" in n else "library" for n, b in found.items() if b >= 10**7}
        namespaces.add("library")
        print(f"{len(found)} repositories from search, {len(namespaces)} namespaces to list", file=sys.stderr)
        repos = {}
        for rows in pool.map(namespace, sorted(namespaces)):
            for r in rows:
                ns = r["namespace"]
                name = r["name"] if ns == "library" else f"{ns}/{r['name']}"
                repos[name] = r
    # A repository whose namespace was not listed has only its search bucket.
    for name, b in found.items():
        if name not in repos and b:
            repos[name] = {"pull_count": b, "last_updated": None}
    return repos


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    jwt = login()
    repos = ranked(jwt) if jwt else discovered()
    order = {name: i for i, name in enumerate(repos)}
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=730)
    fresh = []
    for name, r in repos.items():
        updated = r.get("last_updated")
        if r.get("status_description") == "inactive":
            continue
        if updated and datetime.datetime.fromisoformat(updated.replace("Z", "+00:00")) < cutoff:
            continue
        fresh.append((r.get("pull_count", 0), -order[name], name))
    # Signed-in search is already in exact order, so ties in a bucket keep it.
    fresh.sort(reverse=True)
    fresh = [(pulls, name) for pulls, _, name in fresh]
    print(f"{len(repos)} repositories, {len(fresh)} pushed in two years", file=sys.stderr)
    picked = []
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for start in range(0, len(fresh), 200):
            batch = fresh[start:start + 200]
            for (pulls, name), ref in zip(batch, pool.map(reference, [n for _, n in batch])):
                if ref:
                    picked.append((ref, pulls))
            if len(picked) >= want:
                break
    if len(picked) < want:
        print(f"only {len(picked)} images qualify", file=sys.stderr)
    for ref, pulls in picked[:want]:
        print(f"{ref}\t{pulls}")


if __name__ == "__main__":
    main()
