# Update And Review

This workflow prepares jobs for agent review and imports structured review
results.

Current V1 workflow:

1. Run `rolelens setup-check`.
2. Run `rolelens update`.
3. Review files exported under `review_queue/`.
4. Follow `prompts/reviewer.md` for each queued job.
5. Write one JSON review result per job under `review_results/`.
6. Run `rolelens import-reviews review_results/`.
7. Run `rolelens report`.

Useful commands:

```bash
rolelens setup-check
rolelens update
# agent reviews review_queue/*.prompt.md
rolelens import-reviews review_results/
rolelens report
```

Manual and custom sources:

- Use `prompts/manual_import.md` when the user pastes one JD.
- Use `prompts/source_capture.md` when the user points to an official careers
  page that RoleLens does not scrape directly.
- Use `prompts/source_discovery.md` when the user wants to discover additional
  source candidates before adding them to `config/sources.yaml` or a private
  `config/sources.local.yaml`.

Review policy:

- Use `candidate/profile.yaml` first.
- Use `candidate/cv.md` only as private context.
- Do not copy CV details into public reports.
- Do not perform external salary, visa, or company research unless the user explicitly authorizes it.
- Leave `external_research` empty unless external research was explicitly authorized.
- Treat `review_queue/*.job.json` as the source of truth for JD text and metadata.
- Do not edit `reports/latest.*` directly; regenerate with `rolelens report`.
