import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Circle, LifeBuoy, Loader2, MessageCircle } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { aidApi, communityKeys, messagesApi, type AidItem } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * One aid case and its shopping list (FreeShop_Prompt 8).
 *
 * The internal verification note is not on this page because it is not in
 * the response: the public DTO does not carry the field at all
 * (backend app/schemas/emergency.py). That is a stronger guarantee than a
 * component remembering not to render something.
 *
 * "Kömək edə bilərəm" creates a COMMITMENT, not a delivery. The tick appears
 * when an administrator confirms the thing arrived - claiming it on a click
 * would tell the next visitor the family already has blankets that are still
 * in a stranger's hallway.
 */
function ItemRow({
  item,
  onOffer,
  pending,
  canOffer,
}: {
  item: AidItem;
  onOffer: (item: AidItem, quantity: number) => void;
  pending: boolean;
  canOffer: boolean;
}) {
  const { t } = useT();
  const [quantity, setQuantity] = useState(1);
  const remaining = Math.max(item.quantity_needed - item.quantity_committed, 0);

  return (
    <li className="aid-item">
      <span className="aid-item__mark" aria-hidden="true">
        {item.is_satisfied ? <Check size={15} /> : <Circle size={15} />}
      </span>

      <div style={{ minWidth: 0, display: 'grid', gap: '0.2rem' }}>
        <span className="aid-item__title">
          {item.title}
          {item.priority === 'urgent' && <Badge tone="danger">{t('aid.priority.urgent')}</Badge>}
        </span>

        <span className="subtle tabular" style={{ fontSize: '0.8125rem' }}>
          {t('aid.itemCounts', {
            needed: item.quantity_needed,
            committed: item.quantity_committed,
            received: item.quantity_received,
          })}
        </span>

        {item.notes && (
          <span className="muted" style={{ fontSize: '0.8125rem' }}>
            {item.notes}
          </span>
        )}
      </div>

      {canOffer && remaining > 0 && (
        <div className="aid-item__offer">
          <label className="sr-only" htmlFor={`qty-${item.id}`}>
            {t('aid.quantity')}
          </label>
          <input
            id={`qty-${item.id}`}
            className="input aid-item__qty"
            type="number"
            min={1}
            max={Math.max(remaining, 1)}
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Number(e.target.value) || 1))}
          />
          <Button size="sm" disabled={pending} onClick={() => onOffer(item, quantity)}>
            {t('aid.canHelp')}
          </Button>
        </div>
      )}
    </li>
  );
}

export default function AidDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { t, lang } = useT();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  const aidCase = useQuery({
    queryKey: communityKeys.aidCase(slug ?? '', lang),
    queryFn: ({ signal }) => aidApi.one(slug ?? '', lang, signal),
    enabled: Boolean(slug),
  });

  useDocumentTitle(aidCase.data?.title ?? t('aid.title'));

  const offer = useMutation({
    mutationFn: ({ item, quantity }: { item: AidItem; quantity: number }) =>
      aidApi.offer(item.id, { quantity }),
    onSuccess: async () => {
      toast.success(t('aid.offerSent'));
      await queryClient.invalidateQueries({
        queryKey: communityKeys.aidCase(slug ?? '', lang),
      });
      await queryClient.invalidateQueries({ queryKey: communityKeys.myCommitments(lang) });
      // Offering opens a thread with the administrator, server-side.
      await queryClient.invalidateQueries({ queryKey: communityKeys.conversations(lang) });
    },
    onError: () => toast.error(t('aid.offerFailed')),
  });

  const contact = useMutation({
    mutationFn: () => messagesApi.open('emergency', aidCase.data?.id ?? 0),
    onSuccess: (conversation) => {
      void navigate(`/messages/${conversation.id}`);
    },
    onError: () => toast.error(t('messages.openFailed')),
  });

  if (aidCase.isPending) return <Skeleton height={280} radius="var(--r-lg)" />;
  if (aidCase.isError) return <ErrorState onRetry={() => void aidCase.refetch()} />;

  const item = aidCase.data;

  return (
    <section style={{ display: 'grid', gap: '1.25rem' }}>
      <article className="card aid-detail">
        <div className="need-card__head">
          <span className="aid-card__icon" aria-hidden="true">
            <LifeBuoy size={20} />
          </span>
          <h1 style={{ fontSize: '1.375rem' }}>{item.title}</h1>
          {!item.accepts_offers && (
            <Badge tone={item.status === 'completed' ? 'success' : 'neutral'}>
              {t(`aid.status.${item.status}`)}
            </Badge>
          )}
        </div>

        {item.beneficiary_display_name && <p className="subtle">{item.beneficiary_display_name}</p>}

        <PlaceLine location={item.location} />

        {item.description && <p style={{ whiteSpace: 'pre-wrap' }}>{item.description}</p>}

        <div className="section-head" style={{ marginTop: '0.5rem' }}>
          <h2 style={{ fontSize: '1rem' }}>{t('aid.needed')}</h2>
          <span className="subtle tabular">
            {t('aid.progress', { done: item.items_satisfied, total: item.items_total })}
          </span>
        </div>

        <ul className="aid-list">
          {item.items.map((row) => (
            <ItemRow
              key={row.id}
              item={row}
              pending={offer.isPending}
              canOffer={Boolean(user) && item.accepts_offers}
              onOffer={(target, quantity) => offer.mutate({ item: target, quantity })}
            />
          ))}
        </ul>

        {!user && item.accepts_offers && (
          <Button variant="primary" onClick={openAuth}>
            {t('aid.signInToHelp')}
          </Button>
        )}

        {user && item.accepts_offers && (
          <Button variant="secondary" disabled={contact.isPending} onClick={() => contact.mutate()}>
            {contact.isPending ? (
              <Loader2 size={15} className="spin" aria-hidden="true" />
            ) : (
              <MessageCircle size={15} aria-hidden="true" />
            )}
            {t('aid.contactCoordinator')}
          </Button>
        )}
      </article>
    </section>
  );
}
