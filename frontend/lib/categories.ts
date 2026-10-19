export type CategoryCopy = {
  oneLiner: string;
  product: { name: string; description: string; price: string };
  audiences: string[];
  words: string[];
  offer: string;
};

export const OTHER_CATEGORY = "Otro";

const CATEGORY_COPY = {
  "Muebles y deco": {
    oneLiner: "Muebles de madera maciza hechos a mano en Montevideo",
    product: { name: "Mesa Nórdica", description: "hecha a mano, en roble macizo", price: "$ 18.500" },
    audiences: ["Familias", "Parejas jóvenes", "Empresas y oficinas", "Arquitectos y decoradores"],
    words: ["Cálidos", "Artesanales", "Confiables", "Duraderos", "Modernos", "Prolijos"],
    offer: "15% en sillas hasta fin de mes",
  },
  Gastronomía: {
    oneLiner: "Pastas caseras y viandas para el mediodía en Pocitos",
    product: { name: "Sorrentinos de calabaza", description: "masa casera, salsa a elección", price: "$ 420" },
    audiences: ["Oficinistas", "Familias", "Estudiantes", "Eventos y empresas"],
    words: ["Caseros", "Ricos", "Abundantes", "Frescos", "Rápidos", "Amables"],
    offer: "2x1 en postres los martes",
  },
  Indumentaria: {
    oneLiner: "Ropa de mujer de diseño propio, hecha en Uruguay",
    product: { name: "Campera de jean", description: "oversize, con forro de corderito", price: "$ 3.200" },
    audiences: ["Mujeres jóvenes", "Mamás", "Adolescentes", "Hombres"],
    words: ["Originales", "Cómodos", "Modernos", "De calidad", "Únicos", "Atentos"],
    offer: "Envío gratis en compras de más de $ 2.000",
  },
  Belleza: {
    oneLiner: "Peluquería y uñas con turnos en el día, en el Centro",
    product: { name: "Esmaltado semipermanente", description: "dura 3 semanas, más de 60 colores", price: "$ 750" },
    audiences: ["Mujeres de 25 a 45", "Novias y eventos", "Adolescentes", "Hombres"],
    words: ["Prolijos", "Cálidos", "Puntuales", "Delicados", "Modernos", "Profesionales"],
    offer: "20% en tu primer turno",
  },
  Servicios: {
    oneLiner: "Instalaciones eléctricas y aire acondicionado en Canelones",
    product: { name: "Instalación de aire", description: "con garantía de un año", price: "Desde $ 4.500" },
    audiences: ["Hogares", "Comercios", "Empresas", "Inmobiliarias"],
    words: ["Confiables", "Puntuales", "Prolijos", "Rápidos", "Honestos", "Profesionales"],
    offer: "Visita técnica gratis este mes",
  },
} satisfies Record<string, CategoryCopy>;

type ListedCategory = keyof typeof CATEGORY_COPY;

const FALLBACK_COPY: CategoryCopy = {
  oneLiner: "Qué hacés, para quién y dónde, en una frase",
  product: { name: "Tu producto estrella", description: "qué lo hace especial", price: "$ 1.000" },
  audiences: ["Familias", "Jóvenes", "Empresas", "Turistas"],
  words: ["Confiables", "Cálidos", "Originales", "Atentos", "Modernos", "De calidad"],
  offer: "10% en tu primera compra",
};

export const CATEGORIES = [...Object.keys(CATEGORY_COPY), OTHER_CATEGORY];

export function copyFor(category: string | null | undefined): CategoryCopy {
  return category && isListedCategory(category) ? CATEGORY_COPY[category] : FALLBACK_COPY;
}

// hasOwn, not `in`: the category is Owner free text and "constructor" must not hit Object.prototype.
export function isListedCategory(category: string): category is ListedCategory {
  return Object.hasOwn(CATEGORY_COPY, category);
}
