import { Badge } from '@/components/ui/Badge';
import { type RequestStatus, statusLabel, statusTone } from '@/lib/utils/requestStatus';

/** Request status, named and toned from one shared mapping. */
export function StatusPill({ status }: { status: RequestStatus }) {
  return <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>;
}
