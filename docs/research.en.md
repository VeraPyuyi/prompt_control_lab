# Research evidence workspace

Install the preview with `python -m pip install "./promptcontrollab-0.3.0a2-py3-none-any.whl[ui,research]"`,
then run `pcl ui --runs runs --language en`. The wheel includes the interface and
synthetic examples; using it does not require Node or a source checkout.

## First analysis

1. Open **Research** and select a tool. Choose **Load a synthetic example** to
   learn without model calls, or upload your saved evidence.
2. Read the capability summary. Raw records can support local reconstruction;
   saved scores can support a defined statistical replay; saved tables support
   descriptive display. Missing provenance remains visible.
3. Select analyses and run. Completed suites are retained. Cancel stops the
   current owned calculation; resume restarts an unfinished suite from the same
   frozen inputs and seed. History also exposes work interrupted by process exit.
4. Read the explanations and download JSON, CSV, English/Chinese HTML, or the
   replay ZIP. Import that ZIP into another workspace to recompute its selected
   analyses. The HTML embeds its figures and does not require the original server.

The interface separates source integrity, numerical agreement, statistical
support, protocol assumptions and practical value. A negative or undefined
result remains a result. An interval containing zero does not establish
equivalence; an integrity hash does not establish a historical prediction lock.

## What the tools answer

| Tool | Main question |
| --- | --- |
| Readout and execution | Did answers, parsing, scoring ranks or execution conditions change? |
| Control response | What local response is measured, and which stages used labels? |
| Measurement value | Does the observed benefit justify the complete recorded cost? |
| Transfer prediction | Does the result persist on new questions or unseen prompts? |
| Replay and properties | Which files, numbers, protocol conditions and local premises can be checked? |

Version 2 accepts explicit raw-record or saved-summary documents. Numeric and
A–E multiple-choice parsers have separate versions. Fixed-score violations are
reported alongside observations instead of discarding execution differences.
Five-fold selection averages within-pair/fold AUCs; scores from different folds
are not pooled. Unknown costs stay unknown, and incomplete batches receive no
discovery credit. Primitive timing is not presented as measured strategy benefit.

See the [complete input contracts and synthetic examples](../examples/research/a2/README.md).
Legacy version 1 inputs and the five original CLI commands remain supported.

## CLI and local API

```bash
pcl research import --input evidence.zip --runs runs
pcl research run --bundle-id BUNDLE_ID --runs runs
pcl research status JOB_ID --runs runs
pcl research cancel JOB_ID --runs runs
pcl research resume JOB_ID --runs runs
pcl research export JOB_ID --runs runs
```

Import prints the bundle ID; run prints the job record. Alternatively provide
`--spec analysis.json` containing `schema_version: "pcl.research-analysis/v1"`,
`bundle_id`, and a subset of the imported bundle's `analyses`. A changed selection
creates a new job; resume preserves the previous specification.

The local API exposes `/api/research-bundles` and `/api/research-jobs`, with
`/{id}/events`, `/{id}/cancel`, `/{id}/resume` and `/{id}/artifacts/{filename}`
under research jobs. Upload the file bytes to
`POST /api/research-bundles?filename=evidence.zip` using the current local
`X-PCL-Session` token. Research analysis never invokes uploaded commands or model APIs.

Research jobs share the experiment queue and single-active lease. One CPU child
executes one suite at a time, with numerical-library threads limited to one.
This stays within the two-worker ceiling and avoids overlapping resampling suites.

## Input and evidence boundaries

- UTF-8 JSON/CSV, non-object NPZ and ZIP data are supported. Uploads are at most
  64 MiB; aggregate decoded data are at most 512 MiB; archives contain at most
  10,000 members. CSV cells follow the Python reader's field-size limit.
- Paths, links, array headers and sizes are checked. Script/HTML archive members
  are not executed or embedded. Credential fields must be removed before import.
- Input files are copied into the selected workspace. Analysis does not rewrite
  the supplied source. Export includes the supplied data and committed results;
  review the material before sharing it with others.
- Recognized retained supporting tables are shown as saved summaries. Table
  previews are bounded; the original data remain in the replay bundle.
- The separate frozen statistical protocol uses 20,000 shared draws, its original
  seeds and 18/24/22 correction families. It covers 52 primary intervals when all
  required suites are present. Expected values are read only after computation.
  Changing scientific settings requires a separately versioned protocol.
- The public preview is read-only. New real research inputs and real model
  acceptance materials are not shipped. Public examples are synthetic.

The five-person first-use study remains a separate pending acceptance item;
automated tests and the offline walkthrough do not substitute for participants.
