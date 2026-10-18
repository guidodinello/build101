import Image from "next/image";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { previewEnabled } from "@/lib/post-render/preview";
import { SAMPLE_SLIDES } from "@/lib/post-render/samples";
import { FAMILIES } from "@/lib/post-render/spec";

const THUMB_WIDTH = 216;
const THUMB_HEIGHT = 270;

export default function PostTemplatesPage() {
  return (
    <Suspense>
      <Templates />
    </Suspense>
  );
}

async function Templates() {
  await connection();
  if (!previewEnabled()) notFound();
  const indexes = SAMPLE_SLIDES.map((_, position) => position + 1);
  return (
    <main className="flex flex-col gap-12 overflow-x-auto bg-neutral-100 p-8">
      {FAMILIES.map((family) => (
        <section key={family} className="flex flex-col gap-3">
          <h2 className="font-mono text-sm text-neutral-600">{family}</h2>
          <div className="flex">
            {indexes.map((index) => (
              <a key={index} href={`/api/render/preview?family=${family}&index=${index}&logo=1`} target="_blank">
                <Image
                  src={`/api/render/preview?family=${family}&index=${index}&logo=1`}
                  alt={`${family} ${index}`}
                  width={THUMB_WIDTH}
                  height={THUMB_HEIGHT}
                  unoptimized
                />
              </a>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
