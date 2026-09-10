import { useQuery } from '@tanstack/react-query';
import { LifeBuoy } from 'lucide-react';
import { Link } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { aidApi, communityKeys, type AidCase } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';

/**
 * "Təcili yardım" - admin-verified community aid (FreeShop_Prompt 8).
 *
 * Progress is shown as "3 of 7 items covered" and nothing more. No progress
 * bar racing to 100%, no urgency counter, no "only 2 left!" - the prompt
 * asks for progress without manipulative gamification, and this is community
 * aid rather than a fundraising campaign.
 */
export function AidCaseCard({ aidCase }: { aidCase: AidCase }) {
  const { t } = useT();

  return (
    <Link to={`/aid/${aidCase.slug}`} className="card aid-card">
      <span className="aid-card__icon" aria-hidden="true">
        <LifeBuoy size={18} />
      </span>

      <div style={{ minWidth: 0, display: 'grid', gap: '0.35rem' }}>
        <div className="need-card__head">
          <h3 className="need-card__title">{aidCase.title}</h3>
          {aidCase.status === 'paused' && <Badge tone="neutral">{t('aid.status.paused')}</Badge>}
          {aidCase.status === 'completed' && (
            <Badge tone="success">{t('aid.status.completed')}</Badge>
          )}
        </div>

        {aidCase.beneficiary_display_name && (
          <p className="subtle" style={{ fontSize: '0.8125rem' }}>
            {aidCase.beneficiary_display_name}
          </p>
        )}

        <div className="need-card__meta">
          <PlaceLine location={aidCase.location} />
          <span className="subtle tabular">
            {t('aid.progress', {
              done: aidCase.items_satisfied,
              total: aidCase.items_total,
            })}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function AidPage() {
  const { t, lang } = useT();
  useDocumentTitle(t('aid.title'));

  const cases = useQuery({
    queryKey: communityKeys.aidCases(lang, false),
    queryFn: ({ signal }) => aidApi.cases(lang, false, signal),
  });

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1.25rem' }}>
        <h1>{t('aid.title')}</h1>
        <p>{t('aid.lead')}</p>
      </div>

      {cases.isError && <ErrorState onRetry={() => void cases.refetch()} />}

      {cases.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 2 }, (_, i) => (
            <Skeleton key={i} height={96} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {cases.data?.length === 0 && (
        <EmptyState
          title={t('aid.empty')}
          description={t('aid.emptyText')}
          icon={<LifeBuoy size={22} />}
        />
      )}

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {(cases.data ?? []).map((item) => (
          <AidCaseCard key={item.id} aidCase={item} />
        ))}
      </div>
    </>
  );
}
