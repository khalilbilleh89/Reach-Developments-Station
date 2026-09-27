import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));

function harness(items) {
  const slots = [];
  let cursor = 0;
  let retries = 0;
  const calls = [];
  class ApiError extends Error {}
  const projects = {
    images: async () => items,
    imageUrl: (projectId, imageId) => `/image/${projectId}/${imageId}`,
    addImage: async (...args) => {
      calls.push(args);
      if (args[2].name === "broken.png") throw new ApiError("signature rejected");
    },
    removeImage: async (...args) => calls.push(["remove", ...args]),
  };
  const source = readFileSync(
    new URL("../src/components/projects/ProjectImages.tsx", import.meta.url),
    "utf8",
  );
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "react") return {
      useState(initial) {
        const index = cursor++;
        slots[index] ??= { value: typeof initial === "function" ? initial() : initial };
        return [slots[index].value, value => {
          slots[index].value = typeof value === "function" ? value(slots[index].value) : value;
        }];
      },
    };
    if (name === "@/components/ui") return new Proxy({}, { get: (_, key) => key });
    if (name === "@/lib/answer") return {
      useAnswer: () => ({ status: "ready", data: items, retry: () => { retries += 1; } }),
    };
    if (name === "@/lib/api") return { ApiError, projects };
    return require(name);
  }, exports);
  return {
    calls,
    retries: () => retries,
    render(props) {
      cursor = 0;
      return exports.ProjectImages({ projectId: "project", ...props });
    },
  };
}

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}

const images = [
  { id: "inside", category: "interior", filename: "lobby.png" },
  { id: "outside", category: "exterior", filename: "facade.webp" },
  { id: "render", category: "render_3d", filename: "courtyard.jpg" },
];

test("readers see grouped images and meaningful alternatives without mutation controls", () => {
  const view = nodes(harness(images).render({ canEdit: false }));
  assert.equal(view.filter(node => node.type === "img").length, 3);
  assert.deepEqual(
    view.filter(node => node.type === "img").map(node => node.props.alt),
    ["Interior image: lobby.png", "Exterior image: facade.webp", "3D renders image: courtyard.jpg"],
  );
  assert.equal(view.filter(node => node.type === "input").length, 0);
  assert.equal(view.filter(node => node.type === "Button").length, 0);
});

test("writers can select multiple files; all are attempted and server truth refreshes after partial failure", async () => {
  const h = harness(images);
  let view = nodes(h.render({ canEdit: true }));
  const files = [
    { name: "one.png", type: "image/png", size: 20, arrayBuffer: async () => new ArrayBuffer(1) },
    { name: "broken.png", type: "image/png", size: 20, arrayBuffer: async () => new ArrayBuffer(1) },
    { name: "three.webp", type: "image/webp", size: 20, arrayBuffer: async () => new ArrayBuffer(1) },
  ];
  view.find(node => node.type === "input").props.onChange({ target: { files } });
  view = nodes(h.render({ canEdit: true }));
  view.find(node => node.type === "Button" && String(node.props.children).includes("Add 3")).props.onClick();
  await settle();

  assert.deepEqual(h.calls.map(call => call[2].name), ["one.png", "broken.png", "three.webp"]);
  assert.equal(h.retries(), 1);
  const notice = nodes(h.render({ canEdit: true })).find(node => node.type === "Notice");
  assert.equal(notice.props.tone, "error");
  assert.match(notice.props.children, /2 uploaded/);
  assert.match(notice.props.children, /signature rejected/);
});

test("removal confirmation names the image and explains retained history", () => {
  const h = harness(images);
  let view = nodes(h.render({ canEdit: true }));
  const remove = view.find(node => node.type === "Button" && node.props.children === "Remove");
  remove.props.onClick();
  view = nodes(h.render({ canEdit: true }));
  const dialog = view.find(node => node.type === "ConfirmDialog");
  assert.equal(dialog.props.title, "Remove lobby.png?");
  assert.match(dialog.props.body, /retained history/);
});
