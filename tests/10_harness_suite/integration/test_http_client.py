import json

import httpx

from factory.infra.http_client import _fix_openrouter_error_finish_reason


def _make_response(status_code: int, body: dict, content_type: str = "application/json") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": content_type},
    )


def test_fix_openrouter_error_finish_reason_rewrites_error_to_stop():
    body = {"choices": [{"finish_reason": "error", "message": {"content": "oops"}}]}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["choices"][0]["finish_reason"] == "stop"


def test_fix_openrouter_error_finish_reason_error_field_sets_502():
    body = {"error": {"message": "rate limited", "code": "rate_limit_exceeded"}}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 502


def test_fix_openrouter_error_finish_reason_choices_none_sets_502():
    body = {"choices": None}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 502


def test_fix_openrouter_error_finish_reason_choices_empty_list_sets_502():
    body = {"choices": []}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 502


def test_fix_openrouter_error_finish_reason_choices_not_list_sets_502():
    body = {"choices": "not-a-list"}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 502


def test_fix_openrouter_error_finish_reason_non_json_passes_through():
    resp = httpx.Response(
        status_code=200,
        content=b"not json",
        headers={"content-type": "text/plain"},
    )
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 200


def test_fix_openrouter_error_finish_reason_non_200_passes_through():
    body = {"error": {"message": "something went wrong"}}
    resp = _make_response(500, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 500


def test_fix_openrouter_error_finish_reason_valid_choices_unchanged():
    body = {"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["choices"][0]["finish_reason"] == "stop"


def test_fix_openrouter_error_finish_reason_mixed_choices_rewrites_only_error():
    body = {
        "choices": [
            {"finish_reason": "stop", "message": {"content": "ok"}},
            {"finish_reason": "error", "message": {"content": "fail"}},
        ]
    }
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 200
    parsed = resp.json()
    assert parsed["choices"][0]["finish_reason"] == "stop"
    assert parsed["choices"][1]["finish_reason"] == "stop"


def test_fix_openrouter_error_finish_reason_no_choices_key_sets_502():
    body = {"id": "chatcmpl-123"}
    resp = _make_response(200, body)
    _fix_openrouter_error_finish_reason(resp)
    assert resp.status_code == 502