"""Pydantic models describing the subset of the ejudge HTTP API we plan to call.

The classes below intentionally mirror the fields documented in the official
Swagger spec (see :mod:`backend.ejudge.doc.json`) and the wiki excerpts shared
in the task description.  They are meant to be the single source of truth for
any future HTTP clients or service layers that will talk to ejudge.  Keeping
this file well-documented gives autonomous agents the context they need to
extend the integration without re-reading the spec from scratch.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, model_validator

# -- Shared scalar aliases --------------------------------------------------
# Using ``Annotated`` adds validation metadata directly on the types and keeps
# downstream model definitions compact.  This follows the more declarative style
# encouraged in the latest Pydantic releases.
ContestId = Annotated[int, Field(gt=0, description='Unique ejudge contest identifier.')]
RunId = Annotated[int, Field(gt=0, description='Numeric identifier of a run returned by submit-run.')]
SubmitId = Annotated[int, Field(gt=0, description='Identifier of a submit returned by submit-run-input.')]
UserId = Annotated[int, Field(gt=0, description='ejudge user identifier.')]
LanguageId = Annotated[int, Field(gt=0, description='Numeric identifier of an ejudge language preset.')]
ProblemId = Annotated[int, Field(gt=0, description='Numeric identifier of an ejudge problem inside the contest.')]
Milliseconds = Annotated[int, Field(ge=0, description='Duration reported by ejudge in milliseconds.')]
BytesCount = Annotated[int, Field(ge=0, description='Memory usage in bytes reported by ejudge.')]

NotificationKind = Literal['str', 'u64', 'uuid', 'ulid']
"""Supported serialization strategies for the ``notify_queue`` identifier."""


class EjudgeBaseModel(BaseModel):
    """Base class shared by all ejudge integration models."""

    model_config = ConfigDict(extra='forbid', populate_by_name=True, str_strip_whitespace=True)


class NotificationTarget(EjudgeBaseModel):
    """Target queue descriptor for ejudge notification hooks (see wiki docs)."""

    driver: Annotated[int, Field(gt=0, description='ejudge-internal identifier of the notification driver (redis == 1).')]
    kind: Annotated[NotificationKind, Field(description='Interpretation strategy for the queue identifier.')]
    queue: Annotated[str, Field(min_length=1, max_length=128, description='Opaque identifier of the consumer queue.')]

    @model_validator(mode='after')
    def _normalize_queue(self) -> NotificationTarget:
        """Trim whitespace and ensure the queue identifier remains non-empty."""

        self.queue = self.queue.strip()
        if not self.queue:
            msg = 'Notification queue identifier cannot be empty.'
            raise ValueError(msg)
        return self


class SubmitRunRequest(EjudgeBaseModel):
    """Form body for the privileged ``submit-run`` endpoint.

    The API accepts multipart form-data.  The model ensures the mutually
    exclusive selectors (problem, language, code payload) are filled in
    correctly before a request is assembled.
    """

    contest_id: ContestId
    action: Literal['submit-run'] = Field(default='submit-run', frozen=True)
    sender_user_login: Annotated[str | None, Field(description='Optional login to submit on behalf of another user.')] = None
    sender_user_id: Annotated[UserId | None, Field(description='Alternative numeric identifier for impersonated submissions.')] = None
    sender_ip: Annotated[IPvAnyAddress | None, Field(description='Original client IP address, if the submitter is proxied.')] = None
    sender_ssl_flag: Annotated[bool | None, Field(description='Set to ``True`` when the user submitted via HTTPS.')] = None
    problem_uuid: Annotated[UUID | None, Field(description='UUID of the problem to target. Mutually exclusive with ``problem_name`` and ``problem``.')] = None
    problem_name: Annotated[str | None, Field(description='Problem short or internal name. Mutually exclusive with ``problem_uuid`` and ``problem``.')] = None
    problem: Annotated[ProblemId | None, Field(description='Numeric problem identifier. Mutually exclusive with the other problem selectors.')] = None
    variant: Annotated[int | None, Field(description='Optional variant identifier for variant-aware problem sets.')] = None
    language_name: Annotated[str | None, Field(description='Short name of the language preset. Mutually exclusive with ``lang_id``.')] = None
    lang_id: Annotated[int | str | None, Field(description='Language identifier (numeric or short name). Mutually exclusive with ``language_name``.')] = None
    eoln_type: Annotated[int | None, Field(ge=0, description='Line-ending conversion strategy recognised by ejudge.')] = None
    is_visible: Annotated[bool | None, Field(description='Set to ``True`` to force the submission to be visible in the UI.')] = None
    file: Annotated[bytes | None, Field(description='Source code payload as raw bytes. Mutually exclusive with ``text_form``.')] = None
    text_form: Annotated[str | None, Field(description='Source code payload as UTF-8 text. Mutually exclusive with ``file``.')] = None
    not_ok_is_cf: Annotated[bool | None, Field(description='Treat any non-OK verdict as ``Check Failed`` when set.')] = None
    rejudge_flag: Annotated[bool | None, Field(description='Submit with the low-priority rejudge queue when ``True``.')] = None
    ext_user_kind: Annotated[str | None, Field(description='External system identifier type, if ejudge should persist it.')] = None
    ext_user: Annotated[str | None, Field(description='Concrete external system identifier for the submitter.')] = None
    notify_driver: Annotated[int | None, Field(description='Notification driver identifier (see :class:`NotificationTarget`).')] = None
    notify_kind: Annotated[NotificationKind | None, Field(description='Notification queue encoding kind.')] = None
    notify_queue: Annotated[str | None, Field(description='Notification queue identifier payload.')] = None

    @model_validator(mode='after')
    def _ensure_problem_selector(self) -> SubmitRunRequest:
        """Ejudge expects exactly one problem selector in the request."""

        problem_fields = [self.problem_uuid, self.problem_name, self.problem]
        if sum(value is not None for value in problem_fields) != 1:
            raise ValueError('Exactly one of ``problem_uuid``, ``problem_name`` or ``problem`` must be provided.')
        return self

    @model_validator(mode='after')
    def _ensure_language_selector(self) -> SubmitRunRequest:
        if (self.language_name is None) == (self.lang_id is None):
            raise ValueError('Exactly one of ``language_name`` or ``lang_id`` must be provided.')
        return self

    @model_validator(mode='after')
    def _ensure_source_payload(self) -> SubmitRunRequest:
        if (self.file is None) == (self.text_form is None):
            raise ValueError('Provide either ``file`` bytes or ``text_form`` text payload.')
        return self

    @model_validator(mode='after')
    def _ensure_notification_triplet(self) -> SubmitRunRequest:
        provided = {name: getattr(self, name) for name in ('notify_driver', 'notify_kind', 'notify_queue')}
        if any(value is not None for value in provided.values()) and not all(value is not None for value in provided.values()):
            raise ValueError('Notification parameters must be provided together (driver, kind, queue).')
        return self


class SubmitRunInputRequest(EjudgeBaseModel):
    """Form body for the privileged ``submit-run-input`` endpoint."""

    contest_id: ContestId
    action: Literal['submit-run-input'] = Field(default='submit-run-input', frozen=True)
    sender_user_login: Annotated[str | None, Field(description='Optional login to submit on behalf of another user.')] = None
    sender_user_id: Annotated[UserId | None, Field(description='Alternative numeric identifier for impersonated submissions.')] = None
    sender_ip: Annotated[IPvAnyAddress | None, Field(description='Original client IP address, if the submitter is proxied.')] = None
    sender_ssl_flag: Annotated[bool | None, Field(description='Set to ``True`` when the user submitted via HTTPS.')] = None
    prob_id: Annotated[str | int, Field(description='Problem identifier (short name, internal name, or numeric id).')]
    lang_id: Annotated[str | int, Field(description='Language identifier (short name or numeric id).')]
    eoln_type: Annotated[int | None, Field(ge=0, description='Line-ending conversion strategy recognised by ejudge.')] = None
    file: Annotated[bytes | None, Field(description='Source code payload as raw bytes. Mutually exclusive with ``text_form``.')] = None
    text_form: Annotated[str | None, Field(description='Source code payload as UTF-8 text. Mutually exclusive with ``file``.')] = None
    file_input: Annotated[bytes | None, Field(description='Custom stdin payload as raw bytes. Mutually exclusive with ``text_form_input``.')] = None
    text_form_input: Annotated[str | None, Field(description='Custom stdin payload as text. Mutually exclusive with ``file_input``.')] = None
    ext_user_kind: Annotated[str | None, Field(description='External system identifier type, if ejudge should persist it.')] = None
    ext_user: Annotated[str | None, Field(description='Concrete external system identifier for the submitter.')] = None
    notify_driver: Annotated[int | None, Field(description='Notification driver identifier (see :class:`NotificationTarget`).')] = None
    notify_kind: Annotated[NotificationKind | None, Field(description='Notification queue encoding kind.')] = None
    notify_queue: Annotated[str | None, Field(description='Notification queue identifier payload.')] = None

    @model_validator(mode='after')
    def _ensure_source_payload(self) -> SubmitRunInputRequest:
        if (self.file is None) == (self.text_form is None):
            raise ValueError('Provide either ``file`` bytes or ``text_form`` text payload for the source code.')
        return self

    @model_validator(mode='after')
    def _ensure_stdin_payload(self) -> SubmitRunInputRequest:
        if (self.file_input is None) == (self.text_form_input is None):
            raise ValueError('Provide either ``file_input`` bytes or ``text_form_input`` text payload for stdin.')
        return self

    @model_validator(mode='after')
    def _ensure_notification_triplet(self) -> SubmitRunInputRequest:
        provided = {name: getattr(self, name) for name in ('notify_driver', 'notify_kind', 'notify_queue')}
        if any(value is not None for value in provided.values()) and not all(value is not None for value in provided.values()):
            raise ValueError('Notification parameters must be provided together (driver, kind, queue).')
        return self


class GetSubmitRequest(EjudgeBaseModel):
    """Query parameters for the privileged ``get-submit`` endpoint."""

    contest_id: ContestId
    action: Literal['get-submit'] = Field(default='get-submit', frozen=True)
    submit_id: SubmitId


class GetUserRequest(EjudgeBaseModel):
    """Query parameters for the privileged ``get-user`` endpoint."""

    contest_id: ContestId
    action: Literal['get-user'] = Field(default='get-user', frozen=True)
    other_user_id: Annotated[UserId | None, Field(description='Numeric user identifier to fetch. Mutually exclusive with ``other_user_login``.')] = None
    other_user_login: Annotated[str | None, Field(description='Login of the user to fetch. Mutually exclusive with ``other_user_id``.')] = None
    global_: Annotated[bool | None, Field(alias='global', description='Set to true to request global (non contest specific) data.')] = None

    model_config = ConfigDict(extra='forbid', populate_by_name=True, str_strip_whitespace=True)

    @model_validator(mode='after')
    def _ensure_selector(self) -> GetUserRequest:
        if (self.other_user_id is None) == (self.other_user_login is None):
            raise ValueError('Exactly one of ``other_user_id`` or ``other_user_login`` must be provided.')
        return self


# -- Reply payloads ---------------------------------------------------------


class EjudgeError(EjudgeBaseModel):
    """Standard error block embedded in ejudge replies."""

    num: int
    symbol: str
    message: Annotated[str | None, Field(description='Optional verbose description returned by ejudge.')] = None


class EjudgeReply(EjudgeBaseModel):
    """Generic wrapper for ejudge reply envelopes."""

    ok: bool
    action: str
    server_time: Annotated[int | None, Field(description='Unix timestamp reported by ejudge.')] = None
    reply_id: Annotated[int | None, Field(description='Opaque response identifier used by ejudge.')] = None
    request_id: Annotated[int | None, Field(description='Identifier correlating the reply with the originating request.')] = None
    result: Annotated[Any | None, Field(description='Successful payload returned by ejudge.')] = None
    error: Annotated[EjudgeError | None, Field(description='Error details when ``ok`` is false.')] = None


class SubmitRunResult(EjudgeBaseModel):
    """Successful payload returned by ``submit-run``."""

    run_id: RunId
    run_uuid: Annotated[UUID | None, Field(description='Optional UUID for the created run (depends on ejudge version).')] = None


class SubmitRunReply(EjudgeReply):
    """Reply envelope for ``submit-run``."""

    result: Annotated[SubmitRunResult | None, Field(description='Successful payload returned by ejudge.')] = None


class SubmitRunInputResult(EjudgeBaseModel):
    """Successful payload returned by ``submit-run-input``."""

    submit_id: SubmitId


class SubmitRunInputReply(EjudgeReply):
    """Reply envelope for ``submit-run-input``."""

    result: Annotated[SubmitRunInputResult | None, Field(description='Successful payload returned by ejudge.')] = None


class SubmitDetails(EjudgeBaseModel):
    """Rich status document returned by ``get-submit`` and notifications."""

    submit_id: SubmitId
    user_id: UserId
    prob_id: ProblemId
    lang_id: LanguageId
    ext_user_kind: Annotated[str | None, Field(description='External identifier type stored with the submit.')] = None
    ext_user: Annotated[str | None, Field(description='External identifier value stored with the submit.')] = None
    notify_driver: Annotated[int | None, Field(description='Notification driver identifier recorded for the submit.')] = None
    notify_kind: Annotated[NotificationKind | None, Field(description='Notification queue encoding kind recorded for the submit.')] = None
    notify_queue: Annotated[str | None, Field(description='Notification queue identifier recorded for the submit.')] = None
    status: Annotated[int, Field(description='Numeric ejudge status code.')]
    status_str: Annotated[str, Field(description='Short human-readable status string (e.g. OK, WA, TL).')]
    compiler_output: Annotated[str | None, Field(description='Compiler diagnostic output, if any.')] = None
    test_checker_output: Annotated[str | None, Field(description='Checker diagnostic output, if any.')] = None
    time: Milliseconds | None = Field(default=None, description='CPU time spent processing the submission.')
    real_time: Milliseconds | None = Field(default=None, description='Wall clock time spent processing the submission.')
    exit_code: Annotated[int | None, Field(description='Process exit code reported by ejudge.')] = None
    term_signal: Annotated[int | None, Field(description='Termination signal (POSIX) if the process was killed.')] = None
    max_memory_used: BytesCount | None = Field(default=None, description='Maximum virtual memory usage reported by ejudge.')
    max_rss: BytesCount | None = Field(default=None, description='Maximum resident memory usage reported by ejudge.')
    input: Annotated[str | None, Field(description='Captured stdin used for the submission (submit-run-input only).')] = None
    output: Annotated[str | None, Field(description='Captured stdout produced by the submission.')] = None
    error: Annotated[str | None, Field(description='Captured stderr produced by the submission.')] = None


class GetSubmitReply(EjudgeReply):
    """Reply envelope for ``get-submit``."""

    result: Annotated[SubmitDetails | None, Field(description='Successful payload returned by ejudge.')] = None


class UserContestState(EjudgeBaseModel):
    """Contest membership details embedded in :class:`UserProfile`."""

    contest_id: ContestId
    create_time: Annotated[int | None, Field(description='Unix timestamp of the membership creation.')] = None
    status: Annotated[int | None, Field(description='Contest-specific status flag.')] = None
    is_banned: Annotated[bool | None, Field(description='Whether the user is banned from the contest.')] = None
    is_disqualified: Annotated[bool | None, Field(description='Whether the user has been disqualified.')] = None
    is_incomplete: Annotated[bool | None, Field(description='Whether the registration data is incomplete.')] = None
    is_invisible: Annotated[bool | None, Field(description='Whether the membership is hidden from public listings.')] = None
    is_locked: Annotated[bool | None, Field(description='Whether the membership is locked.')] = None
    is_privileged: Annotated[bool | None, Field(description='Whether the user has elevated privileges in the contest.')] = None
    is_reg_readonly: Annotated[bool | None, Field(description='Whether the registration is read-only.')] = None
    last_change_time: Annotated[int | None, Field(description='Timestamp of the last membership change.')] = None
    user_id: Annotated[UserId | None, Field(description='Redundant user identifier returned by ejudge.')] = None


class UserCookie(EjudgeBaseModel):
    """Active ejudge session cookies associated with the user."""

    client_key: Annotated[str | None, Field(description='Identifier of the client that issued the cookie.')] = None
    contest_id: ContestId | None = None
    cookie: Annotated[str | None, Field(description='Opaque cookie value.')] = None
    expire: Annotated[int | None, Field(description='Expiration timestamp.')] = None
    ip: Annotated[str | None, Field(description='Last known IP address for the cookie.')] = None
    is_job: Annotated[bool | None, Field(description='Whether this cookie was issued for a background job.')] = None
    is_ws: Annotated[bool | None, Field(description='Whether this cookie belongs to a websocket session.')] = None
    locale_id: Annotated[int | None, Field(description='Locale identifier used for the session.')] = None
    priv_level: Annotated[int | None, Field(description='Privilege level stored in the cookie.')] = None
    recovery: Annotated[bool | None, Field(description='True when this cookie was created during password recovery.')] = None
    role: Annotated[int | None, Field(description='ejudge internal role identifier.')] = None
    ssl: Annotated[bool | None, Field(description='Whether the cookie was issued over HTTPS.')] = None
    team_login: Annotated[bool | None, Field(description='Whether the cookie belongs to a team login.')] = None
    user_id: Annotated[UserId | None, Field(description='User identifier duplicated in the cookie object.')] = None


class UserInfo(EjudgeBaseModel):
    """User profile fragment returned as part of ``get-user``."""

    contest_id: ContestId | None = None
    city: Annotated[str | None, Field(description='City stored in the contest profile.')] = None
    city_en: Annotated[str | None, Field(description='English representation of the city.')] = None
    area: Annotated[str | None, Field(description='Geographical area or region.')] = None
    locale_id: Annotated[int | None, Field(description='Locale identifier for the contest profile.')] = None
    phone: Annotated[str | None, Field(description='Contact phone number stored in the contest profile.')] = None
    school: Annotated[str | None, Field(description='School or organisation listed in the contest profile.')] = None
    grade: Annotated[str | None, Field(description='Academic grade or class.')] = None
    user_id: Annotated[UserId | None, Field(description='Identifier referencing the owning user.')] = None


class UserProfile(EjudgeBaseModel):
    """Aggregated user descriptor returned by ``get-user``."""

    user_id: UserId
    user_login: Annotated[str, Field(description='Login handle displayed by ejudge.')]
    email: Annotated[str | None, Field(description='Primary email registered with ejudge.')] = None
    is_banned: Annotated[bool | None, Field(description='Global user ban flag.')] = None
    is_invisible: Annotated[bool | None, Field(description='Whether the user is hidden from global listings.')] = None
    is_locked: Annotated[bool | None, Field(description='Whether the account is globally locked.')] = None
    is_privileged: Annotated[bool | None, Field(description='Whether the user has global privileged access.')] = None
    never_clean: Annotated[bool | None, Field(description='Whether the user should never be cleaned up automatically.')] = None
    passwd_method: Annotated[int | None, Field(description='Password hashing method identifier.')] = None
    read_only: Annotated[bool | None, Field(description='Whether the account is marked read-only.')] = None
    registration_time: Annotated[int | None, Field(description='Timestamp of the global registration.')] = None
    show_email: Annotated[bool | None, Field(description='Whether email visibility is enabled.')] = None
    show_login: Annotated[bool | None, Field(description='Whether login visibility is enabled.')] = None
    simple_registration: Annotated[bool | None, Field(description='Whether the user registered via the simplified flow.')] = None
    last_access_time: Annotated[int | None, Field(description='Last time the user accessed ejudge.')] = None
    last_change_time: Annotated[int | None, Field(description='Last time the account changed.')] = None
    last_login_time: Annotated[int | None, Field(description='Last successful login timestamp.')] = None
    last_minor_change_time: Annotated[int | None, Field(description='Last change affecting non-critical data.')] = None
    last_pwdchange_time: Annotated[int | None, Field(description='Last password change timestamp.')] = None
    contests: Annotated[list[UserContestState] | None, Field(description='Contest-specific membership descriptors.')] = None
    cookies: Annotated[list[UserCookie] | None, Field(description='Active cookies associated with the user.')] = None
    infos: Annotated[list[UserInfo] | None, Field(description='Contest-specific profile fields.')] = None


class GetUserReply(EjudgeReply):
    """Reply envelope for ``get-user``."""

    result: Annotated[UserProfile | None, Field(description='Successful payload returned by ejudge.')] = None


# Friendly aliases exported at package level.
__all__ = [
    'ContestId',
    'EjudgeError',
    'EjudgeReply',
    'GetSubmitReply',
    'GetSubmitRequest',
    'GetUserReply',
    'GetUserRequest',
    'LanguageId',
    'NotificationKind',
    'NotificationTarget',
    'ProblemId',
    'RunId',
    'SubmitDetails',
    'SubmitId',
    'SubmitRunInputReply',
    'SubmitRunInputRequest',
    'SubmitRunInputResult',
    'SubmitRunReply',
    'SubmitRunRequest',
    'SubmitRunResult',
    'UserContestState',
    'UserCookie',
    'UserId',
    'UserInfo',
    'UserProfile',
]
