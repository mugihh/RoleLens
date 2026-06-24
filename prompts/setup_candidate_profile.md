# Setup Candidate Profile

Help the user create `candidate/profile.yaml` from their job-search preferences.

Use `candidate/profile.example.yaml` as the starting structure. Ask for the
required basics first:

- Target regions
- Target roles
- Roles to avoid
- Priority companies or sources
- Language preferences
- Visa or work authorization preferences
- Compensation importance
- Remote or hybrid preferences

Then ask whether they want optional customization:

- Custom review dimensions
- Report display preferences
- Scoring weights for future use
- Special red flags
- Special green flags
- Whether external salary, company, or visa research is desired when explicitly authorized

Candidate CV context:

- If `candidate/cv.md` already exists, use it as the private candidate CV context.
- If the user provides a TeX or PDF resume under `candidate/`, help convert it
  into `candidate/cv.md` before review workflows. The source filename may vary.
- The generated `candidate/cv.md` should be a clean Markdown summary of the resume:
  education, experience, projects, skills, and relevant technical context.
- Do not put job-search preferences in `candidate/cv.md`; preferences belong in
  `candidate/profile.yaml`.
- The CLI does not parse TeX or PDF resumes. Resume conversion is an agent-assisted
  setup task.

Privacy rules:

- Do not commit `candidate/profile.yaml`.
- Do not commit `candidate/cv.md` or private resume source files such as TeX/PDF resumes.
- Do not copy private CV content into public reports.
- Do not browse for salary, visa, or company research unless the user explicitly authorizes it.
