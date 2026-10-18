from fastapi.testclient import TestClient

from app.channels.router import get_inbound_handler
from app.main import app
from app.media.public import PublicImages, get_public_images


def test_a_stored_image_is_served_by_its_path_and_others_are_not() -> None:
    images = PublicImages()
    path = images.add(b"jpeg bytes")
    app.dependency_overrides[get_public_images] = lambda: images
    app.dependency_overrides[get_inbound_handler] = lambda: None
    try:
        with TestClient(app) as client:
            found = client.get(path)
            missing = client.get("/media/not-a-token.jpg")
    finally:
        app.dependency_overrides.clear()

    assert found.status_code == 200
    assert found.headers["content-type"] == "image/jpeg"
    assert found.content == b"jpeg bytes"
    assert missing.status_code == 404


def test_the_oldest_image_is_dropped_past_the_cap() -> None:
    images = PublicImages(max_images=1)
    first = images.add(b"1").removeprefix("/media/").removesuffix(".jpg")
    images.add(b"2")

    assert images.get(first) is None


def test_keep_serves_an_evicted_image_again_at_the_same_path() -> None:
    images = PublicImages(max_images=2)
    path = images.add(b"1")
    images.add(b"2")
    images.add(b"3")
    token = path.removeprefix("/media/").removesuffix(".jpg")
    assert images.get(token) is None

    images.keep(path, b"1")

    assert images.get(token) == b"1"


def test_keep_makes_a_live_image_the_newest() -> None:
    images = PublicImages(max_images=2)
    first = images.add(b"1")
    second = images.add(b"2")

    images.keep(first, b"1")
    images.add(b"3")

    assert images.get(first.removeprefix("/media/").removesuffix(".jpg")) == b"1"
    assert images.get(second.removeprefix("/media/").removesuffix(".jpg")) is None
