# CLI

## Purpose

`promptcontrollab.cli` is the stable command-line composition layer. It registers commands, validates arguments, resolves project defaults, dispatches to domain APIs, formats human or JSON output, and converts known failures into concise `pcl: error:` messages.

## Use cases

- Discover available workflows through one `pcl` entry point.
- Run domain operations from local terminals, scripts, CI, and adapters.
- Preserve stable flags, defaults, output schemas, and exit behavior while internal modules evolve.
- Offer English and Chinese guidance without changing machine-readable values.

## CLI commands

```bash
pcl --help
pcl start --guide
pcl quickstart --out demo --open-report
pcl choose --need "compare two prompts"
pcl doctor --json
```

Domain commands are documented in the corresponding module README rather than duplicated here.

## Python API

The console entry point remains importable:

```python
from promptcontrollab.cli import build_parser, main

parser = build_parser()
exit_code = main(["doctor", "--json"])
```

`_reconfigure_windows_pipe` remains a compatibility helper for the existing console entry point; leading-underscore helpers are otherwise private.

## Inputs/Artifacts

- Inputs: command arguments, standard input, project configuration, environment variables, and domain-specific files.
- Outputs: terminal text or JSON, domain artifacts, and conventional process exit codes.
- The CLI owns presentation and dispatch; domain modules own artifact semantics.

## Dependencies

Argument parsing uses the Python standard library. A command imports its domain implementation and reports any missing optional extra with an actionable installation message.

## Extension points

- Register a parser and handler in the matching domain command module.
- Reuse shared path, language, JSON, and error-formatting helpers.
- Keep command handlers thin and place business logic in the domain package.

## Limitations

- The CLI is not a second implementation of domain logic.
- Private command helpers are not compatibility APIs.
- Interactive output may evolve, but documented JSON schemas and public flags require explicit compatibility review.

## Tests/Examples

CLI tests cover parser construction, help, errors, Windows pipe behavior, and workflow smoke paths. Run:

```bash
python -m pytest tests -k "cli or quickstart or start or choose or doctor"
```
