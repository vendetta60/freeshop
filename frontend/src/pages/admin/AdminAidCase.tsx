import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SelectField, TextField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminCommunityApi, adminCommunityKeys } from '@/lib/api/admin';
import type { CaseStatus, CommitmentStatus, ItemPriority } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

/**
 * Which status buttons a case gets, mirroring the server's
 * `CASE_TRANSITIONS` (app/services/emergency_service.py). There is no path
 * back to `draft`: a case the community has already seen cannot be un-seen.
 */
const NEXT: Record<CaseStatus, CaseStatus[]> = {
  draft: ['active', 'cancelled'],
  active: ['paused', 'completed', 'cancelled'],
  paused: ['active', 'completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

const COMMITMENT_NEXT: Record<CommitmentStatus, CommitmentStatus[]> = {
  offered: ['accepted', 'cancelled'],
  accepted: ['received', 'cancelled'],
  received: [],
  cancelled: [],
};

/**
 * One aid case: publish it, manage the list of needed items, and work
 * through the offers the community has made (FreeShop_Prompt 11).
 *
 * Marking an offer `received` is what moves the public progress figure. It
 * lives here, on the administrator's page, because it is a statement that
 * the thing physically arrived - a donor confirming their own delivery would
 * turn the public page into a wish list.
 */
export default function AdminAidCase() {
  const { id } = useParams<{ id: string }>();
  const caseId = Number(id);
  const { t, lang } = useT();
  const queryClient = useQueryClient();

  const [itemTitle, setItemTitle] = useState('');
  const [itemQty, setItemQty] = useState('1');
  const [itemPriority, setItemPriority] = useState<ItemPriority>('normal');

  const aidCase = useQuery({
    queryKey: adminCommunityKeys.aidCase(caseId),
    queryFn: ({ signal }) => adminCommunityApi.aidCase(caseId, signal),
    enabled: Number.isFinite(caseId),
  });

  const commitments = useQuery({
    queryKey: adminCommunityKeys.commitments(caseId),
    queryFn: ({ signal }) => adminCommunityApi.commitments(caseId, signal),
    enabled: Number.isFinite(caseId),
  });

  useDocumentTitle(aidCase.data?.title ?? t('admin.aid.title'));

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: adminCommunityKeys.aidCase(caseId) });
    await queryClient.invalidateQueries({ queryKey: adminCommunityKeys.commitments(caseId) });
    await queryClient.invalidateQueries({ queryKey: adminCommunityKeys.aidCases() });
    // The public aid pages changed too.
    await queryClient.invalidateQueries({ queryKey: ['aid'] });
  };

  const setStatus = useMutation({
    mutationFn: (status: CaseStatus) => adminCommunityApi.setCaseStatus(caseId, status),
    onSuccess: refresh,
    onError: () => toast.error(t('admin.aid.statusFailed')),
  });

  const addItem = useMutation({
    mutationFn: () =>
      adminCommunityApi.addItem(caseId, {
        title_az: itemTitle.trim(),
        quantity_needed: Number(itemQty) || 1,
        priority: itemPriority,
      }),
    onSuccess: async () => {
      setItemTitle('');
      setItemQty('1');
      await refresh();
    },
    onError: () => toast.error(t('admin.aid.itemFailed')),
  });

  const removeItem = useMutation({
    mutationFn: (itemId: number) => adminCommunityApi.deleteItem(itemId),
    onSuccess: refresh,
    onError: () => toast.error(t('admin.aid.itemFailed')),
  });

  const setCommitment = useMutation({
    mutationFn: ({ id: commitmentId, status }: { id: number; status: CommitmentStatus }) =>
      adminCommunityApi.setCommitmentStatus(commitmentId, status),
    onSuccess: refresh,
    onError: () => toast.error(t('admin.aid.commitmentFailed')),
  });

  if (aidCase.isPending) return <Skeleton height={320} radius="var(--r-lg)" />;
  if (aidCase.isError) return <ErrorState onRetry={() => void aidCase.refetch()} />;

  const item = aidCase.data;

  return (
    <section style={{ display: 'grid', gap: '1.25rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{item.title}</h1>
        <Link to="/admin/aid" className="btn btn--ghost btn--sm">
          {t('common.back')}
        </Link>
      </header>

      <div className="card admin__form">
        <div className="listing-row__head">
          <Badge tone={item.status === 'active' ? 'accent' : 'neutral'}>
            {t(`aid.status.${item.status}`)}
          </Badge>
          <PlaceLine location={item.location} showDistance={false} />
        </div>

        {item.description_az && <p className="muted">{item.description_az}</p>}

        {/* Admin-only, and labelled as such on screen so nobody writes
            something here believing the family will read it. */}
        {item.verification_note_internal && (
          <div className="internal-note">
            <span className="internal-note__label">{t('admin.aid.verification')}</span>
            <p>{item.verification_note_internal}</p>
          </div>
        )}

        <div className="row-actions">
          {NEXT[item.status].map((status) => (
            <Button
              key={status}
              size="sm"
              variant={status === 'active' ? 'primary' : 'secondary'}
              disabled={setStatus.isPending}
              onClick={() => setStatus.mutate(status)}
            >
              {t(`admin.aid.action.${status}`)}
            </Button>
          ))}
        </div>
      </div>

      <section aria-labelledby="items" className="card admin__form">
        <h2 id="items" style={{ fontSize: '1rem' }}>
          {t('aid.needed')}
        </h2>

        <ul className="aid-list">
          {item.items.map((row) => (
            <li key={row.id} className="aid-item">
              <div style={{ minWidth: 0, display: 'grid', gap: '0.15rem' }}>
                <span className="aid-item__title">
                  {row.title}
                  {row.priority === 'urgent' && (
                    <Badge tone="danger">{t('aid.priority.urgent')}</Badge>
                  )}
                </span>
                <span className="subtle tabular" style={{ fontSize: '0.8125rem' }}>
                  {t('aid.itemCounts', {
                    needed: row.quantity_needed,
                    committed: row.quantity_committed,
                    received: row.quantity_received,
                  })}
                </span>
              </div>
              <Button
                size="sm"
                variant="ghost"
                icon
                aria-label={t('admin.aid.removeItem')}
                disabled={removeItem.isPending}
                onClick={() => removeItem.mutate(row.id)}
              >
                <Trash2 size={14} aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>

        <form
          className="form-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (itemTitle.trim()) addItem.mutate();
          }}
        >
          <TextField
            label={t('admin.aid.itemTitle')}
            value={itemTitle}
            maxLength={200}
            onChange={(e) => setItemTitle(e.target.value)}
          />
          <TextField
            label={t('aid.quantity')}
            type="number"
            min={1}
            max={999}
            value={itemQty}
            onChange={(e) => setItemQty(e.target.value)}
          />
          <SelectField
            label={t('admin.aid.priority')}
            value={itemPriority}
            onChange={(e) => setItemPriority(e.target.value as ItemPriority)}
          >
            <option value="urgent">{t('aid.priority.urgent')}</option>
            <option value="normal">{t('aid.priority.normal')}</option>
            <option value="low">{t('aid.priority.low')}</option>
          </SelectField>
          <Button variant="primary" type="submit" disabled={addItem.isPending}>
            {addItem.isPending ? (
              <Loader2 size={15} className="spin" aria-hidden="true" />
            ) : (
              <Plus size={15} aria-hidden="true" />
            )}
            {t('admin.aid.addItem')}
          </Button>
        </form>
      </section>

      <section aria-labelledby="offers" style={{ display: 'grid', gap: '0.75rem' }}>
        <h2 id="offers" style={{ fontSize: '1rem' }}>
          {t('admin.aid.offers')}
        </h2>

        {commitments.data?.length === 0 && (
          <EmptyState title={t('admin.aid.noOffers')} description={t('admin.aid.noOffersText')} />
        )}

        {(commitments.data ?? []).map((commitment) => (
          <article key={commitment.id} className="card listing-row listing-row--need">
            <div style={{ minWidth: 0, display: 'grid', gap: '0.25rem' }}>
              <div className="listing-row__head">
                <span style={{ fontWeight: 500 }}>{commitment.item_title}</span>
                <Badge tone="neutral">{t(`aid.commitment.${commitment.status}`)}</Badge>
              </div>
              <p className="subtle" style={{ fontSize: '0.8125rem' }}>
                {commitment.user_label} · {t('aid.quantityOf', { count: commitment.quantity })} ·{' '}
                {formatDate(commitment.created_at, lang)}
              </p>
              {commitment.note && <p className="listing-row__note">{commitment.note}</p>}
            </div>

            <div className="row-actions">
              {COMMITMENT_NEXT[commitment.status].map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant={status === 'received' ? 'primary' : 'secondary'}
                  disabled={setCommitment.isPending}
                  onClick={() => setCommitment.mutate({ id: commitment.id, status })}
                >
                  {t(`admin.aid.commitmentAction.${status}`)}
                </Button>
              ))}
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}
