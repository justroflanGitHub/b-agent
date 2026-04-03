"""Business hours and holiday calendar support."""

from datetime import datetime, timedelta
from typing import List, Optional


class BusinessCalendar:
    """Business hours and holiday calendar support."""

    def __init__(self, timezone: str = "UTC", holidays_country: Optional[str] = None):
        self._timezone = timezone
        self._holidays_country = holidays_country
        self._custom_holidays: List[datetime] = []
        self._holidays_cache = None

    def is_business_hours(self, dt: datetime, hours: tuple = (9, 17)) -> bool:
        """Check if datetime is within business hours."""
        return hours[0] <= dt.hour < hours[1]

    def is_holiday(self, dt: datetime) -> bool:
        """Check if datetime is a holiday."""
        date = dt.date()

        # Custom holidays first
        for h in self._custom_holidays:
            if h.date() == date:
                return True

        # Country holidays
        if self._holidays_country:
            try:
                import holidays as hol
                if self._holidays_cache is None or self._holidays_cache[0] != date.year:
                    self._holidays_cache = (
                        date.year,
                        hol.country_holidays(self._holidays_country, years=date.year),
                    )
                return date in self._holidays_cache[1]
            except ImportError:
                pass
        return False

    def is_weekend(self, dt: datetime) -> bool:
        """Check if datetime is a weekend (Saturday/Sunday)."""
        return dt.weekday() >= 5

    def next_business_time(self, after: datetime, hours: tuple = (9, 17)) -> datetime:
        """Get next valid business time."""
        candidate = after
        for _ in range(366):
            if self.is_weekend(candidate):
                candidate = (candidate + timedelta(days=1)).replace(
                    hour=hours[0], minute=0, second=0, microsecond=0
                )
                continue
            if self.is_holiday(candidate):
                candidate = (candidate + timedelta(days=1)).replace(
                    hour=hours[0], minute=0, second=0, microsecond=0
                )
                continue
            if not self.is_business_hours(candidate, hours):
                if candidate.hour >= hours[1]:
                    candidate = (candidate + timedelta(days=1)).replace(
                        hour=hours[0], minute=0, second=0, microsecond=0
                    )
                else:
                    candidate = candidate.replace(
                        hour=hours[0], minute=0, second=0, microsecond=0
                    )
                continue
            return candidate
        return after + timedelta(days=365)

    def add_holidays(self, dates: List[datetime]):
        """Add custom holidays."""
        self._custom_holidays.extend(dates)
