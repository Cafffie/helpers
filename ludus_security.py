Below is everything I added to get past Ludus's Cloudflare check and to prepare for Cloud Run, taken from the current files on disk. 
There are four parts. Line numbers refer to run_extractor.py.

What the site does
wvcarts.org itself has no protection. The ticketing site wvcarts.ludus.com sits behind a Cloudflare managed challenge. 
A plain request gets HTTP 403 with the title "Just a moment…" and the text "Performing security verification". 
Its checkbox is hidden inside a closed shadow root, so Marquee's older approach of clicking the Turnstile iframe finds nothing to click.

Part 1 — Solving the challenge: CDP mode + solve_captcha() (from peakradar)
Every page, including the hub, show pages, seatmaps and wvcarts.org pages, opens through _open. run_extractor.py:425-478:

def _open(self, sb: Any, url: str, label: str) -> bool:
    try:
        sb.activate_cdp_mode(url)            # drive Chrome over CDP, not WebDriver
        sb.wait_for_ready_state_complete()   # every page waits for readyState complete
    except Exception as e:
        if not self._is_driver_alive(sb):
            raise _SessionDeadError(f"browser died opening {url}: {e}") from e
        self.custom_logger.error("Failed to load %s (%s): %s", label, url, e)
        return False

    marker = self._detect_challenge(sb)
    if not marker:
        return True

    self._log_challenge_diagnostics(sb, label, marker)
    for attempt in range(1, CHALLENGE_SOLVE_ATTEMPTS + 1):      # 4 attempts
        try:
            sb.solve_captcha()                                   # SeleniumBase's CDP captcha solver
        except Exception as e:
            self.custom_logger.warning("solve_captcha attempt %d/%d raised on %s: %s", ...)
        human_delay(*DELAY_AFTER_CHALLENGE)                      # 4-6s
        sb.wait_for_ready_state_complete()
        marker = self._detect_challenge(sb)
        if not marker:
            self.custom_logger.info("Challenge cleared on %s after %d attempt(s)", label, attempt)
            return True
    self._log_challenge_diagnostics(sb, label, marker)
    self.custom_logger.error("Challenge did not clear on %s after %d attempts (proxy active: %s)", ...)
    if not self.proxy_active and config.is_proxy2_configured():
        raise _ChallengeBlockedError(...)                        # -> Part 3, proxy fallback
    return False

Why it works:

activate_cdp_mode drives Chrome over the DevTools protocol, so Chrome doesn't carry the usual WebDriver automation markers that Cloudflare checks. The diagnostics confirm navigator.webdriver: False.
solve_captcha() reaches the checkbox inside the shadow root, which a normal DOM click can't.
Every _open failure is also retried by _open_with_retries: 3 attempts, with cooldowns growing from 4-7s to 12-21s (:480-488).

Detecting the challenge (:384-394) checks the page title and body against markers in the config:

CHALLENGE_TITLE_MARKERS = ("just a moment", "attention required", "please wait", "one more step")
CHALLENGE_BODY_MARKERS  = ("performing security verification", "checking if your connection",
                           "verify you are human", "_incapsula_resource", "request unsuccessful")

The markers deliberately don't include a bare "cloudflare", because a cleared page can still show a "protected by Cloudflare" badge.

Part 2 — Captcha logging: what triggered it and what it's checking
_log_challenge_diagnostics (:396-423) runs when a challenge is first seen and again if it never clears:

diag = sb.cdp.evaluate("""(() => ({
    url: location.href,
    title: document.title,
    cloudflare_chl_opt: typeof window._cf_chl_opt !== 'undefined',   // Cloudflare challenge script loaded
    cloudflare_chl_type: (window._cf_chl_opt || {}).cType || null,    // challenge type
    cloudflare_ray: (...innerText).match(/Ray ID:\\s*([0-9a-f]+)/i)?.[1] || null,
    turnstile_iframe: !!document.querySelector('iframe[src*="challenges.cloudflare.com"]'),
    incapsula: !!document.querySelector('script[src*="_Incapsula_Resource"], ...'),
    hcaptcha: !!document.querySelector('iframe[src*="hcaptcha"]'),
    webdriver: navigator.webdriver,          // the automation flag Cloudflare checks
    user_agent: navigator.userAgent,
    languages: navigator.languages,
    body_excerpt: (...innerText).slice(0, 200)
}))()""")

This is what the live run logged. It shows a managed challenge with no visible iframe, and a browser that doesn't look automated:

Bot challenge on Ludus hub (matched title:just a moment): {'cloudflare_chl_opt': True,
 'cloudflare_ray': 'a422bd6c6b41eefb', 'turnstile_iframe': False, 'incapsula': False,
 'webdriver': False, 'user_agent': '...Chrome/154...', 'languages': ['en-US','en'],
 'body_excerpt': 'wvcarts.ludus.com\nPerforming security verification...'}
Challenge cleared on Ludus hub after 2 attempt(s)

Part 3 — Cloud Run: Marquee's browser setup + proxy fallback
3a. Visible (headed) Chrome on a virtual display
:229-241:

def _build_sb_kwargs(self, proxy: str | None) -> dict:
    sb_kwargs = self.get_sb_kwargs(proxy=proxy)     # keeps uc, --no-sandbox, --disable-dev-shm-usage, proxy slot
    sb_kwargs.pop("headless2", None)                # drop Chrome --headless=new
    sb_kwargs["headless"] = False                   # real (headed) browser
    sb_kwargs["xvfb"] = True                        # SeleniumBase starts its own virtual X display on Linux
    sb_kwargs["chromium_arg"] = f"{sb_kwargs['chromium_arg']}{EXTRA_CHROMIUM_ARGS}"
    return sb_kwargs
  
with, from the config:
EXTRA_CHROMIUM_ARGS = (
    " --disable-blink-features=AutomationControlled"     # hides automation flag
    " --lang=en-US,en;q=0.9"                              # consistent US locale
    " --webrtc-ip-handling-policy=disable_non_proxied_udp"
    " --force-webrtc-ip-handling-policy"                  # stops WebRTC leaking the real IP behind the proxy
)

Why: Headless Chrome is easier for Cloudflare to identify. Marquee found that headless mode wouldn't clear the Ludus challenge, and it runs headed on Cloud Run. The Dockerfile already installs xvfb and sets DISPLAY=:99, so a headed browser works in the container. On Windows xvfb=True does nothing and a normal window opens. The anti-automation flags are added to get_sb_kwargs()'s own chromium_arg rather than replacing it, so the container-safe flags are kept.

3b. US sticky residential proxy, copied from Marquee unchanged
_start_local_proxy_2_us_sticky (:243-371) is a small local relay:

if not config.is_proxy2_configured():
    return None, lambda: None                                    # no creds locally -> no proxy

session_id = f"{random.getrandbits(40):010x}"
sticky_user = f"customer-{config.PROXY2_USER}-cc-{PROXY_SESSION_COUNTRY}-sessid-{session_id}"
#              ^ Oxylabs: US exit IP, pinned to ONE session id = same IP for the whole run
auth_header = f"Proxy-Authorization: Basic {b64(sticky_user:PROXY2_PASS)}\r\n".encode()

# Listens on 127.0.0.1:<free port>; for every Chrome connection it opens a socket
# to PROXY2_HOST, injects the Proxy-Authorization header into the request, and
# pipes bytes both ways (CONNECT tunnels for HTTPS). Chrome itself gets a plain,
# unauthenticated proxy address -- Chrome can't pass proxy credentials in UC/CDP mode.
...
return local_addr, stop        # "127.0.0.1:PORT", and a stop() for the finally block

Why a sticky IP: Cloudflare issues its clearance cookie to one IP. If the IP rotated on every request, each page would be challenged again.

Why it matters on Cloud Run: deploy.yml:320-324 injects PROXY2_HOST/USER/PASS/ENABLED into every job, so the proxy is available there. Without it, Cloudflare sees a Google data-centre IP, which it trusts far less than the office IP my tests ran from.

3c. Proxy only as a fallback
This follows the repo's "proxy is the last resort" rule. :1204-1272:

def _run_session(self, use_proxy: bool) -> None:
    local_proxy, stop_proxy = (
        self._start_local_proxy_2_us_sticky() if use_proxy else (None, lambda: None)
    )
    self.proxy_active = bool(local_proxy)
    try:
        with SB(**self._build_sb_kwargs(local_proxy)) as sb:     # with SB(**kwargs), as you asked
            ...collect listing, venue pages, scrape_shows(sb)...
    finally:
        stop_proxy()

def extract(self) -> bytes:
    use_proxy = False                                           # session 1: no proxy
    for session in range(1, SESSION_MAX_RESTARTS + 2):          # up to 3 sessions
        try:
            self._run_session(use_proxy)
        except _SessionDeadError as e:                          # Chrome crashed -> fresh browser
            ...; continue
        except _ChallengeBlockedError as e:                     # challenge wouldn't clear unproxied
            use_proxy = True                                    # -> restart behind the sticky proxy
            ...; continue
        if self.pending_shows is not None:
            break

How it runs on Cloud Run:

Session 1: headed Chrome with no proxy. If Cloudflare clears, the whole run is done this way (as in every local run).
Challenge fails: if any page's challenge fails all 4 solve_captcha attempts and proxy credentials exist, _open raises _ChallengeBlockedError. It passes up through extract_seat_metrics, scrape_one_show and scrape_shows, which all re-raise it rather than recording anything.
Session 2: starts behind the US sticky proxy and carries on with self.pending_shows. Shows already scraped are kept. The interrupted show is re-scraped from scratch; it is marked "seen" only after it finishes, so it isn't skipped as a duplicate.
No proxy credentials (e.g. locally): _open returns False and the normal retries apply.

Part 4 — Holding up when things go wrong
Situation	Handling
Seatmap loaded but circles not drawn yet	|sb.cdp.select("circle.seat", timeout=20) waits for the seats to render instead of a fixed sleep. If the chart area is present but empty, it returns failed, which is retried and never recorded as sold out.
Chrome crashes |	_is_driver_alive detects it and raises _SessionDeadError, then a fresh browser opens (at most 3 sessions).
Show page doesn't render its showtime list	|_load_show_page re-opens it up to 3 times, then the show is deferred to later passes (3 passes, with a 45-90s cooldown between).
Pacing	|human_delay between shows and seatmaps, and human_scroll after page loads. No bare sleep calls.

Verified vs. not verified

Verified locally: 3 full live runs. The latest used the headed + xvfb setup: the challenge cleared in 2 attempts, all 20 seatmaps read, and CSV validation passed 47/0/0. The proxy escalation was tested with mocked sessions, and a blocked session restarts as [False, True].
Not verified:
Cloud Run: I can't run it there from here.
The proxy path: it has never gone through a real proxy, because there are no PROXY2_* credentials on this machine.
On the first dev Cloud Run run, look for one of these in the log:

-Challenge cleared on Ludus hub means it works without a proxy.
-restarting behind the US sticky proxy followed by Local US sticky proxy 2 started means the fallback kicked in.
-Bot challenge ... {diagnostics} repeated with no clear means it failed. Send me that log and the diagnostics will show what Cloudflare objected to.





















