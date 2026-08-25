import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { CheckboxField, SelectField, TextAreaField, TextField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys, type SiteSettings } from '@/lib/api/admin';
import { ApiError } from '@/lib/api/client';
import { useT } from '@/lib/i18n';
import { toast } from '@/stores/toastStore';

type TextKey = { key: string; labelKey: string; area?: boolean; hintKey?: string };

const CONTACT: TextKey[] = [
  { key: 'contact_phone', labelKey: 'admin.settings.phone' },
  { key: 'whatsapp', labelKey: 'admin.settings.whatsapp', hintKey: 'admin.settings.whatsappHint' },
  { key: 'telegram', labelKey: 'admin.settings.telegram' },
  { key: 'email', labelKey: 'admin.settings.email' },
  { key: 'address_az', labelKey: 'admin.settings.addressAz' },
  { key: 'address_en', labelKey: 'admin.settings.addressEn' },
  { key: 'working_hours_az', labelKey: 'admin.settings.hoursAz' },
  { key: 'working_hours_en', labelKey: 'admin.settings.hoursEn' },
];

const CONTENT: TextKey[] = [
  { key: 'hero_title_az', labelKey: 'admin.settings.heroTitleAz' },
  { key: 'hero_title_en', labelKey: 'admin.settings.heroTitleEn' },
  { key: 'hero_subtitle_az', labelKey: 'admin.settings.heroSubtitleAz', area: true },
  { key: 'hero_subtitle_en', labelKey: 'admin.settings.heroSubtitleEn', area: true },
  { key: 'about_az', labelKey: 'admin.settings.aboutAz', area: true },
  { key: 'about_en', labelKey: 'admin.settings.aboutEn', area: true },
  { key: 'contact_intro_az', labelKey: 'admin.settings.introAz', area: true },
  { key: 'contact_intro_en', labelKey: 'admin.settings.introEn', area: true },
  { key: 'footer_note_az', labelKey: 'admin.settings.footerAz' },
  { key: 'footer_note_en', labelKey: 'admin.settings.footerEn' },
];

function asText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

/**
 * Site settings: contacts, appearance, language and every static page string
 * (plan.md 7.3).
 *
 * Only CHANGED keys are sent. A blanket PATCH of the whole map would rewrite
 * every row on every save, so two admins editing different sections would
 * overwrite each other with values neither of them touched.
 */
export default function AdminSettings() {
  const { t } = useT();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<SiteSettings>({});
  // The last saved snapshot, kept in state rather than a ref: it is compared
  // against `values` during render to decide what is dirty, and a ref read
  // during render would not re-render when it changes.
  const [original, setOriginal] = useState<SiteSettings>({});

  const settings = useQuery({
    queryKey: adminKeys.settings(),
    queryFn: ({ signal }) => adminApi.settings(signal),
  });

  const loaded = useRef(false);
  useEffect(() => {
    if (!settings.data || loaded.current) return;
    loaded.current = true;
    setOriginal(settings.data);
    setValues(settings.data);
  }, [settings.data]);

  const changed = Object.keys(values).filter(
    (key) => JSON.stringify(values[key]) !== JSON.stringify(original[key]),
  );

  const save = useMutation({
    mutationFn: () =>
      adminApi.saveSettings(Object.fromEntries(changed.map((key) => [key, values[key]]))),
    onSuccess: async (saved) => {
      setOriginal(saved);
      setValues(saved);
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      // The public site reads the same values, so its caches are stale now.
      await queryClient.invalidateQueries({ queryKey: ['contact'] });
      toast.success(t('admin.settings.saved'));
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : t('admin.settings.saveFailed')),
  });

  if (settings.isError) return <ErrorState onRetry={() => void settings.refetch()} />;
  if (settings.isPending) return <Skeleton height={480} radius="var(--r-lg)" />;

  const set = (key: string, value: unknown) =>
    setValues((current) => ({ ...current, [key]: value }));

  const socials = (values.socials ?? {}) as Record<string, string>;
  const enabledLangs = Array.isArray(values.enabled_langs)
    ? (values.enabled_langs as string[])
    : ['az'];

  const renderText = (item: TextKey) =>
    item.area ? (
      <TextAreaField
        key={item.key}
        label={t(item.labelKey)}
        rows={3}
        value={asText(values[item.key])}
        hint={item.hintKey ? t(item.hintKey) : undefined}
        onChange={(e) => set(item.key, e.target.value)}
      />
    ) : (
      <TextField
        key={item.key}
        label={t(item.labelKey)}
        value={asText(values[item.key])}
        hint={item.hintKey ? t(item.hintKey) : undefined}
        onChange={(e) => set(item.key, e.target.value)}
      />
    );

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.settings')}</h1>
        <Button
          variant="primary"
          size="sm"
          disabled={changed.length === 0 || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {changed.length > 0 ? t('common.saveCount', { count: changed.length }) : t('common.save')}
        </Button>
      </header>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('admin.settings.contact')}</h2>
        <div className="form-row">{CONTACT.map(renderText)}</div>
        <div className="form-row">
          <TextField
            label={t('admin.settings.instagram')}
            value={socials.instagram ?? ''}
            onChange={(e) => set('socials', { ...socials, instagram: e.target.value })}
          />
          <TextField
            label={t('admin.settings.facebook')}
            value={socials.facebook ?? ''}
            onChange={(e) => set('socials', { ...socials, facebook: e.target.value })}
          />
        </div>
      </div>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('admin.settings.appearance')}</h2>
        <p className="muted" style={{ fontSize: '0.8125rem' }}>
          {t('admin.settings.appearanceHint')}
        </p>
        <div className="form-row">
          <SelectField
            label={t('admin.settings.accent')}
            value={asText(values.accent) || 'azure'}
            onChange={(e) => set('accent', e.target.value)}
          >
            <option value="azure">{t('admin.settings.accentAzure')}</option>
            <option value="bronze">{t('admin.settings.accentBronze')}</option>
          </SelectField>
          <SelectField
            label={t('admin.settings.theme')}
            value={asText(values.default_theme) || 'system'}
            onChange={(e) => set('default_theme', e.target.value)}
          >
            <option value="system">{t('admin.settings.themeSystem')}</option>
            <option value="light">{t('admin.settings.themeLight')}</option>
            <option value="dark">{t('admin.settings.themeDark')}</option>
          </SelectField>
        </div>
      </div>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('admin.settings.language')}</h2>
        <div className="form-row">
          <SelectField
            label={t('admin.settings.defaultLang')}
            value={asText(values.default_lang) || 'az'}
            onChange={(e) => set('default_lang', e.target.value)}
          >
            <option value="az">{t('admin.settings.langAz')}</option>
            <option value="en">{t('admin.settings.langEn')}</option>
          </SelectField>
        </div>
        <fieldset className="fieldset">
          <legend className="field__label">{t('admin.settings.enabledLangs')}</legend>
          {(['az', 'en'] as const).map((code) => (
            <CheckboxField
              key={code}
              label={t(code === 'az' ? 'admin.settings.langAz' : 'admin.settings.langEn')}
              checked={enabledLangs.includes(code)}
              // AZ is the fallback for every untranslated field, so turning it
              // off would leave nothing to fall back to (plan.md 7.3).
              disabled={code === 'az'}
              onChange={(e) =>
                set(
                  'enabled_langs',
                  e.target.checked
                    ? [...new Set([...enabledLangs, code])]
                    : enabledLangs.filter((lang) => lang !== code),
                )
              }
            />
          ))}
        </fieldset>
      </div>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('admin.settings.content')}</h2>
        <p className="muted" style={{ fontSize: '0.8125rem' }}>
          {t('admin.settings.contentHint')}
        </p>
        <div className="form-row">{CONTENT.map(renderText)}</div>
      </div>
    </section>
  );
}
