from app.carousel.schemas import MAX_SLIDES
from app.llm.client import Tool
from app.posts.maker import MIN_SLIDES

CREATE_POST: Tool = {
    "type": "function",
    "name": "create_post",
    "description": (
        "Start making an Instagram post from the Owner's photos: one photo makes a single-image "
        "post, several make a carousel with one slide per photo. Call it only when the Owner "
        "asked for a post and you know whether they want the photos as they are or a design; "
        "never for greetings, questions or comments on an existing post. It returns at once and "
        "the images reach the Owner a few minutes later."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": (
                    "What the post is about, in the Owner's words: the product, the angle, and "
                    "every detail they gave (prices, conditions, what to highlight)."
                ),
            },
            "asset_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Ids of the photos to use, from <recent_photos> (e.g. f1) or "
                    "<brand_photos> (e.g. b1)."
                ),
            },
            "style": {
                "type": "string",
                "enum": ["photos", "design"],
                "description": (
                    "photos: the Owner's photos as they are (cropped to 4:5), with a caption. "
                    "design: new images made from the photos, with text on them."
                ),
            },
            "replaces": {
                "type": "string",
                "description": (
                    "Only when remaking a post that was already sent because the Owner asked "
                    "for a change: the id of that post (from its [post ... sent] note), so the "
                    "old one can no longer be published."
                ),
            },
            "with_logo": {
                "type": "boolean",
                "description": (
                    "true only when the Owner asked for their logo on the post and "
                    "<brand_logo> is present: it goes small in a corner of every image, exactly "
                    "as they uploaded it."
                ),
            },
            "slide_count": {
                "type": "integer",
                "minimum": MIN_SLIDES,
                "maximum": MAX_SLIDES,
                "description": (
                    "design only, and only when the Owner asked for a number of slides that "
                    "differs from the number of photos."
                ),
            },
        },
        "required": ["brief", "asset_ids", "style"],
        "additionalProperties": False,
    },
}

APPROVE_POST: Tool = {
    "type": "function",
    "name": "approve_post",
    "description": (
        "Publish a post to the Owner's Instagram now. Call it only when the Owner's last "
        'message explicitly tells you to publish it ("subilo", "publicalo", "dale, '
        'subila"). Never for praise ("me encanta", "está lindo"): ask "¿Lo subo?" '
        "instead. It returns at once; the Owner gets the Instagram link when it is live."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "post_id": {
                "type": "string",
                "description": "Id of the post to publish, from its [post ... sent] note.",
            },
            "next": {
                "type": "string",
                "enum": ["publish_now"],
                "description": "publish_now: publish right away.",
            },
        },
        "required": ["post_id", "next"],
        "additionalProperties": False,
    },
}

TOOLS = [CREATE_POST, APPROVE_POST]
