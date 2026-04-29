# Claude Code Prompts

5 free Claude Code prompts I actually use as an indie dev. From a pack of 100.

**👉 Get the full pack: 100 prompts across 10 categories — $9 lifetime**
https://pamandeepsingh.gumroad.com/l/claude-prompts-100

---

## What's in the full pack

10 categories, 10 prompts each:

1. Debugging & error analysis
2. Code review & refactoring
3. Writing tests
4. Git, commits, PRs
5. Documentation
6. Database & SQL
7. API design & integration
8. Performance & profiling
9. Security audits
10. Shipping & deployment

---

## 5 Free Samples

### 1. Trace a stack trace (debugging)

```
Read this stack trace and tell me: (1) the actual root cause, not just the surface symptom, (2) which file/line to fix first, (3) whether this is a one-off or a class of bugs.

{paste stack trace}
```

### 2. Honest code review (refactoring)

```
Review {file path} like a senior engineer who has to maintain this for 3 years. Be direct. Flag: bugs, footguns, naming, missing edge cases, unnecessary cleverness. Skip style nits.
```

### 3. Test the bug, then fix it (testing)

```
Bug: {describe}. First write a failing test that reproduces it. Then fix the bug. Show test output before and after.
```

### 4. Write the PR description (git)

```
Read all commits on this branch since `main`: `git log main..HEAD`. Write a PR description with: Summary (3 bullets), Why now, Test plan, Risks.
```

### 5. SQL injection scan (security)

```
Read {file} and find every place user input reaches a SQL query. Flag any that aren't using parameterized queries. False positives OK — be paranoid.
```

---

## Why a paid pack instead of just open-sourcing?

Because the full 100 took me a year to refine and I'd like coffee money. The 5 above are genuinely useful on their own. If they save you an hour, the $9 pays for itself ten times over.

If you ship code with Claude Code regularly, the full pack pays for itself the first week.

---

## License

Personal & commercial use OK. Don't resell the file or repackage as a course.

## Support

Questions? Open an issue here, or reply to your Gumroad receipt.

---

⭐ Star this repo if any of the 5 prompts saved you time today.
