Springboro's own CDP solve_captcha() loop is kept as the fallback. _open runs the step above once before it switches to CDP mode.

Code: run_extractor.py:389-478

def _uc_challenge_visible(self, sb: Any) -> bool:
    """Challenge check for the pre-CDP (UC mode) phase."""
    try:
        title = (sb.execute_script("return document.title || '';") or "").lower()
        body = (
            sb.execute_script(
                "return document.body ? document.body.innerText : '';"
            )
            or ""
        ).lower()
    except Exception:
        return False
    return any(m in title for m in SECURITY_CHECK_TITLE_MARKERS) or any(
        m in body for m in SECURITY_CHECK_BODY_MARKERS
    )

def _uc_clear_challenge(self, sb: Any, url: str, label: str) -> None:
    """marquee_youth_theater / siouxcitycommunitytheatre's clearing step,
    both of which clear *.ludus.com on Cloud Run: uc_open_with_reconnect,
    stealth, then a Turnstile click (DOM click, then the PyAutoGUI
    solvers) until the challenge is gone or LUDUS_SECURITY_WAIT_SECONDS pass.
    Best effort -- it only primes the Cloudflare cookie; _open then
    switches to CDP mode, whose solve_captcha() loop remains the fallback."""
    try:
        sb.uc_open_with_reconnect(url, reconnect_time=4)
        self._inject_stealth(sb)
    except Exception as e:
        self.custom_logger.warning("UC open failed for %s: %s", label, e)
        return
    start = time.time()
    last_reconnect = start
    while time.time() - start < LUDUS_SECURITY_WAIT_SECONDS:
        if not self._uc_challenge_visible(sb):
            self.custom_logger.info("UC step cleared challenge on %s", label)
            return
        human_scroll(sb)
        human_delay(0.8, 1.8)
        clicked = False
        try:
            frame = sb.find_element('iframe[src*="challenges.cloudflare.com"]')
            sb.switch_to_frame(frame)
            sb.click('input[type="checkbox"]')
            sb.switch_to_default_content()
            clicked = True
        except Exception:
            try:
                sb.switch_to_default_content()
            except Exception:
                pass
        if not clicked:
            for method in ("uc_gui_click_captcha", "uc_gui_handle_captcha"):
                try:
                    getattr(sb, method)()
                    break
                except Exception as e:
                    self.custom_logger.debug(
                        "%s failed on %s: %s", method, label, e
                    )
        human_delay(3, 4)
        # Marquee's periodic re-open: a stuck challenge can keep
        # re-triggering on the same live connection.
        if self._uc_challenge_visible(sb) and time.time() - last_reconnect > 30:
            for reconnect_time in RECONNECT_RETRY_SECONDS:
                try:
                    sb.uc_open_with_reconnect(url, reconnect_time=reconnect_time)
                    break
                except Exception as e:
                    self.custom_logger.debug(
                        "uc_open_with_reconnect(%s) failed: %s", reconnect_time, e
                    )
            self._inject_stealth(sb)
            last_reconnect = time.time()
    self.custom_logger.info(
        "UC step did not clear %s in %ds -- falling back to CDP solve",
        label,
        LUDUS_SECURITY_WAIT_SECONDS,
    )


The hook in _open (run_extractor.py:474-478):
if not self._cdp_active:
    self._uc_clear_challenge(sb, url, label)
    sb.activate_cdp_mode(url)
    self._cdp_active = True
else:
    sb.cdp.open(url)

Config: springboro_community_theatre_config.py:95-101
LUDUS_SECURITY_WAIT_SECONDS = 60
RECONNECT_RETRY_SECONDS = (15, 20, 25)

