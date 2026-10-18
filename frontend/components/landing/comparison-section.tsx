import { Bubble, DayChip } from "@/components/landing/chat";

const COLUMNS = ["Agency or freelancer", "DIY tools", "AI employee apps"];

const ROWS = [
  { label: "Who does the work", values: ["They do", "You do", "You manage the bots"], neitor: "Neitor's team" },
  { label: "Where it happens", values: ["Calls, email, meetings", "At a computer", "In a web dashboard"], neitor: "In your WhatsApp" },
  { label: "Learning curve", values: ["None", "High", "Medium"], neitor: "None" },
  { label: "Language", values: ["Yours", "Mostly English-first", "English-first"], neitor: "Your Spanish" },
  { label: "Cost", values: ["A monthly retainer", "Low, plus your hours", "Monthly subscription"], neitor: "From US$8 a month" },
];

export function ComparisonSection() {
  return (
    <section aria-labelledby="compare-title">
      <DayChip headingId="compare-title">Neitor vs. the alternatives</DayChip>
      <Bubble
        from="neitor"
        time="6:38 PM"
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
                    {column === "DIY tools" ? (
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
          Other apps give you a team you have to manage. Neitor gives you one person who manages the team for you.
        </p>
      </Bubble>
    </section>
  );
}
