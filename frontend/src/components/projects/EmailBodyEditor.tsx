"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Field, Notice } from "@/components/ui";
import { emailPlainText, plainEmailHtml, sanitizeEmailHtml } from "@/lib/emailFormatting";

const commands = [
  ["bold", "Bold"], ["italic", "Italic"], ["underline", "Underline"],
  ["strikeThrough", "Strikethrough"], ["insertUnorderedList", "Bullet list"],
  ["insertOrderedList", "Numbered list"], ["removeFormat", "Clear formatting"],
  ["undo", "Undo"], ["redo", "Redo"],
] as const;

export function EmailBodyEditor({body, html, disabled = false, onChange}: {
  body: string; html: string | null; disabled?: boolean;
  onChange: (body: string, html: string) => void;
}) {
  const editor = useRef<HTMLDivElement>(null);
  const selection = useRef<Range | null>(null);
  const [message, setMessage] = useState("");
  const initial = useRef({body, html});
  useEffect(() => {
    if (editor.current) editor.current.innerHTML = initial.current.html === null
      ? plainEmailHtml(initial.current.body) : sanitizeEmailHtml(initial.current.html);
  }, []);
  const remember = () => {
    const selected = window.getSelection();
    if (selected?.rangeCount && editor.current?.contains(selected.anchorNode) && editor.current.contains(selected.focusNode)) {
      selection.current = selected.getRangeAt(0).cloneRange();
    }
  };
  const changed = () => {
    if (!editor.current) return;
    const clean = sanitizeEmailHtml(editor.current.innerHTML);
    const plain = emailPlainText(clean);
    setMessage(plain.length > 20000 || clean.length > 100000 ? "This email is too long. Shorten it before saving." : "");
    onChange(plain, clean);
    remember();
  };
  const command = (name: string, value?: string) => {
    if (!editor.current || disabled) return;
    editor.current.focus();
    const selected = window.getSelection();
    if (selection.current && editor.current.contains(selection.current.commonAncestorContainer)) {
      selected?.removeAllRanges(); selected?.addRange(selection.current);
    }
    // Native editing retains the browser undo stack. Clipboard uses the modern API.
    document.execCommand("styleWithCSS", false, "false");
    const applied = document.execCommand(name, false, value);
    changed();
    if (!applied) setMessage("This formatting action is unavailable here. Select text in the email body and try again.");
  };
  return <div className="stack">
    <div className="email-format-toolbar" role="group" aria-label="Email formatting">
      {commands.map(([name, label]) => <Button key={name} type="button" disabled={disabled} onMouseDown={event => event.preventDefault()} onClick={() => command(name)}>{label}</Button>)}
    </div>
    <Field label="Email body"><div ref={editor} className="input email-rich-body email-rich-editor" role="textbox" aria-label="Email body" aria-multiline="true" aria-disabled={disabled} dir="auto" contentEditable={!disabled} suppressContentEditableWarning
      onInput={changed} onKeyUp={remember} onMouseUp={remember} onBlur={remember}
      onPaste={event => {
        event.preventDefault();
        const pasted = event.clipboardData.getData("text/html");
        command("insertHTML", pasted ? sanitizeEmailHtml(pasted) : plainEmailHtml(event.clipboardData.getData("text/plain")));
      }} onDrop={event => event.preventDefault()} /></Field>
    {message ? <Notice tone="info">{message}</Notice> : null}
  </div>;
}

export function EmailBodyPreview({body, html}: {body: string; html?: string | null}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.innerHTML = html == null ? plainEmailHtml(body) : sanitizeEmailHtml(html);
  }, [body, html]);
  return <div ref={ref} className="email-rich-body" dir="auto" />;
}
