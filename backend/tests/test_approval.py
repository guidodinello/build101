import pytest

from app.conversation.approval import Approval, classify, decide, ordinal
from app.posts.store import Post, PostImage


def pending_post(post_id: str) -> Post:
    return Post(
        post_id, "59899000001", [PostImage(f"/media/{post_id}.jpg", b"x")], f"caption {post_id}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "subilo",
        "Subilo!",
        "súbilo",
        "SUBILOOOO",
        "subila",
        "publicalo",
        "dale, subila",
        "aprobado",
        "lo apruebo",
        "ya podés subirlo",
        "me encanta, subilo",
        "subilo ahora",
        "subilo ya",
    ],
)
def test_an_instruction_to_publish_approves(text: str) -> None:
    assert classify(text) == "approve"


@pytest.mark.parametrize(
    "text",
    [
        "me encanta",
        "está lindo",
        "dale",
        "buenísimo!!",
        "subí estas fotos",
        "armame un post",
        "no lo subas",
        "todavía no, subilo después",
        "nunca lo publiques",
        "",
    ],
)
def test_praise_negation_and_other_requests_do_not_approve(text: str) -> None:
    assert classify(text) == "none"


@pytest.mark.parametrize(
    "text", ["subilo mañana a la tarde", "publicalo el viernes", "subilo a las 18:30", "subilo hoy"]
)
def test_an_approval_with_a_time_is_scheduling(text: str) -> None:
    assert classify(text) == "approve_later"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", 1),
        ("el 2", 2),
        ("la primera", 1),
        ("la segunda", 2),
        ("el último", 3),
        ("la última", 3),
        ("la 3", 3),
        ("4", None),
        ("0", None),
        ("hola", None),
        ("la primera por favor", None),
        ("subilo", None),
    ],
)
def test_ordinal_picks_a_number_from_a_short_reply(text: str, expected: int | None) -> None:
    assert ordinal(text, count=3) == expected


def test_one_pending_post_is_approved_by_an_explicit_instruction() -> None:
    approval, awaiting = decide("subilo", [pending_post("p1")], False, False)

    assert approval == Approval(post_id="p1")
    assert not awaiting


def test_several_pending_posts_ask_which_one_and_wait_for_a_number() -> None:
    approval, awaiting = decide("subilo", [pending_post("p1"), pending_post("p2")], False, False)

    assert approval.post_id is None
    assert approval.reason == "several_pending"
    assert [(item["n"], item["post_id"]) for item in approval.pending] == [(1, "p1"), (2, "p2")]
    assert awaiting


def test_a_number_after_several_pending_picks_that_post_in_code() -> None:
    pending = [pending_post("p1"), pending_post("p2")]

    approval, awaiting = decide("la segunda", pending, True, False)

    assert approval.post_id == "p2"
    assert not awaiting


def test_a_number_without_the_question_before_it_approves_nothing() -> None:
    approval, _ = decide("2", [pending_post("p1"), pending_post("p2")], False, False)

    assert approval.post_id is None


def test_a_reply_that_is_not_a_number_clears_the_wait() -> None:
    pending = [pending_post("p1"), pending_post("p2")]

    approval, awaiting = decide("hola", pending, True, False)

    assert approval.post_id is None
    assert not awaiting


def test_no_pending_post_and_scheduling_and_praise_give_their_reasons() -> None:
    assert decide("subilo", [], False, False)[0].reason == "no_pending_post"
    assert decide("subilo mañana", [pending_post("p1")], False, False)[0].reason == (
        "scheduling_not_available"
    )
    assert decide("me encanta", [pending_post("p1")], False, False)[0].reason == (
        "approval_not_explicit"
    )


def test_photos_make_it_a_post_request_even_with_an_instruction() -> None:
    approval, awaiting = decide("subilas así", [pending_post("p1")], True, True)

    assert approval.post_id is None
    assert not awaiting
