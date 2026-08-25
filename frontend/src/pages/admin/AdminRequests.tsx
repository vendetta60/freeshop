import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Mail, Phone, X } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { TextAreaField } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { StatusPill } from '@/components/ui/StatusPill';
import { useT } from '@/lib/i18n';
import { STATUS_ORDER } from '@/lib/utils/requestStatus';
import { adminApi, adminKeys, type AdminOrderRequest, type RequestStatus } from '@/lib/api/admin';
import { useDebounced } from '@/lib/hooks/useDebounced';
import { Price } from '@/components/ui/Price';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

/**
 * The request queue: the screen the shop is actually run from.
 *
 * A row opens a detail panel rather than a separate route, because the work
 * is triage - read, call, mark - and losing the list between every request
 * makes that loop slower for no benefit.
 */
export default function AdminRequests() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RequestStatus | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const [note, setNote] = useState('');

  const q = useDebounced(search, 250);
  const query = { status: status ?? undefined, q: q || undefined, page };

  const requests = useQuery({
    queryKey: adminKeys.requests(query),
    queryFn: ({ signal }) => adminApi.requests(query, signal),
  });

  const selected: AdminOrderRequest | undefined = requests.data?.items.find(
    (item) => item.id === openId,
  );

  const update = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number;
      patch: { status?: RequestStatus; admin_note?: string };
    }) => adminApi.updateRequest(id, patch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      toast.success(t('admin.request.updated'));
    },
    onError: () => toast.error(t('admin.request.updateFailed')),
  });

  const open = (request: AdminOrderRequest) => {
    setOpenId(request.id);
    setNote(request.admin_note ?? '');
    // Opening a new request is the moment it stops being unseen, so the
    // status follows the actual work rather than waiting for a second click.
    if (request.status === 'new') {
      update.mutate({ id: request.id, patch: { status: 'viewed' } });
    }
  };

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.requests')}</h1>
      </header>

      <div className="admin__toolbar">
        <input
          className="input"
          type="search"
          value={search}
          placeholder={t('admin.request.searchPlaceholder')}
          aria-label={t('admin.request.searchLabel')}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      <div className="filter-rail" role="group" aria-label={t('admin.request.statusFilter')}>
        <Chip
          active={status === null}
          onClick={() => {
            setStatus(null);
            setPage(1);
          }}
        >
          {t('common.all')}
        </Chip>
        {STATUS_ORDER.map((value) => (
          <Chip
            key={value}
            active={status === value}
            onClick={() => {
              setStatus(value);
              setPage(1);
            }}
          >
            {t(`status.${value}`)}
          </Chip>
        ))}
      </div>

      {requests.isError && <ErrorState onRetry={() => void requests.refetch()} />}
      {requests.isPending && (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} height={52} radius="var(--r-md)" />
          ))}
        </div>
      )}

      {requests.data && requests.data.items.length === 0 && (
        <EmptyState
          title={t('admin.request.empty')}
          description={status ? t('admin.request.emptyFiltered') : t('admin.request.emptyText')}
        />
      )}

      {requests.data && requests.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('admin.request.no')}</th>
                <th scope="col">{t('admin.request.customer')}</th>
                <th scope="col">{t('admin.request.amount')}</th>
                <th scope="col">{t('admin.request.status')}</th>
                <th scope="col">{t('admin.request.date')}</th>
              </tr>
            </thead>
            <tbody>
              {requests.data.items.map((request) => (
                <tr
                  key={request.id}
                  className="row--clickable"
                  tabIndex={0}
                  role="button"
                  aria-label={t('admin.request.open', { no: request.request_no })}
                  onClick={() => open(request)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      open(request);
                    }
                  }}
                >
                  <td className="tabular" style={{ fontWeight: 500 }}>
                    {request.request_no}
                  </td>
                  <td>
                    <span style={{ display: 'block' }}>
                      {request.user_name ?? t('account.noName')}
                    </span>
                    <span className="subtle tabular" style={{ fontSize: '0.75rem' }}>
                      {request.contact_phone}
                    </span>
                  </td>
                  <td>
                    <Price minor={request.total_minor} />
                  </td>
                  <td>
                    <StatusPill status={request.status} />
                  </td>
                  <td className="muted">{formatDate(request.created_at, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {requests.data && (
        <Pagination
          page={requests.data.page}
          pages={requests.data.pages}
          total={requests.data.total}
          onChange={setPage}
        />
      )}

      {selected && (
        <>
          <button
            type="button"
            className="scrim"
            aria-label={t('common.close')}
            onClick={() => setOpenId(null)}
          />
          <aside
            className="glass glass--deep request-panel"
            aria-label={t('admin.request.details')}
          >
            <header className="request-panel__head">
              <div>
                <h2 className="tabular" style={{ fontSize: '1.0625rem' }}>
                  {selected.request_no}
                </h2>
                <p className="muted" style={{ fontSize: '0.8125rem' }}>
                  {formatDate(selected.created_at, lang)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon
                aria-label={t('common.close')}
                onClick={() => setOpenId(null)}
              >
                <X size={16} aria-hidden="true" />
              </Button>
            </header>

            <div className="request-panel__contacts">
              <a className="contact-row" href={`tel:${selected.contact_phone.replace(/\s/g, '')}`}>
                <Phone size={15} aria-hidden="true" />
                <span className="tabular">{selected.contact_phone}</span>
              </a>
              {selected.contact_email && (
                <a className="contact-row" href={`mailto:${selected.contact_email}`}>
                  <Mail size={15} aria-hidden="true" />
                  {selected.contact_email}
                </a>
              )}
            </div>

            {selected.note && (
              <p className="request-panel__note">
                <span className="subtle" style={{ display: 'block', fontSize: '0.75rem' }}>
                  {t('admin.request.customerNote')}
                </span>
                {selected.note}
              </p>
            )}

            <ul className="plain-list">
              {selected.items.map((item) => (
                <li key={item.id} className="request-line">
                  <span style={{ minWidth: 0 }}>{item.title}</span>
                  <span className="muted tabular">×{item.quantity}</span>
                  <Price minor={item.line_total_minor} />
                </li>
              ))}
            </ul>

            <p className="request-panel__total">
              <span>{t('common.total')}</span>
              <strong>
                <Price minor={selected.total_minor} />
              </strong>
            </p>

            <div className="filter-rail" role="group" aria-label={t('admin.request.changeStatus')}>
              {STATUS_ORDER.map((value) => (
                <Chip
                  key={value}
                  active={selected.status === value}
                  onClick={() => update.mutate({ id: selected.id, patch: { status: value } })}
                >
                  {t(`status.${value}`)}
                </Chip>
              ))}
            </div>

            <TextAreaField
              label={t('admin.request.adminNote')}
              rows={3}
              value={note}
              hint={t('admin.request.adminNoteHint')}
              onChange={(e) => setNote(e.target.value)}
            />
            <Button
              variant="secondary"
              size="sm"
              disabled={update.isPending || note === (selected.admin_note ?? '')}
              onClick={() => update.mutate({ id: selected.id, patch: { admin_note: note } })}
            >
              {t('admin.request.saveNote')}
            </Button>
          </aside>
        </>
      )}
    </section>
  );
}
