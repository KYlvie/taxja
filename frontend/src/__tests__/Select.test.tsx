/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { useForm } from 'react-hook-form';

import Select from '../components/common/Select';

function RegisteredSelectHarness() {
  const { register, watch } = useForm<{ asset_type: string }>({
    defaultValues: {
      asset_type: '',
    },
  });

  return (
    <div>
      <span data-testid="selected-value">{watch('asset_type') || ''}</span>
      <Select
        {...register('asset_type')}
        value={watch('asset_type') || ''}
        placeholder="Select asset type"
        options={[
          { value: 'vehicle', label: 'Car' },
          { value: 'computer', label: 'Computer' },
        ]}
      />
    </div>
  );
}

describe('Select', () => {
  beforeAll(() => {
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('keeps plain controlled onChange handlers working with string values', () => {
    const onChange = vi.fn();

    render(
      <Select
        value=""
        onChange={onChange}
        placeholder="Pick one"
        options={[
          { value: 'vehicle', label: 'Car' },
          { value: 'computer', label: 'Computer' },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.mouseDown(screen.getByRole('option', { name: 'Car' }));

    expect(onChange).toHaveBeenCalledWith('vehicle');
  });

  it('updates react-hook-form registered fields when an option is selected', async () => {
    render(<RegisteredSelectHarness />);

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.mouseDown(screen.getByRole('option', { name: 'Car' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-value')).toHaveTextContent('vehicle');
    });

    expect(screen.getByRole('combobox')).toHaveTextContent('Car');
  });
});
