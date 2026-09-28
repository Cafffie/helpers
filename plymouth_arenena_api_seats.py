Now I have the full picture. The per-section endpoint /api/seatmaps/products/{perf_code}/sections/{section_code} 
returns real per-seat data with rows[].name (row letter) and seats[].name (seat number), seats[].isAvailable, seats[].status, 
and seats[].priceCategory. Let me read the config file, then write the implementation:

Security
It isn't a captcha. There's no captcha widget on any page. The site uses:

Akamai Bot Manager on tickets.plymoutharena.com. This covers the ticket APIs and seat maps, and it sets the _abck, bm_sz, ak_bmsc and bm_sv cookies.
Cloudflare in front of the WordPress site (__cf_bm cookie).
Plain requests gets an instant 403 "Access Denied". Our curl_cffi Chrome impersonation gets through.

Our session's Akamai cookie never becomes validated. It stays at ~-1~, because we never run Akamai's browser script. Akamai lets an unvalidated client through up to some volume, then blocks it for a few minutes. That's what hit your run: after about 10 minutes and roughly 400 requests, the block lasted at least 5 minutes, then lifted.

Is it fixed?
Not fully. What I've done so far lowers the risk; nothing I've done removes it.

Filtering to 2 shows cut a run from about 400+ requests to about 90. Three full runs since (11:22, 11:26, 11:41) had zero 403s.
On Cloud Run, a 403 retries once through proxy slot 2. The deploy passes the PROXY2_* secrets.
That's evidence at today's volume, not proof it can't happen again. It also hasn't been run on Cloud Run. Two things would harden it, and I'd need your go-ahead for either:

Cooldown and fresh session on a 403. Wait about 7 minutes (the block lasted at least 5), then retry with fresh cookies. It's cheap, and the Cloud Run timeout is 23 hours. The catch: I can only prove it works during a real block, and I won't hammer the site on purpose to cause one.
Get a validated Akamai cookie from one real browser visit at the start of each run, and reuse it for the API calls. This I can verify now, by checking the cookie changes from ~-1~ to validated. It adds about a minute of browser time per run.
I'd recommend doing both: option 2 addresses the cause, and option 1 covers anything that slips through. Want me to go ahead?

1. Seat IDs are real seats in the house format
Before, seat_pricing held price bands like "FLAT 3", which was the reviewer's comment. 
The scraper now calls the per-seat endpoint for each section and writes TIERED 2 CC27-style IDs.
# plymouth_arena_config.py
SECTION_SEATS_API_URL = (
    TICKETS_BASE_URL
    + "/api/seatmaps/products/{perf_code}/sections/{section_code}"
)

# run_extractor.py -- _fetch_section_seats
for row in rows:
    row_name = str(row.get("name") or "")
    for seat in row.get("seats") or []:
        if seat.get("status") == "NoSeat":      # grid placeholder, not a seat
            continue
        if not seat.get("isAvailable"):          # Sold / Unavailable / Dibs
            continue
        seat_name = str(seat.get("name") or "")
        seat_id = f"{section_label} {row_name}{seat_name}"   # "TIERED 2 CC27"

2. Every section is checked, including ones the summary calls sold out
The summary's isSoldOut flag was wrong on the live site many times. 
For Simon Brodkin, TIERED 1, 2 and 3 were marked sold out while the booking page showed them full of seats. 
Now per-seat data wins, and the summary is only used for a section with no per-seat layout.
# extract_seats
per_seat = self._fetch_section_seats(
    perf_code, section_code, section_label, price_by_category
)
if per_seat is not None:
    for entry in per_seat:
        if entry["seat"] not in seen_labels:
            seen_labels.add(entry["seat"])
            seats.append(entry)
    if per_seat and section_is_sold_out:
        self.custom_logger.info(
            "  Section %s (%s): summary says sold out, but per-seat data "
            "has %d bookable seat(s) -- using per-seat data", ...)
else:
    # No per-seat layout: section-level entry from summary (unchanged logic)


3. Seats not on sale are skipped
Seat FLAT 7 AA22 at Jeff Wayne reported isAvailable: true, but its price category (12)
isn't in the sales offer, and the booking page showed it grey.
Seats like that are no longer counted.
price_cat = seat.get("priceCategory")
if price_cat and price_cat not in price_by_category:
    self.custom_logger.info(
        "  Seat %s: priceCategory=%s not in salesoffer -- not on sale, skipped",
        seat_id, price_cat)
    continue


4. A failed per-seat request retries instead of falling back
Before, a failed request quietly swapped real seats for a "FLAT 4" label.
Now the error propagates, so the existing 3-attempt retry for each performance tries again.
data = self._get_json(url) or {}   # raises on failure -> performance retry loop
rows = data.get("rows") or []
if not rows:
    return None                    # only case that falls back to section level

5. The availability call retries brief failures
In your run, Dreamboys got HTTP 400 once, then 200 on 7 re-calls in a row. 
A 404 isn't retried, because Simon Brodkin returns 404 every time.

for attempt in range(1, AVAILABILITY_MAX_ATTEMPTS + 1):   # = 3
    try:
        data = self._get_json(url) or []
        return {...}
    except Exception as exc:
        response = getattr(exc, "response", None)
        if response is not None and response.status_code == 404:
            break
        if attempt < AVAILABILITY_MAX_ATTEMPTS:
            human_delay(*DELAY_BETWEEN_API_CALLS)


6. Genre filter: plays/drama and musicals only
The rule rests on the check of all 38 full show pages described above:

Comedy and tribute tags are dropped outright.
A show is kept only if its listing headline, or the first sentence of its page description, calls itself a musical or a play/drama.
Only the first sentence is read, because later sentences mention other works. 
Fisherman's Friends' second sentence, for example, says the band "inspired… a touring stage musical".
# config
SHOW_MUSICAL_TEXT_RE = (
    r"\bmusical\s+(?:theatre|theater|version|production)\b"
    r"|\b(?:the|a|new|hit)\s+musical\b(?!\s+(?:vision|maestro|director|talent))"
)
SHOW_PLAY_TEXT_RE = r"\b(?:a\s+(?:new\s+)?play|stage\s+play|drama|tragedy)\b"
SHOW_EXCLUDED_TAGS = frozenset({"comedy", "tribute"})

# run_extractor.py
def _classify_show(headline, description, genre_hint):
    tags = {g for g in genre_hint.split(", ") if g}
    if tags & SHOW_EXCLUDED_TAGS:
        return None
    first_sentence = re.split(r"[.!?\u2026]", description or "", maxsplit=1)[0]
    text = f"{headline} {first_sentence}"
    if re.search(SHOW_MUSICAL_TEXT_RE, text, re.IGNORECASE):
        return standardize_category("Musical")
    if re.search(SHOW_PLAY_TEXT_RE, text, re.IGNORECASE):
        return standardize_category("Play")
    return None
The description comes from the show page (.info-details .more-less-content). 
Out-of-scope shows are dropped in extract() before any seat-map calls, and the category is written into each CSV row.
Today this keeps Jeff Wayne's War of the Worlds and Cirque: The Greatest Show, both as Musical.

7. Housekeeping
Stale log lines, docstrings and config comments are corrected.
.claude/agents/prod-scraper-fixer.md records the per-seat endpoint and the unreliable sold-out flag. 
It also covers the price-category rule and the genre rule.
Current security in the scraper
What the site uses: Akamai Bot Manager on tickets.plymoutharena.com (cookies _abck, bm_sz, ak_bmsc, bm_sv), 
and Cloudflare in front of the WordPress site (__cf_bm). There is no captcha; a block is a hard 403 "Access Denied".

What the scraper does about it:

a. Chrome TLS impersonation. Plain requests gets a 403 on every ticket endpoint; curl_cffi impersonating Chrome gets through.
# config
CURL_IMPERSONATE = "chrome124"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
# __init__
self._http = curl_requests.Session(impersonate=CURL_IMPERSONATE)
self._http.headers.update(HEADERS)

b. Proxy fallback, only on 401/403. It retries once through proxy slot 2, which is set up on Cloud Run via the PROXY2_* secrets. 
Locally there's no proxy, so it's skipped.
b. Proxy fallback, only on 401/403. It retries once through proxy slot 2, which is set up on Cloud Run via the PROXY2_* secrets. Locally there's no proxy, so it's skipped.

def _http_get(self, url):
    resp = self._http.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code in (401, 403):
        proxied = self._get_proxied_session()   # None if PROXY2_* unset
        if proxied is not None:
            resp = proxied.get(url, timeout=REQUEST_TIMEOUT)
    return resp

def _get_proxied_session(self):
    if self._proxy_http is None:
        proxies = self.get_proxies_dict_2()
        if not proxies:
            return None
        session = curl_requests.Session(impersonate=CURL_IMPERSONATE)
        session.headers.update(HEADERS)
        session.proxies.update(proxies)
        self._proxy_http = session
    return self._proxy_http

c. Block diagnostics. Every non-200 response is logged with its Akamai reference, so a block can be diagnosed from the Cloud Run log alone.
akamai_ref = resp.headers.get("Akamai-GRN") or resp.headers.get("X-Akamai-Session-Info")
self.custom_logger.error("Non-200 response: %s -> HTTP %s | Akamai-GRN=%s | body: %s", ...)

d. Pacing and retries.
DELAY_BETWEEN_SHOWS = (2.0, 4.0)
DELAY_BETWEEN_PERFORMANCES = (1.0, 2.5)
DELAY_BETWEEN_API_CALLS = (0.5, 1.5)      # human_delay() before each section call
DELAY_BETWEEN_PASSES = (30.0, 60.0)
LISTING_MAX_ATTEMPTS = SHOW_FETCH_MAX_ATTEMPTS = SEATMAP_MAX_ATTEMPTS = SHOW_PASS_MAX_ATTEMPTS = 3
AVAILABILITY_MAX_ATTEMPTS = 3

e. Real browser, only when needed. _verify_sold_out_via_browser opens a SeleniumBase browser via self.get_sb_kwargs() only when every section looks sold out but the availability check says tickets remain.

The gap: our Akamai cookie stays unvalidated (~-1~), so Akamai can still block the scraper after enough requests. 
That's what hit your full run. Scraping 2 shows instead of 38 cuts the request count by about 80%, and the three full runs since had no 403s. 
It isn't proof it can't happen again. The two fixes I suggested would close it: a cooldown with fresh cookies after a 403, and a validated cookie from one browser visit per run. 
Want me to go ahead with those?


















