import { request } from '@/lib/api/client';

export type User = {
  id: number;
  email: string | null;
  phone: string | null;
  phone_verified: boolean;
  full_name: string | null;
  avatar_url: string | null;
  preferred_lang: string;
  role: 'admin' | 'user';
  /** The saved default location, as a LABEL. Coordinates are never sent. */
  location_label: string | null;
  location_city: string | null;
  /** A label alone is not enough to sort by distance - the gazetteer has to
   *  have recognised the place. This is what the nearby sort depends on. */
  has_location: boolean;
};

export type Session = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type OtpSent = {
  expires_in: number;
  channel: string;
  /** True only in development with the console channel: the UI can then point
   *  at the dev inbox instead of saying "check your phone". */
  dev_inbox: boolean;
};

export const authApi = {
  google: (credential: string) =>
    request<Session>('/auth/google', { method: 'POST', body: { credential } }),

  sendOtp: (phone: string) =>
    request<OtpSent>('/auth/phone/send-otp', { method: 'POST', body: { phone } }),

  verifyOtp: (phone: string, code: string) =>
    request<Session>('/auth/phone/verify-otp', { method: 'POST', body: { phone, code } }),

  logout: () => request<void>('/auth/logout', { method: 'POST' }),

  me: () => request<User>('/users/me'),

  updateMe: (patch: { full_name?: string; preferred_lang?: string }) =>
    request<User>('/users/me', { method: 'PATCH', body: patch }),

  /** Attach or change the phone on an existing account (plan.md 6.2). The
   *  same OTP machinery as sign-in, with purpose `verify_phone`. */
  sendPhoneOtp: (phone: string) =>
    request<OtpSent>('/users/me/phone/send-otp', { method: 'POST', body: { phone } }),

  verifyPhoneOtp: (phone: string, code: string) =>
    request<User>('/users/me/phone/verify-otp', { method: 'POST', body: { phone, code } }),

  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<User>('/users/me/avatar', { method: 'POST', body: form });
  },
};

/** Dev-only: the OTP inbox that makes the console channel demoable. */
export const devApi = {
  otpInbox: () =>
    request<{ items: { phone: string; code: string; expires_in: number }[] }>('/dev/otp-inbox'),
};
