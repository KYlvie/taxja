import {
  type ReactNode,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import './Select.css';

/* ── Types ── */

interface FlatOption {
  value: string;
  label: string;
  disabled?: boolean;
  title?: string;
  icon?: ReactNode;
}

interface GroupOption {
  label: string;
  options: FlatOption[];
}

type OptionItem = FlatOption | GroupOption;

function isGroup(o: OptionItem): o is GroupOption {
  return 'options' in o;
}

export interface SelectProps {
  value?: string;
  /**
   * Accepts both controlled `(value: string) => void` callbacks
   * and react-hook-form `{...register()}` ChangeHandler via spread.
   * RHF's handler internally normalises the argument (checks for .target).
   */
  onChange?: (...event: any[]) => void;
  onBlur?: (...event: any[]) => void;
  options: OptionItem[];
  placeholder?: string;
  name?: string;
  id?: string;
  disabled?: boolean;
  error?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  'aria-label'?: string;
}

/* ── Helpers ── */

function flattenOptions(options: OptionItem[]): FlatOption[] {
  const flat: FlatOption[] = [];
  for (const o of options) {
    if (isGroup(o)) flat.push(...o.options);
    else flat.push(o);
  }
  return flat;
}

/* ── Chevron SVG ── */
const Chevron = () => (
  <svg className="custom-select__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

/* ── Check SVG ── */
const Check = () => (
  <svg className="custom-select__check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

/* ── Component ── */

const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    value,
    onChange,
    onBlur,
    options,
    placeholder,
    name,
    id,
    disabled,
    error,
    size = 'md',
    className,
    'aria-label': ariaLabel,
  },
  ref,
) {
  const nativeRef = useRef<HTMLSelectElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const shouldEmitEventLikeChange =
    typeof ref === 'function' && typeof onBlur === 'function' && Boolean(name);

  // Expose the native select to parent (for RHF register())
  useImperativeHandle(ref, () => nativeRef.current!, []);

  const flat = useMemo(() => flattenOptions(options), [options]);
  const enabledFlat = useMemo(() => flat.filter((o) => !o.disabled), [flat]);

  const selectedOption = useMemo(
    () => flat.find((o) => o.value === value),
    [flat, value],
  );

  /* ── Positioning ── */
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0, above: false });

  const calcPosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const above = spaceBelow < 300 && rect.top > spaceBelow;
    setPos({
      top: above ? rect.top : rect.bottom + 4,
      left: rect.left,
      width: rect.width,
      above,
    });
  }, []);

  /* ── Open / Close ── */
  const open = useCallback(() => {
    if (disabled) return;
    calcPosition();
    setIsOpen(true);
    // Focus current value in list
    const idx = enabledFlat.findIndex((o) => o.value === value);
    setFocusedIndex(idx >= 0 ? flat.indexOf(enabledFlat[idx]) : 0);
  }, [disabled, calcPosition, enabledFlat, value, flat]);

  const close = useCallback(() => {
    setIsOpen(false);
    setFocusedIndex(-1);
    triggerRef.current?.focus();
  }, []);

  const selectValue = useCallback(
    (val: string) => {
      // Update hidden native select
      if (nativeRef.current) {
        const nativeSet = Object.getOwnPropertyDescriptor(
          HTMLSelectElement.prototype,
          'value',
        )?.set;
        nativeSet?.call(nativeRef.current, val);
        const evt = new Event('change', { bubbles: true });
        nativeRef.current.dispatchEvent(evt);
      }
      if (shouldEmitEventLikeChange && nativeRef.current) {
        onChange?.({
          target: nativeRef.current,
          currentTarget: nativeRef.current,
          type: 'change',
        });
      } else {
        onChange?.(val);
      }
      close();
    },
    [onChange, close, shouldEmitEventLikeChange],
  );

  /* ── Close on outside click / scroll / escape ── */
  useEffect(() => {
    if (!isOpen) return;

    const handleOutside = (e: MouseEvent) => {
      if (
        triggerRef.current?.contains(e.target as Node) ||
        dropdownRef.current?.contains(e.target as Node)
      )
        return;
      close();
    };

    const handleScroll = (e: Event) => {
      if (dropdownRef.current?.contains(e.target as Node)) return;
      close();
    };

    document.addEventListener('mousedown', handleOutside);
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', close);

    return () => {
      document.removeEventListener('mousedown', handleOutside);
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', close);
    };
  }, [isOpen, close]);

  /* ── Keyboard ── */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (disabled) return;

      if (!isOpen) {
        if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
          e.preventDefault();
          open();
        }
        return;
      }

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          close();
          break;
        case 'ArrowDown': {
          e.preventDefault();
          let next = focusedIndex + 1;
          while (next < flat.length && flat[next].disabled) next++;
          if (next < flat.length) setFocusedIndex(next);
          break;
        }
        case 'ArrowUp': {
          e.preventDefault();
          let prev = focusedIndex - 1;
          while (prev >= 0 && flat[prev].disabled) prev--;
          if (prev >= 0) setFocusedIndex(prev);
          break;
        }
        case 'Home':
          e.preventDefault();
          setFocusedIndex(flat.findIndex((o) => !o.disabled));
          break;
        case 'End': {
          e.preventDefault();
          for (let i = flat.length - 1; i >= 0; i--) {
            if (!flat[i].disabled) {
              setFocusedIndex(i);
              break;
            }
          }
          break;
        }
        case 'Enter':
        case ' ':
          e.preventDefault();
          if (focusedIndex >= 0 && !flat[focusedIndex].disabled) {
            selectValue(flat[focusedIndex].value);
          }
          break;
        default: {
          // Type-to-search: jump to first option starting with typed char
          if (e.key.length === 1) {
            const ch = e.key.toLowerCase();
            const startIdx = focusedIndex + 1;
            const idx =
              flat.findIndex(
                (o, i) =>
                  i >= startIdx &&
                  !o.disabled &&
                  o.label.toLowerCase().startsWith(ch),
              ) ??
              flat.findIndex(
                (o) => !o.disabled && o.label.toLowerCase().startsWith(ch),
              );
            if (idx >= 0) setFocusedIndex(idx);
          }
        }
      }
    },
    [disabled, isOpen, open, close, focusedIndex, flat, selectValue],
  );

  /* ── Scroll focused option into view ── */
  useEffect(() => {
    if (!isOpen || focusedIndex < 0) return;
    const el = dropdownRef.current?.querySelector(
      `[data-index="${focusedIndex}"]`,
    );
    el?.scrollIntoView({ block: 'nearest' });
  }, [isOpen, focusedIndex]);

  /* ── Render options ── */
  let flatIdx = -1;

  const renderOptions = () => {
    flatIdx = -1;
    return options.map((item, groupIdx) => {
      if (isGroup(item)) {
        return (
          <div key={`g-${groupIdx}`} role="group" aria-label={item.label}>
            <div className="custom-select__group-label">{item.label}</div>
            {item.options.map((opt) => {
              flatIdx++;
              return renderOption(opt, flatIdx);
            })}
          </div>
        );
      }
      flatIdx++;
      return renderOption(item, flatIdx);
    });
  };

  const renderOption = (opt: FlatOption, idx: number) => {
    const isSelected = opt.value === value;
    const isFocused = idx === focusedIndex;
    return (
      <div
        key={opt.value}
        role="option"
        aria-selected={isSelected}
        aria-disabled={opt.disabled || undefined}
        data-index={idx}
        className={[
          'custom-select__option',
          isSelected && 'custom-select__option--selected',
          isFocused && 'custom-select__option--focused',
          opt.disabled && 'custom-select__option--disabled',
        ]
          .filter(Boolean)
          .join(' ')}
        onMouseEnter={() => !opt.disabled && setFocusedIndex(idx)}
        onMouseDown={(e) => {
          e.preventDefault(); // prevent blur on trigger
          if (!opt.disabled) selectValue(opt.value);
        }}
        title={opt.title}
      >
        {opt.icon && <span className="custom-select__icon">{opt.icon}</span>}
        <span className="custom-select__label">{opt.label}</span>
        {isSelected && <Check />}
      </div>
    );
  };

  const triggerId = id ? `${id}-trigger` : undefined;
  const dropdownId = id ? `${id}-listbox` : name ? `${name}-listbox` : undefined;

  const rootCls = [
    'custom-select',
    size === 'sm' && 'custom-select--sm',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const triggerCls = [
    'custom-select__trigger',
    error && 'custom-select__trigger--error',
    !selectedOption && placeholder && 'custom-select__trigger--placeholder',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rootCls}>
      {/* Hidden native select for RHF */}
      <select
        ref={nativeRef}
        className="custom-select__native"
        name={name}
        id={id}
        value={value ?? ''}
        disabled={disabled}
        tabIndex={-1}
        aria-hidden="true"
        onChange={() => {
          // Native change events are dispatched by selectValue();
          // RHF's onChange is called directly with the string value there.
        }}
        onBlur={(e) => onBlur?.(e)}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {flat.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      {/* Visible trigger */}
      <button
        ref={triggerRef}
        type="button"
        id={triggerId}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls={dropdownId}
        aria-label={ariaLabel}
        disabled={disabled}
        className={triggerCls}
        title={selectedOption?.title ?? selectedOption?.label ?? placeholder}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleKeyDown}
      >
        {selectedOption?.icon && <span className="custom-select__icon">{selectedOption.icon}</span>}
        <span className="custom-select__label">
          {selectedOption?.label ?? placeholder ?? '\u00A0'}
        </span>
        <Chevron />
      </button>

      {/* Dropdown portal */}
      {isOpen &&
        createPortal(
          <div
            ref={dropdownRef}
            role="listbox"
            id={dropdownId}
            aria-label={ariaLabel}
            className={[
              'custom-select__dropdown',
              pos.above && 'custom-select__dropdown--above',
            ]
              .filter(Boolean)
              .join(' ')}
            style={{
              top: pos.above ? undefined : pos.top,
              bottom: pos.above
                ? window.innerHeight - pos.top + 4
                : undefined,
              left: pos.left,
              width: Math.max(pos.width, 160),
            }}
          >
            {renderOptions()}
          </div>,
          document.body,
        )}
    </div>
  );
});

export default Select;
