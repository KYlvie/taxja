import { beforeEach, describe, expect, it, vi } from 'vitest';

const post = vi.fn();

vi.mock('../services/api', () => ({
  default: {
    post,
  },
}));

describe('documentService.confirmAsset', () => {
  beforeEach(() => {
    vi.resetModules();
    post.mockReset();
  });

  it('posts confirmation payload to the confirm-asset endpoint', async () => {
    post.mockResolvedValue({ data: { asset_id: 'abc' } });
    const { documentService } = await import('../services/documentService');

    const payload = {
      put_into_use_date: '2026-03-20',
      business_use_percentage: 80,
      gwg_elected: false,
      depreciation_method: 'degressive' as const,
      degressive_afa_rate: 0.25,
    };

    const result = await documentService.confirmAsset(42, payload);

    expect(post).toHaveBeenCalledWith('/documents/42/confirm-asset', payload);
    expect(result).toEqual({ asset_id: 'abc' });
  });
});
