---
description: Search the live OpenRouter catalog by name, id, or company
argument-hint: nemotron
allowed-tools: Bash
---

Search the live OpenRouter model catalog for: $ARGUMENTS

Immediately run:

```bash
py -3 "$HOME/.cc-bridge/refresh_clo_models.py" --search $ARGUMENTS
```

If that path is missing, run:

```bash
py -3 "$HOME/github-tools/multi-agentic-harness/gateway/refresh_clo_models.py" --search $ARGUMENTS
```

Show the matching ids. Tell the user to `/model` and paste an id, or open `/model` and press `/` to type-filter the picker. Do not switch models yourself.
