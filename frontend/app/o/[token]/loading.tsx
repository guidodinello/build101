import { Skeleton } from "@/components/ui/skeleton";

export default function OnboardingLoading() {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-120 flex-col gap-5 px-4 pt-17" aria-busy>
      <span className="sr-only">Cargando…</span>
      <Skeleton className="h-1.5 w-full rounded-full" />
      <Skeleton className="mt-4 h-8 w-3/4" />
      <div className="flex flex-col gap-4">
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-12 w-full rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  );
}
