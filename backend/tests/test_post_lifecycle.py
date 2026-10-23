"""The Post lifecycle through its interface: state changes, ADR 0007 and the Approval inputs."""

from datetime import timedelta

import pytest

from app.conversation.approval import Approval
from app.conversation.photos import Photo, local_now
from app.posts.lifecycle import ApprovedPost, PostLifecycle
from app.posts.store import InMemoryPosts, Post, PostImage

SENDER = "59899000000"
OTHER_SENDER = "59899000001"


def sent_post(post_id: str = "p1", sender: str = SENDER) -> Post:
    return Post(post_id, sender, [PostImage(f"/media/{post_id}.jpg", b"jpeg")], "Mesa de roble")


def lifecycle_with(*post_ids: str) -> tuple[PostLifecycle, list[Post]]:
    lifecycle = PostLifecycle()
    posts = [sent_post(post_id) for post_id in post_ids]
    for post in posts:
        lifecycle.add(post)
    return lifecycle, posts


def photo(received_at_offset: timedelta) -> Photo:
    return Photo("f1", b"jpeg", None, received_at=local_now() + received_at_offset)


def approve_and_publish(lifecycle: PostLifecycle, post: Post) -> None:
    lifecycle.approve(SENDER, post.id)
    approved = lifecycle.authorize_tap(SENDER, post.id)
    assert approved is not None
    lifecycle.begin_publish(approved)


# State changes


def test_a_new_post_waits_for_the_owner_and_is_pending() -> None:
    lifecycle, [post] = lifecycle_with("p1")

    assert lifecycle.awaiting_approval(post)
    assert lifecycle.pending(SENDER) == [post]


def test_yes_reaction_approves_only_the_exact_message_that_asked_to_publish() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    lifecycle.note_reply(SENDER, "¡Listo! ¿Lo subo?", post.id)
    lifecycle.note_sent(SENDER, "wamid.OUT")

    assert lifecycle.reaction_approval(SENDER, "👍", "wamid.OTHER", []) == Approval()
    assert lifecycle.reaction_approval(SENDER, "❤️", "wamid.OUT", []) == Approval()
    assert lifecycle.reaction_approval(SENDER, "👍", "wamid.OUT", []).post_id == post.id


def test_yes_reaction_cannot_approve_after_new_photos_arrive() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    lifecycle.note_reply(SENDER, "¡Listo! ¿Lo subo?", post.id)
    lifecycle.note_sent(SENDER, "wamid.OUT")

    approval = lifecycle.reaction_approval(SENDER, "👍", "wamid.OUT", [photo(timedelta(seconds=1))])

    assert approval == Approval()
    assert post.status == "pending_approval"


def test_the_tap_approves_only_a_post_still_waiting_for_it() -> None:
    lifecycle, [post] = lifecycle_with("p1")

    assert lifecycle.approve(SENDER, "p1") is post
    assert post.status == "approved"
    assert lifecycle.approve(SENDER, "p1") is None  # a second tap is stale
    assert lifecycle.approve(OTHER_SENDER, "p1") is None  # and so is another Owner's


def test_an_approved_post_is_still_pending_so_subilo_can_publish_it() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    lifecycle.approve(SENDER, "p1")

    assert not lifecycle.awaiting_approval(post)
    assert lifecycle.pending(SENDER) == [post]


@pytest.mark.parametrize("approve_first", [False, True])
def test_a_pending_or_approved_post_can_be_discarded_once(approve_first: bool) -> None:
    lifecycle, [post] = lifecycle_with("p1")
    if approve_first:
        lifecycle.approve(SENDER, "p1")

    assert lifecycle.discard(SENDER, "p1") is post
    assert post.status == "discarded"
    assert lifecycle.discard(SENDER, "p1") is None
    assert lifecycle.pending(SENDER) == []
    assert lifecycle.discarded_post(SENDER, "p1") is post


def test_a_post_that_is_not_discarded_is_not_offered_for_another() -> None:
    lifecycle, _ = lifecycle_with("p1")

    assert lifecycle.discarded_post(SENDER, "p1") is None


def test_replacing_a_post_retires_it_from_the_pending_list() -> None:
    lifecycle, [post] = lifecycle_with("p1")

    lifecycle.replace(post)

    assert post.status == "replaced"
    assert lifecycle.pending(SENDER) == []
    assert lifecycle.pending_post(SENDER, "p1") is None


def test_retire_only_touches_a_post_that_is_still_pending() -> None:
    lifecycle, [pending, busy] = lifecycle_with("p1", "p2")
    approve_and_publish(lifecycle, busy)

    assert lifecycle.retire(SENDER, "p1") is True
    assert pending.status == "replaced"
    assert lifecycle.retire(SENDER, "p2") is False
    assert busy.status == "publishing"
    assert lifecycle.retire(SENDER, "nope") is False


def test_a_revision_or_video_starts_only_from_a_pending_post() -> None:
    lifecycle, [post, done] = lifecycle_with("p1", "p2")
    lifecycle.published(done, "https://instagram.test/p/1", "ext-1")

    assert lifecycle.approvable_post(SENDER, "p1") is post
    assert lifecycle.approvable_post(SENDER, "nope") == {"error": "unknown_post"}
    assert lifecycle.approvable_post(SENDER, "p2") == {
        "error": "post_not_pending",
        "status": "published",
    }


# ADR 0007: the publisher only gets what the lifecycle authorizes


def test_text_approval_authorizes_only_the_post_this_turns_approval_names() -> None:
    lifecycle, [post, _] = lifecycle_with("p1", "p2")

    approved = lifecycle.authorize_text(SENDER, "p1", Approval(post_id="p1"))

    assert isinstance(approved, ApprovedPost)
    assert approved.post is post


def test_text_approval_without_the_owners_words_authorizes_nothing() -> None:
    lifecycle, _ = lifecycle_with("p1")

    assert lifecycle.authorize_text(SENDER, "p1", Approval()) == {"error": "approval_not_explicit"}
    assert lifecycle.authorize_text(SENDER, "p1", Approval(post_id="p2")) == {
        "error": "approval_not_explicit"
    }


def test_a_refused_approval_carries_the_numbered_list_for_the_owner() -> None:
    lifecycle, _ = lifecycle_with("p1")
    pending = [{"n": 1, "post_id": "p1"}]

    refused = lifecycle.authorize_text(
        SENDER, "p1", Approval(reason="several_pending", pending=pending)
    )

    assert refused == {"error": "several_pending", "pending": pending}


def test_text_approval_refuses_unknown_and_no_longer_pending_posts() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    approval = Approval(post_id="p1")
    assert lifecycle.authorize_text(SENDER, "nope", approval) == {"error": "unknown_post"}

    lifecycle.replace(post)

    assert lifecycle.authorize_text(SENDER, "p1", approval) == {
        "error": "post_not_pending",
        "status": "replaced",
    }


def test_the_tap_publishes_only_a_post_approved_with_its_own_button() -> None:
    lifecycle, _ = lifecycle_with("p1")

    assert lifecycle.authorize_tap(SENDER, "p1") is None  # [Publicar ahora] before [Aprobar]
    lifecycle.approve(SENDER, "p1")
    assert isinstance(lifecycle.authorize_tap(SENDER, "p1"), ApprovedPost)
    assert lifecycle.authorize_tap(OTHER_SENDER, "p1") is None


def test_only_the_lifecycle_can_mint_an_approved_post() -> None:
    post = sent_post()

    with pytest.raises(TypeError):
        ApprovedPost(post, object())


def test_a_retry_is_authorized_only_after_a_definite_failure() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    assert lifecycle.authorize_retry(SENDER, "p1") is None

    approve_and_publish(lifecycle, post)
    assert lifecycle.authorize_retry(SENDER, "p1") is None  # still publishing
    lifecycle.failed(post)

    approved = lifecycle.authorize_retry(SENDER, "p1")
    assert approved is not None
    assert lifecycle.begin_publish(approved) is post
    assert post.publish_attempts == 2
    assert post.idempotency_key == "p1-r2"


# Publishing outcomes


def test_a_publish_starts_busy_and_counts_the_attempt() -> None:
    lifecycle, [post] = lifecycle_with("p1")

    approve_and_publish(lifecycle, post)

    assert post.status == "publishing"
    assert post.publish_attempts == 1
    assert lifecycle.authorize_tap(SENDER, "p1") is None  # a second tap finds it busy


def test_a_published_post_keeps_its_permalink_and_leaves_the_pending_list() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    approve_and_publish(lifecycle, post)

    lifecycle.published(post, "https://instagram.test/p/1", "ext-1")

    assert (post.status, post.permalink, post.external_post_id) == (
        "published",
        "https://instagram.test/p/1",
        "ext-1",
    )
    assert lifecycle.pending(SENDER) == []


def test_an_unknown_outcome_is_pending_never_a_failure() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    approve_and_publish(lifecycle, post)

    lifecycle.publish_pending(post, "ext-9")

    assert post.status == "publish_pending"
    assert post.external_post_id == "ext-9"
    assert lifecycle.authorize_retry(SENDER, "p1") is None  # it may be live: never publish again


def test_a_busy_post_is_not_dropped_when_the_store_is_full() -> None:
    lifecycle = PostLifecycle(InMemoryPosts(max_per_sender=1))
    busy = sent_post("p1")
    lifecycle.add(busy)
    approve_and_publish(lifecycle, busy)

    lifecycle.add(sent_post("p2"))

    assert lifecycle.get(SENDER, "p1") is busy


# Approval inputs


def test_several_pending_posts_are_listed_and_the_next_number_picks_from_that_list() -> None:
    lifecycle, [first, second] = lifecycle_with("p1", "p2")

    asked = lifecycle.approval_for(SENDER, "subilo", attached=False, recent_photos=[])
    lifecycle.replace(first)  # the list the Owner saw still decides what "2" means
    picked = lifecycle.approval_for(SENDER, "la segunda", attached=False, recent_photos=[])

    assert asked.reason == "several_pending"
    assert [item["post_id"] for item in asked.pending] == ["p1", "p2"]
    assert picked.post_id == second.id


def test_a_number_means_nothing_when_no_list_was_shown() -> None:
    lifecycle, _ = lifecycle_with("p1", "p2")

    assert lifecycle.approval_for(SENDER, "2", attached=False, recent_photos=[]) == Approval()


def test_one_pending_post_is_approved_by_subilo() -> None:
    lifecycle, _ = lifecycle_with("p1")

    approval = lifecycle.approval_for(SENDER, "subilo", attached=False, recent_photos=[])

    assert approval.post_id == "p1"


def test_photos_with_the_message_or_after_the_post_ask_for_a_post_not_an_approval() -> None:
    lifecycle, _ = lifecycle_with("p1")
    later = photo(timedelta(minutes=5))

    attached = lifecycle.approval_for(SENDER, "subilo", attached=True, recent_photos=[])
    waiting = lifecycle.approval_for(SENDER, "subilo", attached=False, recent_photos=[later])

    assert attached == Approval()
    assert waiting == Approval()


def test_a_photo_sent_before_the_post_does_not_block_its_approval() -> None:
    lifecycle, _ = lifecycle_with("p1")
    earlier = photo(timedelta(minutes=-5))

    approval = lifecycle.approval_for(SENDER, "subilo", attached=False, recent_photos=[earlier])

    assert approval.post_id == "p1"


def test_a_yes_approves_only_the_post_the_last_reply_asked_to_publish() -> None:
    lifecycle, _ = lifecycle_with("p1")
    assert lifecycle.approval_for(SENDER, "sí", attached=False, recent_photos=[]) == Approval()

    lifecycle.note_reply(SENDER, "Quedó lindo. ¿Lo subo?")
    assert lifecycle.approval_for(SENDER, "sí", attached=False, recent_photos=[]).post_id == "p1"

    lifecycle.note_reply(SENDER, "¿Le cambio el título?")  # a newer reply asks nothing
    assert lifecycle.approval_for(SENDER, "sí", attached=False, recent_photos=[]) == Approval()


def test_a_reply_about_a_post_offers_that_post_even_with_several_pending() -> None:
    lifecycle, _ = lifecycle_with("p1", "p2")

    lifecycle.note_reply(SENDER, "¿Lo subo?", "p2")

    assert lifecycle.approval_for(SENDER, "dale", attached=False, recent_photos=[]).post_id == "p2"


def test_a_reply_that_asks_about_no_pending_post_offers_nothing() -> None:
    lifecycle, [post] = lifecycle_with("p1")
    lifecycle.replace(post)

    lifecycle.note_reply(SENDER, "¿Lo subo?", "p1")

    assert lifecycle.approval_for(SENDER, "sí", attached=False, recent_photos=[]) == Approval()


def test_approval_state_is_per_sender() -> None:
    lifecycle, _ = lifecycle_with("p1")
    lifecycle.note_reply(SENDER, "¿Lo subo?")

    approval = lifecycle.approval_for(OTHER_SENDER, "sí", attached=False, recent_photos=[])

    assert approval == Approval()
