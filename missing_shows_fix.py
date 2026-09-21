Fix 1 — dropdown wait retry (_get_performance_instances)

# -- Dropdown mechanism (Spektrix eventDetails.aspx) --
# Confirmed live (Disney's Frozen): the page renders in stages --
# the left-hand content appears first, but the "Dates and times"
# panel on the right (the InstanceList dropdown) can take several
# MINUTES longer to show up, not just a few extra seconds. A lone
# 15s wait_for_element_present gave up long before it ever
# appeared, which reads as "this show has zero bookable
# performances" instead of "it just needed more time." Retry the
# wait itself (same page, no reload -- this is a client-side render
# delay, not a failed navigation) for up to ~5 minutes total before
# concluding there's no dropdown.
has_dropdown = False
_DROPDOWN_WAIT_MAX_ATTEMPTS = 3
_DROPDOWN_WAIT_TIMEOUT = 90
for attempt in range(1, _DROPDOWN_WAIT_MAX_ATTEMPTS + 1):
    try:
        sb.wait_for_element_present(
            SELECTORS["instance_dropdown"], timeout=_DROPDOWN_WAIT_TIMEOUT
        )
        has_dropdown = True
        break
    except Exception:
        if attempt < _DROPDOWN_WAIT_MAX_ATTEMPTS:
            self.custom_logger.info(
                "  [Attempt %d/%d] InstanceList dropdown not present yet "
                "-- waiting longer",
                attempt,
                _DROPDOWN_WAIT_MAX_ATTEMPTS,
            )
            human_delay(3, 5)


Fix 2 — browser session restart on a dead/wedged session
def _open_browser_session(self):
    """Open an SB() session without a `with` block, so it can be torn
    down and replaced mid-run on a dead/wedged session instead of only
    at function exit. Returns (context_manager, sb) -- close via
    context_manager directly (not sb).
    """
    context_manager = SB(
        uc=True,
        test=True,
        headless=RUN_HEADLESS,
        browser="chrome",
        locale="en-US",
        chromium_arg="--enable-features=TranslateUI",
    )
    sb = context_manager.__enter__()
    return context_manager, sb

def _close_browser_session(self, context_manager) -> None:
    if context_manager is None:
        return
    try:
        context_manager.__exit__(None, None, None)
    except Exception:
        pass

def _is_browser_alive(self, sb) -> bool:
    """Confirmed live (Cloud Run, 2026-09-17): once chromedriver wedges
    mid-run, every remaining show in every remaining pass fails
    identically -- a ReadTimeoutError against chromedriver's own local
    control port, not a website issue at all -- for the rest of the
    job. Check liveness explicitly before each show so a wedged
    session gets restarted instead of every remaining show silently
    failing against it for the rest of the run.
    """
    if sb is None:
        return False
    try:
        sb.get_current_url()
        return True
    except Exception:
        return False
