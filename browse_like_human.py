1. entcenter_for_the_arts (run_extractor.py:289). 
Its docstring says it reads, peeks down, moves the mouse, scrolls through and returns to the top. 
This is the fuller version.
def _browse_like_human(self, sb) -> None:
    """Read, peek down, move the mouse, scroll through, return to top —
    the scroll/pointer/dwell signal Imperva's reese84 sensor scores."""
    try:
        human_delay(*DELAY_READ_PAGE)
        sb.execute_script(JS_SCROLL_PEEK)
        human_delay(*DELAY_AFTER_SCROLL)
        human_mouse_move(sb)
        human_delay(*DELAY_AFTER_SCROLL)
        human_scroll(sb)
        human_delay(*DELAY_AFTER_SCROLL)
        sb.execute_script(JS_SCROLL_TOP)
        human_delay(*DELAY_AFTER_SCROLL)
    except Exception as e:
        self.custom_logger.warning("Human-behaviour scroll failed: %s", e)

Its constants, from entcenter_for_the_arts_config.py:
DELAY_READ_PAGE = (2, 4)
DELAY_AFTER_SCROLL = (1, 2.5)
JS_SCROLL_PEEK = "window.scrollTo(0, 300);"
JS_SCROLL_TOP = "window.scrollTo(0, 0);"

2. barn_theatre_cirencester (run_extractor.py:347). This one is shorter: it dwells, moves the mouse, then scrolls.
def _browse_like_human(self, sb) -> None:
    """Dwell, move the pointer and scroll — the behavioural signal
    bot sensors score."""
    try:
        human_delay(*DELAY_READ_PAGE)
        human_mouse_move(sb)
        human_delay(*DELAY_AFTER_SCROLL)
        human_scroll(sb)
        human_delay(*DELAY_AFTER_SCROLL)
    except Exception as e:
        self.custom_logger.warning("Human-behaviour scroll failed: %s", e)

Both call the shared helpers from utils.scraping_helpers: human_delay, human_mouse_move and human_scroll. 
I also found humanize_page in birminghamhippodrome, oldtownplayhouse, novabillings, stokerep and theatre_royal_nottingham. 
Say so if you'd rather see that one.



That one is at novabillings/run_extractor.py:557. The other four are:

Scraper	Location	What differs
birminghamhippodrome	run_extractor.py:270	Mouse at 36% / 43% of the window. Delays 0.8–1.8s and 0.5–1.2s. Logs "Humanizing flow".
oldtownplayhouse	run_extractor.py:281	Accepts cookies first. Mouse at 45% / 45%. Delays come from config constants (HUMANIZE_DELAY, HUMANIZE_SCROLL_DELAY).
stokerep	run_extractor.py:636	Accepts cookies after the first delay. Mouse at 33% / 45%. Delays 0.8–2.0s and 0.6–1.4s.
theatre_royal_nottingham	run_extractor.py:269	Named _humanize_page. Accepts cookies first. Mouse at 52% / 40%. Shorter delays: 0.5–1.4s and 0.3–0.9s.
If you want the version that places the mouse by window percentage, here is oldtownplayhouse:

def humanize_page(self, sb, context: str = "page") -> None:
    try:
        self.accept_cookies_if_present(sb)
        human_delay(*HUMANIZE_DELAY)

        try:
            sb.execute_script(
                """
                window.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: Math.floor(window.innerWidth * 0.45),
                    clientY: Math.floor(window.innerHeight * 0.45),
                    bubbles: true
                }));
                """
            )
        except Exception as exc:
            self.custom_logger.warning("Mouse-move dispatch skipped: %r", exc)

        human_scroll(sb)
        human_delay(*HUMANIZE_SCROLL_DELAY)

    except Exception as exc:
        self.custom_logger.warning("Humanize skipped for %s: %s", context, exc)

