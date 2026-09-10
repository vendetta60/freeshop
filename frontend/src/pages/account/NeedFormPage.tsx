import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, HandHeart, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { LocationPicker } from '@/components/community/LocationPicker';
import { Button } from '@/components/ui/Button';
import { SelectField, TextAreaField, TextField } from '@/components/ui/Field';
import { EmptyState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { ApiError } from '@/lib/api/client';
import { communityKeys, needsApi } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * "Mənə lazımdır" - say what you are looking for (FreeShop_Prompt 4).
 *
 * NO PHONE GATE, unlike offering an item. Publishing a listing is a promise
 * to meet a stranger and hand something over, so it needs a verified number;
 * admitting you need a pushchair is not, and requiring one would exclude
 * exactly the people this board exists for. The server agrees - see
 * `create_need` in app/api/v1/needs.py.
 *
 * The location prefills from the profile and stays editable: the common case
 * is "where I live", and the exception is one select away.
 */
export default function NeedFormPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  useDocumentTitle(t('needs.post'));

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [place, setPlace] = useState({ city: user?.location_city ?? '', district: '' });
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [done, setDone] = useState(false);

  const categories = useQuery({
    queryKey: catalogueKeys.categories(lang),
    queryFn: ({ signal }) => catalogueApi.categories(lang, signal),
    staleTime: 5 * 60_000,
  });

  const submit = useMutation({
    mutationFn: () =>
      needsApi.create({
        title: title.trim(),
        description: description.trim(),
        category_id: categoryId ? Number(categoryId) : null,
        quantity_needed: Number(quantity) || 1,
        city: place.city || null,
        district: place.district || null,
      }),
    onSuccess: async () => {
      setDone(true);
      await queryClient.invalidateQueries({ queryKey: communityKeys.myNeeds(lang) });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.field) {
        setErrors({ [error.field]: error.message });
        return;
      }
      toast.error(t('needs.failed'));
    },
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('needs.signInTitle')}
        description={t('needs.signInText')}
        icon={<HandHeart size={22} />}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  if (done) {
    return (
      <div className="card success-panel">
        <span className="success-panel__tick">
          <Check size={22} aria-hidden="true" />
        </span>
        <h1 style={{ fontSize: '1.375rem' }}>{t('needs.submitted')}</h1>
        <p className="muted">{t('needs.submittedText')}</p>
        <div className="row-actions">
          <Link to="/profile/needs" className="btn btn--primary btn--md">
            {t('needs.mine')}
          </Link>
          <Button
            variant="secondary"
            onClick={() => {
              setDone(false);
              setTitle('');
              setDescription('');
              setQuantity('1');
            }}
          >
            {t('needs.another')}
          </Button>
        </div>
      </div>
    );
  }

  const validate = () => {
    const found: Record<string, string | undefined> = {};
    if (title.trim().length < 2) found.title = t('needs.validation.title');
    setErrors(found);
    return Object.keys(found).length === 0;
  };

  const tree = categories.data ?? [];
  const ordered = tree.flatMap((parent) => [parent, ...parent.children]);

  return (
    <section style={{ display: 'grid', gap: '1rem', maxWidth: '46rem' }}>
      <header className="hero" style={{ paddingBottom: '0.5rem' }}>
        <h1>{t('needs.post')}</h1>
        <p>{t('needs.postLead')}</p>
      </header>

      <form
        className="card admin__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (validate()) submit.mutate();
        }}
      >
        <TextField
          label={t('needs.what')}
          required
          value={title}
          error={errors.title}
          maxLength={200}
          placeholder={t('needs.whatPlaceholder')}
          onChange={(e) => {
            setTitle(e.target.value);
            setErrors((current) => ({ ...current, title: undefined }));
          }}
        />

        <TextAreaField
          label={t('needs.details')}
          rows={4}
          value={description}
          maxLength={4000}
          placeholder={t('needs.detailsPlaceholder')}
          onChange={(e) => setDescription(e.target.value)}
        />

        <SelectField
          label={t('needs.category')}
          value={categoryId}
          hint={t('needs.categoryHint')}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="">{t('admin.product.choose')}</option>
          {ordered.map((category) => (
            <option key={category.id} value={category.id}>
              {category.parent_id ? `— ${category.name}` : category.name}
            </option>
          ))}
        </SelectField>

        <TextField
          label={t('needs.quantityLabel')}
          type="number"
          min={1}
          max={999}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />

        <LocationPicker
          city={place.city}
          district={place.district}
          onChange={setPlace}
          hint={t('location.needHint')}
        />

        <Button variant="primary" type="submit" disabled={submit.isPending}>
          {submit.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {t('needs.submit')}
        </Button>
      </form>
    </section>
  );
}
