import { QueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api/client';

/**
 * Shared query client.
 *
 * `staleTime: 60s` for catalogue data (plan.md 11): the nav, the catalogue
 * page and the command palette all read the same endpoints, and without a
 * shared cache every navigation refetches all of it.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      // Refetching on every tab focus is noise for a catalogue that changes
      // a few times a day, and it makes the app feel busy for no reason.
      refetchOnWindowFocus: false,
      retry: (count, error) => {
        // 4xx means the request was wrong; repeating it will not fix that.
        if (error instanceof ApiError && error.status < 500) return false;
        return count < 2;
      },
    },
  },
});
