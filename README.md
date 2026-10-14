# range-index

Layer indexes and startup profiles for [Range](https://github.com/andreygrehov/range),
so the first run of a popular container image is lazy for everyone: the most
pulled images on Docker Hub and every official image, at every version.

The first time Range opens a container image, it reads each layer once to index
it: where every file starts in the layer, and the points to resume gzip or zstd
decompression from. This repository publishes those indexes, so Range can fetch
one instead of reading the whole layer. The images themselves stay in their
registries. Nothing here is a copy of an image.

## Layout

Each index is a release asset, named by the layer's digest and sharded by the
first two hex digits:

```
https://github.com/andreygrehov/range-index/releases/download/<ab>/sha256-<ab...>.idx
```

A startup profile lists the blocks an image reads when it starts, so Range can
fetch them at once. It is named by the digest of the image's platform manifest:

```
https://github.com/andreygrehov/range-index/releases/download/<ab>/range-oci-1-sha256-<ab...>.profile.json
```

Range looks here when it has no index of its own for a layer. A missing entry
means Range indexes the layer itself, as before. `RANGE_INDEX_URL` points Range
at another catalog, and `RANGE_INDEX_URL=off` turns the catalog off.

## The command map

The map says which image holds each command, so Range can run a command this
machine does not have from the image that brought it: `pdflatex` from
`texlive/texlive`, `nvcc` from `nvidia/cuda`. The catalog builds it every day
from the layer indexes above, without reading a layer, and publishes it as a
small root and shards named by their content:

```
https://github.com/andreygrehov/range-index/releases/download/commands/commands.json
https://github.com/andreygrehov/range-index/releases/download/<ab>/sha256-<ab...>.commands.json.gz
```

The first hex digits of the SHA-256 of a command's name pick its shard, and
the root names the shard for each prefix. A client fetches the root,
then the one shard it needs, and keeps both: a shard never changes. The shards
go up first and the root last, so a client never sees a root whose shards are
missing. `range commands which pdflatex` shows what the map says.

A command belongs to the image that brought it, not to every image built on
that one: `pip` is `python`'s, though hundreds of images carry it. Where the
data cannot choose, such as `java`, [pins.txt](pins.txt) decides.

## What Range checks

An index is used only when it names the same layer digest and size as the
image's manifest. Every byte Range then reads from the registry is checked
against a SHA-256 for each 64 KiB in the index. An index holds short runs of a
layer's uncompressed bytes, the 32 KiB window before each checkpoint, so this
catalog covers public images only.

## Which images

Every night the [index workflow](.github/workflows/index.yml) lists:

- Of the 2500 most pulled repositories on Docker Hub, each one pushed in the
  last two years. [top-images.py](top-images.py) makes this list.
- Every image that Docker's official images build, one tag for each image.
  [official-images.py](official-images.py) makes this list.
- The images in [images.txt](images.txt).

It indexes the layers the catalog does not hold yet, records the profiles it
does not hold yet, and publishes them. To add an image, add it to images.txt.
To build indexes yourself:

```
range index python:3.12 --platform linux/amd64,linux/arm64 -o out
```
