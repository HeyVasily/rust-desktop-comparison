# Optional desktop results: schema 1

`site/app.js` loads `data/desktop-results.json` independently of the historical
CSV. An absent file, failed request, malformed JSON or unsupported schema leaves
the static desktop-profile notice and historical page intact. Do not commit a
placeholder measurement file.

Generate the file only from a real imported series:

```sh
python3 tools/build_desktop_site_data.py measurements/SERIES
# Check the committed site data against its source series without rewriting it:
python3 tools/build_desktop_site_data.py measurements/SERIES --check
# Or write a review copy elsewhere:
python3 tools/build_desktop_site_data.py measurements/SERIES --output out/desktop-results.json
```

The input is the importer's `summary.csv`, `desktop-acceptance.csv` and
`paired-egui-ab.json`, with imported raw evidence under `measurements/native-RUN`.
The generator does not re-run the importer or manufacture samples. It preserves
CSV values as strings, including zeros and precision, and preserves A/B JSON
numbers without recalculating or merging summaries. Diagnostic/minimized and
historical results are not promoted to current primary measurements.

## Data contract

| Field | Type and meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `series` | Repository-relative imported series directory |
| `sources` | Array of `{label, url}` links to the three input files |
| `limitations` | Array of plain-text interpretation limits |
| `platforms` | Linux, Windows and macOS entries, even when no result exists |
| `platforms[].id`, `.name` | Stable OS identifier and display name |
| `platforms[].candidates` | All five expected desktop candidates |
| `candidates[].framework`, `.name` | Importer framework ID and current-profile display name |
| `candidates[].experiments` | One entry per exact runner/run/source/build/image identity; empty means missing evidence |
| `experiments[].identity` | `os`, `run_id`, `source_commit`, `source_hash`, `source_manifest_sha256`, `build_inputs_sha256`, `image_version` |
| `experiments[].measurements` | Unchanged primary desktop `comparison` summary rows; empty means not measured, never zero MiB |
| `experiments[].invocations` | Unchanged acceptance CSV rows, plus `links` to existing outcomes, check JSON and any retained per-invocation screenshots (the current importer retains none) |
| `experiments[].acceptance` | Derived overall status, individual check states, normal and dark-startup invocation counts |
| `experiments[].links` | Verified-format GitHub run/source URLs; not a claim that the run passed |
| `paired_ab` | Comparison-phase A/B summary rows with `platform` and `source_url`; absence means no eligible paired result |

`acceptance.status` is `fully_verified`, `failed`, `environment_error`,
`incomplete` or `not_run`. Its check fields are `startup_light`, `startup_dark`,
`live_theme`, `clipboard`, `cleanup` (settings), `process_cleanup`, `evidence`,
`provenance` and `repetition_coverage`. A fully verified label needs all checks passed, clean native
process cleanup, a normal light-start invocation, a **separate dark-startup**
invocation, complete imported evidence and the same nonempty source/build/run
identity (valid commit and build/source digests, run ID and runner image).
Separate commits or build inputs never fill each other's missing tests.
Environment failures and incomplete evidence remain visible.

`normal_repetitions` and `dark_repetitions` are the sorted observed repetition
numbers for light normal and dark-startup cases. `repetition_coverage` passes only
when both sets are nonempty and identical, with no duplicate `(case, repetition)`.
`missing_cases` contains `{case, repetition}` records for a missing counterpart;
`duplicate_cases` adds `count` for repeated invocations of the same case. A normal
case in r2 with dark cases in r1/r2/r3 remains incomplete, while its valid memory
observation remains n=1. These fields describe observed coverage, not an inference
that a requested job with no artifact ran.

Memory `n` is the number of eligible measured comparison invocations. Acceptance
invocation counts are displayed separately: a successful smoke test can have
fully verified acceptance and **no memory measurement**. Conversely, a valid
light-start measurement can coexist with a failed separate dark-start check;
the site retains the numbers and exposes that failure instead of claiming full
verification.

Snapshot URLs are emitted only for imported files that exist. The renderer uses
these provided links, not guessed image paths. Text is rendered as text content,
not injected HTML. Memory metrics stay named and are not directly comparable
across OSes. Paired deltas describe the entire configured egui profile difference
after use, not the allocation of the clipboard feature alone.
