import { useQueryClient } from '@tanstack/react-query';
import { Info, Loader2, Mail, Phone, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { authApi, devApi } from '@/lib/api/auth';
import { cartApi, cartKeys } from '@/lib/api/cart';
import { ApiError } from '@/lib/api/client';
import { useT } from '@/lib/i18n';
import { siteConfig } from '@/lib/site/config';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

type Step = 'method' | 'code';

/**
 * Sign in / sign up sheet.
 *
 * Doubles as the "invitation" from plan.md 9.8: when a guest presses
 * "Səbətə at", this opens showing the product they wanted, and their intent
 * is replayed the moment they sign in - so the action completes and they
 * never click twice.
 */
export function AuthSheet() {
  const { t } = useT();
  const open = useUiStore((s) => s.authOpen);
  const close = useUiStore((s) => s.closeAuth);
  const intent = useUiStore((s) => s.pendingIntent);
  const clearIntent = useUiStore((s) => s.clearIntent);
  const openCart = useUiStore((s) => s.openCart);

  const setSession = useAuthStore((s) => s.setSession);
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>('method');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  // Read from the boot-time site config rather than fetched again here: the
  // sheet used to issue its own request on every open, which raced the one
  // main.tsx already makes.
  const googleEnabled = siteConfig()?.google_enabled ?? false;

  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, close]);

  if (!open) return null;

  const messageFor = (err: unknown): string => {
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
        return t('error.phoneInvalid');
      default:
        return err.message;
    }
  };

  const sendCode = async () => {
    setBusy(true);
    setError(null);
    try {
      const sent = await authApi.sendOtp(phone);
      setStep('code');
      // In development the console channel exposes the code, so show it
      // rather than telling the user to check a phone that will never ring.
      if (sent.dev_inbox) {
        const inbox = await devApi.otpInbox().catch(() => null);
        setDevCode(inbox?.items[0]?.code ?? null);
      }
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setError(null);
    try {
      const session = await authApi.verifyOtp(phone, code);
      setSession(session);

      // Complete the interrupted add-to-cart, then show the result.
      if (intent) {
        await cartApi.add(intent.id, 1).catch(() => null);
        clearIntent();
      }
      await queryClient.invalidateQueries({ queryKey: cartKeys.cart() });

      close();
      if (intent) openCart();
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  };

  const canSend = phone.replace(/\D/g, '').length >= 9;
  const canVerify = code.trim().length >= 4;

  return (
    <>
      <button type="button" className="scrim" aria-label={t('common.close')} onClick={close} />
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        className="glass glass--specular glass--deep auth-sheet"
      >
        <header className="auth-sheet__head">
          <h2 id="auth-title" style={{ fontSize: '1.0625rem' }}>
            {step === 'method' ? t('auth.title') : t('auth.codeTitle')}
          </h2>
          <Button variant="ghost" size="sm" icon onClick={close} aria-label={t('common.close')}>
            <X size={16} aria-hidden="true" />
          </Button>
        </header>

        <div className="auth-sheet__body">
          {intent && (
            <div className="auth-intent">
              <span className="auth-intent__media">
                {intent.image ? <img src={intent.image} alt="" /> : null}
              </span>
              <span>
                <span className="subtle" style={{ display: 'block', fontSize: '0.75rem' }}>
                  {t('auth.inviteTitle')}
                </span>
                <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>{intent.title}</span>
              </span>
            </div>
          )}

          {step === 'method' ? (
            <>
              <Button
                variant="secondary"
                size="lg"
                disabled={!googleEnabled}
                title={googleEnabled === false ? t('auth.googleDisabled') : t('auth.google')}
              >
                <GoogleMark />
                {t('auth.google')}
              </Button>

              {!googleEnabled && (
                <p className="auth-note">
                  <Info size={13} aria-hidden="true" />
                  {t('auth.googleNotSetUp')}
                </p>
              )}

              <div className="auth-divider">
                <span>{t('auth.or')}</span>
              </div>

              <label htmlFor="auth-phone" className="ks-label" style={{ marginBottom: 0 }}>
                <Phone size={13} aria-hidden="true" /> {t('auth.phone')}
              </label>
              <input
                id="auth-phone"
                className="input"
                inputMode="tel"
                value={phone}
                onChange={(e) => {
                  setPhone(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && canSend) void sendCode();
                }}
                placeholder="+994 50 000 00 00"
                aria-invalid={error !== null}
              />

              {error && <p style={{ color: 'var(--danger)', fontSize: '0.8125rem' }}>{error}</p>}

              <Button
                variant="primary"
                size="lg"
                disabled={!canSend || busy}
                onClick={() => void sendCode()}
              >
                {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
                {t('auth.sendCode')}
              </Button>
            </>
          ) : (
            <>
              <p className="muted" style={{ fontSize: '0.875rem' }}>
                <strong>{phone}</strong> {t('auth.codeSent')}
              </p>

              {devCode && (
                <p className="auth-note">
                  <Info size={13} aria-hidden="true" />
                  Demo rejimi — kod: <strong className="tabular">{devCode}</strong>
                </p>
              )}

              <label htmlFor="auth-code" className="ks-label" style={{ marginBottom: 0 }}>
                <Mail size={13} aria-hidden="true" /> {t('auth.code')}
              </label>
              <input
                id="auth-code"
                className="input tabular"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => {
                  setCode(e.target.value.replace(/\D/g, ''));
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && canVerify) void verify();
                }}
                placeholder="000000"
                style={{ letterSpacing: '0.3em', fontSize: '1.125rem' }}
                aria-invalid={error !== null}
              />

              {error && <p style={{ color: 'var(--danger)', fontSize: '0.8125rem' }}>{error}</p>}

              <Button
                variant="primary"
                size="lg"
                disabled={!canVerify || busy}
                onClick={() => void verify()}
              >
                {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
                {t('auth.verify')}
              </Button>

              <button
                type="button"
                className="auth-switch"
                onClick={() => {
                  setStep('method');
                  setCode('');
                  setError(null);
                }}
                style={{ background: 'none', border: 0, color: 'var(--accent)' }}
              >
                {t('auth.changeNumber')}
              </button>
            </>
          )}

          <p className="subtle" style={{ fontSize: '0.6875rem', textAlign: 'center' }}>
            {t('auth.terms')}
          </p>
        </div>
      </div>
    </>
  );
}

/** Google's mark, inline so it needs no external request (CSP-safe). */
function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45.1 24.5c0-1.6-.1-2.7-.4-3.9H24v7.1h12.1c-.2 1.8-1.6 4.6-4.5 6.4l6.9 5.3c4.1-3.8 6.6-9.4 6.6-15z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.9 0 10.9-2 14.5-5.3l-6.9-5.3c-1.8 1.3-4.3 2.2-7.6 2.2-5.8 0-10.7-3.8-12.5-9.1l-7.1 5.5C8.1 41.1 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.5 28.5c-.5-1.4-.7-2.9-.7-4.5s.3-3.1.7-4.5l-7.1-5.5C2.9 17 2 20.4 2 24s.9 7 2.4 10l7.1-5.5z"
      />
      <path
        fill="#EA4335"
        d="M24 10.6c3.2 0 5.4 1.4 6.7 2.6l6.1-6C33 3.8 29 2 24 2 15.4 2 8.1 6.9 4.4 14l7.1 5.5c1.8-5.3 6.7-8.9 12.5-8.9z"
      />
    </svg>
  );
}
