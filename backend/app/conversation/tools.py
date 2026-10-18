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
                "description": "Ids of the photos to use, from <recent_photos> (e.g. f1).",
            },
            "style": {
                "type": "string",
                "enum": ["photos", "design"],
                "description": (
                    "photos: the Owner's photos as they are (cropped to 4:5), with a caption. "
                    "design: new images made from the photos, with text on them."
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

TOOLS = [CREATE_POST]
