# A general `diagnose` skill

There is no open-ended debugging skill.

## Why this is out of scope

It went unused in real projects. The two needs it covered have narrower homes: what a model's evaluation results mean is a
`diagnosis-card`, and improving a model in rounds is a map from the `to-diagnosis-map` preset. Debugging code inside a
ticket is ordinary ticket work under `rigor`.

## Prior discussion

- 2026-10: dropped; `diagnosis-record` was renamed `diagnosis-card` and split from the `to-diagnosis-map` preset.
