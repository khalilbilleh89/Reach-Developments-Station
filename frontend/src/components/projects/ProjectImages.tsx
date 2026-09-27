"use client";

import { useEffect, useState } from "react";

import { ApiError, projects } from "@/lib/api";
import type { ProjectImage } from "@/lib/api";
import { Button, Card, Field, FormDialog, Notice } from "@/components/ui";

const CATEGORIES = [
  { value: "interior", label: "Interior" },
  { value: "exterior", label: "Exterior" },
  { value: "render_3d", label: "3D shots" },
] as const;

export function ProjectImages({ projectId, canEdit }: { projectId: string; canEdit: boolean }) {
  const [items, setItems] = useState<ProjectImage[]>([]);
  const [category, setCategory] = useState<ProjectImage["category"]>("interior");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removeId, setRemoveId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    projects.images(projectId).then(images => { if (active) setItems(images); })
      .catch(caught => { if (active) setError(caught instanceof ApiError ? caught.message : "Could not load project images."); });
    return () => { active = false; };
  }, [projectId]);

  const upload = async () => {
    setBusy(true);
    setError(null);
    try {
      for (const file of files) {
        if (file.size > 10 * 1024 * 1024) throw new Error(`${file.name} is larger than 10 MB.`);
        await projects.addImage(projectId, category, file);
      }
      setItems(await projects.images(projectId));
      setFiles([]);
    } catch (caught) {
      setItems(await projects.images(projectId).catch(() => items));
      setError(caught instanceof Error ? caught.message : "Could not add the image.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!removeId) return;
    setBusy(true);
    setError(null);
    try {
      await projects.removeImage(projectId, removeId);
      setItems(await projects.images(projectId));
      setRemoveId(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not remove the image.");
    } finally {
      setBusy(false);
    }
  };

  return <Card title="Project images" description="Interior, exterior and 3D project shots. Add or remove images at any time.">
    {error ? <Notice tone="error">{error}</Notice> : null}
    {canEdit ? <div className="project-images-controls">
      <Field label="Image category"><select className="input" value={category} onChange={event => setCategory(event.target.value as ProjectImage["category"])}>{CATEGORIES.map(option => <option value={option.value} key={option.value}>{option.label}</option>)}</select></Field>
      <Field label="Images" hint="JPEG, PNG or WebP; up to 10 MB each."><input className="input" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => setFiles(Array.from(event.target.files ?? []))} /></Field>
      <Button onClick={() => void upload()} disabled={busy || files.length === 0}>{busy ? "Working…" : `Add ${files.length || ""} image${files.length === 1 ? "" : "s"}`}</Button>
    </div> : null}
    {CATEGORIES.map(option => {
      const images = items.filter(item => item.category === option.value);
      return <section key={option.value} className="project-images-section" aria-label={`${option.label} images`}>
        <h3>{option.label}</h3>
        {images.length ? <div className="project-images-grid">{images.map(item => <figure key={item.id} className="project-image">
          {/* Project images are authenticated same-origin files, not remote optimized assets. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={projects.imageUrl(projectId, item.id)} alt={`${option.label} — ${item.filename}`} loading="lazy" />
          <figcaption><span>{item.filename}</span>{canEdit ? <Button small variant="danger" onClick={() => setRemoveId(item.id)}>Remove</Button> : null}</figcaption>
        </figure>)}</div> : <p className="muted">No {option.label.toLowerCase()} images yet.</p>}
      </section>;
    })}
    {removeId ? <FormDialog title="Remove image" description="This image will disappear from the project gallery. Its removal remains in the audit history." confirmLabel="Remove image" busy={busy} onCancel={() => setRemoveId(null)} onSubmit={() => void remove()}><p>Remove {items.find(item => item.id === removeId)?.filename}?</p></FormDialog> : null}
  </Card>;
}
