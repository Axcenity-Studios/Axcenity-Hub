"""Luau highlighting for the docs' code blocks, in the editor's own syntax colours.

`EditorLuauLexer` is a Pygments lexer that splits code exactly as the editor's
script tab does (`crates/editor-kit/src/lua_syntax.rs` `tokens`): its keywords,
`true`/`false`/`nil` as literals, its 34 builtins (never after `.` or `:`), numbers
(`0xFF`, `1.5e-3`), quoted strings that stop at the line's end, and long-bracket
strings and comments (`[==[ … ]==]`, `--[[ … ]]`) that span lines. Pygments' own
Luau lexer marks a different set of names as builtins, so it isn't used.

`highlight(code, language)` renders a fenced block's contents as HTML: `luau` and
`lua` get `<span class="luau-…">` pieces (the `.luau-*` rules in styles/source.css
colour them, contrast-tested in both schemes); every other language is escaped
plain text.
"""

from collections.abc import Iterator

from django.utils.html import escape
from pygments.lexer import Lexer
from pygments.token import Comment, Keyword, Name, Number, String, Text, _TokenType

from marketing.drawings import LUAU_BUILTINS, LUAU_KEYWORDS, LUAU_LITERALS

LUAU_LANGUAGES = frozenset({"luau", "lua"})

# The editor's kinds of piece, as Pygments token types, and the class each is drawn with.
KINDS: dict[_TokenType, str] = {
    Keyword: "keyword",
    Keyword.Constant: "literal",
    Name.Builtin: "builtin",
    Number: "number",
    String: "string",
    Comment: "comment",
}


def _is_alpha(char: str) -> bool:
    return char.isascii() and (char.isalpha() or char == "_")


def _is_alnum(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char == "_")


def _long_bracket_level(code: str, i: int) -> int | None:
    """If a long bracket (`[[`, `[=[`, `[==[`…) starts at `i`, how many `=` it has."""
    if code[i : i + 1] != "[":
        return None
    j = i + 1
    while j < len(code) and code[j] == "=":
        j += 1
    return j - i - 1 if code[j : j + 1] == "[" else None


def _long_bracket_end(code: str, i: int, level: int) -> int:
    """After the long bracket opened at `i` closes (`]` + `=`×level + `]`), or the end."""
    close = "]" + "=" * level + "]"
    at = code.find(close, i + level + 2)
    return len(code) if at < 0 else at + len(close)


def _line_end(code: str, i: int) -> int:
    at = code.find("\n", i)
    return len(code) if at < 0 else at


def _quoted_string_end(code: str, i: int) -> int:
    """After the closing quote, or at the end of the line if it's never closed."""
    quote, j = code[i], i + 1
    while j < len(code):
        char = code[j]
        if char == "\\" and j + 1 < len(code) and code[j + 1].isascii():
            j += 2
        elif char == "\n":
            return j
        elif char == quote:
            return j + 1
        else:
            j += 1
    return len(code)


def _number_end(code: str, i: int) -> int:
    """Covers `12`, `3.5`, `.5`, `1e-3`, `0xFF` and `0x1p4`."""
    exponent = "pP" if code[i : i + 2] in ("0x", "0X") else "eE"
    j = i
    while j < len(code):
        char = code[j]
        sign = char in "+-" and j > i and code[j - 1] in exponent
        if _is_alnum(char) or char == "." or sign:
            j += 1
        else:
            break
    return j


def editor_tokens(code: str) -> Iterator[tuple[int, _TokenType, str]]:
    """(start, token type, text) pieces covering all of `code`, as the editor splits it."""
    i, plain_start = 0, 0
    while i < len(code):
        start, char = i, code[i]
        if code.startswith("--", i):
            level = _long_bracket_level(code, i + 2)
            i = _long_bracket_end(code, i + 2, level) if level is not None else _line_end(code, i)
            kind = Comment
        elif char in "\"'":
            i, kind = _quoted_string_end(code, i), String
        elif (level := _long_bracket_level(code, i)) is not None:
            i, kind = _long_bracket_end(code, i, level), String
        elif (char.isascii() and char.isdigit()) or (
            char == "." and code[i + 1 : i + 2].isascii() and code[i + 1 : i + 2].isdigit()
        ):
            i, kind = _number_end(code, i), Number
        elif _is_alpha(char):
            while i < len(code) and _is_alnum(code[i]):
                i += 1
            word = code[start:i]
            field = start > 0 and code[start - 1] in ".:"
            if word in LUAU_KEYWORDS:
                kind = Keyword
            elif word in LUAU_LITERALS:
                kind = Keyword.Constant
            elif word in LUAU_BUILTINS and not field:
                kind = Name.Builtin
            else:
                kind = Text
        else:
            i, kind = i + 1, Text
        if kind is Text:
            continue
        if plain_start < start:
            yield plain_start, Text, code[plain_start:start]
        yield start, kind, code[start:i]
        plain_start = i
    if plain_start < len(code):
        yield plain_start, Text, code[plain_start:]


class EditorLuauLexer(Lexer):
    """Luau, split the way the Axcenity editor's script tab splits it."""

    name = "Luau (Axcenity editor)"
    aliases = ["axcenity-luau"]

    def __init__(self, **options):
        # Keep the code exactly as written: no stripped or added newlines, no tab expansion.
        options.setdefault("stripnl", False)
        options.setdefault("ensurenl", False)
        super().__init__(**options)

    def get_tokens_unprocessed(self, text):
        yield from editor_tokens(text)


def highlight(code: str, language: str) -> str:
    """A fenced block's contents as HTML: Luau and Lua in the editor's colours, anything
    else as escaped plain text. The trailing newline the fence leaves is dropped."""
    code = code.removesuffix("\n")
    if language.lower() not in LUAU_LANGUAGES:
        return str(escape(code))
    pieces = []
    for kind, text in EditorLuauLexer().get_tokens(code):
        css = KINDS.get(kind)
        pieces.append(f'<span class="luau-{css}">{escape(text)}</span>' if css else escape(text))
    return "".join(pieces)
