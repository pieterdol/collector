/** Half-star rating display; interactive when onChange is provided
 * (click left half = .5, right half = full, click current value = clear). */

interface Props {
  value: number;
  onChange?: (value: number | null) => void;
  size?: number;
}

export function RatingStars({ value, onChange, size = 16 }: Props) {
  const stars = [1, 2, 3, 4, 5];

  function pick(star: number, half: boolean) {
    if (!onChange) return;
    const next = half ? star - 0.5 : star;
    onChange(next === value ? null : next);
  }

  return (
    <span
      role={onChange ? "slider" : "img"}
      aria-label={`${value} of 5 stars`}
      aria-valuenow={onChange ? value : undefined}
      aria-valuemin={onChange ? 0 : undefined}
      aria-valuemax={onChange ? 5 : undefined}
      className="inline-flex gap-[2px]"
      style={{ fontSize: size, lineHeight: 1, letterSpacing: 1 }}
    >
      {stars.map((star) => {
        const fill = Math.min(1, Math.max(0, value - star + 1));
        return (
          <span key={star} className="relative inline-block select-none">
            <span className="opacity-25">★</span>
            {fill > 0 && (
              <span
                className="absolute inset-0 overflow-hidden"
                style={{ width: fill >= 1 ? "100%" : "50%" }}
              >
                ★
              </span>
            )}
            {onChange && (
              <>
                <button
                  type="button"
                  aria-label={`${star - 0.5} stars`}
                  onClick={() => pick(star, true)}
                  className="absolute inset-y-0 left-0 w-1/2 cursor-pointer opacity-0"
                />
                <button
                  type="button"
                  aria-label={`${star} stars`}
                  onClick={() => pick(star, false)}
                  className="absolute inset-y-0 right-0 w-1/2 cursor-pointer opacity-0"
                />
              </>
            )}
          </span>
        );
      })}
    </span>
  );
}
