export const WHATSAPP_URL = process.env.NEXT_PUBLIC_WHATSAPP_URL ?? "https://wa.me/";

export const WHATSAPP_START_URL = `${WHATSAPP_URL}?text=${encodeURIComponent("Hola Neitor")}`;
