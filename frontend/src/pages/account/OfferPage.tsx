import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Gift, ImagePlus, Loader2, ShieldAlert, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';

import { LocationPicker } from '@/components/community/LocationPicker';
import { Button } from '@/components/ui/Button';
import { CheckboxField, SelectField, TextAreaField, TextField } from '@/components/ui/Field';
import { EmptyState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys, listingApi, listingKeys } from '@/lib/api/catalogue';
import { ApiError } from '@/lib/api/client';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/** Manat as typed ("12,50") to integer qəpik. Money never becomes a float. */
function toMinor(input: string): number | null {
  const cleaned = input.trim().replace(/\s/g, '').replace(',', '.');
  if (cleaned === '') return 0;
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, fraction = ''] = cleaned.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}

/**
 * Offer something you no longer use.
 *
 * The form is deliberately short — a name, a category, a few words — because
 * the barrier to giving a chair away has to be lower than the barrier to
 * putting it on the kerb. Everything else about the listing is the
 * moderator's job, not the giver's.
 */
export default function OfferPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  useDocumentTitle(t('offer.title'));

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [isFree, setIsFree] = useState(true);
  const [price, setPrice] = useState('');

  // Prefilled from the giver's saved location and editable, because most
  // things are handed over where the giver lives and some are not
  // (FreeShop_Prompt 1).
  const [place, setPlace] = useState({ city: user?.location_city ?? '', district: '' });

  // Give away or lend (FreeShop_Prompt 7). `giveaway` is the default because
  // it is what this board has always been for.
  const [transferType, setTransferType] = useState<'giveaway' | 'loan'>('giveaway');
  const [maxDays, setMaxDays] = useState('7');
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [done, setDone] = useState(false);

  /**
   * Photos are chosen BEFORE the listing exists, then uploaded the moment it
   * does. The alternative - save, then come back to add pictures - is how a
   * board fills up with listings nobody can see the item in.
   *
   * The preview URL is held WITH its file rather than derived in an effect:
   * an object URL is a resource that has to be released, and pairing it with
   * the file makes creating and revoking it two halves of the same event.
   */
  const [photos, setPhotos] = useState<{ file: File; url: string }[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  // Mirrors `photos` so the unmount cleanup releases the current list rather
  // than whatever it was on first render. Written from an effect, not during
  // render, because a ref touched while rendering is a ref that lies.
  const photosRef = useRef(photos);
  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);
  useEffect(
    () => () => {
      for (const photo of photosRef.current) URL.revokeObjectURL(photo.url);
    },
    [],
  );

  const dropPhoto = (index: number) => {
    setPhotos((current) => {
      const gone = current[index];
      if (gone) URL.revokeObjectURL(gone.url);
      return current.filter((_, i) => i !== index);
    });
  };

  const clearPhotos = () => {
    setPhotos((current) => {
      for (const photo of current) URL.revokeObjectURL(photo.url);
      return [];
    });
  };

  const categories = useQuery({
    queryKey: catalogueKeys.categories(lang),
    queryFn: ({ signal }) => catalogueApi.categories(lang, signal),
    staleTime: 5 * 60_000,
  });

  const submit = useMutation({
    mutationFn: async () => {
      const listing = await listingApi.submit({
        title_az: title.trim(),
        description_az: description.trim(),
        category_id: Number(categoryId),
        price_minor: isFree ? 0 : (toMinor(price) ?? 0),
        city: place.city || null,
        district: place.district || null,
        transfer_type: transferType,
        max_borrow_days: transferType === 'loan' ? Number(maxDays) || null : null,
      });

      if (photos.length > 0) {
        // A photo upload that fails must not throw away the listing the
        // person just wrote: the listing is already saved, so this reports
        // the partial failure instead of unwinding it.
        try {
          await listingApi.addImages(
            listing.id,
            photos.map((photo) => photo.file),
          );
        } catch {
          toast.error(t('offer.photosFailed'));
        }
      }
      return listing;
    },
    onSuccess: async () => {
      setDone(true);
      await queryClient.invalidateQueries({ queryKey: listingKeys.mine(lang) });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.field) {
        setErrors({ [error.field]: error.message });
        return;
      }
      toast.error(t('offer.failed'));
    },
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('offer.signInTitle')}
        description={t('offer.signInText')}
        icon={<Gift size={22} />}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  // The phone gate (plan.md 9.3) is enforced server-side; saying so here means
  // nobody fills in a form only to be refused at the end of it.
  if (!user.phone_verified) {
    return (
      <EmptyState
        title={t('offer.needsPhone')}
        description={t('offer.needsPhoneText')}
        icon={<ShieldAlert size={22} />}
        action={
          <Link to="/profile" className="btn btn--primary btn--md">
            {t('offer.toProfile')}
          </Link>
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
        <h1 style={{ fontSize: '1.375rem' }}>{t('offer.submitted')}</h1>
        <p className="muted">{t('offer.submittedText')}</p>
        <div className="row-actions">
          <Link to="/profile/listings" className="btn btn--primary btn--md">
            {t('listings.title')}
          </Link>
          <Button
            variant="secondary"
            onClick={() => {
              setDone(false);
              setTitle('');
              setDescription('');
              setPrice('');
              setIsFree(true);
              clearPhotos();
            }}
          >
            {t('offer.another')}
          </Button>
        </div>
      </div>
    );
  }

  const validate = () => {
    const found: Record<string, string | undefined> = {};
    if (title.trim().length < 2) found.title_az = t('admin.validation.title');
    if (!categoryId) found.category_id = t('admin.validation.category');
    if (!isFree && toMinor(price) === null) found.price_minor = t('admin.validation.price');
    setErrors(found);
    return Object.keys(found).length === 0;
  };

  const tree = categories.data ?? [];
  const ordered = tree.flatMap((parent) => [parent, ...parent.children]);

  return (
    <section style={{ display: 'grid', gap: '1rem', maxWidth: '46rem' }}>
      <header className="hero" style={{ paddingBottom: '0.5rem' }}>
        <h1>{t('offer.title')}</h1>
        <p>{t('offer.lead')}</p>
      </header>

      <form
        className="card admin__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (validate()) submit.mutate();
        }}
      >
        <TextField
          label={t('offer.name')}
          required
          value={title}
          error={errors.title_az}
          maxLength={200}
          placeholder={t('offer.namePlaceholder')}
          onChange={(e) => {
            setTitle(e.target.value);
            setErrors((current) => ({ ...current, title_az: undefined }));
          }}
        />

        <TextAreaField
          label={t('offer.description')}
          rows={5}
          value={description}
          maxLength={4000}
          placeholder={t('offer.descriptionPlaceholder')}
          onChange={(e) => setDescription(e.target.value)}
        />

        <SelectField
          label={t('offer.category')}
          required
          value={categoryId}
          error={errors.category_id}
          onChange={(e) => {
            setCategoryId(e.target.value);
            setErrors((current) => ({ ...current, category_id: undefined }));
          }}
        >
          <option value="">{t('admin.product.choose')}</option>
          {ordered.map((category) => (
            <option key={category.id} value={category.id}>
              {category.parent_id ? `— ${category.name}` : category.name}
            </option>
          ))}
        </SelectField>

        <div className="field">
          <span className="field__label">{t('offer.photos')}</span>
          <div className="image-grid">
            {photos.map((photo, index) => (
              <figure key={photo.url} className="image-tile">
                <img src={photo.url} alt="" />
                <figcaption className="image-tile__actions">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon
                    aria-label={t('offer.removePhoto')}
                    onClick={() => dropPhoto(index)}
                  >
                    <X size={14} aria-hidden="true" />
                  </Button>
                </figcaption>
              </figure>
            ))}

            {photos.length < 8 && (
              <button
                type="button"
                className="image-tile image-tile--add"
                onClick={() => fileInput.current?.click()}
              >
                <ImagePlus size={20} aria-hidden="true" />
                <span>{t('offer.addPhoto')}</span>
              </button>
            )}
          </div>
          <p className="field__hint">{t('offer.photosHint')}</p>

          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => {
              const chosen = Array.from(e.target.files ?? []);
              // Refused here as well as on the server, so the visitor is told
              // now rather than after writing the whole listing.
              const kept = chosen.filter((file) => {
                if (!file.type.startsWith('image/')) {
                  toast.error(t('offer.photoNotImage', { name: file.name }));
                  return false;
                }
                if (file.size > 5 * 1024 * 1024) {
                  toast.error(t('offer.photoTooLarge', { name: file.name }));
                  return false;
                }
                return true;
              });
              setPhotos((current) =>
                [
                  ...current,
                  ...kept.map((file) => ({ file, url: URL.createObjectURL(file) })),
                ].slice(0, 8),
              );
              e.target.value = '';
            }}
          />
        </div>

        <LocationPicker
          city={place.city}
          district={place.district}
          onChange={setPlace}
          hint={t('location.listingHint')}
        />

        {/* Give away or lend. A radio pair rather than a checkbox: the two
            are different promises, and "not permanent" is not what a person
            reads on an unticked box. */}
        <fieldset className="field">
          <legend className="field__label">{t('offer.transferType')}</legend>
          <div className="radio-row">
            <label className="radio-option">
              <input
                type="radio"
                name="transfer_type"
                checked={transferType === 'giveaway'}
                onChange={() => setTransferType('giveaway')}
              />
              <span>{t('offer.giveaway')}</span>
            </label>
            <label className="radio-option">
              <input
                type="radio"
                name="transfer_type"
                checked={transferType === 'loan'}
                onChange={() => setTransferType('loan')}
              />
              <span>{t('offer.lend')}</span>
            </label>
          </div>
          <p className="field__hint">
            {transferType === 'loan' ? t('offer.lendHint') : t('offer.giveawayHint')}
          </p>
        </fieldset>

        {transferType === 'loan' && (
          <TextField
            label={t('loan.maxDays')}
            type="number"
            min={1}
            max={365}
            value={maxDays}
            hint={t('offer.maxDaysHint')}
            onChange={(e) => setMaxDays(e.target.value)}
          />
        )}

        {/* Free is ticked by default: it is the reason the site exists. */}
        <CheckboxField
          label={t('offer.free')}
          hint={t('offer.freeHint')}
          checked={isFree}
          onChange={(e) => setIsFree(e.target.checked)}
        />

        {!isFree && (
          <TextField
            label={t('offer.price')}
            inputMode="decimal"
            value={price}
            error={errors.price_minor}
            placeholder="10,00"
            onChange={(e) => {
              setPrice(e.target.value);
              setErrors((current) => ({ ...current, price_minor: undefined }));
            }}
          />
        )}

        <Button variant="primary" type="submit" disabled={submit.isPending}>
          {submit.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
          {submit.isPending && photos.length > 0 ? t('offer.uploading') : t('offer.submit')}
        </Button>
      </form>
    </section>
  );
}
