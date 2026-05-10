# Innovation and Contribution

PromptControlLab is not another script that only prints an average score. Its contribution is to
turn prompt evaluation into a fuller diagnostic workflow.

## 1. From Single Scores to Reproducible Protocols

The toolkit records train/validation/withheld splits, split hashes, leakage checks, and run
manifests.

Contribution: cleaner prompt optimization reports with less validation overfitting and test
leakage.

## 2. From Average Scores to Statistical Reliability

The toolkit includes paired bootstrap, paired permutation tests, and Holm correction.

Contribution: prompt changes can be treated more like regression tests instead of one-off score
comparisons.

## 3. Systematic Soft-to-Hard Risk

Soft prompt research often needs to explain whether learned vectors can be projected to hard
tokens. PromptControlLab reports nearest-token projection gaps as a standard diagnostic.

Contribution: clearer deployment risk reporting for soft prompts and better study of embedding
geometry.

## 4. Hidden-State Trajectories as Diagnostic Objects

The toolkit imports hidden-state trajectories and reports drift, decay slope, and turnpike-like
signals.

Contribution: prompt evaluation can inspect internal dynamics in addition to output scores.

## 5. Riccati Surrogate Diagnostics

The toolkit checks stability on finite-dimensional Riccati/DARE surrogates and states the boundary
clearly: this is a surrogate diagnostic, not a proof about a full language model.

Contribution: reusable interfaces for LLM control, prompt control, and trajectory diagnostics.

## 6. Time-Varying Soft-Control Lane

The toolkit compares static, time-varying, shuffled, and random method groups in one artifact
format.

Contribution: more systematic mechanism checks for time-varying prompts.

## Overall Contribution

PromptControlLab helps move the field toward:

- more reproducible prompt optimization;
- more engineering-oriented prompt regression testing;
- more measurable soft prompt deployment risk;
- routine hidden-state trajectory diagnostics;
- prompt engineering that can grow into prompt control engineering.

