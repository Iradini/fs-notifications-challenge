import asyncio 

from fs_notifications_challenge.application.channel_registry import (
    ChannelRegistry,
    UnsupportedChannelError,
)
from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.notification import Notification
from fs_notifications_challenge.infrastructure.channels import build_channel_registry
from fs_notifications_challenge.infrastructure.channels.email import EmailSender
from fs_notifications_challenge.infrastructure.channels.provider import SimulatedProvider
from fs_notifications_challenge.infrastructure.channels.push import PushSender
from fs_notifications_challenge.infrastructure.channels.sms import SmsSender, fit_single_segment

TOKEN = "fcm_" + "a1B2c3D4" * 8
FIELD = {Channel.EMAIL: "email", Channel.SMS: "phone", Channel.PUSH: "token"}


def make(channel: Channel, address: str, title: str = "Hello", content: str = "World") -> Notification:
    return Notification(
        user_id=1, title=title, content=content, channel=channel, id=7,
        recipient=ContactInfo(**{FIELD[channel]: address})
    )


def run(coro):
    return asyncio.run(coro)


# --- registry -------------------------------------------------

def test_registry_resolves_every_channel():
    registry = build_channel_registry()
    assert registry.channels == set(Channel)
    assert isinstance(registry.get(Channel.SMS), SmsSender)


def test_registry_rejects_duplicates_and_unknow():
    registry = ChannelRegistry([EmailSender()])
    try:
        registry.register(EmailSender())
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        registry.get(Channel.PUSH)
        raise AssertionError("expected UnsupportedChannelError")
    except UnsupportedChannelError:
        pass


def test_sender_uses_the_address_for_its_channel():
    n = Notification(
        user_id=1, title="Test", content="TestContent", channel=Channel.SMS, id=7,
        recipient=ContactInfo(email="test@example.com", phone="+59899123456"),
    )
    result = run(SmsSender().send(n))
    assert result.success and result.detail["to"] == "+59899123456"


# --- email -----------------------------------------------------

def test_email_ok_records_address():
    result = run(EmailSender().send(make(Channel.EMAIL, "ana@example.com", title="<b>Hi</b>")))
    assert result.success
    assert result.detail["to"] == "ana@example.com"
    assert result.detail["template"] == "notification_email_v1"


def test_email_invalid_address_is_permanent():
    result = run(EmailSender().send(make(Channel.EMAIL, "not-an-email")))
    assert not result.success and not result.retryable


def test_provider_outage_is_transient():
    sender = EmailSender(SimulatedProvider("email", failure_rate=1.0))
    result = run(sender.send(make(Channel.EMAIL, "ana@example.com")))
    assert not result.success and result.retryable


# --- sms ------------------------------------------------------

def test_sms_normalizes_number():
    result = run(SmsSender().send(make(Channel.SMS, "+598 99 123 456")))
    assert result.success and result.detail["to"] == "+59899123456"


def test_sms_rejects_local_format():
    result = run(SmsSender().send(make(Channel.SMS, "099 123 456")))
    assert not result.success and not result.retryable


def test_sms_gsm7_truncates_at_160():
    text, encoding, truncated = fit_single_segment("a" * 200)
    assert (len(text), encoding, truncated) == (160, "GSM-7", True)
    assert text.endswith("...")


def test_sms_at_sign_statys_gsm7():
    assert fit_single_segment("Write to ana@example.com")[1] == "GSM-7"


def test_sms_accent_switches_to_ucs2_limit_70():
    text, encoding, truncated = fit_single_segment("Notificatión" * 10)
    assert encoding == "UCS-2" and truncated and len(text) <= 70


def test_sms_short_message_untouched():
    assert fit_single_segment("Hola mundo") == ("Hola mundo", "GSM-7", False)


# --- push -------------------------------------------------------------------

def test_push_ok_masks_token():
    result = run(PushSender().send(make(Channel.PUSH, TOKEN)))
    assert result.success
    assert TOKEN not in str(result.detail)
    assert result.detail["payload"]["data"] == {"notification_id": "7"}


def test_push_rejects_bad_token():
    result = run(PushSender().send(make(Channel.PUSH, "short")))
    assert not result.success and not result.retryable


def test_push_clips_long_title_and_body():
    result = run(PushSender().send(make(Channel.PUSH, TOKEN, title="T" * 100, content="B" * 500)))
    note = result.detail["payload"]["notification"]
    assert len(note["title"]) == 65 and len(note["body"]) == 240