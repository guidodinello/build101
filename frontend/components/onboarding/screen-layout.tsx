import type { FormEvent, ReactNode } from "react";
import { Bubble, Display } from "@/components/landing/chat";
import { cn } from "@/lib/utils";

type ScreenLayoutProps = {
  header?: ReactNode;
  icon?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  onSubmit?: () => void;
};

export function ScreenLayout({
  header,
  icon,
  title,
  subtitle,
  children,
  footer,
  onSubmit,
}: ScreenLayoutProps) {
  const body = (
    <>
      <main className={cn("flex flex-1 flex-col gap-7 px-4 pb-10", header ? "pt-3" : "pt-8")}>
        <Bubble
          from="neitor"
          className="px-5 pt-4.5 pb-4.5 sm:max-w-[92%] sm:text-[17px]"
          rowClassName="my-0 motion-safe:animate-rise"
        >
          {icon}
          <Display as="h1" className="text-[30px] leading-[1.04]">
            {title}
          </Display>
          {subtitle && (
            <p className="mt-2 text-base leading-snug text-pretty text-muted-foreground">{subtitle}</p>
          )}
        </Bubble>
        {children}
      </main>
      {footer && (
        <footer className="sticky bottom-0 bg-linear-to-t from-background from-70% to-background/0 px-4 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
          {footer}
        </footer>
      )}
    </>
  );

  return (
    <div className="flex min-h-dvh w-full flex-1 flex-col bg-dot-grid">
      <div className="mx-auto flex w-full max-w-120 flex-1 flex-col">
        {header}
        {onSubmit ? (
          <form
            noValidate
            className="flex flex-1 flex-col"
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            {body}
          </form>
        ) : (
          body
        )}
      </div>
    </div>
  );
}
