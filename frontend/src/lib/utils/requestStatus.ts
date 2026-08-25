export type RequestStatus = 'new' | 'viewed' | 'completed' | 'cancelled';

export type StatusTone = 'neutral' | 'accent' | 'success' | 'danger';

/**
 * One mapping used by both the admin queue and the buyer's own history, so
 * the two can never disagree about what "viewed" is called or looks like.
 *
 * Kept out of the component file so importing the labels does not drag a
 * component into a module that only wanted a string.
 */
const STATUS: Record<RequestStatus, { label: string; tone: StatusTone }> = {
  new: { label: 'Yeni', tone: 'accent' },
  viewed: { label: 'Baxıldı', tone: 'neutral' },
  completed: { label: 'Tamamlandı', tone: 'success' },
  cancelled: { label: 'Ləğv edildi', tone: 'danger' },
};

export const STATUS_ORDER: RequestStatus[] = ['new', 'viewed', 'completed', 'cancelled'];

export function statusLabel(status: RequestStatus): string {
  return STATUS[status]?.label ?? status;
}

export function statusTone(status: RequestStatus): StatusTone {
  return STATUS[status]?.tone ?? 'neutral';
}
