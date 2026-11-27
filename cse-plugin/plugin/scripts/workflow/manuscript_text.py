"""Bounded TeX source projection for prose inspection."""

from pathlib import Path
import re

SPACE = re.compile(r"\s*")
COMMAND = re.compile(r"\\([A-Za-z@]+)\*?|\\[^\n]")
INCLUDE = re.compile(r"\\(?:input|include)\s*\{([^{}\n]+)\}")
DEFINITION = re.compile(r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand|def)\*?\s*")
STORED_DEFINITION = re.compile(
    r"\\cs_(?:new|set)(?:_[a-z]+)*:[Nc]p?[nex]\s*(?:\\[A-Za-z_:@]+|\{[^{}]*\})(?:\s*#\d+)*"
    r"|\\expandafter\s*\\def\s*\\csname\b[^\\]*\\endcsname\b"
)
VALUE_SETTER = re.compile(r"(?m)^[ \t]*\\resultvalue[ \t]*\{[^{}\n]+\}[ \t]*\{[^{}\n]*\}[ \t]*$")
TABULAR = r"tabular\*?|tabularx|tabulary|longtable|tblr|longtblr"
HIDDEN_ENV = (r"verbatim\*?|lstlisting|minted|tikzpicture|pgfpicture|axis|groupplot|"
              r"semilog[xy]axis|loglogaxis|polaraxis|filecontents\*?|comment")
EQUATION_ENV = r"equation\*?|align\*?|gather\*?|displaymath|math|multline\*?"
INLINE_MATH = r"(?s)(?<!\\)\$\$.*?\$\$|(?<!\\)\$[^$]*?(?<!\\)\$|\\\(.*?\\\)|\\\[.*?\\\]"
QUANTITY = re.compile(r"\\(?:si|SI|unit|num|qty|numrange|qtyrange|tablenum|ang)\*?$")
HEADING = r"(?:sub)*section|chapter|paragraph"
DECLARATION = re.compile(
    r"\b(?:funding|disclaimers?|conflicts? of interest|competing interests?|"
    r"declarations? of (?:competing interest|interest)|disclosures?)\b", re.I
)
UNPRINTED = {
    "author": 1, "affiliation": 1, "affil": 1, "institute": 1, "address": 1,
    "orcid": 1, "orcidlink": 1, "orcidID": 1, "thanks": 1, "email": 1,
    "ead": 1, "corref": 1, "cortext": 2, "authorrunning": 1, "titlerunning": 1,
    "lstinputlisting": 1, "includegraphics": 1, "inputminted": 2, "graphicspath": 1,
    "label": 1, "bibliography": 1, "addbibresource": 1, "bibliographystyle": 1,
    "usepackage": 1, "documentclass": 1, "definecolor": 3, "colorlet": 2,
    "setlength": 2, "newlength": 1, "hypersetup": 1, "tnote": 1,
    "ref": 1, "eqref": 1, "pageref": 1, "autoref": 1, "cref": 1, "Cref": 1,
    "includeonly": 1, "addplot": 1, "addplot3": 1,
}


def blank(text):
    return re.sub(r"[^\n]", " ", text)


def hide(pattern, text, flags=0):
    return re.sub(pattern, lambda match: blank(match[0]), text, flags=flags)


GROUP_TOKENS = {
    "{": re.compile(r"\\[^\n]|[{}]"),
    "[": re.compile(r"\\[^\n]|[\[\]]"),
}


def group(text, position, opening="{", closing="}"):
    """Return the content bounds and end of a balanced argument, or None."""
    position = SPACE.match(text, position).end()
    if position == len(text) or text[position] != opening:
        return None
    depth = 1
    for token in GROUP_TOKENS[opening].finditer(text, position + 1):
        if token[0] == opening:
            depth += 1
        elif token[0] == closing:
            depth -= 1
            if depth == 0:
                return position + 1, token.start(), token.end()
    return None


def options(text, position):
    while arg := group(text, position, "[", "]"):
        position = arg[2]
    return position


def commands(text, transform):
    """Replace commands while keeping the source line of every remaining token."""
    cursor = 0
    pieces = []
    while match := COMMAND.search(text, cursor):
        end, replacement = transform(match, text)
        pieces.extend((text[cursor:match.start()], replacement))
        cursor = end
    return "".join(pieces) + text[cursor:]


def prepare_tex(text):
    """Hide source-only content and harvest zero-argument macros."""
    text = hide(r"(?<!\\)%[^\n]*", text)
    # shortcut: recognize standalone resultvalue entries; other project setters need an explicit convention.
    text = hide(VALUE_SETTER, text)
    # shortcut: mask drawing and code environments as a unit; inspect their embedded labels in print.
    text = hide(r"\\begin\{(" + HIDDEN_ENV + r")\}.*?\\end\{\1\}", text, re.S)
    macros = {}

    def prepare(match, source):
        name, end = match[1], match.end()
        if definition := STORED_DEFINITION.match(source, match.start()):
            if body := group(source, definition.end()):
                end = body[2]
        elif DEFINITION.fullmatch(match[0]):
            arg = group(source, end)
            macro = source[arg[0]:arg[1]].strip() if arg and name != "def" else None
            cursor = end
            if macro:
                cursor = arg[2]
            elif direct := re.match(r"\s*(\\[A-Za-z@]+)", source[cursor:]):
                macro, cursor = direct[1], cursor + direct.end()
            argument_start = options(source, cursor)
            parameters = re.match(r"(?:\s*#\d)+", source[argument_start:]) if name == "def" else None
            if parameters:
                argument_start += parameters.end()
            if body := group(source, argument_start):
                if macro and not parameters and source[cursor:argument_start].strip() in {"", "[0]"}:
                    macros[macro] = " ".join(source[body[0]:body[1]].split())
                end = body[2]
        elif name in UNPRINTED:
            end = options(source, end)
            for _ in range(UNPRINTED[name]):
                if arg := group(source, end):
                    end = arg[2]
                end = options(source, end)
        else:
            return end, match[0]
        return end, blank(source[match.start():end])

    return commands(text, prepare), macros


def tex_visible(text, macros, math=False, prose_only=False):
    """Project common printed commands while retaining wrapped source lines."""
    text = hide(r"\\begin\{(" + EQUATION_ENV + r")\}.*?\\end\{\1\}", text, re.S)
    # shortcut: simple macros expand up to three passes; parameterized or longer chains need a rendered read.
    for _ in range(3 if macros else 0):
        expanded = COMMAND.sub(lambda m: macros.get(m[0], m[0]), text)
        if expanded == text:
            break
        text = expanded
    if not math:
        text = hide(INLINE_MATH, text)
    if prose_only:
        text = hide(r"\\begin\{(" + TABULAR + r")\}.*?\\end\{\1\}", text, re.S)

    def project(match, source):
        name, end = match[1], match.end()
        start = match.start()
        if name is None:
            return end, match[0][1:] if match[0] in {r"\#", r"\_", r"\%", r"\&", r"\$"} else " "
        arguments = end
        end = options(source, end)
        if "cite" in name.lower():
            note = group(source, arguments, "[", "]")
            last = note
            while last and (following := group(source, last[2], "[", "]")):
                last = following
            if arg := group(source, end):
                end = arg[2]
            if last and not prose_only:
                return end, blank(source[start:last[0]]) + source[last[0]:last[1]] + blank(source[last[1]:end])
        elif name in {"input", "include", "begin", "end", "href", "captionof"}:
            if arg := group(source, end):
                end = arg[2]
            if name == "captionof":
                end = options(source, end)
        elif QUANTITY.fullmatch(match[0]):
            values = {"si": 0, "unit": 0, "numrange": 2, "qtyrange": 2}.get(name, 1)
            units = int(name in {"si", "unit", "qty", "SI", "qtyrange"})
            parts = [blank(source[start:end])]
            for index in range(values + units):
                if arg := group(source, end):
                    parts.append(source[end:arg[2]] if math and index < values else blank(source[end:arg[2]]))
                    end = arg[2]
            return end, " ".join(parts)
        elif name in {"ce", "ch"} and not math:
            if arg := group(source, end):
                end = arg[2]
        elif name in {"times", "cdot"}:
            return end, ("×" if name == "times" else "·")
        return end, blank(source[start:end])

    return commands(text, project).replace("{", " ").replace("}", " ").replace("$", " ").replace("~", " ")


def tex_sources(paths):
    """Discover explicit files and literal includes once, in manuscript order."""
    sources = {}

    def visit(path, base):
        path = path.resolve()
        if path in sources:
            return
        try:
            text, macros = prepare_tex(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            sources[path] = None, {}, {}, str(error)
            return
        links = {}
        sources[path] = text, macros, links, None
        for match in INCLUDE.finditer(text):
            target = Path(match[1].strip())
            if not target.suffix:
                target = target.with_suffix(".tex")
            included = path.parent / target
            if not included.is_file():
                included = base / target
            links[match.start()] = included.resolve()
            visit(included, base)

    for path in paths:
        visit(path, path.resolve().parent)
    return sources


SECTION = re.compile(r"\\(?:" + HEADING + r")\*?(?![A-Za-z])")
BOUNDARY = re.compile(
    INCLUDE.pattern + r"|\\(?:" + HEADING + r"|captionof|caption|tablefootnote|par)\*?(?![A-Za-z])"
    r"|\\(?P<edge>begin|end)\{(?P<env>" + TABULAR + "|" + EQUATION_ENV
    + r"|document|abstract|tablenotes|(?:table|figure)\*?|threeparttable)\}|\n[ \t]*\n"
)
ROW_COMMAND = r"\\(?:toprule|midrule|bottomrule|hline|cmidrule|cline|addlinespace|endhead|endfirsthead|endfoot|endlastfoot)\b"


def table_cells(text, start, end):
    # shortcut: split only at top-level TeX row and column separators; inspect custom table macros in print.
    depth = 0
    for token in re.compile(INLINE_MATH + r"|\\\\(?:\s*\[[^\]]*\])?|\\[^\n]|[{}&]").finditer(text, start, end):
        if token[0] == "{":
            depth += 1
        elif token[0] == "}":
            depth -= 1
        elif depth == 0 and (token[0] == "&" or token[0].startswith(r"\\")):
            yield start, token.start()
            start = token.end()
    yield start, end


def tex_events(text, links):
    """Yield source spans for prose, structural boundaries, captions, cells and notes."""
    position = 0
    end_document = re.search(r"\\end\{document\}", text)
    if begin := re.search(r"\\begin\{document\}", text):
        position = begin.end()
    limit = end_document.start() if end_document else len(text)
    while match := BOUNDARY.search(text, position, limit):
        yield "paragraph", position, match.start(), None
        position = match.end()
        command = match[0]
        if match.start() in links:
            yield "include", match.start(), position, links[match.start()]
        elif SECTION.fullmatch(command):
            if arg := group(text, options(text, position)):
                position = arg[2]
                yield "section", arg[0], arg[1], None
        elif command.startswith((r"\caption", r"\tablefootnote")):
            if command.startswith(r"\captionof") and (arg := group(text, position)):
                position = arg[2]
            if arg := group(text, options(text, position)):
                position = arg[2]
                yield ("note" if command.startswith(r"\tablefootnote") else "caption"), arg[0], arg[1], None
        elif match["edge"] == "begin" and match["env"] != "abstract":
            env = match["env"]
            if re.fullmatch(TABULAR + "|tablenotes|" + EQUATION_ENV, env):
                close = text.find(r"\end{" + env + "}", position, limit)
                if close < 0:
                    continue
                position = options(text, position)
                if re.fullmatch(TABULAR, env):
                    for _ in range(2 if env in {"tabular*", "tabularx", "tabulary"} else 1):
                        if arg := group(text, position):
                            position = options(text, arg[2])
                    for start, end in table_cells(text, position, close):
                        cell = re.sub(ROW_COMMAND + r"\s*(?:\[[^]]*\]|\{[^}]*\})?", lambda m: blank(m[0]), text[start:end])
                        yield "cell", start, end, cell
                elif env == "tablenotes":
                    notes = list(re.finditer(r"\\item\b", text[position:close]))
                    starts = [position] + [options(text, position + note.end()) for note in notes]
                    ends = [position + note.start() for note in notes] + [close]
                    for start, end in zip(starts, ends):
                        yield "note", start, end, None
                position = close + len(env) + len(r"\end{}")
        elif match["env"] == "abstract":
            yield match["edge"] + " abstract", match.start(), position, None
    yield "paragraph", position, limit, None
