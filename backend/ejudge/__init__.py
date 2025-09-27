"""Typed primitives and HTTP helpers for the ejudge integration layer."""

from .client import EjudgeClient, EjudgeClientError, EjudgeReplyError
from .mocks import (
    RecordedCall,
    create_mock_transport,
    make_get_submit_reply,
    make_get_user_reply,
    make_submit_details,
    make_submit_run_input_reply,
    make_submit_run_reply,
)
from .models import (
    EjudgeError,
    EjudgeReply,
    GetSubmitReply,
    GetSubmitRequest,
    GetUserReply,
    GetUserRequest,
    NotificationKind,
    NotificationTarget,
    SubmitDetails,
    SubmitRunInputReply,
    SubmitRunInputRequest,
    SubmitRunReply,
    SubmitRunRequest,
)

__all__ = [
    'EjudgeClient',
    'EjudgeClientError',
    'EjudgeError',
    'EjudgeReply',
    'EjudgeReplyError',
    'GetSubmitReply',
    'GetSubmitRequest',
    'GetUserReply',
    'GetUserRequest',
    'NotificationKind',
    'NotificationTarget',
    'RecordedCall',
    'SubmitDetails',
    'SubmitRunInputReply',
    'SubmitRunInputRequest',
    'SubmitRunReply',
    'SubmitRunRequest',
    'create_mock_transport',
    'make_get_submit_reply',
    'make_get_user_reply',
    'make_submit_details',
    'make_submit_run_input_reply',
    'make_submit_run_reply',
]
