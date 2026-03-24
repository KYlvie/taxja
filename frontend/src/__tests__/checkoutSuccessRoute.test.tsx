import { describe, expect, it } from 'vitest';

import { router } from '../routes';

describe('checkout success route', () => {
  it('is registered as a top-level public route', () => {
    const topLevelPaths = router.routes.map((route: any) => route.path ?? null);
    expect(topLevelPaths).toContain('/checkout/success');

    const protectedBranch = router.routes.find(
      (route: any) => Array.isArray(route.children) && route.children.some((child: any) => child.path === 'dashboard'),
    );

    const protectedChildPaths = (protectedBranch?.children ?? []).map((child: any) => child.path ?? null);
    expect(protectedChildPaths).not.toContain('checkout/success');
  });
});
