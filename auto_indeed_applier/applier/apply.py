"""Drive the Indeed Apply ("Easy Apply") multi-step flow for one job.

The Indeed Apply form is a multi-page wizard. We loop, page by page:
  1. Fill every input/textarea/select/radio we recognize on the current step.
  2. Click "Continue" to advance.
  3. Repeat until we reach the "Review"/"Submit" step.
  4. Submit (or stop, depending on config).

Selectors live near the top so they're easy to repair when Indeed changes them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from playwright.sync_api import Page, TimeoutError as PWTimeout

from .browser import human_delay
from .questions import QuestionResolver
from .search import JobPosting

# --- Selectors -------------------------------------------------------------
APPLY_BUTTON_SELECTORS = [
    "#indeedApplyButton",
    "button:has-text('Apply now')",
    "button:has-text('Easy Apply')",
    "[data-testid='indeedApplyButton']",
    "span.indeed-apply-button",
]

CONTINUE_SELECTORS = [
    "button:has-text('Continue')",
    "button:has-text('Next')",
    "button[data-testid='continue-button']",
]

SUBMIT_SELECTORS = [
    "button:has-text('Submit your application')",
    "button:has-text('Submit application')",
    "button:has-text('Submit')",
    "button[data-testid='submit-application']",
]

REVIEW_MARKERS = [
    "text=Review your application",
    "text=Please review",
]


class Outcome(Enum):
    SUBMITTED = "submitted"
    DRAFTED = "drafted"          # filled, stopped before submit (auto_submit=false)
    SKIPPED = "skipped"
    NOT_EASY_APPLY = "not_easy_apply"
    ERROR = "error"


@dataclass
class ApplyResult:
    outcome: Outcome
    detail: str = ""


class Applier:
    def __init__(
        self,
        page: Page,
        profile: dict[str, Any],
        resolver: QuestionResolver,
        behavior: dict[str, Any],
        delays: dict[str, Any],
        screenshot_dir: str,
    ) -> None:
        self.page = page
        self.profile = profile
        self.resolver = resolver
        self.behavior = behavior
        self.delays = delays
        self.screenshot_dir = screenshot_dir
        self.action_delay = (
            float(delays.get("min_action_delay", 1.5)),
            float(delays.get("max_action_delay", 4.0)),
        )

    # -- public ------------------------------------------------------------
    def apply_to(self, job: JobPosting) -> ApplyResult:
        try:
            self.page.goto(job.url, wait_until="domcontentloaded", timeout=45_000)
            human_delay(*self.action_delay)

            apply_btn = self._find_first(self.page, APPLY_BUTTON_SELECTORS)
            if not apply_btn:
                return ApplyResult(Outcome.NOT_EASY_APPLY,
                                   "No Indeed Apply button (external application).")

            apply_btn.click()
            human_delay(*self.action_delay)

            form = self._form_root()
            return self._walk_form(form, job)

        except PWTimeout as exc:
            self._screenshot(job, "timeout")
            return ApplyResult(Outcome.ERROR, f"timeout: {exc}")
        except Exception as exc:  # noqa: BLE001 — we want to keep the run alive
            self._screenshot(job, "error")
            return ApplyResult(Outcome.ERROR, f"{type(exc).__name__}: {exc}")

    # -- form walking ------------------------------------------------------
    def _form_root(self):
        """The Indeed Apply form often renders inside an iframe."""
        for _ in range(10):
            for frame in self.page.frames:
                if "indeed" in (frame.url or "") and "apply" in (frame.url or ""):
                    return frame
            self.page.wait_for_timeout(500)
        return self.page  # fall back to the main page

    def _walk_form(self, root, job: JobPosting) -> ApplyResult:
        max_steps = 25  # guardrail against infinite loops
        for _step in range(max_steps):
            root = self._form_root()  # iframe ref can change between steps
            self._fill_current_step(root)
            human_delay(*self.action_delay)

            # Are we at the final submit?
            submit_btn = self._find_first(root, SUBMIT_SELECTORS)
            if submit_btn:
                if not self.behavior.get("auto_submit", False):
                    self._screenshot(job, "review")
                    return ApplyResult(Outcome.DRAFTED,
                                       "Reached review step; auto_submit is off.")
                if self.behavior.get("screenshot_each", True):
                    self._screenshot(job, "pre_submit")
                submit_btn.click()
                human_delay(*self.action_delay)
                if self._looks_submitted(root):
                    return ApplyResult(Outcome.SUBMITTED, "Application submitted.")
                return ApplyResult(Outcome.ERROR,
                                   "Clicked submit but no confirmation detected.")

            # Otherwise advance.
            cont = self._find_first(root, CONTINUE_SELECTORS)
            if not cont:
                # Nothing to continue and no submit: likely a required field we
                # couldn't fill (e.g. unanswerable question) or an unknown step.
                if self._has_unanswered_required(root):
                    if self.behavior.get("on_unanswered_required") == "skip":
                        return ApplyResult(Outcome.SKIPPED,
                                           "Required question we couldn't answer.")
                self._screenshot(job, "stuck")
                return ApplyResult(Outcome.ERROR, "No Continue/Submit button found.")

            cont.click()
            human_delay(*self.action_delay)

        return ApplyResult(Outcome.ERROR, "Exceeded max form steps.")

    # -- field filling -----------------------------------------------------
    def _fill_current_step(self, root) -> None:
        self._maybe_upload_resume(root)
        self._fill_text_inputs(root)
        self._fill_textareas(root)
        self._fill_selects(root)
        self._fill_radio_groups(root)
        self._fill_checkboxes(root)

    def _fill_text_inputs(self, root) -> None:
        inputs = root.query_selector_all(
            "input[type='text'], input[type='email'], input[type='tel'], "
            "input[type='number'], input:not([type])"
        )
        for inp in inputs:
            try:
                if not inp.is_visible() or not inp.is_editable():
                    continue
                if (inp.input_value() or "").strip():
                    continue  # already prefilled
                label = self._label_for(root, inp)
                answer = self.resolver.answer_for(label).value
                if answer:
                    inp.fill(answer)
            except Exception:
                continue

    def _fill_textareas(self, root) -> None:
        for area in root.query_selector_all("textarea"):
            try:
                if not area.is_visible() or (area.input_value() or "").strip():
                    continue
                label = self._label_for(root, area)
                ans = self.resolver.answer_for(label)
                value = ans.value
                if not value and ("cover" in label.lower() or "why" in label.lower()):
                    value = self.profile.get("cover_letter", "")
                if value:
                    area.fill(value)
            except Exception:
                continue

    def _fill_selects(self, root) -> None:
        for sel in root.query_selector_all("select"):
            try:
                if not sel.is_visible():
                    continue
                label = self._label_for(root, sel)
                target = self.resolver.answer_for(label).value
                if not target:
                    continue
                options = sel.query_selector_all("option")
                for opt in options:
                    text = (opt.inner_text() or "").strip().lower()
                    if target.lower() in text:
                        sel.select_option(value=opt.get_attribute("value"))
                        break
            except Exception:
                continue

    def _fill_radio_groups(self, root) -> None:
        """Indeed renders screening questions as fieldsets of radios."""
        for fieldset in root.query_selector_all("fieldset"):
            try:
                legend = fieldset.query_selector("legend")
                question = legend.inner_text().strip() if legend else ""
                if not question:
                    continue
                target = self.resolver.answer_for(question).value
                if not target:
                    continue
                # Click the option label whose text best matches the answer.
                clicked = self._click_matching_option(fieldset, target)
                if not clicked:
                    # Yes/No fallback.
                    self._click_matching_option(fieldset, "Yes" if target.lower()
                                                in ("yes", "true", "1") else "No")
            except Exception:
                continue

    def _fill_checkboxes(self, root) -> None:
        """Tick standalone required consent checkboxes."""
        for box in root.query_selector_all("input[type='checkbox']"):
            try:
                if not box.is_visible() or box.is_checked():
                    continue
                label = self._label_for(root, box).lower()
                if any(k in label for k in ("agree", "consent", "terms", "certify",
                                            "acknowledge")):
                    box.check()
            except Exception:
                continue

    def _click_matching_option(self, scope, target: str) -> bool:
        for label in scope.query_selector_all("label"):
            text = (label.inner_text() or "").strip().lower()
            if target.lower() in text:
                try:
                    label.click()
                    return True
                except Exception:
                    continue
        return False

    # -- resume ------------------------------------------------------------
    def _maybe_upload_resume(self, root) -> None:
        resume = self.profile.get("resume_path")
        if not resume or not os.path.exists(resume):
            return
        for finput in root.query_selector_all("input[type='file']"):
            try:
                finput.set_input_files(resume)
                human_delay(*self.action_delay)
            except Exception:
                continue

    # -- helpers -----------------------------------------------------------
    def _label_for(self, root, element) -> str:
        """Best-effort accessible label for a form control."""
        for getter in ("aria-label", "placeholder", "name", "id"):
            val = element.get_attribute(getter)
            if val and getter in ("aria-label", "placeholder"):
                return val
        # <label for="id">
        el_id = element.get_attribute("id")
        if el_id:
            lbl = root.query_selector(f"label[for='{el_id}']")
            if lbl:
                return lbl.inner_text().strip()
        # Nearest enclosing label / preceding text
        try:
            handle = element.evaluate_handle(
                "el => el.closest('label') || el.closest('[role=group]') "
                "|| el.parentElement"
            )
            text = handle.evaluate("n => n ? n.innerText : ''")
            if text:
                return text.strip()
        except Exception:
            pass
        return element.get_attribute("name") or ""

    def _has_unanswered_required(self, root) -> bool:
        # Indeed marks errors with role=alert or aria-invalid after a failed step.
        if root.query_selector("[aria-invalid='true']"):
            return True
        if root.query_selector("[role='alert']"):
            return True
        return False

    def _looks_submitted(self, root) -> bool:
        for marker in [
            "text=application has been submitted",
            "text=Application submitted",
            "text=You've applied",
            "text=has been sent",
        ]:
            try:
                if self.page.query_selector(marker):
                    return True
            except Exception:
                pass
        return False

    def _find_first(self, scope, selectors):
        for sel in selectors:
            try:
                el = scope.query_selector(sel)
                if el and el.is_visible():
                    return el
            except Exception:
                continue
        return None

    def _screenshot(self, job: JobPosting, tag: str) -> None:
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            safe = "".join(c for c in job.job_id if c.isalnum())[:24]
            path = os.path.join(self.screenshot_dir, f"{safe}_{tag}.png")
            self.page.screenshot(path=path, full_page=True)
        except Exception:
            pass
