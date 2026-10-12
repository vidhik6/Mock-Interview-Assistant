# Data sources and licensing

This project uses an internal synthetic supplement plus optional public datasets when present.

- Synthetic supplemental questions: stored in `data/supplemental_hr_behavioral.json` and marked as `source: synthetic`.
- Kaggle: Software Engineering Interview Questions Dataset (syedmharis). Use only when the CSV is present locally; verify the specific license before redistribution.
- Hugging Face: `ali-alkhars/interviews`. Check the dataset card for the license and terms for the snapshot used.

The loader flags missing reference answers and falls back to the supplemental set when a source is absent or incomplete.
