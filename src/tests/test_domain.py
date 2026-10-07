import pytest

from fs_notifications_challenge.domain.channel import Channel
from fs_notifications_challenge.domain.contact import ContactInfo
from fs_notifications_challenge.domain.errors import DomainError
from fs_notifications_challenge.domain.notification import Notification, NotificationLockedError, Status
from fs_notifications_challenge.domain.user import UserProfile


def make(**overrides) -> Notification:
    data = dict(user_id=1, title="Test", content="Test Content", channel=Channel.EMAIL, recipient=ContactInfo(email="test@example.com"))
    return Notification(**{**data, **overrides})


def test_address_for_picks_the_address_of_the_channel():
    contact = ContactInfo(email="test@example.com", phone="+59899123456")
    assert contact.address_for(Channel.EMAIL) == "test@example.com"
    assert contact.address_for(Channel.SMS) == "+59899123456"
    assert contact.address_for(Channel.PUSH) == None


def test_channel_needs_a_matching_address():
    with pytest.raises(DomainError):
        make(channel=Channel.SMS)  # recipient only has an email


def test_change_delivery_validates_before_assigning():
    n = make()
    with pytest.raises(DomainError):
        n.change_delivery(channel=Channel.SMS)
    assert n.channel is Channel.EMAIL


def test_change_delivery_switches_channel_and_clear_stale_error():
    n = make()
    n.record_error("smtp timeout")
    n.change_delivery(channel=Channel.SMS, recipient=ContactInfo(phone="+59899123456"))
    assert n.channel is Channel.SMS and n.last_error is None


def test_edit_rejects_blank_and_keeps_old_values():
    n = make()
    with pytest.raises(DomainError):
        n.edit(title=" ")
    assert n.title == "Test"


@pytest.mark.parametrize("action",[
    lambda n: n.mark_sent(),
    lambda n: n.mark_failed("x"),
    lambda n: n.record_error("x"),
    lambda n: n.change_delivery(channel=Channel.EMAIL), 
])
def test_delivery_is_locked_after_sent(action):
    n = make()
    n.mark_sent()
    with pytest.raises(DomainError):
        action(n)
    assert n.status is Status.SENT


def test_profile_needs_some_contact():
    with pytest.raises(DomainError):
        UserProfile(user_id=1, contact=ContactInfo())


def test_delete_works_in_any_status_and_is_idempotent():
    n = make()
    n.mark_sent()
    n.delete()
    first = n.deleted_at
    n.delete()
    assert n.is_deleted and n.deleted_at == first
    assert n.status is Status.SENT  # deleting doesn't rewrite delivery history


def test_deleted_notification_cannot_change():
    n = make()
    n.delete()
    with pytest.raises(NotificationLockedError):
        n.mark_sent()


def test_text_stays_editable_after_sent():
    n = make()
    n.mark_sent()
    sent_at = n.sent_at
    n.edit(title="Fixed Typo")
    assert (n.title, n.status, n.sent_at) == ("Fixed Typo", Status.SENT, sent_at)
    assert n.updated_at is not None


def test_edit_with_same_text_is_not_an_edit():
    n = make()
    n.edit(title="Test", content="Test Content")
    assert n.updated_at is None


def test_deleted_notification_text_is_locked_too():
    n = make()
    n.delete()
    with pytest.raises(NotificationLockedError):
        n.edit(title="New")