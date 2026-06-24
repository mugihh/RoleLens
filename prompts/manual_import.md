# Manual Job Import

Use this prompt when the user gives a job description URL or pasted job text.

Create one Markdown file under `imports/manual/` with YAML frontmatter:

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

If the user only provides a URL, try to read the page only if web access is
available and appropriate. If the page cannot be read, ask the user to paste the
job description text.

Do not include private candidate or CV information in manual import files.
