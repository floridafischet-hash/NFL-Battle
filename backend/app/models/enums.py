from enum import StrEnum


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"


class Conference(StrEnum):
    AFC = "AFC"
    NFC = "NFC"


class SeasonStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class Round(StrEnum):
    WILD_CARD = "WILD_CARD"
    DIVISIONAL = "DIVISIONAL"
    CONFERENCE = "CONFERENCE"
    SUPER_BOWL = "SUPER_BOWL"


class MatchStatus(StrEnum):
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    FINAL = "FINAL"
    VOID = "VOID"


class ResultSource(StrEnum):
    ADMIN = "ADMIN"
    AGENT = "AGENT"


class ChangeRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ActorType(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class AgentRunStatus(StrEnum):
    APPLIED = "APPLIED"
    DUPLICATE = "DUPLICATE"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    OK = "OK"


class ReportStatus(StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    APPLIED = "APPLIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    SUPERSEDED = "SUPERSEDED"


class SystemMessageType(StrEnum):
    MATCHUP = "MATCHUP"
    KICKOFF = "KICKOFF"
    HALFTIME = "HALFTIME"
    FINAL = "FINAL"
    CORRECTION = "CORRECTION"
    LEADERBOARD = "LEADERBOARD"
    OPEN_PICKS = "OPEN_PICKS"
    NEXT_ROUND = "NEXT_ROUND"
    CHAMPION = "CHAMPION"
    INFO = "INFO"


class UploadKind(StrEnum):
    CHAT = "CHAT"
    AVATAR = "AVATAR"
    LOGO = "LOGO"
