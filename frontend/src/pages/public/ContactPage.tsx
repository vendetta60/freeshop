import { useQuery } from '@tanstack/react-query';
import { Clock, Mail, MapPin, MessageCircle, Phone, Send } from 'lucide-react';

import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { siteText } from '@/lib/site/config';

/**
 * Contact page (plan.md 4.4).
 *
 * Values come from the settings table so the admin changes them without a
 * deploy (plan.md 7.3). They are placeholders until W5 is filled in.
 */
export default function ContactPage() {
  const { t, lang } = useT();
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: catalogueKeys.contact(lang),
    queryFn: ({ signal }) => catalogueApi.contact(lang, signal),
    staleTime: 5 * 60_000,
  });

  useDocumentTitle(t('contact.title'));
  const channels = data
    ? [
        {
          Icon: Phone,
          label: t('contact.phone'),
          value: data.phone,
          href: `tel:${data.phone.replace(/\s/g, '')}`,
        },
        {
          Icon: MessageCircle,
          label: t('contact.whatsapp'),
          value: data.phone,
          href: `https://wa.me/${data.whatsapp}`,
        },
        {
          Icon: Send,
          label: t('contact.telegram'),
          value: data.telegram,
          href: `https://t.me/${data.telegram.replace('@', '')}`,
        },
        { Icon: Mail, label: t('contact.email'), value: data.email, href: `mailto:${data.email}` },
      ]
    : [];

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1.5rem' }}>
        <h1>{t('contact.title')}</h1>
        <p>{siteText('contact_intro', lang, t('contact.lead'))}</p>
      </div>

      {/* Without this branch a failed fetch renders an empty grid, which
          reads as "this shop has no contact details" - the worst possible
          message on the page whose entire purpose is contact. */}
      {isError && (
        <ErrorState
          title={t('contact.loadFailed')}
          description={t('contact.loadFailedText')}
          onRetry={() => void refetch()}
        />
      )}

      <div className="contact-grid">
        {isPending
          ? Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} height={70} radius="var(--r-lg)" />
            ))
          : channels.map(({ Icon, label, value, href }) => (
              <a key={label} href={href} className="card contact-card">
                <span className="contact-card__icon">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <span>
                  <span className="subtle" style={{ display: 'block', fontSize: '0.75rem' }}>
                    {label}
                  </span>
                  <span style={{ fontWeight: 500 }}>{value}</span>
                </span>
              </a>
            ))}
      </div>

      {data && (
        <div
          className="card"
          style={{ padding: '1.25rem', marginTop: '1rem', display: 'grid', gap: '0.75rem' }}
        >
          <p style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <MapPin size={16} aria-hidden="true" className="subtle" />
            {data.address}
          </p>
          <p style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={16} aria-hidden="true" className="subtle" />
            {data.working_hours}
          </p>
          <p className="subtle" style={{ fontSize: '0.8125rem' }}>
            {t('contact.noPayments')}
          </p>
        </div>
      )}
    </>
  );
}
