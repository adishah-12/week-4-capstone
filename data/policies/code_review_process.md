# Code Review Process

## Purpose
Code review ensures code quality, shares knowledge across the team, and catches
defects before they reach production.

## When a Review Is Required
Every change to a shared branch (main, release/*, staging) requires at least
one approving review before merge. Direct pushes to these branches are disabled
at the repository level.

## Opening a Pull Request
- Keep pull requests focused: one logical change per PR. Large refactors should
  be split into reviewable steps where possible.
- Include a description of what changed and why, not just what changed.
- Link the related ticket or issue.
- Ensure automated tests and linting pass before requesting review — reviewers
  should not be the first line of defense for broken builds.

## Reviewer Responsibilities
- Respond to review requests within one business day.
- Focus first on correctness and design, then on style and naming.
- Distinguish blocking comments ("must fix before merge") from suggestions
  ("consider this, but not required").
- Approve once concerns are addressed, or explicitly request changes with
  actionable feedback — avoid leaving a PR in limbo.

## Author Responsibilities
- Respond to feedback rather than merging around it.
- If you disagree with a comment, discuss it in the PR rather than silently
  ignoring it or overriding the reviewer.
- Re-request review after making substantive changes.

## Merge Requirements
- At least one approval from someone other than the author.
- All CI checks passing (tests, linting, type checks).
- No unresolved blocking comments.
- Squash or rebase merges are preferred to keep history readable.

## Emergency Hotfixes
Production-down hotfixes may be merged with a single expedited review, but
must still go through the standard review process retroactively within
24 hours, and the incident must be documented.
