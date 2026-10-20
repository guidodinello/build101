import { Bubble, DayChip } from "@/components/landing/chat";

const FAQS = [
  {
    question: "¿Tengo que descargar algo?",
    answer: "No. Solo WhatsApp. El único paso en la web es un formulario de 5 minutos, que abrís desde un link en el chat.",
  },
  {
    question: "¿Van a publicar sin preguntarme?",
    answer: "Nunca. Cada post te llega primero, y sale solo después de que tocás Aprobar.",
  },
  {
    question: "¿Necesitan mi contraseña de Instagram?",
    answer: "No. Conectás tu cuenta en la página de inicio de sesión del propio Instagram. Nunca vemos tu contraseña.",
  },
  {
    question: "¿Va a sonar como un robot?",
    answer: "Aprende tu tono, tus palabras y tu estilo del formulario y de cada corrección que le hacés.",
  },
  {
    question: "¿Puedo mandar solo audios?",
    answer: "Sí. Hablale a Neitor como le hablarías a cualquiera de tu equipo, con tus palabras.",
  },
  { question: "¿En qué redes?", answer: "Hoy en Instagram. Facebook y TikTok vienen en camino." },
];

export function FaqSection() {
  return (
    <section aria-labelledby="faq-title">
      <DayChip id="faq" headingId="faq-title">
        Preguntas frecuentes
      </DayChip>
      <dl>
        {FAQS.map((faq) => (
          <div key={faq.question}>
            <dt>
              <Bubble from="owner" rowClassName="motion-safe:reveal-on-scroll">
                {faq.question}
              </Bubble>
            </dt>
            <dd>
              <Bubble from="neitor" rowClassName="motion-safe:reveal-on-scroll">
                {faq.answer}
              </Bubble>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
