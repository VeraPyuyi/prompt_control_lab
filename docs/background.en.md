# Background

Prompt engineering often reports that one prompt scores higher than another, but the score alone
does not explain whether the change is reliable.

Common risks include:

- Repeatedly tuning on validation data and mistaking a validation artifact for progress.
- Mixing train, validation, and withheld examples.
- Looking only at the average score while a task slice regresses.
- Training a soft prompt that works well, then losing behavior when it is projected to hard tokens.
- Changing a prompt without checking whether hidden-state trajectories become more unstable.

PromptControlLab turns these risks into inspectable steps. It does not only ask "what is the
score?" It also asks:

- Was the data split clean?
- Is the prompt change statistically reliable?
- Which slices improved or regressed?
- Is soft-to-hard deployment risky?
- Did the hidden trajectory become more stable or more drifting?
- Does a time-varying prompt help because of temporal structure?

It is designed for prompt optimization research, reproducible experiments, local prompt regression
testing, soft prompt deployment analysis, and open-model hidden-state diagnostics.

