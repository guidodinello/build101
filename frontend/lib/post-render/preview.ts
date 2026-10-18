export function previewEnabled(): boolean {
  return process.env.ENABLE_TEMPLATE_PREVIEW === "true";
}
