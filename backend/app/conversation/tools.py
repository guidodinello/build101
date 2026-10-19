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
                    "Only when remaking a sent post with other photos or another style: the id "
                    "of that post (from its [post ... sent] note), so the old one can no longer "
                    "be published and the new one keeps what the Owner didn't ask to change. "
                    "For any other change use revise_post."
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

REVISE_POST: Tool = {
    "type": "function",
    "name": "revise_post",
    "description": (
        "Remake a post the Owner already got, changing only what they asked and keeping "
        "everything else (photos, style, logo, the rest of the text and design). Use it for "
        'any change to a sent post ("más corto", "cambiale el título", "sin emojis", "otro '
        'color de fondo"). The new version reaches the Owner a few minutes later and replaces '
        "the old one."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "post_id": {
                "type": "string",
                "description": "Id of the post to change, from its [post ... sent] note.",
            },
            "change": {
                "type": "string",
                "description": "The change, in the Owner's words, with every detail they gave.",
            },
            "part": {
                "type": "string",
                "enum": ["caption", "images"],
                "description": (
                    "caption: only the text that goes under the post (caption and hashtags); "
                    "the images stay exactly as they are, nothing is generated. images: what is "
                    "on the images (a design's headlines, colors, layout or scene); only for a "
                    "design."
                ),
            },
        },
        "required": ["post_id", "change", "part"],
        "additionalProperties": False,
    },
}

LIST_POSTS: Tool = {
    "type": "function",
    "name": "list_posts",
    "description": (
        "The posts made for the Owner, oldest first, with their status (pending_approval, "
        "approved, publishing, publish_pending, published, failed, discarded, replaced) and "
        'Instagram link. For questions like "¿ya se subió?" or "¿qué posts tengo '
        'pendientes?", or to find a post id the conversation no longer shows.'
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

REMEMBER: Tool = {
    "type": "function",
    "name": "remember",
    "description": (
        "Keep a fact about the business or a standing preference of the Owner for every future "
        'conversation and post: "no poner precios en los posts", "abrimos sábados de 9 a 13", '
        '"prefiere carruseles", "el envío es gratis en Montevideo". Not for details of a '
        "single post. Saved notes appear in <owner_notes>; never save one that is already "
        "there."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "One short sentence in Spanish, in the Owner's words if you can.",
            },
        },
        "required": ["note"],
        "additionalProperties": False,
    },
}

FORGET: Tool = {
    "type": "function",
    "name": "forget",
    "description": (
        "Drop a note from <owner_notes> that the Owner corrected or no longer wants (to "
        "change one, forget it and remember the new version)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "The note's id from <owner_notes>."},
        },
        "required": ["note_id"],
        "additionalProperties": False,
    },
}

UPDATE_BRAND: Tool = {
    "type": "function",
    "name": "update_brand",
    "description": (
        "Change the brand itself (<brand_brain>): how it sounds, who it talks to, what it "
        "posts about, its colors, what it sells or what it must avoid. Use it for the "
        "correction after [brand fix asked], and when the Owner asks to change their brand "
        "later. The new brand summary reaches the Owner in a minute, for them to confirm."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "change": {
                "type": "string",
                "description": "The change, in the Owner's words, with every detail they gave.",
            },
        },
        "required": ["change"],
        "additionalProperties": False,
    },
}

TOOLS: list[Tool] = [
    CREATE_POST,
    REVISE_POST,
    APPROVE_POST,
    LIST_POSTS,
    REMEMBER,
    FORGET,
    UPDATE_BRAND,
]
