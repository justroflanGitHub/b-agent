"""Cron expression parser and schedule calculator.

Supports standard 5-field cron expressions plus:
- Business hours filtering
- Weekend exclusion
- Holiday calendar (via `holidays` package)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

# Day-of-week mapping (cron: 0=Sunday, 7=Sunday)
DOW_MAP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


@dataclass
class CronSchedule:
    """Cron expression parser and next-run calculator.

    Expression format: MINUTE HOUR DAY MONTH DAY_OF_WEEK
    Examples:
        "0 9 * * MON"        — Every Monday at 9:00
        "*/15 * * * *"       — Every 15 minutes
        "0 9 1 * *"          — 1st of every month at 9:00
        "30 17 * * FRI"      — Every Friday at 17:30
    """

    expression: str = "0 9 * * *"
    timezone: str = "UTC"
    business_hours_only: bool = False
    business_hours: Optional[Tuple[int, int]] = None  # (start_hour, end_hour) e.g. (9, 17)
    exclude_weekends: bool = False
    exclude_holidays: bool = False
    holiday_country: Optional[str] = None

    def __post_init__(self):
        self._fields = self.expression.strip().split()
        if len(self._fields) != 5:
            raise ValueError(f"Invalid cron expression (need 5 fields): {self.expression}")
        if self.business_hours and not self.business_hours_only:
            self.business_hours_only = True

    def next_occurrence(self, after: datetime) -> datetime:
        """Calculate next scheduled occurrence after `after`."""
        tz = self._get_tz()
        local_dt = after.astimezone(tz) if after.tzinfo else after.replace(tzinfo=tz)

        # Start from next minute
        candidate = local_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search forward (max 366 days)
        max_iter = 525600  # minutes in a year
        for _ in range(max_iter):
            if self._matches_minute(candidate) and self._matches_hour(candidate):
                if self._matches_day_of_month(candidate) and self._matches_month(candidate):
                    if self._matches_day_of_week(candidate):
                        # Apply business rules
                        if self.exclude_weekends and candidate.weekday() >= 5:
                            candidate = self._next_valid_day(candidate)
                            continue
                        if self.business_hours_only and self.business_hours:
                            h = candidate.hour
                            if h < self.business_hours[0] or h >= self.business_hours[1]:
                                # Jump to next business-hour slot
                                candidate = (
                                    candidate.replace(hour=self.business_hours[0], minute=0) + timedelta(days=1)
                                    if h >= self.business_hours[1]
                                    else candidate.replace(hour=self.business_hours[0], minute=0)
                                )
                                continue
                        if self.exclude_holidays and self._is_holiday(candidate):
                            candidate += timedelta(days=1)
                            candidate = candidate.replace(hour=0, minute=0)
                            continue
                        return candidate
            candidate += timedelta(minutes=1)

        # Fallback
        return after + timedelta(days=365)

    def should_run_now(self, now: datetime, tolerance_minutes: int = 1) -> bool:
        """Check if the schedule triggers now (within tolerance)."""
        tz = self._get_tz()
        local_dt = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)

        if not (self._matches_minute(local_dt) and self._matches_hour(local_dt)):
            return False
        if not (self._matches_day_of_month(local_dt) and self._matches_month(local_dt)):
            return False
        if not self._matches_day_of_week(local_dt):
            return False
        if self.exclude_weekends and local_dt.weekday() >= 5:
            return False
        if self.business_hours_only and self.business_hours:
            h = local_dt.hour
            if h < self.business_hours[0] or h >= self.business_hours[1]:
                return False
        if self.exclude_holidays and self._is_holiday(local_dt):
            return False
        return True

    def get_upcoming(self, count: int = 10, after: Optional[datetime] = None) -> List[datetime]:
        """Get next N scheduled occurrences."""
        results = []
        cursor = after or datetime.now(timezone.utc)
        for _ in range(count):
            nxt = self.next_occurrence(cursor)
            results.append(nxt)
            cursor = nxt + timedelta(minutes=1)
        return results

    def _get_tz(self):
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(self.timezone)
        except (ImportError, KeyError):
            return timezone.utc

    def _matches_field(self, value: int, field_str: str, min_val: int, max_val: int) -> bool:
        """Match a value against a cron field expression."""
        if field_str == "*":
            return True

        for part in field_str.split(","):
            # Step: */N
            if part.startswith("*/"):
                step = int(part[2:])
                return value % step == 0

            # Range: N-M
            if "-" in part and "/" not in part:
                start, end = part.split("-")
                return int(start) <= value <= int(end)

            # Range with step: N-M/S
            if "-" in part and "/" in part:
                range_part, step = part.split("/")
                start, end = range_part.split("-")
                start, end, step = int(start), int(end), int(step)
                return start <= value <= end and (value - start) % step == 0

            # Exact value
            try:
                return value == int(part)
            except ValueError:
                # Named day of week
                if part.lower() in DOW_MAP:
                    return value == DOW_MAP[part.lower()]
                return False

        return False

    def _matches_minute(self, dt: datetime) -> bool:
        return self._matches_field(dt.minute, self._fields[0], 0, 59)

    def _matches_hour(self, dt: datetime) -> bool:
        return self._matches_field(dt.hour, self._fields[1], 0, 23)

    def _matches_day_of_month(self, dt: datetime) -> bool:
        return self._matches_field(dt.day, self._fields[2], 1, 31)

    def _matches_month(self, dt: datetime) -> bool:
        return self._matches_field(dt.month, self._fields[3], 1, 12)

    def _matches_day_of_week(self, dt: datetime) -> bool:
        # Cron: 0=Sunday; Python: Monday=0, Sunday=6
        cron_dow = (dt.weekday() + 1) % 7
        return self._matches_field(cron_dow, self._fields[4], 0, 7)

    def _next_valid_day(self, dt: datetime) -> datetime:
        """Skip to next non-weekend day."""
        candidate = dt + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate.replace(hour=0, minute=0)

    def _is_holiday(self, dt: datetime) -> bool:
        if not self.holiday_country:
            return False
        try:
            import holidays as hol

            country_holidays = hol.country_holidays(self.holiday_country)
            return dt.date() in country_holidays
        except ImportError:
            return False
        except Exception:
            return False
