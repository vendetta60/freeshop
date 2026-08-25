import { useId } from 'react';
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';

import { cn } from '@/lib/utils/cn';

/**
 * Labelled form controls.
 *
 * One wrapper rather than three near-identical ones, because the parts that
 * matter - the generated id, the `for` association, `aria-invalid`,
 * `aria-describedby` pointing at the error - are identical for every control
 * type and are exactly what gets skipped when each form hand-rolls its own.
 */

type Common = {
  label: string;
  error?: string | null | undefined;
  hint?: ReactNode | undefined;
  required?: boolean | undefined;
};

function Wrapper({
  label,
  error,
  hint,
  required,
  id,
  errorId,
  children,
}: Common & { id: string; errorId: string; children: ReactNode }) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
        {required && (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && <p className="field__hint">{hint}</p>}
      {error && (
        <p className="field__error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}

export function TextField({
  label,
  error,
  hint,
  required,
  className,
  ...rest
}: Common & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} id={id} errorId={errorId}>
      <input
        id={id}
        className={cn('input', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...rest}
      />
    </Wrapper>
  );
}

export function TextAreaField({
  label,
  error,
  hint,
  required,
  className,
  ...rest
}: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} id={id} errorId={errorId}>
      <textarea
        id={id}
        className={cn('input', 'input--area', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...rest}
      />
    </Wrapper>
  );
}

export function SelectField({
  label,
  error,
  hint,
  required,
  className,
  children,
  ...rest
}: Common & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} id={id} errorId={errorId}>
      <select
        id={id}
        className={cn('input', 'input--select', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...rest}
      >
        {children}
      </select>
    </Wrapper>
  );
}

/** Checkbox with the label beside it rather than above it. */
export function CheckboxField({
  label,
  hint,
  className,
  ...rest
}: { label: string; hint?: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className="field field--inline">
      <input id={id} type="checkbox" className={cn('checkbox', className)} {...rest} />
      <label htmlFor={id} className="field__label field__label--inline">
        {label}
        {hint && <span className="field__hint">{hint}</span>}
      </label>
    </div>
  );
}
