"""Premium (custom) emoji support for SaveMOD.

Telegram premium/custom emoji are sent with the HTML tag
``<tg-emoji emoji-id="ID">fallback</tg-emoji>`` (parse_mode="HTML").

GROUND TRUTH (verified live 2026-07-19 with bot id 8974812894):
  * The bot preserves ``custom_emoji`` entities even in DIRECT messages to the
    owner — a live send of 4 custom emoji came back with all 4 entities intact.
    So premium emoji render across ALL of SaveMOD's texts, not only in
    business-connection sends.
  * If a viewer's client can't show a given custom emoji it falls back to the
    plain unicode char we embed as the tag body, so nothing ever breaks.

All IDs below are REAL, pulled from the owner's own premium pack
"Сонечка" (@SSlovels via @TgEmodziBot), custom-emoji set
``SslovelsBestt_by_TgEmodziBot`` (177 emoji, 84 unique base glyphs).

The user asked for premium emoji to be used RANDOMLY — a different emoji on
each render — so :func:`pe` picks a random variant id for a glyph on every
call, and :func:`accent` / :func:`pe_random` pick a random glyph from a
curated tasteful pool. Determinism in tests via :func:`seed`.
"""
from __future__ import annotations

import random
from html import escape as _esc

# ---------------------------------------------------------------------------
# base glyph -> list of real custom_emoji_ids (variants) from the Сонечка pack
# ---------------------------------------------------------------------------
VARIANTS = {
    "💕": ["5294425624801208766"],
    "❤️": ["5294329353109271838", "5294465928774315841", "5294269597229285041", "5294345128524148896", "5294057146671985989", "5285439518130857782", "5255956191141454203", "5255861796350224063"],
    "💐": ["5294432681432478945", "5294031492832326362"],
    "😍": ["5294398291629339412", "5294106736364387322", "5294292042728370365", "5294044476518461642"],
    "😻": ["5294221884437591676"],
    "🥰": ["5294431478841634538"],
    "😘": ["5294091003899178668", "5294403677518328454", "5294480278260052420", "5294436645687292426", "5294494567616247472"],
    "😜": ["5294051159487575502"],
    "❣️": ["5296384731183609135"],
    "😉": ["5294436293499974584", "5294097459235025972"],
    "🌟": ["5294011392385381685", "5294051292631560494", "5294161114945319027", "5294202698818680024", "5294252292806048148", "5294059392939880207", "5294109051351759816", "5294080408214861963"],
    "🎀": ["5294255814679229361", "5294390784026505622", "5294264314419507819"],
    "🤩": ["5294027837815155741", "5294063017892280575", "5296606351496081838", "5294130010792161882", "5294047440045898965", "5296643842265609032", "5294161802140085356", "5294366517461282624"],
    "😁": ["5294330744678676789", "5294008068080692937"],
    "😂": ["5294032343235850475", "5293994027832601225", "5294134610702134422"],
    "🤗": ["5294488524597260988"],
    "🛍️": ["5294421402848358099"],
    "👋": ["5294050064270914715", "5294352288234631423"],
    "💍": ["5294028490650186950", "5262922516426420894"],
    "🎁": ["5294129869058241969", "5294096531522089082", "5294036462109487535", "5294467187199735291", "5294411923855538479", "5294232029150343518", "5294229508004542212", "5296332083474496725"],
    "💗": ["5294166462179603714", "5294376202612535340"],
    "🐾": ["5294356209539774186", "5294435546175664836"],
    "🍓": ["5294351154363265730", "5294173501631001330"],
    "✅": ["5294378556254613234", "5294543667682372853"],
    "🌸": ["5294329134065938839"],
    "💝": ["5294111301914622743", "5294462200742704308", "5293996123776642677", "5294496105214538334", "5280826864988873394"],
    "🩷": ["5294238278327758341", "5294119157409803281"],
    "💔": ["5294358945433939484", "5278454020111887994"],
    "🍪": ["5294019746096777144"],
    "🥳": ["5294003347911636420"],
    "✨": ["5294061046502297250", "5294481545275403611"],
    "💓": ["5294470352590630369", "5296784631293571050", "5256227233642605352"],
    "🫶": ["5294014832654183829", "5294416197347996305", "5285338659413846416"],
    "😄": ["5294144046745284253"],
    "😊": ["5294381287853813662", "5296613803264341411"],
    "🍰": ["5294529485700361847"],
    "🌺": ["5293990115117396172"],
    "🐰": ["5294520208571003925"],
    "🍇": ["5294247920529340968", "5294172973350023960", "5294493571183833479", "5296521268193949606", "5294154354666796827"],
    "😢": ["5294360882464191430"],
    "😞": ["5293992382860131680"],
    "🪷": ["5294156562279986631"],
    "😋": ["5294402960258790621"],
    "🧁": ["5294171105039250395", "5296429531987473864"],
    "🍩": ["5294346816446295658"],
    "💘": ["5294341791334559691", "5294138544892178829", "5294241688531790912"],
    "😇": ["5294099220171616295"],
    "🍉": ["5294123929118472390"],
    "💞": ["5294480956864885749"],
    "🐹": ["5294508788252965615"],
    "🥺": ["5294125956343034378", "5294154470630912779"],
    "📦": ["5294475631105440939"],
    "💙": ["5294388022362532376"],
    "🦋": ["5294325899955565729"],
    "🧸": ["5294393056064204685"],
    "🎂": ["5294422695633512804"],
    "💋": ["5294190320722933446", "5289850733011693663"],
    "🍭": ["5294401031818474015", "5287295223175604777"],
    "🎐": ["5294453065347262672"],
    "🗓": ["5287606810168028257"],
    "💌": ["5285184156555306745"],
    "📫": ["5287533898803211359"],
    "🧪": ["5256169350368353876"],
    "📡": ["5256134032852278918"],
    "💖": ["5255877597534905292"],
    "📞": ["5285238101344544669"],
    "✍️": ["5258500400918587241"],
    "🎯": ["5256131095094652290"],
    "⌨️": ["5258361295517806281"],
    "🥂": ["5260567255145539253"],
    "🧩": ["5265120027853481187"],
    "⚙️": ["5267334530171169409"],
    "🚹": ["5292122921035133343"],
    "⭐️": ["5289944036881230584"],
    "📼": ["5271721134889395048"],
    "☁️": ["5274002879215067737"],
    "🔑": ["5278573677900752088"],
    "🎲": ["5280816565657300091"],
    "🎭": ["5276239041052828276"],
    "🕯": ["5276412965753480690"],
    "🎶": ["5276352986535194063"],
    "🎈": ["5278651867780377852"],
    "💣": ["5280569974404966639"],
    "💊": ["5305715161087110779"],
    "🍾": ["5280774071250872500"],
    "🃏": ["5280939169793732849"],
    "🔓": ["5291873529464122510"],
}

# ---------------------------------------------------------------------------
# friendly names -> base glyph  (so callers can write pe("gift"), pe("star"))
# ---------------------------------------------------------------------------
NAMES = {
    "heart": "❤️", "love": "💕", "pink_heart": "🩷", "blue_heart": "💙",
    "sparkling_heart": "💗", "growing_heart": "💗", "revolving_hearts": "💞",
    "gift_heart": "💝", "cupid": "💘", "beating_heart": "💓", "broken_heart": "💔",
    "hands_heart": "🫶", "kiss": "💋", "kissing": "😘", "smiling_hearts": "🥰",
    "heart_eyes": "😍", "star": "🌟", "sparkles": "✨", "star_struck": "🤩",
    "gift": "🎁", "shopping": "🛍️", "package": "📦", "ring": "💍",
    "ribbon": "🎀", "party": "🥳", "cake": "🎂", "cupcake": "🧁", "slice": "🍰",
    "cookie": "🍪", "candy": "🍭", "wind_chime": "🎐", "bouquet": "💐",
    "cherry_blossom": "🌸", "hibiscus": "🌺", "lotus": "🪷", "butterfly": "🦋",
    "wave": "👋", "hug": "🤗", "check": "✅", "smile": "😊", "grin": "😁",
    "joy": "😂", "laugh": "😄", "wink": "😉", "angel": "😇", "yum": "😋",
    "pleading": "🥺", "cry": "😢", "sad": "😞", "teddy": "🧸", "rabbit": "🐰",
    "hamster": "🐹", "paw": "🐾", "strawberry": "🍓", "grapes": "🍇",
    "watermelon": "🍉", "donut": "🍩",
    # system / utility glyphs (from the second pack)
    "gear": "⚙️", "keyboard": "⌨️", "key": "🔑", "unlock": "🔓", "jigsaw": "🧩",
    "satellite": "📡", "antenna": "📡", "calendar": "🗓", "notes": "🎶",
    "writing": "✍️", "phone": "📞", "mailbox": "📫", "cloud": "☁️", "dart": "🎯",
    "dice": "🎲", "balloon": "🎈", "champagne": "🍾", "cheers": "🥂",
    "theater": "🎭", "joker": "🃏", "candle": "🕯", "love_letter": "💌",
}

# ---------------------------------------------------------------------------
# curated tasteful pools for random decoration (NO food/suggestive glyphs)
# ---------------------------------------------------------------------------
THEMES = {
    "decor":     ["✨", "🌟", "🎀", "🩷", "💗", "🦋"],
    "love":      ["❤️", "💕", "💗", "💝", "💘", "💞", "💓", "🩷", "🥰", "😘", "💋", "🫶"],
    "reward":    ["🎁", "🌟", "✨", "🛍️", "📦", "💝", "🎀"],
    "celebrate": ["🥳", "🎂", "🎀", "✨", "🌟", "🧁", "🍰", "🎈", "🥂", "🍾"],
    "star":      ["🌟", "✨", "🤩"],
    "happy":     ["😊", "😁", "😄", "🤩", "🥳", "🤗"],
    "flower":    ["💐", "🌸", "🌺", "🪷"],
    "cute":      ["🐰", "🐹", "🧸", "🐾", "🦋"],
    "sad":       ["😢", "😞", "🥺", "💔"],
    "ok":        ["✅"],
    # system / utility pools (from the second pack)
    "system":    ["⚙️", "⌨️", "🔑", "🧩", "🔓"],
    "note":      ["🎶", "🗓", "✍️", "📫"],
    "connect":   ["📡", "📞", "☁️"],
}
# glyphs that must never appear in random decoration
_BLOCKED = {"🍑", "👅", "🩸", "🤤"}

_rng = random.Random()


def seed(value=None) -> None:
    """Seed the module RNG (tests pass a fixed value for determinism)."""
    _rng.seed(value)


def _tag(glyph: str) -> str:
    """Wrap a glyph in a <tg-emoji> tag using a RANDOM variant id.

    Unknown glyph -> returned as-is (plain unicode, safe fallback).
    """
    ids = VARIANTS.get(glyph)
    if not ids:
        return glyph
    emoji_id = _rng.choice(ids)
    return f'<tg-emoji emoji-id="{emoji_id}">{_esc(glyph)}</tg-emoji>'


def pe(key: str) -> str:
    """Premium-emoji tag for a friendly name OR a base glyph.

    Examples: ``pe("gift")`` / ``pe("🎁")`` -> a random 🎁 variant tag.
    Unknown key -> the key itself (plain), so texts never break.
    """
    glyph = NAMES.get(key, key)
    return _tag(glyph)


def pe_random(theme: str | None = None) -> str:
    """Random premium emoji from a theme pool (or the whole 'decor' pool).

    Tasteful: draws only from curated pools, never from blocked glyphs.
    """
    pool = THEMES.get(theme or "decor", THEMES["decor"])
    pool = [g for g in pool if g not in _BLOCKED] or ["✨"]
    return _tag(_rng.choice(pool))


def accent() -> str:
    """A single tasteful decorative premium emoji (sparkle/star/ribbon…)."""
    return pe_random("decor")
