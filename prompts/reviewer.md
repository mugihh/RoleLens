# Reviewer

Review one RoleLens job from `review_queue/*.prompt.md` and write exactly one
structured JSON result under `review_results/`.

Before reviewing:

1. Read `candidate/profile.yaml` if available.
2. Read `candidate/cv.md` if available.
3. If `candidate/cv.md` is missing but a TeX/PDF resume exists under
   `candidate/`, ask whether to convert it to `candidate/cv.md` before review.
4. Read the matching `review_queue/*.job.json` as the source of truth for job
   metadata and full JD text.

Privacy and research policy:

- Do not copy private CV details into public reports.
- Do not perform external salary, visa, sponsorship, or company research unless
  the user explicitly authorizes it.
- If external research is not authorized, leave `external_research` empty.
- If external research is authorized, cite sources in `external_research` and
  describe findings as signals, not verified facts.

Judgment rubric:

This rubric is intentionally preference-sensitive. Interpret labels such as
`real coding role`, `customer-facing`, `good fit`, and `avoid` through the
candidate preferences in `candidate/profile.yaml`. The user should review and
customize this section before relying on review results.

- Is this actually a coding role?
- What kind of role is it: product, platform, infrastructure, research,
  customer-facing, support, sales engineering, management, or something else?
- How much long-term code ownership is implied?
- Does it involve production systems?
- Which candidate preferences does this role match or conflict with?
- Which candidate experience from `candidate/cv.md` is relevant?
- Is the seniority realistic for the candidate?
- What should the candidate prepare before applying?

Categories:

- `A`: priority apply
- `B`: conditional
- `C`: avoid by default

Output path:

```text
review_results/<job_id>.review.json
```

Output schema:

```json
{
  "job_id": "abc123",
  "reviewed_at": "YYYY-MM-DD",
  "category": "A",
  "fit_score": 86,
  "role_type": "Product ML Engineer",
  "is_real_coding_role": true,
  "coding_intensity": "high",
  "customer_facing_level": "low",
  "reasons": ["Reason grounded in the JD"],
  "risks": ["Risk or tradeoff grounded in the JD"],
  "prep_actions": ["Concrete prep action"],
  "cv_tweaks": ["Small, specific CV edit to tailor the resume for this role"],
  "dimensions": {
    "nlp_relevance": "high",
    "ml_relevance": "high",
    "english_friendliness": "unknown",
    "visa_or_pr_relevance": "unknown",
    "compensation_signal": "unknown"
  },
  "compensation_notes": "No salary research performed.",
  "external_research": []
}
```

Use `high`, `medium`, `low`, or `unknown` for intensity and custom dimension
values when possible.

For category `A` (priority apply) jobs, fill `cv_tweaks` with 2-4 small, specific
edits to tailor the candidate's CV for THIS role: surface a relevant project or
experience, reword a bullet toward the JD's keywords, reorder skills, or add a
keyword the JD emphasizes that the candidate legitimately has. Keep them honest
(no fabricated experience) and concrete enough to act on. For `B`/`C` jobs,
`cv_tweaks` may be left empty.
