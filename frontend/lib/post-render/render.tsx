import { render } from "takumi-js";
import { type Design, HEIGHT, type RenderReport, type Template, WIDTH, createDesign } from "./design";
import { Editorial, editorialLayout } from "./families/editorial";
import { Minimal, minimalLayout } from "./families/minimal";
import { Notes, notesLayout } from "./families/notes";
import { Numbers, numbersLayout } from "./families/numbers";
import { Panorama, panoramaLayout } from "./families/panorama";
import { Scrapbook, scrapbookLayout } from "./families/scrapbook";
import { postRenderer } from "./fonts";
import type { Family, SlideSpec } from "./spec";

const JPEG_QUALITY = 90;

type FamilyTemplate = { layout: (spec: SlideSpec) => string; render: Template };

const TEMPLATES: Record<Family, FamilyTemplate> = {
  editorial: { layout: editorialLayout, render: Editorial },
  numbers: { layout: numbersLayout, render: Numbers },
  panorama: { layout: panoramaLayout, render: Panorama },
  minimal: { layout: minimalLayout, render: Minimal },
  notes: { layout: notesLayout, render: Notes },
  scrapbook: { layout: scrapbookLayout, render: Scrapbook },
};

export type RenderedSlide = { image: Uint8Array; report: RenderReport };

export async function renderSlide(spec: SlideSpec): Promise<RenderedSlide> {
  const renderer = await postRenderer();
  const template = TEMPLATES[spec.family];
  const design: Design = await createDesign(spec, renderer, template.layout(spec));
  const node = await template.render(design);
  const image = await render(node, { width: WIDTH, height: HEIGHT, format: "jpeg", quality: JPEG_QUALITY, renderer });
  return { image, report: design.report };
}
