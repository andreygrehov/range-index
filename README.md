# range-index

Layer indexes for [Range](https://github.com/andreygrehov/range), so the first
run of a popular container image is lazy for everyone.

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

Range looks here when it has no index of its own for a layer. A missing entry
means Range indexes the layer itself, as before. `RANGE_INDEX_URL` points Range
at another catalog, and `RANGE_INDEX_URL=off` turns the catalog off.

## What Range checks

An index is used only when it names the same layer digest and size as the
image's manifest. Every byte Range then reads from the registry is checked
against a SHA-256 for each 64 KiB in the index. An index holds short runs of a
layer's uncompressed bytes, the 32 KiB window before each checkpoint, so this
catalog covers public images only.

## Adding an image

Add it to [images.txt](images.txt). The [index workflow](.github/workflows/index.yml)
runs every day, indexes only the layers the catalog does not hold yet, and
publishes them. To build indexes yourself:

```
range index python:3.12 --platform linux/amd64,linux/arm64 -o out
```
