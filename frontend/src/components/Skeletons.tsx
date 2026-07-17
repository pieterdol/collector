/** Loading placeholders shaped like the real content. */

export function PosterGridSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(154px,1fr))] gap-x-4 gap-y-5 max-[760px]:grid-cols-[repeat(auto-fill,minmax(124px,1fr))]">
      {Array.from({ length: count }, (_, i) => (
        <div key={i}>
          <div className="skeleton aspect-[2/3]" />
          <div className="skeleton mt-2 h-3.5 w-3/4 rounded" />
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="grid grid-cols-[280px_1fr] items-start gap-9 max-[760px]:grid-cols-1">
      <div className="skeleton aspect-[2/3] max-[760px]:max-w-[240px]" />
      <div className="flex flex-col gap-4">
        <div className="skeleton h-4 w-40 rounded" />
        <div className="skeleton h-11 w-3/4 rounded" />
        <div className="skeleton h-4 w-56 rounded" />
        <div className="skeleton mt-4 h-32 rounded-xl" />
      </div>
    </div>
  );
}
