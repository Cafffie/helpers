def _get_terminal_dates(self, sb) -> tuple[str | None, str | None]:
        """Read the show header's real ISO start/end datetimes.

        Far more reliable than parsing the visible "11 – 12 Sept" text
        (confirmed live: that text never carries a year) — the underlying
        <time datetime="..."> attributes do.
        """
        open_date, close_date = None, None
        try:
            start_el = sb.find_element(By.CSS_SELECTOR, SELECTORS["terminal_start"])
            open_date = parser.isoparse(start_el.get_attribute("datetime")).strftime(
                "%Y-%m-%d"
            )
        except Exception as e:
            self.custom_logger.debug(f"terminal start-date extraction failed: {e}")
        try:
            end_el = sb.find_element(By.CSS_SELECTOR, SELECTORS["terminal_end"])
            close_date = parser.isoparse(end_el.get_attribute("datetime")).strftime(
                "%Y-%m-%d"
            )
        except Exception as e:
            self.custom_logger.debug(f"terminal end-date extraction failed: {e}")

        # Single-day shows render the header as plain text with no <time>
        # node at all (e.g. "16 Sept, 7:30pm") — confirmed live — so neither
        # selector above matches. Fall back to parsing that text directly.
        if not open_date and not close_date:
            try:
                posttitle_text = sb.find_element(
                    By.CSS_SELECTOR, SELECTORS["terminal_posttitle"]
                ).get_attribute("textContent")
                date_text = (posttitle_text or "").split(",")[0].strip()
                open_date = self._parse_date(date_text) if date_text else None
            except Exception as e:
                self.custom_logger.debug(f"terminal posttitle fallback failed: {e}")

        # Single-day shows don't render an endDate <time> node at all (there's
        # nothing to end) — when only the start date was found, that one date
        # is both the open and close date, not just an open date.
        if open_date and not close_date:
            close_date = open_date

        return open_date, close_date
