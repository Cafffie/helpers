def _parse_terminal_date(self, text: str):
        """Returns (open_date, close_date) as YYYY-MM-DD strings, or (None, None)."""
        if not text:
            return None, None

        text = text.strip()

        if text.lower() == "now playing":
            self.custom_logger.info(
                "Terminal date is 'Now Playing' — no fixed dates available"
            )
            return None, None

        # "From 30 Sep 2026" -> open only, close unknown
        m = re.match(r"^From\s+(.+)$", text, re.IGNORECASE)
        if m:
            try:
                d = parser.parse(m.group(1), dayfirst=True, fuzzy=True).strftime(
                    "%Y-%m-%d"
                )
                return d, None
            except Exception as e:
                self.custom_logger.warning(
                    f"Failed parsing 'From ...' date '{text}': {e}"
                )
                return None, None

        # "15 Nov 2026 - 7 Mar 2027" (cross month/year, explicit years on both)
        m = re.match(
            r"^(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*[-–—]\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})$",
            text,
        )
        if m:
            start_part, end_part = m.groups()
            try:
                start = parser.parse(start_part, dayfirst=True).strftime("%Y-%m-%d")
                end = parser.parse(end_part, dayfirst=True).strftime("%Y-%m-%d")
                return start, end
            except Exception as e:
                self.custom_logger.warning(
                    f"Failed parsing full cross-year date range '{text}': {e}"
                )
                return None, None

        # "5 - 8 Aug 2026" (same month/year)
        m = re.match(r"^(\d{1,2})\s*-\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", text)
        if m:
            d1, d2, month, year = m.groups()
            try:
                start = parser.parse(f"{d1} {month} {year}", dayfirst=True).strftime(
                    "%Y-%m-%d"
                )
                end = parser.parse(f"{d2} {month} {year}", dayfirst=True).strftime(
                    "%Y-%m-%d"
                )
                return start, end
            except Exception as e:
                self.custom_logger.warning(
                    f"Failed parsing same-month range '{text}': {e}"
                )
                return None, None

        # "28 Aug - 6 Sep 2026" (cross month, same year, year only on end)
        m = re.match(
            r"^(\d{1,2}\s+[A-Za-z]+)\s*-\s*(\d{1,2}\s+[A-Za-z]+)\s+(\d{4})$", text
        )
        if m:
            start_part, end_part, year = m.groups()
            try:
                start = parser.parse(f"{start_part} {year}", dayfirst=True).strftime(
                    "%Y-%m-%d"
                )
                end = parser.parse(f"{end_part} {year}", dayfirst=True).strftime(
                    "%Y-%m-%d"
                )
                return start, end
            except Exception as e:
                self.custom_logger.warning(
                    f"Failed parsing cross-month range '{text}': {e}"
                )
                return None, None

        # Single date, possibly with a time attached, e.g. "22 Jul 2026, 7pm"
        try:
            d = parser.parse(text, dayfirst=True, fuzzy=True).strftime("%Y-%m-%d")
            return d, d
        except Exception as e:
            self.custom_logger.warning(f"Could not parse terminal date '{text}': {e}")
            return None, None
