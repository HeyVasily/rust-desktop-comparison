# Controlled GTK memory evidence: Ubuntu 24.04

[Run 42472650761](https://github.com/HeyVasily/rust-desktop-comparison/actions/runs/42472650761),
source `5096df7e82cd374a98772722f594abd4cfb05398`, succeeded on 2026-11-08.
One compiled binary was measured with X11/default and X11/Cairo on the same
runner. See the [combined analysis](../../../docs/gtk-memory-investigation.md).

Each case retains the uploaded `samples.json` (121 observations), `summary.json`,
requested configuration, application/display/compositor logs, thread snapshot,
cleanup and grouped mappings. Original full `smaps` files are compressed
losslessly as `*.smaps.gz`; decompression reproduces the uploaded bytes.
[Settled start/end PNGs](../../../screenshots/gtk-memory-ab-2026-11-08/ubuntu-24.04)
are unmodified. All other copied artifact files retain their original bytes.

`build/` records runtime/compiler/package metadata, the original two accounting
tests, compile output and source/binary SHA-256 values. The C source and probe
hashes match the Debian experiment; each platform compiled its own binary.
`guest-receipt.json` is the original measurement step receipt (exit 0, 306 seconds).
`run-view.json` is the GitHub completion receipt: every step passed, job duration
344 seconds. The original observer's native watch receipt and complete downloaded
artifact, including the binary, remain outside Git as task evidence.

Summaries were recomputed from raw samples, grouped mappings from full `smaps`,
and every source/binary/PNG hash was checked. Both memory series were constant;
all process scopes contained one app process, with no swap and no recorded CPU
counter increment. The unchanged original 240.27 MiB run did not log its renderer;
this new run does not retroactively fill that missing observation.
