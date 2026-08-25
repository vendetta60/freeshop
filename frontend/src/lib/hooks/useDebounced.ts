import { useEffect, useState } from 'react';

/** Returns `value` after it has stopped changing for `delay` ms. */
export function useDebounced<T>(value: T, delay = 250): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const id = window.setTimeout(() => {
      setSettled(value);
    }, delay);
    return () => {
      window.clearTimeout(id);
    };
  }, [value, delay]);

  return settled;
}
