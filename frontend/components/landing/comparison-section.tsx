import { Bubble, DayChip } from "@/components/landing/chat";

const COLUMNS = ["Agencia o freelancer", "Hacerlo vos", "Apps de empleados con IA"];

const ROWS = [
  { label: "Quién hace el trabajo", values: ["Ellos", "Vos", "Vos, manejando los bots"], neitor: "El equipo de Neitor" },
  { label: "Dónde pasa", values: ["Llamadas, mails, reuniones", "En la compu", "En un panel web"], neitor: "En tu WhatsApp" },
  { label: "Curva de aprendizaje", values: ["Ninguna", "Alta", "Media"], neitor: "Ninguna" },
  { label: "Idioma", values: ["El tuyo", "Casi siempre pensadas en inglés", "Pensadas en inglés"], neitor: "Tu español" },
  { label: "Costo", values: ["Un abono mensual", "Bajo, más tus horas", "Suscripción mensual"], neitor: "Gratis para probar, después US$29 por mes" },
];

export function ComparisonSection() {
  return (
    <section aria-labelledby="compare-title">
      <DayChip headingId="compare-title">Neitor vs. las alternativas</DayChip>
      <Bubble
        from="neitor"
        time="18:38"
        className="w-full max-w-full px-5.5 pt-5.5 sm:max-w-full"
        rowClassName="motion-safe:reveal-on-scroll"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-165 border-collapse text-left text-[15px] leading-snug">
            <thead>
              <tr>
                <td />
                {COLUMNS.map((column) => (
                  <th key={column} scope="col" className="px-3 py-3.5 align-top font-bold">
                    {column}
                    {column === "Hacerlo vos" ? (
                      <span className="block font-normal text-ld-muted">Canva, Meta Suite, ChatGPT</span>
                    ) : null}
                  </th>
                ))}
                <th scope="col" className="rounded-t-[14px] bg-ld-forest px-3 py-3.5 align-top font-bold text-ld-on-dark">
                  Neitor AI
                </th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row, index) => {
                const isLast = index === ROWS.length - 1;
                const border = isLast ? "" : "border-b border-[#eaefeb]";
                return (
                  <tr key={row.label}>
                    <th scope="row" className={`px-3 py-3.5 align-top font-bold ${border}`}>
                      {row.label}
                    </th>
                    {row.values.map((value, column) => (
                      <td key={COLUMNS[column]} className={`px-3 py-3.5 align-top ${border}`}>
                        {value}
                      </td>
                    ))}
                    <td
                      className={`bg-ld-forest px-3 py-3.5 align-top font-bold text-ld-on-dark ${isLast ? "rounded-b-[14px]" : "border-b border-white/10"}`}
                    >
                      {row.neitor}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-4.5 font-heading text-xl leading-snug font-bold tracking-tight">
          Otras apps te dan un equipo que tenés que manejar. Neitor te da una persona que maneja el equipo por vos.
        </p>
      </Bubble>
    </section>
  );
}
