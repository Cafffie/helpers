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
