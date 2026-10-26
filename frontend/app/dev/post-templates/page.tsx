import Image from "next/image";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { previewEnabled } from "@/lib/post-render/preview";
import { SAMPLE_BRANDS, SAMPLE_SLIDES, type SampleBrand } from "@/lib/post-render/samples";
import { FAMILIES, LAYOUTS } from "@/lib/post-render/spec";

const THUMB_WIDTH = 216;
const THUMB_HEIGHT = 270;

export default function PostTemplatesPage({ searchParams }: PageProps<"/dev/post-templates">) {
  return (
    <Suspense>
      <Templates searchParams={searchParams} />
    </Suspense>
  );
}

function Thumb({ query, label }: { query: string; label: string }) {
  const src = `/api/render/preview?${query}`;
  return (
    <a href={src} target="_blank" className="flex shrink-0 flex-col gap-1">
      <Image src={src} alt={label} width={THUMB_WIDTH} height={THUMB_HEIGHT} unoptimized />
      <span className="font-mono text-xs text-neutral-500">{label}</span>
    </a>
  );
}

async function Templates({ searchParams }: { searchParams: PageProps<"/dev/post-templates">["searchParams"] }) {
  await connection();
  if (!previewEnabled()) notFound();
  const params = await searchParams;
  const brands = Object.keys(SAMPLE_BRANDS) as SampleBrand[];
  const brand = brands.find((name) => name === params.brand) ?? "roble";
  const indexes = SAMPLE_SLIDES.map((_, position) => position + 1);
  return (
    <main className="flex flex-col gap-12 overflow-x-auto bg-neutral-100 p-8">
      <nav className="flex gap-4 font-mono text-sm">
        {brands.map((name) => (
          <a key={name} href={`?brand=${name}`} className={name === brand ? "font-bold underline" : "text-neutral-600"}>
            {SAMPLE_BRANDS[name].name}
          </a>
        ))}
      </nav>
      {FAMILIES.map((family) => (
        <section key={family} className="flex flex-col gap-3">
          <h2 className="font-mono text-sm text-neutral-600">{family}</h2>
          <div className="flex gap-2">
            {indexes.map((index) => (
              <Thumb key={index} query={`family=${family}&index=${index}&brand=${brand}&logo=1`} label={`#${index}`} />
            ))}
            {LAYOUTS[family].map((layout) => (
              <Thumb
                key={layout}
                query={`family=${family}&index=${layout === "overlay" || layout === "frame" || layout === "poster" || layout === "window" || layout === "type" ? 1 : 3}&layout=${layout}&brand=${brand}`}
                label={layout}
              />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
