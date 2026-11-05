/** Email formatting is an inert tag subset, never arbitrary HTML or CSS. */
export const escapeEmailText = (value: string) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
export const plainEmailHtml = (value: string) => escapeEmailText(value).replace(/\r?\n/g, "<br>");
const allowed = new Set(["p", "div", "br", "strong", "b", "em", "i", "u", "s", "strike", "ul", "ol", "li"]);
const hidden = new Set(["script", "style", "iframe", "object", "svg", "math", "template", "head"]);

export function sanitizeEmailHtml(value: string): string {
  // Template fragments stay inert, including image/resource loading during paste.
  const template = document.createElement("template");
  template.innerHTML = value;
  const clean = (node: Node, depth: number): string => {
    if (depth > 100) return "";
    if (node.nodeType === 3) return escapeEmailText(node.textContent ?? "");
    if (node.nodeType !== 1) return "";
    const tag = (node as Element).tagName.toLowerCase();
    if (hidden.has(tag)) return "";
    const content = Array.from(node.childNodes).map(child => clean(child, depth + 1)).join("");
    if (!allowed.has(tag)) return content;
    return tag === "br" ? "<br>" : `<${tag}>${content}</${tag}>`;
  };
  return Array.from(template.content.childNodes).map(node => clean(node, 0)).join("");
}

export function emailPlainText(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = sanitizeEmailHtml(html);
  const read = (node: Node): string => {
    if (node.nodeType === 3) return node.textContent ?? "";
    if (node.nodeType !== 1) return "";
    const element = node as Element;
    const tag = element.tagName.toLowerCase();
    if (tag === "br") return "\n";
    const content = Array.from(node.childNodes).map(read).join("");
    if (tag === "li") {
      const parent = element.parentElement;
      const prefix = parent?.tagName === "OL" ? `${Array.from(parent.children).indexOf(element) + 1}. ` : "• ";
      return `${prefix}${content}\n`;
    }
    return ["p", "div", "ul", "ol"].includes(tag) ? `${content}\n` : content;
  };
  return Array.from(template.content.childNodes).map(read).join("").trim();
}

export async function copyFormattedEmail(html: string, plain: string): Promise<"formatted" | "plain"> {
  if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    // Keep this write in the click gesture: Safari requires user activation.
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([sanitizeEmailHtml(html)], {type: "text/html"}),
      "text/plain": new Blob([plain], {type: "text/plain"}),
    })]);
    return "formatted";
  }
  await navigator.clipboard.writeText(plain);
  return "plain";
}
