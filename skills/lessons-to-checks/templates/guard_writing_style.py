"""PreToolUse hook: refuse, once, documentation text that reads like LLM-speak.

reply_checks.py reads chat replies. This hook reads what Claude writes into
documentation files: a README, a guide, release notes, a letter. It runs
before a Write, Edit or MultiEdit call on a file whose extension is in
DOC_EXTENSIONS (.md, .markdown and .rst by default). For a Write it checks
the whole new content. For an Edit or MultiEdit it checks only the new text
being written (new_string), so older text in the file never counts against
an edit. License files (LICENSE, LICENSE.md, LICENCE.txt and the like) are
never checked: their wording is fixed by the license.

The checks, each a list of patterns at the top of this file:

1. "em dash": an em dash anywhere, and an en dash used as a dash (with a
   space on each side). An en dash in a range such as 10-20 written with an
   en dash passes.
2. "negative reassurance": a line that reassures by saying what does not
   happen ("nothing is lost", "no surprises", "rest assured", "pay nothing",
   "don't worry"), and "simply" or "just" used to play a step down
   ("simply run", "just click").
3. "tell word": words that mark generated text and say little ("silently",
   "seamless", "leverage", "delve", "robust", "moat", "legible",
   "honestly").
4. "X, not Y contrast": a ", not ..." contrast. It fires when a text holds
   at least MIN_CONTRASTS of them and at least one for every
   SENTENCES_PER_CONTRAST sentences (2 and 15 by default). So two in a short
   note are listed, and three in a long README of 300 sentences pass.
5. "passive voice": a form of "be" or "get", an optional "not", "never" or
   "-ly" adverb, then a past participle ("is refused", "was never sent",
   "gets deleted"). A step that starts with a verb ("Run in a terminal.",
   "Set to 5 by default.") is not passive. It fires only when MIN_PASSIVE
   or more sentences are passive and they are at least MIN_SHARE of the
   sentences, so a passive kept where the doer does not matter passes.

Aphoristic closing lines ("Small checks, big wins.") are a known tell too,
but no pattern tells them apart from an ordinary short sentence, so this hook
leaves them out. The writing rules in the project's CLAUDE.md still cover
them.

Left out before matching: front matter at the top of the file, fenced code
blocks (an unclosed fence runs to the end of the text), indented code blocks
(4 spaces or a tab after a blank line, outside a list), inline code, URLs,
link targets ("(docs/setup.md)" after "[text]", and reference definitions),
HTML tags and comments (an unclosed comment runs to the end of the text),
block quotes (lines starting with ">"), and text in double quotes, straight
or curly. A quotation that holds quotations of its own is left out whole.
Documents quote people word for word, and a quotation keeps its own words.
Text in single quotes is checked, because a single quote is also an
apostrophe. For an Edit, the hook reads the file to see whether old_string
sits inside a fenced block or an HTML comment; if it does, the new text is
treated the same way.

When a check fires, the hook refuses the call once ("deny"; it never asks
the person) and lists each hit with its line and a plain fix. The identical
call sent again passes: the hook keeps a hash of each refused call in a small
state file. So a passive sentence or a quoted phrase kept on purpose costs
one resend. Any change to the text makes it a new call, checked again.

Add a project's own phrases by adding a pattern to the matching list below
(NEGATIVE_REASSURANCE, TELL_WORDS, and so on), plus a case to the self-test
that must be refused and a similar one that must pass. Add file types to
DOC_EXTENSIONS. Paths that must never be checked (a vendored file, a
changelog copied from elsewhere) go in SKIPPED_PATHS, as glob patterns
matched against the file path with forward slashes, ignoring case.

Saves tokens and time: a document that reads like generated text gets
corrected by the person who reads it. They spot the phrases, write the
correction, and wait for the rewrite, and the rewrite costs another round.
Refused here, the rewrite happens before anyone reads the file. Example: a
Write of a guide that says "Rest assured, nothing is lost" is refused with
the line number and the fix "say what happens"; Claude rewrites it as "The
draft stays in your outbox until you send it" before the person sees it.

Register it (in .claude/settings.json of the project):

    "PreToolUse": [
      {"matcher": "Write|Edit|MultiEdit",
       "hooks": [{"type": "command",
                  "command": "python \\"${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_writing_style.py\\""}]}
    ]

The hook reads its input as UTF-8 bytes and writes its answer as UTF-8,
whatever the console's code page. Read as text on Windows, the input would
be decoded with the code page (cp1252), and every em dash and curly quote
would arrive as other characters and pass unseen.

Every call to a documentation file is logged, one JSON object per line, so
the firing rate and the false positives can be measured at the periodic
audit. A refusal logs the local time, tool, file, the call's hash and each
hit's check, line and matched text (at most 80 characters). A resend that
passes on the refuse-once hash logs the same hash, so a script can count,
per check, the refusals that were sent again unchanged: a likely false
positive, since the text was kept as written. A clean pass logs a short
line. A fault inside the hook lets the call through: a broken check must
never stop work.

Standard library only, Python 3.9 or later.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------- settings

#: The tools whose writes are checked.
TOOLS = ("Write", "Edit", "MultiEdit")
#: File extensions checked, lower case, with the dot. Add ".txt" if the
#: project's plain-text files are documents people read.
DOC_EXTENSIONS = [".md", ".markdown", ".rst"]
#: Glob patterns of paths never checked, matched against the file path with
#: forward slashes, ignoring case, the same way on every system. For example
#: "*/CHANGELOG.md" or "*/vendor/*". Empty by default.
SKIPPED_PATHS: list[str] = []
#: Glob patterns of file names never checked, ignoring case: license texts,
#: whose wording is fixed.
SKIPPED_NAMES = ["license", "license.*", "licence", "licence.*"]

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
LEFT_QUOTE = chr(0x201C)
RIGHT_QUOTE = chr(0x201D)
#: A straight or curly apostrophe, as in "don't".
APOSTROPHE = "['" + chr(0x2019) + "]"

#: (pattern, fix). Matched case-insensitively against the text left after
#: code, URLs and quotations are taken out.
DASHES = [
    (re.escape(EM_DASH), "Use a comma, a colon, parentheses or a new sentence."),
    (r"\s" + re.escape(EN_DASH) + r"\s",
     "Use a comma, a colon, parentheses or a new sentence."),
]
NEGATIVE_REASSURANCE = [
    (r"\bnothing (?:is|gets|will be) lost\b", "Say what happens to it instead."),
    (r"\bnothing happens\b", "Say what does happen, and who does it."),
    (r"\bno surprises\b", "Say what the reader can expect."),
    (r"\brest assured\b", "State the fact; drop the reassurance."),
    (r"\bpays? nothing\b", "Say what the reader pays, and when."),
    (r"\b(?:you\s+)?(?:don" + APOSTROPHE + r"t|do not|never) (?:need to |have to )?worry\b",
     "State the fact; drop the reassurance."),
    (r"\bno need to worry\b", "State the fact; drop the reassurance."),
    (r"\bnothing to worry about\b", "State the fact; drop the reassurance."),
    (r"\bsimply\b", "Drop \"simply\"; describe the step as it is."),
    (r"\bjust (?:run|click|add|use|type|open|press|copy|paste|follow|enter|install"
     r"|call|send|set|edit|change|delete|remove|select|choose|pick)\b",
     "Drop \"just\"; describe the step as it is."),
]
TELL_WORDS = [
    (r"\bsilently\b", "Say what happens and where it shows, or drop the word."),
    (r"\bseamless(?:ly)?\b", "Say what the reader sees, or drop the word."),
    (r"\bleverag(?:e|es|ed|ing)\b", "Use \"use\"."),
    (r"\bdelv(?:e|es|ed|ing)\b", "Use \"look at\" or \"cover\"."),
    (r"\brobust(?:ly)?\b", "Name the property: what it survives or checks."),
    (r"\bmoats?\b", "Name the advantage in plain words."),
    (r"\blegible\b", "Use \"clear\" or \"easy to read\"."),
    (r"\bhonestly\b", "Drop the word."),
]
#: A ", not ..." contrast. Common phrases that are not contrasts are left out.
CONTRASTS = [
    (r",\s+not\s+(?!yet\b|least\b|to mention\b|always\b|all\b|every\b|only\b)\w+",
     "State the fact on its own; keep \"X, not Y\" contrasts rare."),
]
#: Contrasts fire when a text holds at least MIN_CONTRASTS of them and at
#: least one for every SENTENCES_PER_CONTRAST sentences.
MIN_CONTRASTS = 2
SENTENCES_PER_CONTRAST = 15

#: The passive voice: how many passive sentences, and what share of all
#: sentences, before it fires.
MIN_PASSIVE = 3
MIN_SHARE = 0.25
PASSIVE_FIX = ("Name the doer and use the active voice where the doer is known; "
               "keep the passive where the doer is unknown or does not matter.")
IRREGULAR = (
    "kept held sent given made done shown written set stored built read found put "
    "taken seen known paid told sold left lost bought brought caught taught thought "
    "meant run cut hit hurt shut spent lent bent dealt felt heard led met fed won "
    "bound wound ground hung struck stuck spun split spread cast bid let quit "
    "chosen driven drawn grown thrown blown flown worn torn sworn born borne "
    "broken spoken stolen frozen woken hidden ridden bitten forgotten gotten got "
    "begun sung rung drunk sunk shrunk swum understood withdrawn overseen "
    "undertaken mistaken forbidden forgiven"
).split()
#: Words ending in -ed or -en that are not past participles.
NOT_PARTICIPLES = {
    "often", "even", "open", "seven", "eleven", "ten", "then", "when", "token",
    "tokens", "kitchen", "garden", "citizen", "women", "men", "children", "linen",
    "oxygen", "listen", "hen", "pen", "den", "screen", "green", "queen", "teen",
    "between", "indeed", "need", "feed", "seed", "speed", "red", "bed", "hundred",
    "shed", "sacred", "kindred", "wed",
}
#: Idioms with "get" that are not passive ("get started", "get rid of").
GET_IDIOMS = {"started", "rid", "used"}

#: At most this many hits are listed per check.
LIST_AT_MOST = 10
#: Matched text kept in the log, at most this many characters per hit.
LOG_TEXT_AT_MOST = 80
#: Hashes of refused calls kept, newest last.
KEEP_HASHES = 50
STATE_ENV = "WRITING_STYLE_STATE"
LOG_ENV = "WRITING_STYLE_LOG"

# ------------------------------------------------------------------ patterns

BE = r"(?:am|is|are|was|were|be|been|being)"
GET = r"(?:get|gets|got|gotten|getting)"
PARTICIPLE = r"[a-z]+(?:ed|en)|" + "|".join(IRREGULAR)
PASSIVE = re.compile(
    r"\b(" + BE + r"|" + GET + r")\s+(?:not\s+|never\s+)?(?:[a-z]+ly\s+)?(" + PARTICIPLE + r")\b",
    re.IGNORECASE)

FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
#: A fenced block; one left open runs to the end of the text.
FENCED = re.compile(
    r"^[ \t]*(`{3,}|~{3,})[^\n]*(?:\n.*?^[ \t]*\1[`~]*[ \t]*$|.*\Z)",
    re.DOTALL | re.MULTILINE)
FENCE_LINE = re.compile(r"[ \t]*(`{3,}|~{3,})")
#: An HTML comment; one left open runs to the end of the text.
HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
HTML_TAG = re.compile(r"</?[A-Za-z][^<>\n]*>")
INLINE_CODE = re.compile(r"`[^`\n]+`")
URL = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)
#: The target of a Markdown link or image, "(docs/setup.md)" after "[text]",
#: and a reference definition, "[text]: docs/setup.md".
LINK_TARGET = re.compile(
    r"(?<=\])\((?:[^()\s]|\([^()\s]*\))*(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'))?\s*\)")
REFERENCE_DEFINITION = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*\S.*$", re.MULTILINE)
BLOCK_QUOTE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
LIST_ITEM = re.compile(r"[ \t]*(?:[-*+]|\d+[.)])[ \t]")
#: A straight double quote after one of these opens a quotation; after
#: anything else it closes one.
OPENS_AFTER = set("([{<*_-/=")
BLANK_LINE_AHEAD = re.compile(r"[ \t]*(?:\n|\Z)")
#: Where a sentence ends: after . ! ? and space, at a blank line, and before a
#: line that starts a list item, heading or table row.
SENTENCE_BREAK = re.compile(
    r"(?<=[.!?:])[\"')\]]*\s+|\n[ \t]*\n\s*|\n(?=[ \t]*(?:[-*+]\s|\d+[.)]\s|#|\|))")
WORD = re.compile(r"[A-Za-z]{2,}")


def _blank(match: re.Match[str]) -> str:
    """The match with every character but newlines turned into a space, so
    line numbers and positions stay the same."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _blank_text(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def blank_quotations(text: str) -> str:
    """The text with each double-quoted span blanked. Quotes are paired as
    they nest, within a paragraph: a quotation that quotes words of its own
    is blanked whole. A quote left open is not blanked."""
    spans, stack = [], []
    for i, ch in enumerate(text):
        if ch == "\n" and BLANK_LINE_AHEAD.match(text, i + 1):
            stack = []  # quotations do not run across paragraphs
        elif ch == LEFT_QUOTE:
            stack.append(i)
        elif ch == RIGHT_QUOTE or ch == '"':
            before = text[i - 1] if i else "\n"
            if ch == '"' and (before.isspace() or before in OPENS_AFTER):
                stack.append(i)
            elif stack:
                spans.append((stack.pop(), i + 1))
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for k in range(start, end):
            if chars[k] != "\n":
                chars[k] = " "
    return "".join(chars)


def blank_indented_code(text: str) -> str:
    """The text with indented code blocks blanked: lines indented by 4 spaces
    or a tab that follow a blank line (or start the text), outside a list."""
    out, after_blank, in_code, in_list = [], True, False, False
    for line in text.split("\n"):
        blank = not line.strip()
        indented = line.startswith("    ") or line.startswith("\t")
        if in_code and (blank or indented):
            out.append(_blank_text(line))
            continue
        in_code = False
        if indented and after_blank and not in_list and not blank:
            in_code = True
            out.append(_blank_text(line))
            after_blank = False
            continue
        if not blank:
            in_list = bool(LIST_ITEM.match(line)) or (in_list and line[:1] in " \t")
        after_blank = blank
        out.append(line)
    return "\n".join(out)


def clean(text: str) -> str:
    """The text with everything a reader does not read as prose blanked out."""
    text = FRONT_MATTER.sub(_blank, text)
    for pattern in (FENCED, HTML_COMMENT):
        text = pattern.sub(_blank, text)
    text = blank_indented_code(text)
    for pattern in (INLINE_CODE, URL, LINK_TARGET, REFERENCE_DEFINITION, HTML_TAG, BLOCK_QUOTE):
        text = pattern.sub(_blank, text)
    return blank_quotations(text)


def line_at(text: str, pos: int, first_line: int) -> int:
    return first_line + text.count("\n", 0, pos)


def excerpt(text: str, start: int, end: int) -> str:
    """The words around a hit, on one line."""
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    piece = text[left:right if right >= 0 else len(text)]
    return re.sub(r"\s+", " ", piece).strip()[:100]


def sentences(text: str, first_line: int) -> list[tuple[int, str]]:
    """(line, sentence) for each sentence of the cleaned text."""
    found, start = [], 0
    for brk in list(SENTENCE_BREAK.finditer(text)) + [None]:
        end = brk.start() if brk else len(text)
        raw = text[start:end]
        body = re.sub(r"\s+", " ", raw).strip(" -*#>|0123456789.)")
        if WORD.search(body):
            offset = start + (len(raw) - len(raw.lstrip()))
            found.append((line_at(text, offset, first_line), body))
        start = brk.end() if brk else len(text)
    return found


def is_passive(sentence: str) -> bool:
    """True when a form of "be" or "get" is followed by a past participle."""
    for match in PASSIVE.finditer(sentence):
        participle = match.group(2).lower()
        if participle in NOT_PARTICIPLES:
            continue
        if match.group(1).lower().startswith("g") and participle in GET_IDIOMS:
            continue
        return True
    return False


# -------------------------------------------------------------------- checks


def pattern_hits(pieces: list[tuple[str, int]],
                 rules: list[tuple[str, str]]) -> list[tuple[int, str, str, str]]:
    """(line, excerpt, fix, matched text) for each match of each rule."""
    hits = []
    for text, first_line in pieces:
        for pattern, fix in rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                hits.append((line_at(text, match.start(), first_line),
                             excerpt(text, match.start(), match.end()), fix,
                             match.group(0)))
    return sorted(hits)


def passive_hits(pieces: list[tuple[str, int]]) -> tuple[list[tuple[int, str, str, str]], int]:
    """The passive sentences as hits (the sentence is the matched text), and
    the number of sentences."""
    every = [s for text, first_line in pieces for s in sentences(text, first_line)]
    passive = [(line, s[:100], PASSIVE_FIX, s) for line, s in every if is_passive(s)]
    return passive, len(every)


def findings(pieces: list[tuple[str, int]]) -> list[tuple[str, list[tuple[int, str, str, str]]]]:
    """(check name, hits) for each check that fires on the cleaned pieces."""
    out = []
    for name, rules in (("em dash", DASHES),
                        ("negative reassurance", NEGATIVE_REASSURANCE),
                        ("tell word", TELL_WORDS)):
        hits = pattern_hits(pieces, rules)
        if hits:
            out.append((name, hits))
    passive, total = passive_hits(pieces)
    contrasts = pattern_hits(pieces, CONTRASTS)
    if len(contrasts) >= MIN_CONTRASTS and len(contrasts) * SENTENCES_PER_CONTRAST >= total:
        out.append((f"X, not Y contrast ({len(contrasts)} in {total} sentences)", contrasts))
    if len(passive) >= MIN_PASSIVE and total and len(passive) / total >= MIN_SHARE:
        out.append((f"passive voice ({len(passive)} of {total} sentences)", passive))
    return out


# --------------------------------------------------------------------- input


def is_doc(path: str) -> bool:
    if not path:
        return False
    slashed = path.replace("\\", "/")
    if any(fnmatch.fnmatchcase(slashed.lower(), pattern.lower()) for pattern in SKIPPED_PATHS):
        return False
    name = slashed.rsplit("/", 1)[-1].lower()
    if any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in SKIPPED_NAMES):
        return False
    return os.path.splitext(slashed)[1].lower() in DOC_EXTENSIONS


def lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def open_context(before: str) -> str:
    """The opening of a fenced block or HTML comment still open at the end of
    `before` (the file up to an Edit's old_string), else ""."""
    fence = ""
    for line in before.split("\n")[:-1]:
        match = FENCE_LINE.match(line)
        if not fence and match:
            fence = match.group(1)
        elif fence and re.fullmatch(r"[ \t]*" + re.escape(fence) + r"[`~]*[ \t]*", line):
            fence = ""
    if fence:
        return fence + "\n"
    outside = FENCED.sub(_blank, before)
    opened = outside.rfind("<!--")
    if opened >= 0 and outside.find("-->", opened) < 0:
        return "<!--"
    return ""


def texts_written(tool: str, tool_input: dict) -> list[tuple[str, int, str]]:
    """(new text, the file line it starts on, an opening it sits inside) for
    each piece the call writes. A MultiEdit's edits are applied in turn to a
    copy of the file, so each line number is the line in the edited file."""
    if tool == "Write":
        content = tool_input.get("content")
        return [(lf(content), 1, "")] if isinstance(content, str) else []
    try:
        current: str | None = Path(tool_input.get("file_path") or "").read_text(encoding="utf-8")
    except (OSError, ValueError):
        current = None
    edits = [tool_input] if tool == "Edit" else tool_input.get("edits") or []
    pieces = []
    for edit in edits:
        if not (isinstance(edit, dict) and isinstance(edit.get("new_string"), str)):
            continue
        new, old = lf(edit["new_string"]), lf(edit.get("old_string") or "")
        first, inside = 1, ""
        if current is not None and old and old in current:
            index = current.index(old)
            first = 1 + current[:index].count("\n")
            inside = open_context(current[:index])
            current = (current.replace(old, new) if edit.get("replace_all")
                       else current.replace(old, new, 1))
        pieces.append((new, first, inside))
    return pieces


def cleaned_pieces(tool: str, tool_input: dict) -> list[tuple[str, int]]:
    """(cleaned text, first line) for each piece; text inside an open fence
    or comment is cleaned as it would be in the file."""
    return [(clean(inside + text)[len(inside):], first)
            for text, first, inside in texts_written(tool, tool_input)]


# --------------------------------------------------------------------- state


def _base() -> str:
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    return os.path.join(project, ".claude") if project else os.path.dirname(os.path.abspath(__file__))


def state_path() -> str:
    return os.environ.get(STATE_ENV) or os.path.join(_base(), "logs", "writing-style-refused.json")


def log_path() -> str:
    return os.environ.get(LOG_ENV) or os.path.join(_base(), "logs", "guard_writing_style.log")


def call_hash(event: dict) -> str:
    key = json.dumps([event.get("tool_name"), event.get("tool_input")], sort_keys=True,
                     ensure_ascii=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def load_hashes(path: str) -> list[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [h for h in data if isinstance(h, str)] if isinstance(data, list) else []


def remember(path: str, seen: list[str], digest: str) -> None:
    """Add the hash, written to a fresh file and moved into place."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fresh = path + ".tmp"
    with open(fresh, "w", encoding="utf-8") as f:
        json.dump((seen + [digest])[-KEEP_HASHES:], f)
    os.replace(fresh, path)


def log(outcome: str, **fields: object) -> None:
    """Append one JSON line: the local time, the outcome, then `fields`."""
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        entry = {"time": datetime.now().isoformat(timespec="seconds"), "outcome": outcome}
        entry.update(fields)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def check_name(name: str) -> str:
    """The check's name without its count: "passive voice (3 of 4 sentences)"
    becomes "passive voice"."""
    return name.split(" (")[0]


def logged_hits(found: list[tuple[str, list[tuple[int, str, str, str]]]]) -> list[dict]:
    return [{"check": check_name(name), "line": line,
             "text": re.sub(r"\s+", " ", matched).strip()[:LOG_TEXT_AT_MOST]}
            for name, hits in found for line, _, _, matched in hits]


def reason(path: str, found: list[tuple[str, list[tuple[int, str, str, str]]]]) -> str:
    lines = [f"Refused once (writing style) for {os.path.basename(path)}:"]
    for name, hits in found:
        lines.append(f"{name}:")
        for line, text, fix, _ in hits[:LIST_AT_MOST]:
            lines.append(f"  line {line}: {text}  Fix: {fix}")
        if len(hits) > LIST_AT_MOST:
            lines.append(f"  (and {len(hits) - LIST_AT_MOST} more)")
    lines.append("Rewrite these, then write again. If every one is meant (a quotation, "
                 "a passive where the doer does not matter), send the same call again "
                 "unchanged and it will pass.")
    return "\n".join(lines)


def decide(event: dict) -> tuple[str | None, list[str]]:
    """(deny reason or None, names of the checks that fired)."""
    tool, tool_input = event.get("tool_name"), event.get("tool_input")
    if tool not in TOOLS or not isinstance(tool_input, dict):
        return None, []
    path = tool_input.get("file_path") or ""
    if not isinstance(path, str) or not is_doc(path):
        return None, []
    found = findings(cleaned_pieces(tool, tool_input))
    names = [check_name(name) for name, _ in found]
    if not found:
        log("pass", tool=tool, file=path)
        return None, []
    state = state_path()
    seen = load_hashes(state)
    digest = call_hash(event)
    if digest in seen:
        log("pass-resent", tool=tool, file=path, hash=digest, checks=names)
        return None, names
    remember(state, seen, digest)
    log("deny", tool=tool, file=path, hash=digest, hits=logged_hits(found))
    return reason(path, found), names


def read_event() -> object:
    """The event, read as UTF-8 bytes whatever the console's code page."""
    return json.loads(sys.stdin.buffer.read().decode("utf-8"))


def answer(payload: dict) -> None:
    """Write the answer to stdout as UTF-8 whatever the console's code page."""
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main() -> int:
    try:
        event = read_event()
        if not isinstance(event, dict):
            return 0
        why, _ = decide(event)
    except Exception as error:  # a broken check never blocks work
        print(f"guard_writing_style: let the call through after an error: {error!r}",
              file=sys.stderr)
        log("error", error=type(error).__name__)
        return 0
    if why:
        answer({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": why,
            }
        })
    return 0


if __name__ == "__main__":
    sys.exit(main())
