# Denoise performance investigation — M4 Mac mini

Measured on 2026-10-20 against `projects/2026-08-16.proj_denoise`, at application
revision `0b31c75`. Hardware: Apple M4, 4 performance and 6 efficiency CPU cores,
16 GiB unified memory. NumPy 2.5.4 and OpenCV 5.0.0; OpenCV reports 10 threads.

The project has 15 light frames and 15 dark frames, all 9984 × 6656 RGB uint16
uncompressed TIFFs. Each decoded input is 380.25 MiB. A normalized RGB float32
frame is 760.5 MiB, and 15 such frames occupy 11.14 GiB. Keeping both complete
stacks in RAM would already exceed this machine's total memory.

The configured method is sigma clipping, threshold 1.2, three iterations, with
five-pixel tapered coverage. The sky mask covers 52.96% of the image.

## Implemented improvements

The investigation below records the original implementation at `0b31c75`.
The following changes were subsequently implemented and measured on the same
full-resolution project. These are sequential local measurements; source-file
caching, memory pressure, and other machine activity affect elapsed time.

| Change | Before | After | Measured improvement | Commit |
| --- | ---: | ---: | --- | --- |
| Persist the normalized master dark | 105.6 s fresh alignment, cache build included | 21.0 s fresh alignment in a new process | 80% less alignment time | `bc9cc24` |
| Buffered scratch I/O | 224.1 s stack with cached dark | 137.2 s | 39% less stack time | `23503b4` |
| Optional intermediate TIFF compression, off by default | 137.2 s stack | 118.1 s | 14% less stack time | `dceb3d8` |
| Reuse arrays, broadcast weights, tune CPU chunks/workers | 48.9 s reduction / 152.9 s total | 32.1 s reduction / 126.0 s total | 34% less reduction time / 18% less total time in repeat | `e5cf154` |

The fourth change's first full run measured 33.1 seconds for reduction versus
49.1 seconds previously, but slower loading/encoding offset most of the gain:
total time was 116.2 versus 118.1 seconds. The adjacent baseline/optimized repeat
in the table confirmed the reduction improvement under slower I/O conditions.
Treat the total-time improvements as local observations rather than stable
percentages; reduction consistently improved by about one third. The final
repeat also includes a shortcut for sigma clipping with entirely empty coverage.

The project cache is `2026-08-16.denoise/cache/master_dark.npz`, approximately
761 MiB. It holds the normalized float32 median, including fractional values,
and a signature of source paths, sizes, modification/change timestamps, and the
calibration algorithm version. Reopening the project reuses it; changing source
identity or metadata rebuilds it. The measured cache read took 0.24 seconds.
Publication is atomic, and corrupt caches or cache-write failures fall back to
normal calibration. The first build still incurs calibration work.

Buffered scratch transfers retain bounded conversion windows and independent
reader handles, with one sync per written frame. Scratch-write time fell from
72.8 to 12.3 seconds in the cached-dark full-stack comparison. This retains
disk staging rather than holding all light frames in memory.
The class and module were subsequently renamed to `DiskFrameBuffer` and
`src/startrails/lib/denoise/stacking/disk_buffer.py` in `e9e1b15` to reflect this
implementation. All callers were updated; there is no compatibility alias.

The Advanced stacking options now include intermediate TIFF compression.
Disabling it reduced total encode time from 28.9 to 11.6 seconds, including the
extra final encode. Sky, ground, and base intermediates use about 380 MiB each
instead of roughly 332 MiB. The final output remains compressed, and decoded
pixels are identical in both modes.

CPU reduction now broadcasts coverage across RGB channels, reuses differences
and weighted-variance buffers, and skips clipping iterations for entirely empty
coverage. Ground arithmetic retains its previous float64 intermediates and
weighted variance retains its multiplication order. Four workers use small
input tiles, still bounded by the aggregate scratch budget. For this project,
default chunks contain two rows. Measured temporary allocations excluding the
full output were about 87 MiB for sky and 121 MiB for ground, within the 256 MiB
budget. Normalization also removes full-frame division/clipping temporaries.

Full-resolution sky, ground, and base outputs matched every saved uint16
reference pixel, including after the empty-coverage shortcut. Direct kernel
checks also matched float outputs across frame counts, grayscale/RGB,
binary/soft/empty masks, sigma iterations, and supported normalization dtypes.

Validation used temporary scripts and outputs outside the repository; no test
files were added to the implementation commits. Checks covered cache reuse,
invalidation, corruption, cancellation, unwritable-cache fallback, scratch
round trips and concurrent readers, compression tags, settings persistence,
and offscreen Qt bindings.

## Full-resolution baseline

Fresh alignment was run with the saved transforms cleared in an isolated config.
All 15 frames aligned successfully. No source project or existing outputs were
written. These are individual local runs, not cold-cache statistical estimates.

| Alignment work | Seconds |
| --- | ---: |
| Total Align Stars | 107.3 |
| Build master dark, including staging/integration | 85.5 |
| Decode light frames | 10.9 |
| Subtract dark | 4.1 |
| Detect stars, including reference | 6.4 |
| Match stars | 0.2 |

Master-dark construction accounts for 79.7% of alignment time. Within that
85.5 seconds, dark decoding took 10.5 seconds, scratch writes 33.0 seconds, and
scratch reads 18.5 seconds. The instrumented median calls took 19.9 seconds
including the much smaller star-detection median calls. Nested timings overlap;
they must not be added to their parent totals.

Stacking used the project's saved transforms and produced the normal sky,
ground, base-composite, output-composite, and gradient-mask artifacts in a
temporary directory. Total time was **328.5 seconds (5 minutes 29 seconds)**.
The major wall-time phases, rounded from the progress boundaries, were:

| Stacking phase | Seconds |
| --- | ---: |
| Master-dark preparation | 88.4 |
| Sky loading, calibration, warping, and staging | 66.8 |
| Sky reduction | 43.6 |
| Ground loading, calibration, and staging | 60.1 |
| Ground reduction | 37.4 |
| Fallback, masks, and compositor preparation | 3.3 |
| Encoding/saving outputs | 28.9 |

Within those phases, scratch writes accounted for 116.1 seconds, of which
15.1 seconds were explicit flush calls. Scratch reads accumulated 119.7 seconds
across workers; that is **not** 119.7 seconds of additional wall time. Image
warping itself took just 1.4 seconds for all 15 frames, mask warping 0.3 seconds,
and taper generation 3.6 seconds. The three TIFF encodes took 28.6 seconds.

Peak process RSS was **8.80 GiB**, excluding the GUI and OS file cache. This was
a standalone operation; a GUI retaining prior images/results can need more
memory. The result supports retaining bounded buffers and reducing I/O and
temporary arrays before increasing concurrency.

## Recommended work, in order

### 1. Reuse the master dark across UI actions and repeated runs

`AlignStars.prepare_calibrator()` rebuilds the master on every call. The separate
UI actions for alignment and stacking each call it. The combined
`DenoisePipeline` already shares a calibrator within one pipeline run, but this
does not extend to the separate UI actions or later runs.

Cache the normalized float32 master, keyed by dark file identity, size, mtime,
and calibration algorithm version. A disk cache avoids retaining another
760.5 MiB between actions; a bounded in-session cache can be optional. Invalidate
when any input changes, and publish the cache only after successful completion.
Keep fractional calibrated values and mixed input bit depths supported.

This targets the measured 85.5-second alignment setup and the equivalent setup
in stacking. The remaining fresh-alignment work measured about 21.8 seconds;
that is a potential floor before cache-loading overhead, not a measured optimized
runtime. Removing star matching entirely would save only 0.2 seconds here.

Relevant code: `src/startrails/op/denoise/align_stars.py`,
`src/startrails/lib/denoise/calibration/dark.py`, and
`src/startrails/workflow/denoise.py`.

### 2. Reduce scratch I/O while retaining bounded memory

One stack operation stages 11.14 GiB of darks, 11.14 GiB of sky pixels,
3.71 GiB of tapered coverage, and 11.14 GiB of ground pixels: **37.13 GiB of
logical scratch writes**, plus corresponding reads. This is data volume through
the scratch layer, not a claim about physical SSD traffic after OS caching.

`MemmapFrameBuffer` flushes each roughly 8 MiB mapping before closing it. This
project triggers 4,800 flushes across dark, sky, coverage, and ground staging.
The measured flush time was only 15.1 of the 116.1 seconds spent writing, so
removing flush calls alone cannot eliminate most of the staging cost.
The existing mapping lifetime and scratch budgets were introduced to bound
memory; preserve those properties when experimenting with buffered positional
I/O or less frequent flushes. Measure dirty-page pressure as well as elapsed
time. [NumPy documents flush as writing array changes to the disk file](https://numpy.org/doc/stable/reference/generated/numpy.memmap.flush.html).

A separate scratch-write experiment used four copies of one full-resolution
normalized light frame (2.97 GiB per trial), in A/B/B/A order:

| Writer | First trial | Second trial |
| --- | ---: | ---: |
| Current bounded memory maps | 3.64 s | 11.49 s |
| Bounded `os.pwrite`, `fsync` after each frame | 1.62 s | 1.72 s |

Both writers used the same approximately 8 MiB windows. Every pixel of the
first and last frames was read through the existing buffer reader and matched
exactly. This is evidence to pursue buffered writes, not a measured end-to-end
speedup. The baseline varied substantially with system/cache state, and the
experiment did not measure full-project dirty-page pressure or Windows support.
This experiment preceded the production buffered-I/O change summarized above.

For homogeneous uint16 darks, staging native uint16 and normalizing each read
chunk would halve dark scratch traffic while preserving the current float32
median calculation. Keep a correct path for mixed input dtypes. Reusing a cached
master is still the larger opportunity on subsequent operations.

The light frames are also decoded and calibrated twice during stacking: once
for the sky and again for the ground. Staging ground alongside sky avoids the
second source read and subtraction, but increases peak scratch disk space by
11.14 GiB. It should not require retaining multiple decoded frames in RAM.

Relevant code: `src/startrails/lib/denoise/stacking/disk_buffer.py` (formerly
`memmap_buffer.py`) and
`src/startrails/lib/denoise/stacking/freeze_ground.py`.

### 3. Make intermediate TIFF compression configurable

The sky, ground, and base-composite TIFF encodes consumed 28.6 seconds, or 8.7%
of stacking wall time. The existing saved sky/ground files are roughly 332 MiB
each versus 380 MiB uncompressed, so Deflate saves only about 13% on this data.
Benchmark uncompressed or faster lossless intermediate output, keeping the
chosen final-export behavior. This trades disk space for latency without
changing pixel values. The output composite already copies the encoded base
TIFF when formats match, so a fourth encode is already avoided.

Relevant code: `src/startrails/op/denoise/stack_denoise.py` and
`src/startrails/lib/image_io.py`.

### 4. Reduce temporary allocations before increasing concurrency

CPU stacking uses `min(workers, 2)`, regardless of a larger `max_workers` setting.
The 256 MiB scratch budget and 96-byte-per-sample estimate restrict this project
to **three rows per task**, or 2,219 tasks for each sky/ground reduction. The
buffers repeatedly map 15 frame slices per task, plus 15 coverage slices for sky.

Ground sigma clipping divides float32 sums by int64 counts, promoting the mean,
differences, and variance to float64. Sky clipping repeats scalar pixel weights
across RGB channels, and both paths allocate multiple intermediate arrays per
iteration. Investigate reusable workspaces and broadcast weights. Evaluate a
float32 ground kernel against rejection masks and final pixel differences before
adopting it: threshold decisions can change even when rounding errors are small.

`normalize_image()` also allocates full-frame conversion/division/clipping
temporaries, and calibrated float32 lights are normalized again in the stacker.
Clipping/dividing an owned conversion buffer in place can remove copies without
changing the input array. Verify exact output equality across supported dtypes.

Then benchmark chunk budgets and one/two/four workers. Simply raising the worker
cap at the same memory budget makes chunks smaller and can increase overhead.
Avoid replacing bounded staging with complete in-memory stacks.

Relevant code: `src/startrails/lib/denoise/stacking/freeze_ground.py` and
`src/startrails/lib/image_io.py`.

### 5. Avoid unused work on repeat alignment and outside the horizon band

`AlignStars.align()` reads and calibrates each light before checking for a cached
transform, even with `warp_frames=False`. Move that work behind the check while
preserving the base image/mask expected by callers. A complete cached-alignment
fast path should also avoid preparing calibration when no caller needs pixels.

Only about 1.21% of pixels in the saved gradient mask intersect the sky, but
nonzero pixels span rows 0 through 4665. `HorizonCompositor.__init__()` uses a
full-width vertical bounding box and prepares the guided filter and color
decomposition throughout that box. Sparse halo-padded tiles could avoid much of
this work and reduce memory. However, compositor preparation took only 2.6
seconds here, so this is primarily a memory opportunity, not a leading runtime
target. Match the filter border behavior, feathering, and zero-coverage ground
fallback; limiting work only to a naive rectangular sky/ground split is unsafe.

### 6. Treat Apple GPU support as a separate optimization

For these operations, `use_gpu=True` selects CuPy only if CUDA is available;
otherwise `get_array_module()` returns NumPy. The measured backend was NumPy.
The Apple GPU reported elsewhere by the application's device-info code is not
used by the dark median or sigma-clipped stacker. Star detection/warping also
uses the CPU OpenCV path.

A Metal/MPS implementation is possible future work; PyTorch already provides an
[MPS backend for supported operations on Apple GPUs](https://docs.pytorch.org/docs/2.14/notes/mps.html).
It would need its own stacking kernels, numerical validation, chunk sizing,
synchronization, and shared-memory accounting. Unified memory does not remove
array copies, temporary tensors, or scratch-file I/O in this implementation.
No GPU speedup was measured here, and the diagnostic subprocess reported MPS
unavailable; that result alone does not establish availability in the GUI app.

## Reproducing measurements

```sh
PYTHONPATH=src .venv/bin/python tools/profile_denoise.py \
  projects/2026-08-16.proj_denoise \
  --operation both --output /tmp/denoise-profile.json
```

Use `--operation stack` to profile stacking with saved transforms, or
`--operation align --reuse-alignment` to inspect the current cached-transform
path. Fresh alignment is the default for `align` and `both`. Temporary scratch
and encoded output files are removed after the run. The project's master-dark
cache is reused or populated, and `--output` optionally saves a JSON report.
Use `--no-compress-intermediates` or `--compress-intermediates` to compare output
encoding, and `--max-workers` to compare CPU concurrency. `--verify-existing`
compares every saved uint16 pixel in the sky, ground, and base results against
the project's existing TIFFs; this verification is excluded from operation time.
Timings are inclusive, and parallel read timings
sum worker durations rather than measuring their combined wall time. Run one
benchmark at a time and keep memory pressure comparable between trials.

The profiler was checked with a small synthetic project through fresh alignment,
dark calibration, stacking, output encoding, JSON reporting, and temporary-file
cleanup. Input project/images were hash-checked for preservation. The reference
project's existing stack artifact sizes and modification times still match its
saved records. Repository Ruff checks passed.
