import { Skeleton } from "@/components/ui/skeleton";

export default function OnboardingLoading() {
  return (
    <div className="flex min-h-dvh w-full flex-1 flex-col bg-dot-grid" aria-busy>
      <div className="mx-auto flex w-full max-w-120 flex-col gap-7 px-3 pt-3">
        <span className="sr-only">Cargando…</span>
        <Skeleton className="h-13 w-full rounded-full bg-white/70" />
        <Skeleton className="mx-1 h-28 w-11/12 rounded-[26px] rounded-tl-lg bg-white/70" />
        <div className="flex flex-col gap-6 px-1">
          {[0, 1, 2].map((row) => (
            <div key={row} className="flex flex-col gap-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-12 w-full rounded-[14px] bg-white/70" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
