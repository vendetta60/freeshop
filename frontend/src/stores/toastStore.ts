import { create } from 'zustand';

export type ToastTone = 'success' | 'error' | 'info';

export type Toast = {
  id: number;
  tone: ToastTone;
  message: string;
};

type ToastState = {
  toasts: Toast[];
  push: (tone: ToastTone, message: string) => void;
  dismiss: (id: number) => void;
};

let nextId = 1;

/**
 * Transient user notifications (plan.md 3.7).
 *
 * Hand-rolled rather than `sonner`: the whole surface is a list, a timer and
 * an aria-live region, and the JS budget (plan.md 11) has more use for a
 * product image than for a toast library.
 *
 * Errors are NOT auto-dismissed. A success message that disappears is fine -
 * the change it describes is visible on screen. A failure that disappears
 * before it is read leaves someone believing the opposite of what happened.
 */
export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],

  push: (tone, message) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, tone, message }] }));
    if (tone !== 'error') {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
      }, 4000);
    }
  },

  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** Convenience helpers so call sites read as prose. */
export const toast = {
  success: (message: string) => useToastStore.getState().push('success', message),
  error: (message: string) => useToastStore.getState().push('error', message),
  info: (message: string) => useToastStore.getState().push('info', message),
};
