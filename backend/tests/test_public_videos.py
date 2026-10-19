import re

from fastapi.testclient import TestClient

from app.channels.router import get_inbound_handler
from app.main import app
from app.media.public import PublicVideos, get_public_videos


def serve(videos: PublicVideos) -> TestClient:
    app.dependency_overrides[get_public_videos] = lambda: videos
    app.dependency_overrides[get_inbound_handler] = lambda: None
    return TestClient(app)


def test_add_returns_a_path_relative_to_the_public_url() -> None:
    path = PublicVideos().add(b"mp4 bytes")

    assert re.fullmatch(r"/media/[\w-]+\.mp4", path)


def test_a_stored_video_is_served_by_its_path_and_others_are_not() -> None:
    videos = PublicVideos()
    path = videos.add(b"mp4 bytes")
    try:
        with serve(videos) as client:
            found = client.get(path)
            missing = client.get("/media/not-a-token.mp4")
    finally:
        app.dependency_overrides.clear()

    assert found.status_code == 200
    assert found.headers["content-type"] == "video/mp4"
    assert found.content == b"mp4 bytes"
    assert missing.status_code == 404


def test_head_answers_with_the_headers_of_the_video_and_no_body() -> None:
    videos = PublicVideos()
    path = videos.add(b"mp4 bytes")
    try:
        with serve(videos) as client:
            found = client.head(path)
            missing = client.head("/media/not-a-token.mp4")
    finally:
        app.dependency_overrides.clear()

    assert found.status_code == 200
    assert found.headers["content-type"] == "video/mp4"
    assert found.headers["content-length"] == str(len(b"mp4 bytes"))
    assert found.content == b""
    assert missing.status_code == 404


def test_the_oldest_video_is_dropped_past_the_cap() -> None:
    videos = PublicVideos(max_videos=1)
    first = videos.add(b"1").removeprefix("/media/").removesuffix(".mp4")
    videos.add(b"2")

    assert videos.get(first) is None


def test_keep_serves_an_evicted_video_again_and_makes_it_the_newest() -> None:
    videos = PublicVideos(max_videos=2)
    first = videos.add(b"1")
    second = videos.add(b"2")
    videos.keep(first, b"1")
    videos.add(b"3")

    assert videos.get(first.removeprefix("/media/").removesuffix(".mp4")) == b"1"
    assert videos.get(second.removeprefix("/media/").removesuffix(".mp4")) is None


def test_an_evicted_clip_is_still_served_while_its_post_holds_it() -> None:
    videos = PublicVideos(max_videos=1)
    held = {"clip": b"1"}
    path = videos.add(held["clip"])
    videos.serve_from(lambda p: held["clip"] if p == path else None)
    videos.add(b"2")  # evicts the first from the LRU
    try:
        with serve(videos) as client:
            got, head = client.get(path), client.head(path)
            missing = client.get("/media/not-a-token.mp4")
    finally:
        app.dependency_overrides.clear()

    assert got.status_code == 200
    assert got.content == b"1"
    assert head.status_code == 200
    assert head.headers["content-length"] == "1"
    assert missing.status_code == 404
