# Controlled GTK memory evidence: Debian 13

Five sequential cases on one disposable Debian 13 VM, 2026-11-08. See the
[analysis and limitations](../../../docs/gtk-memory-investigation.md).

- `summary.json`: all five derived summaries, including observed GTK/GDK renderer
  classes, RSS, PSS, statm RSS, CPU, process/thread counts and screenshot hashes.
- Each case: original 121 observations in `samples.json`; grouped full mappings
  in `start-mappings.json` / `end-mappings.json`; original kernel `smaps` compressed
  losslessly as `*.smaps.gz`; application/display/compositor logs; requested
  configuration, thread snapshot, process cleanup and summary.
- [Screenshots](../../../screenshots/gtk-memory-ab-2026-11-08/debian-13): original
  full-desktop PNGs at both settled endpoints. No cropping or image regeneration.
- `build/`: package/runtime/compiler versions, exact source/binary SHA-256 values,
  compile output, accounting-test output and the original executed source bundle.
- `guest-receipt.json`: original guest exit/duration. `native-terminal.json`:
  original local terminal completion object (stdout was redirected to a task log).
  `controller-phases.log`: generic phase/release lines extracted from that log.

The run built one C executable from source based on `06ffbcb`, with the opt-in
renderer logger. Binary and source hashes are in `build/hashes.txt`. Original
published measurement files were not rewritten. All summaries and mapping groups
were recomputed from the retained originals; all PNG hashes were verified.

`build/executed-inputs.tar.gz` preserves the exact four input files used in the
VM. Its guest launcher used one shared fresh temporary home for the ordinary
`dev` user across all five cases. The subsequent public launcher preserves the
ordinary user's home instead; that launcher adjustment was not executed in this
run. The C application and probe bytes are unchanged. This distinction is retained
rather than relabeling the archived run as a test of later launcher bytes.

Full transport output, the binary, package-install log and the unfiltered artifact
archive remain task artifacts outside Git. The public copies retain the complete
memory evidence; compressed `smaps` decompress byte-for-byte to the originals.
