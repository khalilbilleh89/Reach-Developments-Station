"use client";

import { useState } from "react";
import { Button, RecordPage } from "@/components/ui";
import { technicalSpecifications, type SpecificationImage } from "@/lib/api/technicalSpecifications";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function SpecificationImages({ projectId, specificationId, images, canWrite, onChanged }: {
  projectId: string; specificationId: string; images: SpecificationImage[]; canWrite: boolean; onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState<SpecificationImage | null>(null);
  if (!images.length) return null;
  return <div className="stack stack-tight">
    <p className="footnote">Reference images · Refer to the written specification for coverage and inclusions.</p>
    <div className="specification-images">{images.map(image => <figure key={image.id}>
      <Button variant="link" onClick={() => setOpen(image)} aria-label={"View " + image.filename}>
        {/* Same-origin authenticated, server-decoded images; no remote optimisation. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={technicalSpecifications.imageUrl(projectId, specificationId, image.id)} alt={image.filename} loading="lazy" />
      </Button>
      <figcaption>{image.filename}</figcaption>
      {canWrite ? <DeleteRecordButton label={image.filename} confirmLabel="Remove image" description="Removes this image from the specification guide; stored evidence and audit history are retained." onDelete={reason => technicalSpecifications.removeImage(projectId, specificationId, image.id, reason)} onDeleted={onChanged} /> : null}
    </figure>)}</div>
    {open ? <RecordPage title={open.filename} onClose={() => setOpen(null)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="specification-image-full" src={technicalSpecifications.imageUrl(projectId, specificationId, open.id)} alt={open.filename} />
    </RecordPage> : null}
  </div>;
}
