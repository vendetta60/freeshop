import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Users } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { listingApi, listingKeys } from '@/lib/api/catalogue';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

/**
 * "Kim aldı?" - the giver chooses one of the people who asked
 * (FreeShop_Prompt 5, Rule C).
 *
 * This is the ONLY screen in the application that names the people who
 * requested a listing, and it is shown only to that listing's owner - the
 * server returns 404 to anybody else. Everywhere else the same fact is a
 * count (Rule F).
 *
 * What happens to the others is the point of the whole feature: they are
 * marked `not_selected`, NOT deleted, which is what makes their request
 * eligible to become visible local demand if they consent. The consent
 * itself belongs to them, so this panel does not create anything on their
 * behalf - it only tells the giver that the offer will be made.
 */
export function HandoverPanel({
  productId,
  openRequestCount,
}: {
  productId: number;
  openRequestCount: number;
}) {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const requesters = useQuery({
    queryKey: listingKeys.requesters(productId),
    queryFn: ({ signal }) => listingApi.requesters(productId, signal),
    enabled: open,
  });

  const handover = useMutation({
    mutationFn: (requestItemId: number) => listingApi.handover(productId, requestItemId),
    onSuccess: async (notSelected) => {
      toast.success(
        notSelected.length > 0
          ? t('handover.doneWithOthers', { count: notSelected.length })
          : t('handover.done'),
      );
      await queryClient.invalidateQueries({ queryKey: listingKeys.mine(lang) });
      await queryClient.invalidateQueries({ queryKey: listingKeys.requesters(productId) });
      setOpen(false);
    },
    onError: () => toast.error(t('handover.failed')),
  });

  if (openRequestCount === 0) return null;

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Users size={14} aria-hidden="true" />
        {t('handover.choose', { count: openRequestCount })}
      </Button>
    );
  }

  return (
    <div className="handover">
      <div className="section-head">
        <h3 style={{ fontSize: '0.9375rem' }}>{t('handover.title')}</h3>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          {t('common.cancel')}
        </Button>
      </div>

      <p className="muted" style={{ fontSize: '0.8125rem' }}>
        {t('handover.explain')}
      </p>

      {requesters.isPending && <Skeleton height={64} radius="var(--r-md)" />}

      <ul className="handover__list">
        {(requesters.data ?? []).map((person) => (
          <li key={person.request_item_id} className="handover__row">
            <div style={{ minWidth: 0, display: 'grid', gap: '0.15rem' }}>
              <span style={{ fontWeight: 500 }}>{person.display_name}</span>
              <span className="subtle" style={{ fontSize: '0.75rem' }}>
                {person.request_no} · {formatDate(person.requested_at, lang)}
              </span>
              {person.note && <p className="listing-row__note">{person.note}</p>}
            </div>
            <Button
              size="sm"
              variant="primary"
              disabled={handover.isPending}
              onClick={() => handover.mutate(person.request_item_id)}
            >
              {handover.isPending && <Loader2 size={13} className="spin" aria-hidden="true" />}
              {t('handover.giveToThis')}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
