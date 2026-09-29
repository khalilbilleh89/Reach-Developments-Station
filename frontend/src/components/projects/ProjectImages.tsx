"use client";

import { useState } from "react";

import { Button, Card, ConfirmDialog, EmptyState, Field, Loading, Notice } from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { ApiError, projects } from "@/lib/api";
import type { ProjectImage } from "@/lib/api";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const CATEGORIES = [
  { value: "interior", label: "Interior" },
  { value: "exterior", label: "Exterior" },
  { value: "render_3d", label: "3D renders" },
] as const;

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

export function ProjectImages({ projectId, canEdit }: { projectId: string; canEdit: boolean }) {
  const answer = useAnswer(true, () => projects.images(projectId), [projectId]);
  const [category, setCategory] = useState<ProjectImage["category"]>("interior");
  const [files, setFiles] = useState<File[]>([]);
  const [inputRevision, setInputRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [removeTarget, setRemoveTarget] = useState<ProjectImage | null>(null);

  async function upload(): Promise<void> {
    setBusy(true);
    setNotice(null);
    const failures: string[] = [];
    // Only files the server refused stay selected, so pressing the button again
    // retries those and never uploads an already-stored image a second time.
    const retry: File[] = [];
    let uploaded = 0;
    for (const file of files) {
      if (file.size === 0 || file.size > MAX_IMAGE_BYTES) {
        failures.push(`${file.name}: image must be between 1 byte and 10 MB.`);
        continue;
      }
      try {
        await projects.addImage(projectId, category, file);
        uploaded += 1;
      } catch (caught) {
        failures.push(`${file.name}: ${errorMessage(caught, "could not upload image.")}`);
        retry.push(file);
      }
    }
    // Every file is attempted independently. Reload once at the end so a
    // partial success is represented by server truth rather than local guesses.
    answer.retry();
    if (failures.length) {
      setNotice({
        tone: "error",
        text: `${uploaded} uploaded. ${failures.join(" ")}${retry.length ? ` Press Retry to try the ${retry.length} that failed again.` : ""}`,
      });
      setFiles(retry);
      setInputRevision(value => value + 1);
    } else {
      setNotice({ tone: "success", text: `${uploaded} image${uploaded === 1 ? "" : "s"} added.` });
      setFiles([]);
      setInputRevision(value => value + 1);
    }
    setBusy(false);
  }

  async function remove(): Promise<void> {
    if (!removeTarget) return;
    setBusy(true);
    setNotice(null);
    try {
      await projects.removeImage(projectId, removeTarget.id);
      setRemoveTarget(null);
      setNotice({ tone: "success", text: `${removeTarget.filename} removed from the gallery.` });
      answer.retry();
    } catch (caught) {
      setNotice({ tone: "error", text: errorMessage(caught, "Could not remove the image.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Project images"
      description="Interior, exterior and 3D presentation images for this project."
    >
      {notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}
      {canEdit ? (
        <div className="project-images-controls">
          <Field label="Image category">
            <select
              className="input"
              value={category}
              disabled={busy}
              onChange={event => setCategory(event.target.value as ProjectImage["category"])}
            >
              {CATEGORIES.map(option => (
                <option value={option.value} key={option.value}>{option.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Images" hint="JPEG, PNG or WebP; up to 10 MB each.">
            <input
              key={inputRevision}
              className="input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              disabled={busy}
              onChange={event => setFiles(Array.from(event.target.files ?? []))}
            />
          </Field>
          <Button variant="primary" onClick={() => void upload()} disabled={busy || files.length === 0}>
            {busy
              ? "Working…"
              : notice?.tone === "error" && files.length
                ? `Retry ${files.length} image${files.length === 1 ? "" : "s"}`
                : `Add ${files.length || ""} image${files.length === 1 ? "" : "s"}`}
          </Button>
        </div>
      ) : null}

      {answer.status === "loading" ? <Loading label="Loading project images…" shape="rows" rows={3} /> : null}
      {answer.status === "failed" ? (
        <Notice tone="error">
          {answer.message} <Button small onClick={answer.retry}>Try again</Button>
        </Notice>
      ) : null}
      {answer.status === "denied" ? (
        <EmptyState title="Project images are not available to your role" />
      ) : null}
      {answer.status === "ready" ? CATEGORIES.map(option => {
        const categoryImages = answer.data.filter(image => image.category === option.value);
        return (
          <section key={option.value} className="project-images-section" aria-label={`${option.label} images`}>
            <h3>{option.label}</h3>
            {categoryImages.length ? (
              <div className="project-images-grid">
                {categoryImages.map(image => (
                  <figure key={image.id} className="project-image">
                    {/* Authenticated same-origin binary route; Next image optimization cannot carry this session contract. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={projects.imageUrl(projectId, image.id)}
                      alt={`${option.label} image: ${image.filename}`}
                      loading="lazy"
                    />
                    <figcaption>
                      <span>{image.filename}</span>
                      {canEdit ? (
                        <Button small variant="danger" onClick={() => setRemoveTarget(image)}>Remove</Button>
                      ) : null}
                    </figcaption>
                  </figure>
                ))}
              </div>
            ) : (
              <EmptyState compact title={`No ${option.label.toLowerCase()} images`} />
            )}
          </section>
        );
      }) : null}

      {removeTarget ? (
        <ConfirmDialog
          title={`Remove ${removeTarget.filename}?`}
          body="The image will disappear from the project gallery. Its record and removal attribution remain in retained history."
          confirmLabel="Remove image"
          busy={busy}
          onCancel={() => setRemoveTarget(null)}
          onConfirm={() => void remove()}
        />
      ) : null}
    </Card>
  );
}
