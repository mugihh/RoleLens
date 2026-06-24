# Update And Review

This workflow prepares jobs for agent review and imports structured review
results.

V1 target flow:

1. Run `rolelens setup-check`.
2. Run `rolelens update` when source scanning exists.
3. Review files exported under `review_queue/`.
4. Write one JSON review result per job under `review_results/`.
5. Run `rolelens import-reviews review_results/` when review import exists.
6. Run `rolelens report` when personal report generation exists.

Current local workflow:

1. Run `rolelens setup-check`.
2. Use `prompts/manual_import.md` for manually captured jobs.
3. Run `rolelens import-manual imports/manual/`.
4. Use the schema in `src/rolelens/models.py` when drafting review JSON.

Review policy:

- Use `candidate/profile.yaml` first.
- Use `candidate/cv.md` only as private context.
- Do not copy CV details into public reports.
- Do not perform external salary, visa, or company research unless the user explicitly authorizes it.
- Leave `external_research` empty unless external research was explicitly authorized.
