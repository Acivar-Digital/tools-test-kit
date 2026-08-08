from src2.interfaces.telegram.gatekeeper import Gatekeeper, IngressPayload


def test_gatekeeper_ingress_payload_validation_success():
    """
    Verifies that IngressPayload validation no longer crashes with
    "PydanticDescriptorProxy object is not callable" and successfully validates incoming webhooks.
    """
    payload = {
        "update_id": 802636213,
        "message": {
            "message_id": 4487,
            "from": {
                "id": 999000001,
                "is_bot": False,
                "first_name": "🅵🆁🅰🅽🅲🅸🆂",
                "last_name": "🆈🅰🅿",
                "username": "yapily",
                "language_code": "en",
                "is_premium": True,
            },
            "chat": {
                "id": 999000001,
                "first_name": "🅵🆁🅰🅽🅲🅸🆂",
                "last_name": "🆈🅰🅿",
                "username": "yapily",
                "type": "private",
            },
            "date": 1785374448,
            "text": "/start",
            "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
        },
    }

    # 1. Direct model validation succeeds
    ingress = IngressPayload.model_validate(payload)
    assert ingress.update_id == 802636213
    assert ingress.message is not None
    assert ingress.message.chat.id == 999000001

    # 2. Gatekeeper validation succeeds
    res = Gatekeeper.validate(payload)
    assert res.is_valid is True
    assert res.extracted_text == "/start"
    assert res.chat_id == 999000001
    assert res.error_msg is None


def test_gatekeeper_ingress_payload_edited_message_alias():
    """
    Verifies alias_message_types validator correctly maps edited_message to message.
    """
    payload = {
        "update_id": 802636214,
        "edited_message": {
            "message_id": 4488,
            "from": {"id": 999000001, "is_bot": False, "first_name": "Tester"},
            "chat": {"id": 999000001, "type": "private"},
            "date": 1785374458,
            "text": "/help",
        },
    }

    res = Gatekeeper.validate(payload)
    assert res.is_valid is True
    assert res.extracted_text == "/help"
    assert res.chat_id == 999000001
