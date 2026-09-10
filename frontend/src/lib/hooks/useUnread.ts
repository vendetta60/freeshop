import { useQuery } from '@tanstack/react-query';

import { communityKeys, messagesApi } from '@/lib/api/community';
import { useAuthStore } from '@/stores/authStore';

/**
 * The badge counts for messages and notifications.
 *
 * ONE endpoint for both, polled once for the whole app. The navigation is
 * rendered on every page, so anything it fetches per-component is fetched
 * everywhere - this hook is deliberately the only caller of
 * `/conversations/unread`, and React Query dedupes the rest.
 *
 * Sixty seconds, not five: a give-away board is not a chat application, and
 * a badge that is a minute stale has cost nobody anything. The conversation
 * screen itself polls faster, because that is where somebody is waiting.
 */
const POLL_MS = 60_000;

export function useUnread(): { conversations: number; notifications: number; total: number } {
  const signedIn = useAuthStore((s) => s.user !== null);

  const { data } = useQuery({
    queryKey: communityKeys.unread(),
    queryFn: ({ signal }) => messagesApi.unread(signal),
    enabled: signedIn,
    refetchInterval: POLL_MS,
    // A failed badge fetch must never surface as an error state - it is
    // decoration on every other screen in the app.
    retry: false,
  });

  const conversations = data?.conversations ?? 0;
  const notifications = data?.notifications ?? 0;
  return { conversations, notifications, total: conversations + notifications };
}
