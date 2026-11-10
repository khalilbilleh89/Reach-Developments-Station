"""Small inert email HTML vocabulary; never retain attributes, URLs or embedded content."""

from html import escape
from html.parser import HTMLParser

from app.core.errors import ValidationError

TAGS = frozenset({"p", "div", "br", "strong", "b", "em", "i", "u", "s", "strike", "ul", "ol", "li"})
BLOCKS = frozenset({"p", "div", "ul", "ol", "li"})
HIDDEN = frozenset({"script", "style", "iframe", "object", "svg", "math", "template", "head"})


class EmailHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html: list[str] = []
        self.text: list[str] = []
        self.stack: list[str] = []
        self.hidden: list[str] = []
        self.lists: list[int | None] = []
        self.has_text = False

    def newline(self) -> None:
        if self.text and not self.text[-1].endswith("\n"):
            self.text.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in HIDDEN:
            self.hidden.append(tag)
        if self.hidden or tag not in TAGS:
            return
        if len(self.stack) >= 100:
            raise ValidationError("Email formatting is nested too deeply.")
        self.html.append(f"<{tag}>")
        if tag in BLOCKS:
            self.newline()
        if tag in {"ul", "ol"}:
            self.lists.append(0 if tag == "ol" else None)
        if tag == "li":
            if self.lists and self.lists[-1] is not None:
                self.lists[-1] += 1
                self.text.append(f"{self.lists[-1]}. ")
            else:
                self.text.append("• ")
        if tag == "br":
            self.text.append("\n")
        else:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag not in self.stack:
            return
        while self.stack:
            closed = self.stack.pop()
            self.html.append(f"</{closed}>")
            if closed in BLOCKS:
                self.newline()
            if closed in {"ul", "ol"} and self.lists:
                self.lists.pop()
            if closed == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.has_text = self.has_text or bool(data.strip())
            self.html.append(escape(data, quote=True))
            self.text.append(data)


def clean_email_html(value: str) -> tuple[str, str]:
    if "\x00" in value or len(value) > 100000:
        raise ValidationError("Email formatting is invalid or too large.")
    parser = EmailHTML()
    parser.feed(value)
    parser.close()
    parser.hidden.clear()
    while parser.stack:
        parser.handle_endtag(parser.stack[-1])
    html = "".join(parser.html).strip()
    plain = "".join(parser.text).strip()
    if not parser.has_text or len(plain) > 20000 or len(html) > 100000:
        raise ValidationError("Enter an email body of 1 to 20,000 characters.")
    return html, plain
