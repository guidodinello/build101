import type { FormEvent, ReactNode } from "react";

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
      <main className="flex flex-1 flex-col gap-5 px-4 pt-6 pb-8">
        {icon}
        <div className="flex flex-col gap-1.5">
          <h1 className="font-heading text-[28px] leading-[1.1] font-bold tracking-tight text-balance">
            {title}
          </h1>
          {subtitle && (
            <p className="text-[15px] leading-snug text-pretty text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {children}
      </main>
      {footer && (
        <footer className="sticky bottom-0 border-t bg-background px-4 pt-3 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
          {footer}
        </footer>
      )}
    </>
  );

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-120 flex-col">
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
  );
}
