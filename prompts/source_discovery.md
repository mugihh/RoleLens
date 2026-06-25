# Source Discovery

Use this prompt when the user wants to discover additional companies or official
career sources that may fit their job-search goals.

Goal: produce a reviewable list of source candidates. Do not directly modify
`config/sources.yaml` unless the user explicitly asks you to.

Allowed research scope:

- Official company websites
- Official careers pages
- Official ATS job boards linked from company websites
- Public company engineering/team pages

Avoid:

- LinkedIn, Indeed, and unofficial aggregators
- Treating salary, visa, sponsorship, or company reputation claims as verified
  facts unless the user explicitly authorized external research and sources are
  cited
- Adding companies just because they are famous if they do not match the user's
  target regions or role goals

Use `candidate/profile.yaml` when available. If it is missing, ask the user for
target regions, target roles, roles to avoid, language preferences, and work
authorization preferences before doing broad discovery.

Preferred output:

```yaml
candidate_sources:
  - name: Example Company
    region: Japan
    careers_url: https://example.com/careers
    ats_type: greenhouse
    source_id: example
    likely_roles:
      - Backend Engineer
      - Machine Learning Engineer
    reason: "Official careers page lists Tokyo engineering roles."
    confidence: medium
    notes: "Needs user review before adding to config/sources.yaml."
```

ATS hints:

- Greenhouse boards often use `boards.greenhouse.io/<source_id>` or
  `job-boards.greenhouse.io/<source_id>`.
- Lever boards often use `jobs.lever.co/<source_id>`.
- Ashby boards often use `jobs.ashbyhq.com/<source_id>`.
- If the ATS cannot be identified, set `ats_type: unknown`.

After presenting candidates, ask the user which sources to add. If approved,
update `config/sources.yaml` with conservative status values:

- `experimental` for sources that appear scrapeable
- `manual_or_experimental` for sources that need manual capture or custom work

Do not add private candidate data to source config.
