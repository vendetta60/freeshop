import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LifeBuoy, Loader2, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { LocationPicker } from '@/components/community/LocationPicker';
import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { TextAreaField, TextField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminCommunityApi, adminCommunityKeys } from '@/lib/api/admin';
import type { CaseStatus } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

const TONE: Record<CaseStatus, 'neutral' | 'accent' | 'success' | 'warning'> = {
  draft: 'neutral',
  active: 'accent',
  paused: 'warning',
  completed: 'success',
  cancelled: 'neutral',
};

/**
 * Aid cases: the list, and the form that creates one (Rule E).
 *
 * A new case is a DRAFT. Publishing is a second, separate press on the case's
 * own page - the first thing typed into a form about a house fire should not
 * be the thing the whole town reads.
 */
export default function AdminAid() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [beneficiary, setBeneficiary] = useState('');
  const [verification, setVerification] = useState('');
  const [place, setPlace] = useState({ city: '', district: '' });

  useDocumentTitle(t('admin.aid.title'));

  const cases = useQuery({
    queryKey: adminCommunityKeys.aidCases(),
    queryFn: ({ signal }) => adminCommunityApi.aidCases(signal),
  });

  const create = useMutation({
    mutationFn: () =>
      adminCommunityApi.createCase({
        title_az: title.trim(),
        description_az: description.trim(),
        beneficiary_display_name: beneficiary.trim() || null,
        verification_note_internal: verification.trim() || null,
        city: place.city || null,
        district: place.district || null,
      }),
    onSuccess: async () => {
      setCreating(false);
      setTitle('');
      setDescription('');
      setBeneficiary('');
      setVerification('');
      await queryClient.invalidateQueries({ queryKey: adminCommunityKeys.aidCases() });
      toast.success(t('admin.aid.created'));
    },
    onError: () => toast.error(t('admin.aid.createFailed')),
  });

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.aid.title')}</h1>
        <Button size="sm" variant="primary" onClick={() => setCreating((open) => !open)}>
          <Plus size={15} aria-hidden="true" />
          {t('admin.aid.new')}
        </Button>
      </header>
      <p className="muted" style={{ fontSize: '0.875rem', marginTop: '-0.5rem' }}>
        {t('admin.aid.lead')}
      </p>

      {creating && (
        <form
          className="card admin__form"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim().length >= 2) create.mutate();
          }}
        >
          <TextField
            label={t('admin.aid.caseTitle')}
            required
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
          />
          <TextAreaField
            label={t('admin.aid.description')}
            rows={4}
            value={description}
            maxLength={8000}
            onChange={(e) => setDescription(e.target.value)}
          />
          <TextField
            label={t('admin.aid.beneficiary')}
            hint={t('admin.aid.beneficiaryHint')}
            value={beneficiary}
            maxLength={120}
            onChange={(e) => setBeneficiary(e.target.value)}
          />
          <LocationPicker city={place.city} district={place.district} onChange={setPlace} />

          {/* The one admin-only field in the application. The public DTO does
              not carry it at all, so it cannot leak through a serializer
              mistake (backend app/schemas/emergency.py). */}
          <TextAreaField
            label={t('admin.aid.verification')}
            hint={t('admin.aid.verificationHint')}
            rows={3}
            value={verification}
            maxLength={4000}
            onChange={(e) => setVerification(e.target.value)}
          />

          <Button variant="primary" type="submit" disabled={create.isPending}>
            {create.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
            {t('admin.aid.createDraft')}
          </Button>
        </form>
      )}

      {cases.isError && <ErrorState onRetry={() => void cases.refetch()} />}
      {cases.isPending && <Skeleton height={96} radius="var(--r-lg)" />}

      {cases.data?.length === 0 && (
        <EmptyState
          title={t('admin.aid.empty')}
          description={t('admin.aid.emptyText')}
          icon={<LifeBuoy size={22} />}
        />
      )}

      {(cases.data ?? []).map((item) => (
        <article key={item.id} className="card listing-row listing-row--need">
          <div style={{ minWidth: 0, display: 'grid', gap: '0.3rem' }}>
            <div className="listing-row__head">
              <Link to={`/admin/aid/${item.id}`} style={{ fontWeight: 500 }}>
                {item.title}
              </Link>
              <Badge tone={TONE[item.status]}>{t(`aid.status.${item.status}`)}</Badge>
            </div>
            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              <PlaceLine location={item.location} showDistance={false} />
              {' · '}
              {t('aid.progress', { done: item.items_satisfied, total: item.items_total })}
              {' · '}
              {formatDate(item.created_at, lang)}
            </p>
          </div>
        </article>
      ))}
    </section>
  );
}
