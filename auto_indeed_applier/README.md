# Auto Indeed Applier

A Python + [Playwright](https://playwright.dev/python/) bot that searches Indeed,
filters jobs against your rules, auto-fills the **Indeed Apply** ("Easy Apply")
forms from your profile, answers screening questions, and submits — keeping a
record so it never applies to the same job twice.

> ⚠️ **Read this first.** Automated access violates
> [Indeed's Terms of Service](https://www.indeed.com/legal), and Indeed uses
> aggressive bot detection (CAPTCHA, device fingerprinting, rate limiting).
> Running this — especially fully automatic submission — can get your account
> **rate-limited, suspended, or banned**, and may send low-quality applications
> to real employers. Use a small `max_applications_per_run`, run it
> infrequently, watch it work (`headless: false`), and **always do a
> `--dry-run` first.** You are responsible for everything it submits under your
> name. This is provided for educational/personal use.

---

## How it works

```
config.yaml ──► search Indeed ──► filter jobs ──► open Indeed Apply
                                                         │
                   record in applications.csv ◄── fill form, answer
                                                  questions, upload
                                                  resume, submit
```

- **One login, reused.** You log in once interactively; the session is saved
  under `user_data/` (gitignored) and reused on every run. No passwords are
  ever stored in config.
- **Deterministic answers.** Screening questions are answered from keyword
  rules in your config — no LLM, so it's predictable and auditable. (You can
  extend `applier/questions.py` to call an LLM if you want.)
- **Never double-applies.** Every job is recorded in `applications.db` /
  `applications.csv` by Indeed job id.

---

## Setup

```bash
cd auto_indeed_applier
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.example.yaml config.yaml
#   then edit config.yaml: your profile, resume path, searches, and answers
```

Put your resume PDF somewhere (e.g. `resumes/your_resume.pdf`) and point
`profile.resume_path` at it.

---

## Usage

```bash
# 1. Log in to Indeed once. A browser opens; sign in (handle 2FA/CAPTCHA),
#    then press ENTER in the terminal.
python main.py login

# 2. DRY RUN — fills every form but never clicks submit. Do this first and
#    watch what it does. Check screenshots/ and applications.csv afterwards.
python main.py run --dry-run

# 3. For real. Honors `behavior.auto_submit` in your config.
python main.py run
```

Useful flags: `--config path.yaml`, `-v` (verbose/debug logging).

---

## Configuration highlights

See [`config.example.yaml`](./config.example.yaml) for the fully-commented file.

| Section | What it controls |
|---|---|
| `search` | queries, location, recency, salary, Easy-Apply-only |
| `filters` | title block/allow lists, company blocklist |
| `limits` | max applications/run, scan depth, human-like delays |
| `behavior` | `auto_submit`, what to do on unanswerable questions, screenshots, headless |
| `profile` | name, contact, resume path, default cover letter |
| `screening_answers` | keyword→answer rules for screening questions |

**Key safety knobs:**

- `behavior.auto_submit: false` → fills everything and stops at the review
  screen for you to submit by hand. The safest mode.
- `behavior.on_unanswered_required: "skip"` → if it hits a required question it
  can't confidently answer, it abandons that application rather than guessing.

---

## When selectors break

Indeed changes its HTML often. When something stops working, the selectors are
isolated in two files:

- `applier/search.py` — job-card / search-result selectors
- `applier/apply.py` — apply button, form fields, continue/submit selectors

Run with `-v` and `headless: false` to see where it gets stuck; screenshots of
failures land in `screenshots/`.

---

## What's intentionally NOT here

- No password storage or credential automation (you log in yourself).
- No CAPTCHA solving / fingerprint spoofing services.
- No mass-blasting: per-run caps and delays are on by default.

---

## Project layout

```
auto_indeed_applier/
├── main.py                 # CLI entry point
├── config.example.yaml     # copy to config.yaml
├── requirements.txt
└── applier/
    ├── config.py           # load & validate config
    ├── browser.py          # Playwright persistent session
    ├── search.py           # build search URLs, collect & filter jobs
    ├── questions.py        # answer screening questions from rules
    ├── apply.py            # drive the Indeed Apply form wizard
    ├── tracker.py          # SQLite + CSV record of applications
    └── runner.py           # orchestration
```

## License / disclaimer

Provided as-is for personal and educational use. Using it is at your own risk
and may breach Indeed's Terms of Service. The authors are not responsible for
account actions, missed/incorrect applications, or any other consequences.
