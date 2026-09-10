def parse_spektrix_seats(html: str) -> tuple[list[dict], int | None]:
    """Parse seat entries and total capacity from a Spektrix chooseseats iframe page.

    Implements the Spektrix seat-map extraction pattern used by:
      - landmark_theatres  (src/scrapers/landmark_theatres/run_extractor.py — _parse_spektrix_seats)
      - parkwood_theatres  (src/scrapers/parkwood_theatres/run_extractor.py)

    Three strategies are tried in order, stopping at the first that yields results:

      Strategy 1 — embedded seatData + areaNames JavaScript object:
        Spektrix injects a JSON-like object containing "seatData" (pipe-separated
        records) and "areaNames" (id→name map).  Fields: id|areaId|x|y|color|…|label|…|available(1)|…
        fields[11] = "A3 - £15.95", fields[13] = "1" if available.

      Strategy 2 — individual seat images (standard Spektrix seat map):
        img[class*="Seat"] elements with title like "A3 - £30.00".
        img[class*="SeatSelectable"] → available seats only.

      Strategy 3 — zone/category price table (no individual seat map):
        table > tr where the first cell is a seat-type label and a later cell
        contains a £ price.  Skips header rows and "Unavailable" labels.

    Parameters
    ----------
    html : str
        Full HTML of the Spektrix chooseseats iframe page.  Obtain this after
        switching into the iframe and calling:
            html = sb.execute_script("return document.documentElement.outerHTML")

    Returns
    -------
    tuple[list[dict], int | None]
        (seat_entries, capacity) where:
          - seat_entries  [{"seat": str, "ticket_price": float}, ...]  available seats only
          - capacity      total seat count (Strategies 1/2) or None (Strategy 3)

    Example
    -------
    sb.switch_to_frame(SPEKTRIX_IFRAME_SELECTOR)
    human_delay(10, 12)
    iframe_html = sb.execute_script("return document.documentElement.outerHTML")
    seats, capacity = parse_spektrix_seats(iframe_html)
    seat_pricing[perf_key] = seats
    sb.switch_to_default_content()
    """
    if not html:
        return [], None

    seat_entries: list[dict] = []
    capacity: int | None = None

    # Strategy 1: seatData embedded in page JavaScript.
    area_match = re.search(r'"areaNames"\s*:\s*(\{[^}]+\})', html)
    seat_match = re.search(r'"seatData"\s*:\s*"([^"]+)"', html)
    if seat_match:
        area_names: dict[str, str] = {}
        if area_match:
            try:
                area_names = json.loads(area_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        seat_data_str = seat_match.group(1)
        total_count = 0
        seen_seats: set[str] = set()

        for entry in seat_data_str.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            fields = entry.split("|")
            if len(fields) < 12:
                continue
            total_count += 1

            available = len(fields) > 13 and fields[13] == "1"
            if not available:
                continue

            label = fields[11]
            price_match = re.search(r"£([\d,]+(?:\.\d{1,2})?)", label)
            if not price_match:
                continue

            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                continue

            name_match = re.match(r"^(.+?)\s*-\s*£", label)
            seat_id = name_match.group(1).strip() if name_match else label.strip()

            area_label = area_names.get(fields[1], "") if len(fields) > 1 else ""
            if area_label and "auditorium" not in area_label.lower():
                full_seat_id = f"{area_label} {seat_id}"
            else:
                full_seat_id = seat_id

            if full_seat_id not in seen_seats:
                seen_seats.add(full_seat_id)
                seat_entries.append({"seat": full_seat_id, "ticket_price": price})

        if total_count:
            return seat_entries, total_count

    # Strategy 2: individual seat images.
    soup = BeautifulSoup(html, "html.parser")
    all_seat_imgs = soup.find_all("img", class_=re.compile(r"^Seat"))
    if all_seat_imgs:
        capacity = len(all_seat_imgs)
        seen_seats2: set[str] = set()
        for seat_img in all_seat_imgs:
            classes = seat_img.get("class") or []
            if not any("SeatSelectable" in cls for cls in classes):
                continue
            title_text = (
                seat_img.get("title") or seat_img.get("tooltip") or ""
            ).strip()
            seat_match2 = re.match(r"^(.+?)\s*-\s*£([\d.]+)", title_text)
            if seat_match2:
                seat_id = seat_match2.group(1).strip()
                if seat_id not in seen_seats2:
                    seen_seats2.add(seat_id)
                    seat_entries.append(
                        {"seat": seat_id, "ticket_price": float(seat_match2.group(2))}
                    )
        return seat_entries, capacity

    # Strategy 3: zone/category price table.
    price_re = re.compile(r"£\s*([\d.]+)")
    skip_labels = frozenset(
        {"ticket type", "type", "category", "price", "unavailable", ""}
    )
    seen_labels: set[str] = set()

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        if label.lower() in skip_labels:
            continue
        for cell in cells[1:]:
            price_match3 = price_re.search(cell.get_text(strip=True))
            if price_match3:
                price = float(price_match3.group(1))
                if label not in seen_labels:
                    seen_labels.add(label)
                    seat_entries.append({"seat": label, "ticket_price": price})
                break

    return seat_entries, capacity
