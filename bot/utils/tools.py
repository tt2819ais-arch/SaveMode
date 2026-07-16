"""Утилиты для новых команд-инструментов (.qr .calc .pass .mock .rev
.roll .pick .count .b64 .spoiler .tr).

Логика вынесена в чистые функции — их легко покрыть тестами.
"""
import ast
import base64
import io
import math
import operator
import random
import re
import secrets
import string

# ─────────────────────── .calc — безопасный калькулятор ───────────────────────

_ALLOWED_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "abs": abs, "round": round, "log": math.log, "log10": math.log10,
    "floor": math.floor, "ceil": math.ceil, "exp": math.exp,
    "min": min, "max": max, "pow": pow,
}
_ALLOWED_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Недопустимое значение")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left),
                                       _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _ALLOWED_FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"Функция {node.func.id} недоступна")
        return fn(*[_eval_node(a) for a in node.args])
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        raise ValueError(f"Имя {node.id} недоступно")
    raise ValueError("Недопустимое выражение")


def calc(expr: str):
    """Безопасно вычислить арифметическое выражение."""
    expr = (expr or "").strip()
    if not expr:
        raise ValueError("Пустое выражение")
    if len(expr) > 200:
        raise ValueError("Слишком длинное выражение")
    tree = ast.parse(expr, mode="eval")
    result = _eval_node(tree.body)
    # Красивый вывод целых
    if isinstance(result, float) and result.is_integer():
        return int(result)
    if isinstance(result, float):
        return round(result, 10)
    return result


# ─────────────────────── .pass — генератор паролей ───────────────────────

def gen_password(length: int = 16) -> str:
    length = max(4, min(128, int(length)))
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    # гарантируем разнообразие
    pools = [string.ascii_lowercase, string.ascii_uppercase,
             string.digits, "!@#$%^&*()-_=+"]
    pwd = [secrets.choice(p) for p in pools]
    pwd += [secrets.choice(alphabet) for _ in range(length - len(pwd))]
    random.SystemRandom().shuffle(pwd)
    return "".join(pwd)


# ─────────────────────── .mock — насмешливый регистр ───────────────────────

def mock_case(text: str) -> str:
    out, upper = [], False
    for ch in text:
        if ch.isalpha():
            out.append(ch.upper() if upper else ch.lower())
            upper = not upper
        else:
            out.append(ch)
    return "".join(out)


# ─────────────────────── .rev — реверс ───────────────────────

def reverse_text(text: str) -> str:
    return text[::-1]


# ─────────────────────── .roll — кубики / случайное число ───────────────────────

def roll(arg: str = "") -> str:
    arg = (arg or "").strip().lower()
    if not arg:
        return f"🎲 {random.randint(1, 100)} (1–100)"
    # NdM
    m = re.fullmatch(r"(\d+)d(\d+)", arg)
    if m:
        n, sides = int(m.group(1)), int(m.group(2))
        if not (1 <= n <= 50 and 2 <= sides <= 1000):
            raise ValueError("Диапазон: до 50 кубиков, граней 2–1000")
        rolls = [random.randint(1, sides) for _ in range(n)]
        return f"🎲 {' + '.join(map(str, rolls))} = <b>{sum(rolls)}</b>"
    parts = arg.split()
    if len(parts) == 2 and all(p.lstrip("-").isdigit() for p in parts):
        lo, hi = int(parts[0]), int(parts[1])
        if lo > hi:
            lo, hi = hi, lo
        return f"🎲 <b>{random.randint(lo, hi)}</b> ({lo}–{hi})"
    if arg.isdigit():
        hi = int(arg)
        if hi < 1:
            raise ValueError("Число должно быть ≥ 1")
        return f"🎲 <b>{random.randint(1, hi)}</b> (1–{hi})"
    raise ValueError("Формат: .roll | .roll 6 | .roll 2d20 | .roll 10 50")


# ─────────────────────── .pick — выбор варианта ───────────────────────

def pick(text: str) -> str:
    raw = re.split(r"[|,]", text or "")
    options = [o.strip() for o in raw if o.strip()]
    if len(options) < 2:
        raise ValueError("Дайте минимум 2 варианта через «|» или запятую")
    return random.choice(options)


# ─────────────────────── .count — статистика текста ───────────────────────

def count_text(text: str) -> str:
    text = text or ""
    chars = len(text)
    no_spaces = len(re.sub(r"\s", "", text))
    words = len(text.split())
    lines = len(text.splitlines()) or (1 if text else 0)
    return (f"Символов: <b>{chars}</b>\n"
            f"Без пробелов: <b>{no_spaces}</b>\n"
            f"Слов: <b>{words}</b>\n"
            f"Строк: <b>{lines}</b>")


# ─────────────────────── .b64 — Base64 ───────────────────────

def b64(mode: str, text: str) -> str:
    mode = (mode or "").strip().lower()
    if mode in ("e", "enc", "encode", "-e"):
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if mode in ("d", "dec", "decode", "-d"):
        try:
            return base64.b64decode(text.encode("ascii")).decode("utf-8")
        except Exception:
            raise ValueError("Не удалось декодировать Base64")
    raise ValueError("Укажите режим: e (кодировать) или d (декодировать)")


# ─────────────────────── .qr — QR-код ───────────────────────

def make_qr_png(data: str) -> bytes:
    import qrcode
    if not data or not data.strip():
        raise ValueError("Пустые данные для QR")
    if len(data) > 1500:
        raise ValueError("Слишком много данных для QR-кода")
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────── .tr — перевод ───────────────────────

def parse_tr_args(text: str) -> tuple[str, str]:
    """Разобрать аргументы .tr → (код_языка, текст). Без кода → 'ru'."""
    text = (text or "").strip()
    parts = text.split(maxsplit=1)
    # Код языка — двухбуквенный ISO 639-1 (en, ru, de, es, fr, …).
    if len(parts) == 2 and re.fullmatch(r"[a-zA-Z]{2}", parts[0]):
        return parts[0].lower(), parts[1]
    return "ru", text


async def translate(text: str, target: str) -> str:
    """Перевод через бесплатный публичный endpoint Google (best-effort)."""
    import aiohttp
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "auto", "tl": target,
              "dt": "t", "q": text}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, timeout=15) as r:
            data = await r.json(content_type=None)
    return "".join(chunk[0] for chunk in data[0] if chunk and chunk[0])
