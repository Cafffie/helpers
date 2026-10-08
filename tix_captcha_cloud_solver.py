1. How the tix.com captcha is solved
tix.com uses a Cloudflare Turnstile challenge ("Just a moment..."). 
Plain requests and curl_cffi both get a 403, and headless Chrome never cleared it. 
What cleared it was a headed Chrome in SeleniumBase CDP mode with a CDP-native captcha click.

Browser setup. Headed Chrome, run under a virtual display (xvfb) on Linux, plus a WebRTC leak guard when proxied:

def get_sb_kwargs(self, proxy=None) -> dict:
    kwargs = super().get_sb_kwargs(proxy=proxy)
    kwargs.pop("headless2", None)          # headless never cleared it
    kwargs["headless"] = self.headless_mode  # False
    kwargs["xvfb"] = True                  # virtual display on Cloud Run
    if proxy:
        kwargs["chromium_arg"] += PROXY_CHROMIUM_ARGS  # no WebRTC IP leak
    return kwargs

Navigation. CDP mode is turned on at the first navigation of the session and never mixed with classic mode. 
The stealth script is registered then too. uc_open_with_reconnect is deliberately not used because it drops CDP mode:

if not self._cdp_mode_activated:
    sb.activate_cdp_mode(url)      # first navigation of the session
    self._cdp_mode_activated = True
    self._inject_stealth(sb)       # patches webdriver flag, plugins, WebGL renderer
else:
    sb.open(url)                   # never uc_open_with_reconnect afterwards

The click ladder. The challenge is detected by its exact page title, not the word "cloudflare". 
It makes 3 click attempts with a wait after each, then polls the same page, then re-opens the page and repeats for up to 3 rounds:

for attempt in range(1, CLICK_RETRY_ATTEMPTS + 1):          # 3
    sb.uc_gui_click_captcha()                                # CDP-native click
    if self._poll_challenge_clear(sb, CLICK_SETTLE_SECONDS): # 8s
        return True
if self._poll_challenge_clear(sb, CHALLENGE_POLL_SECONDS):   # 60s, same page
    return True
self._log_challenge_diagnostics(sb, url, stage="NOT CLEARED")
return False

Other safeguards:

- The mouseinfo import guard at the top of the file stops a missing tkinter killing the container.
- Every challenge is logged with its markers, ray id and browser fingerprint.
- After the challenge clears, tix's JSON is read from inside the page. In CDP mode I use sb.cdp.evaluate, because sb.execute_script returns nothing there.
Reliability. The click usually clears on the 2nd or 3rd attempt. One earlier local run failed all 9 clicks, then passed on re-test. 
I think the click uses the real mouse and a window was covering the browser, but I couldn't prove it. Cloud Run has no other windows, so that shouldn't apply there.

2. How proxy slots 1 and 2 are applied
I followed the same pattern forgetheatre, novabillings and olathetheatre use for Cloudflare-gated sites. 
The first route to get discovery through is kept for the rest of the run:

def _proxy_routes(self):
    routes = []
    if config.is_proxy2_configured():     # PROXY2_ENABLED + user + pass
        routes.append(("proxy slot 2 (US sticky)", self._start_local_proxy_2_us_sticky))
    if config.is_proxy_configured():      # PROXY_ENABLED + user + pass
        routes.append(("proxy slot 1", self.start_local_proxy))
    routes.append(("direct", lambda: (None, lambda: None)))   # local dev / last resort
    return routes

for session_no in range(1, MAX_SESSIONS + 1):             # 5
    self._route, starter = routes[route_index]
    local_proxy, stop_proxy = starter()
    with SB(**self.get_sb_kwargs(proxy=local_proxy)) as sb:
        try:
            pending = self._discover_shows(sb)
        except RuntimeError as exc:
            if route_index + 1 < len(routes):
                route_index += 1      # next route, fresh session
                continue
            raise                     # all routes failed: fail loudly

Slot 2 pins one sticky US session. Without that, Cloudflare can issue its clearance cookie to one exit IP and reject it from another:
session_id = f"{random.getrandbits(40):010x}"
sticky_user = f"{prefixed}-cc-US-sessid-{session_id}-sesstime-30"   # prefixed = "customer-<PROXY2_USER>"
auth_header = b"Proxy-Authorization: Basic " + base64(f"{sticky_user}:{PROXY2_PASS}")
# A local 127.0.0.1 proxy injects this header on every CONNECT to the upstream,
# so Chrome never sees a 407. Slot 1 uses the base class's own local proxy.


Checked here:

15 offline checks against a stub upstream proxy pass:
The username format is right and the session id stays the same across connections.
A user that already starts with customer- isn't double-prefixed.
Unset slots are skipped.
Route order is slot 2, slot 1, then direct.
A working route survives a browser restart.
If every route is blocked, the run raises.
A capped live run (1 show, direct route since the local .env has no proxy credentials) passed with 47/47 checks.
Lint passes with black, isort --profile black, and flake8.


Needs confirming on Cloud Run:

- The proxy credentials must be set there (PROXY2_ENABLED, PROXY2_HOST, PROXY2_USER, PROXY2_PASS, and the slot 1 equivalents). If a slot is unset, the log says so and skips it.
- If the university site blocks the proxy's IP too, the run will fail on purpose. I removed the tix-only fallback so a blocked season page never writes a wrong open_date.
- The first Cloud Run log shows which route worked and why any route failed.
I also saved offline_proxy_ladder_check.py in the pending folder; it is the 15-check script.



src/scrapers/biletyna_w/run_extractor.py isn't mine, and I didn't touch it this session. It is uncommitted work you did on a different branch, so there is nothing for me to record for it.

My own work this session is the UNO scraper, saved in C:\Users\Awarri User\Documents\ovation_pending\unomaha_theatre\. The lessons from it that are worth recording:

- Tix Cloudflare captcha: it is already in prod-scraper-fixer.md on the UNO branch.
-403 on unomaha.edu from Cloud Run: it is recorded there too, marked as not yet verified on Cloud Run.
-Proxy-ladder change: I haven't added a new entry for it. It is the same pattern forgetheatre, novabillings and olathetheatre already use, and I haven't confirmed it works with the real credentials. 
 When you switch back to the UNO branch and the Cloud Run run confirms which route works, I'll update the existing 403 entry then.

















