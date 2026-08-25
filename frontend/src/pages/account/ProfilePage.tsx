import { Loader2, ShieldCheck } from 'lucide-react';
import { useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { SelectField, TextField } from '@/components/ui/Field';
import { EmptyState } from '@/components/ui/States';
import { authApi, devApi } from '@/lib/api/auth';
import { ApiError, reasonOf } from '@/lib/api/client';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { initialsOf, useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * Profile: name, language, avatar and the phone verification flow.
 *
 * The phone section is the one that matters: publishing a product requires a
 * verified number (plan.md 9.3), and before this page existed the only way to
 * get one was to have signed in by OTP.
 */
export default function ProfilePage() {
  const { t } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const setUser = (next: NonNullable<typeof user>) => useAuthStore.setState({ user: next });

  const [name, setName] = useState(user?.full_name ?? '');
  const [lang, setLang] = useState(user?.preferred_lang ?? 'az');
  const [savingProfile, setSavingProfile] = useState(false);

  const [phone, setPhone] = useState(user?.phone ?? '');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'idle' | 'code'>('idle');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const avatarInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  useDocumentTitle(t('profile.title'));
  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('profile.signInTitle')}
        description={t('profile.signInText')}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const updated = await authApi.updateMe({ full_name: name.trim(), preferred_lang: lang });
      setUser(updated);
      toast.success(t('profile.saved'));
    } catch {
      toast.error(t('profile.saveFailed'));
    } finally {
      setSavingProfile(false);
    }
  };

  const phoneMessage = (err: unknown): string => {
    if (!(err instanceof ApiError)) return t('error.network');
    switch (err.code) {
      case 'OTP_INVALID':
        return t('error.otpInvalid');
      case 'OTP_EXPIRED':
        return t('error.otpExpired');
      case 'OTP_TOO_MANY_ATTEMPTS':
        return t('error.otpAttempts');
      case 'RATE_LIMITED':
        return t('error.rateLimited');
      case 'VALIDATION_ERROR':
        return reasonOf(err) === 'already_registered'
          ? t('error.phoneTaken')
          : t('error.phoneInvalid');
      default:
        return err.message;
    }
  };

  const sendCode = async () => {
    setBusy(true);
    setPhoneError(null);
    try {
      const sent = await authApi.sendPhoneOtp(phone);
      setStep('code');
      if (sent.dev_inbox) {
        const inbox = await devApi.otpInbox().catch(() => null);
        setDevCode(inbox?.items[0]?.code ?? null);
      }
    } catch (err) {
      setPhoneError(phoneMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setPhoneError(null);
    try {
      const updated = await authApi.verifyPhoneOtp(phone, code);
      setUser(updated);
      setStep('idle');
      setCode('');
      setDevCode(null);
      toast.success(t('profile.phoneConfirmed'));
    } catch (err) {
      setPhoneError(phoneMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const uploadAvatar = async (file: File) => {
    setUploading(true);
    try {
      setUser(await authApi.uploadAvatar(file));
      toast.success(t('profile.photoUpdated'));
    } catch (err) {
      toast.error(
        reasonOf(err) === 'too_large' ? t('admin.upload.tooLarge') : t('admin.upload.failed'),
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <section style={{ display: 'grid', gap: '1rem', maxWidth: '46rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('profile.title')}</h1>
      </header>

      <div className="card admin__form">
        <div className="profile-head">
          {user.avatar_url ? (
            <img
              className="avatar avatar--xl"
              src={user.avatar_url}
              alt=""
              width={64}
              height={64}
            />
          ) : (
            <span className="avatar avatar--xl" aria-hidden="true">
              {initialsOf(user)}
            </span>
          )}
          <div>
            <Button
              variant="secondary"
              size="sm"
              disabled={uploading}
              onClick={() => avatarInput.current?.click()}
            >
              {uploading && <Loader2 size={15} className="spin" aria-hidden="true" />}
              {t('profile.changePhoto')}
            </Button>
            <p className="muted" style={{ fontSize: '0.75rem', marginTop: '0.375rem' }}>
              {t('profile.photoHint')}
            </p>
          </div>
          <input
            ref={avatarInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void uploadAvatar(file);
              e.target.value = '';
            }}
          />
        </div>

        <div className="form-row">
          <TextField
            label={t('profile.name')}
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
          />
          <SelectField
            label={t('profile.language')}
            value={lang}
            onChange={(e) => setLang(e.target.value)}
          >
            <option value="az">{t('admin.settings.langAz')}</option>
            <option value="en">{t('admin.settings.langEn')}</option>
          </SelectField>
        </div>

        <Button
          variant="primary"
          size="sm"
          disabled={savingProfile}
          onClick={() => void saveProfile()}
        >
          {savingProfile && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {t('common.save')}
        </Button>
      </div>

      <div className="card admin__form">
        <h2 style={{ fontSize: '1rem' }}>{t('profile.phoneSection')}</h2>

        {user.phone_verified ? (
          <p className="account-menu__verified" style={{ margin: 0 }}>
            <ShieldCheck size={14} aria-hidden="true" />
            {t('profile.phoneVerified', { phone: user.phone ?? '' })}
          </p>
        ) : (
          <p className="muted" style={{ fontSize: '0.8125rem' }}>
            {t('profile.phoneNeeded')}
          </p>
        )}

        {step === 'idle' ? (
          <>
            <TextField
              label={t('profile.phone')}
              inputMode="tel"
              value={phone}
              error={phoneError}
              placeholder="+994 50 123 45 67"
              onChange={(e) => {
                setPhone(e.target.value);
                setPhoneError(null);
              }}
            />
            <Button
              variant="secondary"
              size="sm"
              disabled={busy || phone.replace(/\D/g, '').length < 9}
              onClick={() => void sendCode()}
            >
              {busy && <Loader2 size={15} className="spin" aria-hidden="true" />}
              {user.phone_verified ? t('profile.changePhone') : t('auth.sendCode')}
            </Button>
          </>
        ) : (
          <>
            {devCode && (
              <p className="muted" style={{ fontSize: '0.8125rem' }}>
                {t('profile.testCode')} <strong className="tabular">{devCode}</strong>
              </p>
            )}
            <TextField
              label={t('profile.code')}
              inputMode="numeric"
              maxLength={6}
              value={code}
              error={phoneError}
              onChange={(e) => {
                setCode(e.target.value);
                setPhoneError(null);
              }}
            />
            <div className="row-actions">
              <Button
                variant="primary"
                size="sm"
                disabled={busy || code.trim().length < 4}
                onClick={() => void verify()}
              >
                {busy && <Loader2 size={15} className="spin" aria-hidden="true" />}
                {t('profile.confirm')}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setStep('idle')}>
                {t('common.cancel')}
              </Button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
