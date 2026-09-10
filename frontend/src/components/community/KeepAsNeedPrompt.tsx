import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HandHeart } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { communityKeys, needsApi } from '@/lib/api/community';
import { useT } from '@/lib/i18n';
import { toast } from '@/stores/toastStore';

/**
 * "Bu əşyanı ala bilmədiniz. [Ehtiyac kimi saxla] [Bağla]"
 * (FreeShop_Prompt 5, Rule C).
 *
 * THE CONSENT STEP. Somebody else got the ladder; the demand is still real,
 * but publishing it is this person's decision, not the platform's. Nothing
 * is created until they press the button.
 *
 * "Bağla" dismisses it for this session only, and deliberately does not
 * write anything server-side: a permanent "no thanks" flag would be a column
 * and a migration to remember an answer that costs nothing to ask again next
 * time they visit. Converting a request removes it from the list for good,
 * because the server stops returning lines that already became a need.
 */
export function KeepAsNeedPrompt({
  dismissed,
  onDismiss,
}: {
  dismissed: number[];
  onDismiss: (itemId: number) => void;
}) {
  const { t, lang } = useT();
  const queryClient = useQueryClient();

  const items = useQuery({
    queryKey: communityKeys.convertible(),
    queryFn: ({ signal }) => needsApi.convertible(signal),
  });

  const convert = useMutation({
    mutationFn: (itemId: number) => needsApi.fromRequestItem(itemId),
    onSuccess: async () => {
      toast.success(t('convert.saved'));
      await queryClient.invalidateQueries({ queryKey: communityKeys.convertible() });
      await queryClient.invalidateQueries({ queryKey: communityKeys.myNeeds(lang) });
    },
    onError: () => toast.error(t('convert.failed')),
  });

  const pending = (items.data ?? []).filter((item) => !dismissed.includes(item.request_item_id));
  if (pending.length === 0) return null;

  return (
    <section className="convert-prompts" aria-label={t('convert.title')}>
      {pending.map((item) => (
        <article key={item.request_item_id} className="card convert-prompt">
          <span className="need-card__icon" aria-hidden="true">
            <HandHeart size={16} />
          </span>

          <div style={{ minWidth: 0, display: 'grid', gap: '0.25rem' }}>
            <p style={{ fontWeight: 500 }}>{t('convert.missedOut', { title: item.title })}</p>
            <p className="muted" style={{ fontSize: '0.8125rem' }}>
              {t('convert.explain')}
            </p>
          </div>

          <div className="row-actions">
            <Button
              size="sm"
              variant="primary"
              disabled={convert.isPending}
              onClick={() => convert.mutate(item.request_item_id)}
            >
              {t('convert.keep')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDismiss(item.request_item_id)}>
              {t('convert.dismiss')}
            </Button>
          </div>
        </article>
      ))}
    </section>
  );
}
