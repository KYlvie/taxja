import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './DateInput.css';

export interface DateInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: boolean;
  min?: string;
  max?: string;
  name?: string;
  id?: string;
  className?: string;
  size?: 'sm' | 'md';
  locale?: string;
  todayLabel?: string;
  clearLabel?: string;
  pickerLabel?: string;
}

interface CalendarDay {
  day: number;
  month: number;
  year: number;
  isCurrentMonth: boolean;
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  const jsDay = new Date(year, month, 1).getDay();
  return jsDay === 0 ? 6 : jsDay - 1;
}

function generateCalendarDays(year: number, month: number): CalendarDay[] {
  const days: CalendarDay[] = [];
  const firstDow = getFirstDayOfMonth(year, month);
  const daysInMonth = getDaysInMonth(year, month);

  if (firstDow > 0) {
    const prevMonth = month === 0 ? 11 : month - 1;
    const prevYear = month === 0 ? year - 1 : year;
    const prevDays = getDaysInMonth(prevYear, prevMonth);

    for (let index = firstDow - 1; index >= 0; index -= 1) {
      days.push({
        day: prevDays - index,
        month: prevMonth,
        year: prevYear,
        isCurrentMonth: false,
      });
    }
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    days.push({ day, month, year, isCurrentMonth: true });
  }

  const remaining = 42 - days.length;
  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;

  for (let day = 1; day <= remaining; day += 1) {
    days.push({
      day,
      month: nextMonth,
      year: nextYear,
      isCurrentMonth: false,
    });
  }

  return days;
}

function parseDate(
  value: string,
): { year: number; month: number; day: number } | null {
  if (!value) {
    return null;
  }

  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }

  return {
    year: Number(match[1]),
    month: Number(match[2]) - 1,
    day: Number(match[3]),
  };
}

function toDateString(year: number, month: number, day: number): string {
  const mm = String(month + 1).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return `${year}-${mm}-${dd}`;
}

function isSameDay(
  left: { year: number; month: number; day: number },
  right: { year: number; month: number; day: number },
): boolean {
  return (
    left.year === right.year &&
    left.month === right.month &&
    left.day === right.day
  );
}

const CalendarIcon = () => (
  <svg
    className="date-input__icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const ChevronLeft = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRight = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="9 6 15 12 9 18" />
  </svg>
);

const ClearIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export default function DateInput({
  value = '',
  onChange,
  placeholder = 'dd/mm/yyyy',
  disabled,
  error,
  min,
  max,
  name,
  id,
  className,
  size = 'md',
  locale,
  todayLabel = 'Today',
  clearLabel = 'Clear date',
  pickerLabel = 'Date picker',
}: DateInputProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'days' | 'months' | 'years'>(
    'days',
  );
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const [pos, setPos] = useState({ top: 0, left: 0, above: false });

  const parsed = useMemo(() => parseDate(value), [value]);
  const today = useMemo(() => {
    const date = new Date();
    return {
      year: date.getFullYear(),
      month: date.getMonth(),
      day: date.getDate(),
    };
  }, []);

  const [viewYear, setViewYear] = useState(parsed?.year ?? today.year);
  const [viewMonth, setViewMonth] = useState(parsed?.month ?? today.month);

  useEffect(() => {
    if (parsed) {
      setViewYear(parsed.year);
      setViewMonth(parsed.month);
    }
  }, [parsed]);

  const calDays = useMemo(
    () => generateCalendarDays(viewYear, viewMonth),
    [viewYear, viewMonth],
  );
  const minParsed = useMemo(() => parseDate(min ?? ''), [min]);
  const maxParsed = useMemo(() => parseDate(max ?? ''), [max]);
  const effectiveLocale = locale ?? navigator.language ?? 'en-GB';

  const weekdayNames = useMemo(() => {
    const formatter = new Intl.DateTimeFormat(effectiveLocale, {
      weekday: 'short',
    });

    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(2024, 0, 1 + index);
      return formatter.format(date);
    });
  }, [effectiveLocale]);

  const monthLabel = useMemo(() => {
    const formatter = new Intl.DateTimeFormat(effectiveLocale, {
      month: 'long',
      year: 'numeric',
    });
    return formatter.format(new Date(viewYear, viewMonth, 1));
  }, [effectiveLocale, viewMonth, viewYear]);

  const monthNames = useMemo(() => {
    const formatter = new Intl.DateTimeFormat(effectiveLocale, {
      month: 'short',
    });

    return Array.from({ length: 12 }, (_, index) =>
      formatter.format(new Date(2024, index, 1)),
    );
  }, [effectiveLocale]);

  const yearRange = useMemo(() => {
    const startYear = viewYear - 6;
    return Array.from({ length: 12 }, (_, index) => startYear + index);
  }, [viewYear]);

  const displayValue = useMemo(() => {
    if (!value) {
      return '';
    }

    const date = parseDate(value);
    if (!date) {
      return value;
    }

    return new Date(date.year, date.month, date.day).toLocaleDateString(
      effectiveLocale,
    );
  }, [effectiveLocale, value]);

  const calcPosition = useCallback(() => {
    if (!triggerRef.current) {
      return;
    }

    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const above = spaceBelow < 380 && rect.top > spaceBelow;

    setPos({
      top: above ? rect.top : rect.bottom + 4,
      left: rect.left,
      above,
    });
  }, []);

  const open = useCallback(() => {
    if (disabled) {
      return;
    }

    calcPosition();
    if (parsed) {
      setViewYear(parsed.year);
      setViewMonth(parsed.month);
    }
    setViewMode('days');
    setFocusedIdx(-1);
    setIsOpen(true);
  }, [calcPosition, disabled, parsed]);

  const close = useCallback(() => {
    setIsOpen(false);
    setFocusedIdx(-1);
    setViewMode('days');
    triggerRef.current?.focus();
  }, []);

  const isDayDisabled = useCallback(
    (day: CalendarDay) => {
      const dayValue = toDateString(day.year, day.month, day.day);

      if (minParsed) {
        const minValue = toDateString(
          minParsed.year,
          minParsed.month,
          minParsed.day,
        );
        if (dayValue < minValue) {
          return true;
        }
      }

      if (maxParsed) {
        const maxValue = toDateString(
          maxParsed.year,
          maxParsed.month,
          maxParsed.day,
        );
        if (dayValue > maxValue) {
          return true;
        }
      }

      return false;
    },
    [maxParsed, minParsed],
  );

  const selectDay = useCallback(
    (day: CalendarDay) => {
      if (isDayDisabled(day)) {
        return;
      }

      onChange?.(toDateString(day.year, day.month, day.day));
      close();
    },
    [close, isDayDisabled, onChange],
  );

  const handleClear = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation();
      onChange?.('');
    },
    [onChange],
  );

  const goPrevMonth = useCallback(() => {
    setViewMonth((month) => {
      if (month === 0) {
        setViewYear((year) => year - 1);
        return 11;
      }
      return month - 1;
    });
    setFocusedIdx(-1);
  }, []);

  const goNextMonth = useCallback(() => {
    setViewMonth((month) => {
      if (month === 11) {
        setViewYear((year) => year + 1);
        return 0;
      }
      return month + 1;
    });
    setFocusedIdx(-1);
  }, []);

  const goToday = useCallback(() => {
    onChange?.(toDateString(today.year, today.month, today.day));
    close();
  }, [close, onChange, today.day, today.month, today.year]);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    const handleOutside = (event: MouseEvent) => {
      if (
        triggerRef.current?.contains(event.target as Node) ||
        dropdownRef.current?.contains(event.target as Node)
      ) {
        return;
      }
      close();
    };

    const handleScroll = (event: Event) => {
      if (dropdownRef.current?.contains(event.target as Node)) {
        return;
      }
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
  }, [close, isOpen]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (disabled) {
        return;
      }

      if (!isOpen) {
        if (
          event.key === 'ArrowDown' ||
          event.key === 'ArrowUp' ||
          event.key === 'Enter' ||
          event.key === ' '
        ) {
          event.preventDefault();
          open();
        }
        return;
      }

      switch (event.key) {
        case 'Escape':
          event.preventDefault();
          close();
          break;
        case 'ArrowRight':
          event.preventDefault();
          setFocusedIdx((current) =>
            current < 0 ? 0 : Math.min(current + 1, calDays.length - 1),
          );
          break;
        case 'ArrowLeft':
          event.preventDefault();
          setFocusedIdx((current) => (current < 0 ? 0 : Math.max(current - 1, 0)));
          break;
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIdx((current) =>
            current < 0 ? 0 : Math.min(current + 7, calDays.length - 1),
          );
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIdx((current) => (current < 0 ? 0 : Math.max(current - 7, 0)));
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedIdx >= 0 && focusedIdx < calDays.length) {
            selectDay(calDays[focusedIdx]);
          }
          break;
        default:
          break;
      }
    },
    [calDays, close, disabled, focusedIdx, isOpen, open, selectDay],
  );

  useEffect(() => {
    if (!isOpen || focusedIdx < 0) {
      return;
    }

    const element = dropdownRef.current?.querySelector(
      `[data-idx="${focusedIdx}"]`,
    );
    element?.scrollIntoView({ block: 'nearest' });
  }, [focusedIdx, isOpen]);

  const rootCls = ['date-input', size === 'sm' && 'date-input--sm', className]
    .filter(Boolean)
    .join(' ');
  const triggerCls = [
    'date-input__trigger',
    error && 'date-input__trigger--error',
    !displayValue && 'date-input__trigger--placeholder',
  ]
    .filter(Boolean)
    .join(' ');

  const dropdown = isOpen
    ? createPortal(
        <div
          ref={dropdownRef}
          role="dialog"
          aria-label={pickerLabel}
          className={[
            'date-input__dropdown',
            pos.above && 'date-input__dropdown--above',
          ]
            .filter(Boolean)
            .join(' ')}
          style={{
            top: pos.above ? undefined : pos.top,
            bottom: pos.above ? window.innerHeight - pos.top + 4 : undefined,
            left: pos.left,
          }}
        >
          <div className="date-input__nav">
            {viewMode === 'days' && (
              <button
                type="button"
                className="date-input__nav-btn"
                onClick={goPrevMonth}
                aria-label="Previous month"
              >
                <ChevronLeft />
              </button>
            )}
            {viewMode === 'years' && (
              <button
                type="button"
                className="date-input__nav-btn"
                onClick={() => setViewYear((year) => year - 12)}
                aria-label="Previous years"
              >
                <ChevronLeft />
              </button>
            )}
            <button
              type="button"
              className="date-input__nav-label"
              onClick={() =>
                setViewMode((mode) =>
                  mode === 'days'
                    ? 'months'
                    : mode === 'months'
                      ? 'years'
                      : 'days',
                )
              }
            >
              {viewMode === 'years'
                ? `${yearRange[0]} - ${yearRange[yearRange.length - 1]}`
                : monthLabel}
            </button>
            {viewMode === 'days' && (
              <button
                type="button"
                className="date-input__nav-btn"
                onClick={goNextMonth}
                aria-label="Next month"
              >
                <ChevronRight />
              </button>
            )}
            {viewMode === 'years' && (
              <button
                type="button"
                className="date-input__nav-btn"
                onClick={() => setViewYear((year) => year + 12)}
                aria-label="Next years"
              >
                <ChevronRight />
              </button>
            )}
          </div>

          {viewMode === 'months' && (
            <div className="date-input__grid-picker">
              {monthNames.map((monthName, index) => (
                <button
                  key={monthName}
                  type="button"
                  className={`date-input__grid-cell${index === viewMonth ? ' date-input__grid-cell--selected' : ''}${index === today.month && viewYear === today.year ? ' date-input__grid-cell--today' : ''}`}
                  onClick={() => {
                    setViewMonth(index);
                    setViewMode('days');
                  }}
                >
                  {monthName}
                </button>
              ))}
            </div>
          )}

          {viewMode === 'years' && (
            <div className="date-input__grid-picker">
              {yearRange.map((year) => (
                <button
                  key={year}
                  type="button"
                  className={`date-input__grid-cell${year === viewYear ? ' date-input__grid-cell--selected' : ''}${year === today.year ? ' date-input__grid-cell--today' : ''}`}
                  onClick={() => {
                    setViewYear(year);
                    setViewMode('months');
                  }}
                >
                  {year}
                </button>
              ))}
            </div>
          )}

          {viewMode === 'days' && (
            <>
              <div className="date-input__weekdays">
                {weekdayNames.map((weekday) => (
                  <span key={weekday} className="date-input__weekday">
                    {weekday}
                  </span>
                ))}
              </div>

              <div className="date-input__calendar">
                {calDays.map((calendarDay, index) => {
                  const isDisabled = isDayDisabled(calendarDay);
                  const isSelected =
                    parsed != null &&
                    isSameDay(calendarDay, {
                      year: parsed.year,
                      month: parsed.month,
                      day: parsed.day,
                    });
                  const isToday = isSameDay(calendarDay, today);
                  const isFocused = index === focusedIdx;

                  const dayCls = [
                    'date-input__day',
                    !calendarDay.isCurrentMonth && 'date-input__day--outside',
                    isToday && 'date-input__day--today',
                    isSelected && 'date-input__day--selected',
                    isDisabled && 'date-input__day--disabled',
                    isFocused && 'date-input__day--focused',
                  ]
                    .filter(Boolean)
                    .join(' ');

                  return (
                    <button
                      key={`${calendarDay.year}-${calendarDay.month}-${calendarDay.day}`}
                      type="button"
                      data-idx={index}
                      className={dayCls}
                      disabled={isDisabled}
                      tabIndex={-1}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectDay(calendarDay);
                      }}
                      onMouseEnter={() => setFocusedIdx(index)}
                    >
                      {calendarDay.day}
                    </button>
                  );
                })}
              </div>
            </>
          )}

          <div className="date-input__footer">
            <button
              type="button"
              className="date-input__today-btn"
              onMouseDown={(event) => {
                event.preventDefault();
                goToday();
              }}
            >
              {todayLabel}
            </button>
          </div>
        </div>,
        document.body,
      )
    : null;

  return (
    <div className={rootCls}>
      <input type="hidden" name={name} id={id} value={value} />

      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        disabled={disabled}
        className={triggerCls}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleKeyDown}
      >
        <span className="date-input__label">{displayValue || placeholder}</span>
        {value && !disabled && (
          <span
            className="date-input__clear"
            onClick={handleClear}
            aria-label={clearLabel}
            role="button"
            tabIndex={-1}
          >
            <ClearIcon />
          </span>
        )}
        <CalendarIcon />
      </button>

      {dropdown}
    </div>
  );
}
