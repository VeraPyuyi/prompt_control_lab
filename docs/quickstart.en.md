# Five-minute quickstart

This quickstart creates a complete local report without an API key, model download, or agent execution.

## 1. Install the current source

```bash
python -m pip install -e ".[ui]"
```

Result: the `pcl` command and optional local dashboard become available.

## 2. Generate the demo

```bash
pcl quickstart --out demo --open-report
```

Result: `demo/` contains the fixed dataset, baseline and candidate predictions, reproducible split, metrics, paired statistics, gate result, explanations, and HTML report.

What it means: the command demonstrates the complete artifact contract. Its synthetic fixture verifies the workflow; it is not evidence that one prompt universally improves another.

## 3. Inspect the decision

Open `demo/runs/quick/report.html`, or run:

```bash
pcl ui --runs demo/runs
```

Check four questions in order:

1. What was observed?
2. What can the evidence explain?
3. What does it not prove?
4. What should happen next?

## 4. Apply the same flow to real evidence

```bash
pcl evidence scan --root /path/to/evidence --profile prompt-reach-v2 --out manifest.json
pcl evidence import --manifest manifest.json --out runs/prompt-reach-v2 --portable
```

The scanner reads allowlisted structured evidence and records hashes. It does not execute source experiments or deserialize untrusted model checkpoints.

For checkpoint comparison, continue with the [post-training guide](posttraining.en.md). For an agent lifecycle, continue with the [DeepSeek Harness guide](deepseek_harness.en.md).
