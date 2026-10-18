import { Bubble, DayChip } from "@/components/landing/chat";

const FAQS = [
  {
    question: "Do I need to download anything?",
    answer: "No. Just WhatsApp. The only web step is the 5-minute form, opened from a link in the chat.",
  },
  {
    question: "Will you post without asking me?",
    answer: "Never. Every post comes to you first, and it goes out only after you tap Approve.",
  },
  {
    question: "Do you need my Instagram password?",
    answer: "No. You connect your account on Instagram's own login page. We never see your password.",
  },
  {
    question: "Will it sound like a robot?",
    answer: "It learns your tone, your words and your style from the form and from every correction you make.",
  },
  {
    question: "Can I just send voice notes?",
    answer: "Yes. Talk to Neitor the way you'd talk to anyone on your team, in your own Spanish.",
  },
  { question: "Which networks?", answer: "Instagram today. Facebook and TikTok are on the roadmap." },
];

export function FaqSection() {
  return (
    <section aria-labelledby="faq-title">
      <DayChip id="faq" headingId="faq-title">
        Questions owners ask
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
