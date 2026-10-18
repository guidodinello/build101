import type { ReactNode } from "react";
import { CheckCheckIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Sender = "neitor" | "owner";

type BubbleProps = {
  from: Sender;
  time?: string;
  className?: string;
  rowClassName?: string;
  timeClassName?: string;
  children: ReactNode;
};

export function Bubble({ from, time, className, rowClassName, timeClassName, children }: BubbleProps) {
  const isOwner = from === "owner";
  return (
    <div className={cn("my-2 flex", isOwner && "justify-end", rowClassName)}>
      <div
        className={cn(
          "relative max-w-[92%] rounded-[26px] px-5 pt-4 pb-3 text-[17px] leading-normal sm:max-w-[76%] sm:text-lg",
          isOwner
            ? "rounded-tr-lg bg-ld-forest text-ld-on-dark shadow-bubble-owner"
            : "rounded-tl-lg bg-white text-ld-ink shadow-bubble",
          className,
        )}
      >
        {children}
        {time && <Timestamp time={time} read={isOwner} className={timeClassName} />}
      </div>
    </div>
  );
}

export function Timestamp({ time, read, className }: { time: string; read?: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "mt-2 flex items-center justify-end gap-1 text-xs font-medium tabular-nums",
        read ? "text-ld-sage" : "text-ld-subtle",
        className,
      )}
    >
      {time}
      {read && <CheckCheckIcon className="size-4 text-sky-300" aria-label="Read" />}
    </span>
  );
}

type DayChipProps = {
  id?: string;
  headingId?: string;
  className?: string;
  children: ReactNode;
};

export function DayChip({ id, headingId, className, children }: DayChipProps) {
  const Tag = headingId ? "h2" : "span";
  return (
    <div id={id} className={cn("mt-24 mb-5 flex scroll-mt-28 justify-center sm:mt-30", className)}>
      <Tag
        id={headingId}
        className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-[13px] font-semibold tracking-wide text-[#2d4a3e] shadow-[0_0_0_1px_rgb(14_42_32/0.08)] backdrop-blur-sm"
      >
        <span aria-hidden="true" className="size-1.5 rounded-full bg-ld-accent" />
        {children}
      </Tag>
    </div>
  );
}

type DisplayProps = {
  as?: "h1" | "h2" | "p";
  id?: string;
  className?: string;
  children: ReactNode;
};

export function Display({ as: Tag = "p", id, className, children }: DisplayProps) {
  return (
    <Tag id={id} className={cn("font-heading font-extrabold tracking-[-0.04em] text-balance", className)}>
      {children}
    </Tag>
  );
}

export function Label({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cn("text-xs font-semibold tracking-[0.06em] text-ld-subtle uppercase", className)}>
      {children}
    </span>
  );
}
