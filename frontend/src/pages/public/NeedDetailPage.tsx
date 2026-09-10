import { useMutation, useQuery } from '@tanstack/react-query';
import { HandHeart, Loader2, MessageCircle } from 'lucide-react';
import { useNavigate, useParams } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { ProductCard } from '@/components/product/ProductCard';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { communityKeys, messagesApi, needsApi } from '@/lib/api/community';
import { ApiError } from '@/lib/api/client';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * One need, and the listings that might answer it (FreeShop_Prompt 6).
 *
 * The person who posted it is not named anywhere on this page. "Kömək edə
 * bilərəm" opens a conversation, and the server works out who that reaches
 * from the need itself - the client never learns, or sends, a user id
 * (Rule F, backend messaging_service._counterpart).
 */
export default function NeedDetailPage() {
  const { id } = useParams<{ id: string }>();
  const needId = Number(id);
  const { t, lang } = useT();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const openAuth = useUiStore((s) => s.openAuth);

  const need = useQuery({
    queryKey: communityKeys.need(needId, lang),
    queryFn: ({ signal }) => needsApi.one(needId, lang, signal),
    enabled: Number.isFinite(needId),
  });

  const matches = useQuery({
    queryKey: communityKeys.needMatches(needId, lang),
    queryFn: ({ signal }) => needsApi.matchingListings(needId, lang, signal),
    enabled: Number.isFinite(needId) && need.isSuccess,
  });

  useDocumentTitle(need.data?.title ?? t('needs.title'));

  const startConversation = useMutation({
    mutationFn: () => messagesApi.open('need', needId),
    onSuccess: (conversation) => {
      void navigate(`/messages/${conversation.id}`);
    },
    onError: (error) => {
      // "own_need" is the common one and deserves its own sentence rather
      // than a generic failure - it is not an error the person can fix.
      if (error instanceof ApiError && error.details.reason === 'own_need') {
        toast.error(t('messages.ownNeed'));
        return;
      }
      toast.error(t('messages.openFailed'));
    },
  });

  if (need.isPending) {
    return <Skeleton height={220} radius="var(--r-lg)" />;
  }

  if (need.isError) {
    return <ErrorState onRetry={() => void need.refetch()} />;
  }

  const item = need.data;

  return (
    <section style={{ display: 'grid', gap: '1.5rem' }}>
      <article className="card need-detail">
        <span className="need-card__icon" aria-hidden="true">
          <HandHeart size={20} />
        </span>

        <div style={{ display: 'grid', gap: '0.6rem', minWidth: 0 }}>
          <div className="need-card__head">
            <h1 style={{ fontSize: '1.375rem' }}>{item.title}</h1>
            {item.quantity_needed > 1 && (
              <Badge tone="neutral">{t('needs.quantity', { count: item.quantity_needed })}</Badge>
            )}
            <Badge tone={item.status === 'open' ? 'accent' : 'warning'}>
              {t(`needs.status.${item.status}`)}
            </Badge>
          </div>

          {item.description && <p>{item.description}</p>}

          <div className="need-card__meta">
            <PlaceLine location={item.location} />
            {item.category_name && <span className="subtle">{item.category_name}</span>}
            <span className="subtle">{formatDate(item.created_at, lang)}</span>
          </div>

          <div className="row-actions">
            {user ? (
              <Button
                variant="primary"
                disabled={startConversation.isPending}
                onClick={() => startConversation.mutate()}
              >
                {startConversation.isPending ? (
                  <Loader2 size={15} className="spin" aria-hidden="true" />
                ) : (
                  <MessageCircle size={15} aria-hidden="true" />
                )}
                {t('needs.canHelp')}
              </Button>
            ) : (
              <Button variant="primary" onClick={openAuth}>
                {t('needs.signInToHelp')}
              </Button>
            )}
          </div>
        </div>
      </article>

      {/* Deterministic matching, not a recommendation engine: same category,
          shared words, within range (backend app/services/matching.py). */}
      <section aria-labelledby="matches">
        <div className="section-head">
          <h2 id="matches" style={{ fontSize: '1rem' }}>
            {t('needs.matchingListings')}
          </h2>
        </div>

        {matches.isPending && <Skeleton height={120} radius="var(--r-lg)" />}

        {matches.data?.length === 0 && (
          <EmptyState title={t('needs.noMatches')} description={t('needs.noMatchesText')} />
        )}

        {(matches.data?.length ?? 0) > 0 && (
          <div className="product-grid">
            {(matches.data ?? []).map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
