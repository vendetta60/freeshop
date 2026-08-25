import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

import { useT } from '@/lib/i18n';
import { useToastStore } from '@/stores/toastStore';

const ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
} as const;

/**
 * Toast host. Mounted once in the root layout.
 *
 * `aria-live="polite"` rather than `assertive`: these announce the result of
 * something the user just did, and interrupting a screen reader mid-sentence
 * to say "saved" is rude. Blocking failures are reported inline on the form
 * as well, never only here.
 */
export function ToastHost() {
  const { t } = useT();
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-host" role="status" aria-live="polite">
      {toasts.map((item) => {
        const Icon = ICONS[item.tone];
        return (
          <div key={item.id} className={`toast toast--${item.tone} glass glass--specular`}>
            <Icon size={16} aria-hidden="true" />
            <span>{item.message}</span>
            <button
              type="button"
              className="toast__close"
              aria-label={t('state.dismissToast')}
              onClick={() => dismiss(item.id)}
            >
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
