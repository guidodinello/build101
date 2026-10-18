import { render } from "takumi-js";
import { HEIGHT, WIDTH } from "./chrome";
import { Editorial } from "./families/editorial";
import { Numbers } from "./families/numbers";
import { Panorama } from "./families/panorama";
import { postRenderer } from "./fonts";
import type { Family, SlideSpec } from "./spec";

const JPEG_QUALITY = 90;

const TEMPLATES: Record<Family, (props: { spec: SlideSpec }) => React.ReactNode> = {
  editorial: Editorial,
  numbers: Numbers,
  panorama: Panorama,
};

export async function renderSlide(spec: SlideSpec): Promise<Uint8Array> {
  const Template = TEMPLATES[spec.family];
  return render(<Template spec={spec} />, {
    width: WIDTH,
    height: HEIGHT,
    format: "jpeg",
    quality: JPEG_QUALITY,
    renderer: await postRenderer(),
  });
}
