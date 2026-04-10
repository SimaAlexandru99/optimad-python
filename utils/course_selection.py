from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from .course_db import CourseSession


@dataclass(frozen=True)
class CourseSessionOption:
    session_id: str
    label: str


@dataclass(frozen=True)
class CourseSessionPrefill:
    session_id: str
    course_date: str
    start_time: str
    hours_value: str
    suggested_app_choice: Optional[str]
    meeting_link: str
    label: str
    warning: str = ""


class CourseSessionAdapter:
    PLATFORM_MAPPING = {
        "zoom": "zoom",
        "teams": "teams",
    }

    def sort_sessions(
        self, sessions: Iterable[CourseSession]
    ) -> List[CourseSession]:
        return sorted(
            sessions,
            key=lambda session: (
                session.course_date,
                session.start_time,
                session.course_name.lower(),
                session.group_name.lower(),
            ),
        )

    def build_options(
        self, sessions: Iterable[CourseSession]
    ) -> List[CourseSessionOption]:
        return [
            CourseSessionOption(
                session_id=session.id,
                label=self.format_session_label(session),
            )
            for session in self.sort_sessions(sessions)
        ]

    def filter_options(
        self, options: Iterable[CourseSessionOption], query: str
    ) -> List[CourseSessionOption]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return list(options)
        return [
            option
            for option in options
            if normalized_query in option.label.lower()
        ]

    def format_session_label(self, session: CourseSession) -> str:
        parts = [session.course_date, session.start_time, session.course_name]
        if session.group_name:
            parts.append(session.group_name)
        return " | ".join(parts)

    def build_prefill(self, session: CourseSession) -> CourseSessionPrefill:
        suggested_app = self.map_platform_to_app(session.platform)
        warning = ""
        if session.platform and suggested_app is None:
            warning = (
                f"Platforma importata '{session.platform}' nu se poate mapa automat. "
                "Aplicatia selectata ramane neschimbata."
            )

        return CourseSessionPrefill(
            session_id=session.id,
            course_date=session.course_date,
            start_time=session.start_time,
            hours_value=self._format_hours(session.duration_hours),
            suggested_app_choice=suggested_app,
            meeting_link=session.meeting_link,
            label=self.format_session_label(session),
            warning=warning,
        )

    def map_platform_to_app(self, platform: str) -> Optional[str]:
        normalized = platform.strip().lower()
        if not normalized:
            return None
        return self.PLATFORM_MAPPING.get(normalized)

    def _format_hours(self, duration_hours: float) -> str:
        if float(duration_hours).is_integer():
            return str(int(duration_hours))
        return f"{duration_hours:.2f}".rstrip("0").rstrip(".")

    def format_session_date(self, course_date: str) -> str:
        try:
            return datetime.strptime(course_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            return course_date
