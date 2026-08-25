import { create } from 'zustand';

import { authApi, type Session, type User } from '@/lib/api/auth';
import { setAccessToken, setSessionLostHandler } from '@/lib/api/client';

type AuthState = {
  user: User | null;
  /** True until the boot-time refresh has settled, so the UI does not flash
   *  "signed out" for a user who is in fact signed in. */
  loading: boolean;
  setSession: (session: Session) => void;
  clear: () => void;
  signOut: () => Promise<void>;
};

/**
 * Auth state.
 *
 * NOT persisted, deliberately. The access token lives in memory (see
 * lib/api/client.ts) and the durable half is the httpOnly refresh cookie,
 * which JavaScript cannot read. Persisting the user here would only create a
 * second source of truth that can disagree with the server.
 */
export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  loading: true,

  setSession: (session) => {
    setAccessToken(session.access_token);
    set({ user: session.user, loading: false });
  },

  clear: () => {
    setAccessToken(null);
    set({ user: null, loading: false });
  },

  signOut: async () => {
    try {
      await authApi.logout();
    } finally {
      // Clear locally even if the call failed: the user asked to sign out,
      // and leaving them apparently signed in would be worse than a stale
      // server-side token that expires on its own.
      setAccessToken(null);
      set({ user: null, loading: false });
    }
  },
}));

export function useIsSignedIn(): boolean {
  return useAuthStore((s) => s.user !== null);
}

/** Initials for the avatar fallback: "Aysel Məmmədova" -> "AM". */
export function initialsOf(user: User): string {
  // Explicit emptiness test, not `||`: a blank name must fall through to the
  // email, which `??` would not do.
  const candidates = [user.full_name, user.email, user.phone];
  const source = candidates.find((value) => value?.trim()) ?? '?';
  return source
    .split(/[\s@]+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toLocaleUpperCase('az'))
    .join('');
}

/**
 * Restore the session once, at startup, from the refresh cookie.
 *
 * Called from main.tsx before render so the first paint already knows whether
 * anyone is signed in.
 */
export async function bootstrapAuth(): Promise<void> {
  const store = useAuthStore.getState();

  setSessionLostHandler(() => {
    useAuthStore.getState().clear();
  });

  try {
    const { hydrateSession } = await import('@/lib/api/client');
    if (await hydrateSession()) {
      const user = await authApi.me();
      useAuthStore.setState({ user, loading: false });
      return;
    }
  } catch {
    // No cookie, an expired one, or the API is down. Signed out is the
    // correct and safe conclusion in all three cases.
  }
  store.clear();
}
