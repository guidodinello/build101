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
