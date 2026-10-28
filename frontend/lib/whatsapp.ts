export const WHATSAPP_URL = process.env.NEXT_PUBLIC_WHATSAPP_URL ?? "https://wa.me/";

export const WHATSAPP_START_URL = withText(WHATSAPP_URL, "Hola Neitor");

export function withText(whatsappUrl: string, text: string): string {
  return `${whatsappUrl}?text=${encodeURIComponent(text)}`;
}
