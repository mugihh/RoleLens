# Source Capture

Use this prompt when the user wants to capture jobs from an official company
careers page that RoleLens does not scrape directly yet.

Goal: create RoleLens-compatible import files under `imports/manual/` so the
jobs can enter the normal workflow:

```bash
rolelens import-manual imports/manual/
rolelens update
```

Allowed sources:

- Official company careers pages
- Official ATS job pages linked from the company site
- User-pasted job description text

Avoid:

- LinkedIn, Indeed, and unofficial aggregators
- Guessing missing job description content
- Adding salary, visa, sponsorship, or company claims unless the user explicitly
  authorizes external research
- Copying candidate profile or CV details into import files

Preferred output is one Markdown file per job:

```md
---
company: Example Company
title: Software Engineer
location: Tokyo, Japan
url: https://example.com/job
source: manual
---

Full job description text goes here.
```

Required fields:

- `company`
- `title`
- `location`
- `url`
- full job description body

If a page cannot be read, ask the user to paste the JD text. If several jobs are
captured from the same page, create separate import files and avoid duplicate
URLs.
