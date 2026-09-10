import { useQuery } from '@tanstack/react-query';
import { MessageCircle } from 'lucide-react';
import { Link } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { communityKeys, messagesApi } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * The inbox (FreeShop_Prompt 3).
 *
 * Refetched on an interval rather than over a socket: this deployment is one
 * uvicorn process (plan.md 12.3), messages on a give-away board arrive
 * minutes apart, and a socket layer would add a connection lifecycle, a
 * reconnect story and a second auth path to buy nothing a visitor would
 * notice. FreeShop_Prompt 3 explicitly permits polling for v1.
 */
const POLL_MS = 30_000;

export default function MessagesPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);

  useDocumentTitle(t('messages.title'));

  const conversations = useQuery({
    queryKey: communityKeys.conversations(lang),
    queryFn: ({ signal }) => messagesApi.list(lang, signal),
    enabled: user !== null,
    refetchInterval: POLL_MS,
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('messages.signInTitle')}
        description={t('messages.signInText')}
        icon={<MessageCircle size={22} />}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('messages.title')}</h1>
      </header>

      {conversations.isError && <ErrorState onRetry={() => void conversations.refetch()} />}

      {conversations.isPending && (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} height={72} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {conversations.data?.length === 0 && (
        <EmptyState
          title={t('messages.empty')}
          description={t('messages.emptyText')}
          icon={<MessageCircle size={22} />}
        />
      )}

      <div style={{ display: 'grid', gap: '0.5rem' }}>
        {(conversations.data ?? []).map((conversation) => {
          // Everyone in the thread except you. Threads are always two people
          // today, but reading it this way means a group thread later needs
          // no change here.
          const others = conversation.participants.filter((p) => p.user_id !== user.id);
          const name = others.map((p) => p.display_name).join(', ') || t('messages.unknownParty');

          return (
            <Link
              key={conversation.id}
              to={`/messages/${conversation.id}`}
              className="card conversation-row"
            >
              <div style={{ minWidth: 0, display: 'grid', gap: '0.2rem' }}>
                <div className="conversation-row__head">
                  <span style={{ fontWeight: 500 }}>{name}</span>
                  {conversation.unread_count > 0 && (
                    <Badge tone="accent">{conversation.unread_count}</Badge>
                  )}
                </div>

                {conversation.subject && (
                  <span className="subtle" style={{ fontSize: '0.8125rem' }}>
                    {t(`messages.about.${conversation.type}`, { subject: conversation.subject })}
                  </span>
                )}

                {conversation.last_message_preview && (
                  <p className="conversation-row__preview">{conversation.last_message_preview}</p>
                )}
              </div>

              {conversation.last_message_at && (
                <span className="subtle" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                  {formatDate(conversation.last_message_at, lang)}
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
