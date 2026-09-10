import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';

import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/States';
import { communityKeys, messagesApi, type Message } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';

const POLL_MS = 15_000;
const MAX_BODY = 4000;

/**
 * One conversation (FreeShop_Prompt 3).
 *
 * The API returns messages NEWEST FIRST (keyset pagination on the id, so a
 * thread being written to while it is read cannot duplicate or skip a line).
 * They are reversed for display, because a conversation reads downwards.
 *
 * Polled a little faster than the inbox: this is the screen where somebody is
 * actually waiting for a reply.
 */
export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const conversationId = Number(id);
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const [body, setBody] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const thread = useQuery({
    queryKey: communityKeys.thread(conversationId, lang),
    queryFn: ({ signal }) => messagesApi.thread(conversationId, lang, undefined, signal),
    enabled: Number.isFinite(conversationId) && user !== null,
    refetchInterval: POLL_MS,
  });

  const subject = thread.data?.conversation.subject;
  useDocumentTitle(subject ?? t('messages.title'));

  const newestId = thread.data?.messages[0]?.id ?? null;

  // Scroll to the newest line when one arrives - not on every render, which
  // would fight the reader every time they scrolled up to re-read something.
  useEffect(() => {
    if (newestId !== null) endRef.current?.scrollIntoView({ block: 'end' });
  }, [newestId]);

  const send = useMutation({
    mutationFn: (text: string) => messagesApi.send(conversationId, text),
    onSuccess: async () => {
      setBody('');
      await queryClient.invalidateQueries({
        queryKey: communityKeys.thread(conversationId, lang),
      });
      // The inbox ordering and both badges are now stale.
      await queryClient.invalidateQueries({ queryKey: communityKeys.conversations(lang) });
      await queryClient.invalidateQueries({ queryKey: communityKeys.unread() });
    },
    onError: () => toast.error(t('messages.sendFailed')),
  });

  if (thread.isPending) return <Skeleton height={320} radius="var(--r-lg)" />;

  if (thread.isError) {
    // A thread you are not in is a 404, not a 403 (backend
    // messaging_service.require_participant) - so this is also what a
    // stranger guessing an id sees.
    return (
      <EmptyState
        title={t('messages.notFound')}
        description={t('messages.notFoundText')}
        action={
          <Link to="/messages" className="btn btn--primary btn--md">
            {t('messages.title')}
          </Link>
        }
      />
    );
  }

  const { conversation, messages } = thread.data;
  const others = conversation.participants.filter((p) => p.user_id !== user?.id);
  const name = others.map((p) => p.display_name).join(', ') || t('messages.unknownParty');
  const ordered: Message[] = [...messages].reverse();

  return (
    <section className="thread">
      <header className="thread__head">
        <Link
          to="/messages"
          className="btn btn--ghost btn--sm btn--icon"
          aria-label={t('common.back')}
        >
          <ArrowLeft size={16} aria-hidden="true" />
        </Link>
        <div style={{ minWidth: 0 }}>
          <h1 style={{ fontSize: '1.0625rem' }}>{name}</h1>
          {conversation.subject && (
            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              {t(`messages.about.${conversation.type}`, { subject: conversation.subject })}
            </p>
          )}
        </div>
      </header>

      <div className="thread__messages">
        {ordered.length === 0 && (
          <p className="muted" style={{ textAlign: 'center', padding: '2rem 0' }}>
            {t('messages.threadEmpty')}
          </p>
        )}

        {ordered.map((message) => {
          const mine = message.sender_id === user?.id;
          return (
            <article
              key={message.id}
              className={`bubble ${mine ? 'bubble--mine' : 'bubble--theirs'}`}
            >
              <p className="bubble__body">
                {message.is_deleted ? (
                  <em className="muted">{t('messages.deleted')}</em>
                ) : (
                  message.body
                )}
              </p>
              <time className="bubble__time" dateTime={message.created_at}>
                {formatDate(message.created_at, lang)}
              </time>
            </article>
          );
        })}
        <div ref={endRef} />
      </div>

      {thread.data.next_before_id !== null && (
        <p className="subtle" style={{ textAlign: 'center', fontSize: '0.75rem' }}>
          {t('messages.olderHidden')}
        </p>
      )}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          const text = body.trim();
          if (text) send.mutate(text);
        }}
      >
        <label className="sr-only" htmlFor="composer-body">
          {t('messages.write')}
        </label>
        <textarea
          id="composer-body"
          className="input input--area composer__input"
          rows={2}
          value={body}
          maxLength={MAX_BODY}
          placeholder={t('messages.writePlaceholder')}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            // Enter sends, Shift+Enter breaks the line. The convention every
            // chat uses, and the reason the field is a textarea at all.
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              const text = body.trim();
              if (text) send.mutate(text);
            }
          }}
        />
        <Button
          variant="primary"
          type="submit"
          icon
          aria-label={t('messages.send')}
          disabled={send.isPending || body.trim() === ''}
        >
          {send.isPending ? (
            <Loader2 size={16} className="spin" aria-hidden="true" />
          ) : (
            <Send size={16} aria-hidden="true" />
          )}
        </Button>
      </form>
    </section>
  );
}
