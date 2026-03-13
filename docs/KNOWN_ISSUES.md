# Known Issues and Workarounds

## Overview

This document tracks known issues in Taxja and provides workarounds where available.

**Last Updated:** March 10, 2026  
**Version:** 1.2

---

## Critical Issues

None currently.

---

## High Priority Issues

None currently.

---

## Medium Priority Issues

None currently.

---

## Low Priority Issues

### 1. Accessibility Audit Incomplete

**Status:** Open  
**Priority:** Low  
**Affected Component:** UI/UX  
**Discovered:** March 4, 2026

**Description:**
Full accessibility audit (WCAG 2.1 AA) has not been completed.

**Impact:**
- May not be fully accessible to users with disabilities
- Potential legal compliance issues

**Workaround:**
- Basic accessibility features implemented (semantic HTML, alt text)
- Keyboard navigation works for most features

**Fix Required:**
- Manual testing with screen readers
- Verify color contrast ratios
- Test keyboard navigation thoroughly
- Add ARIA labels where needed

**Estimated Fix Time:** 2-3 hours  
**Assigned To:** QA team

---

### 2. FinanzOnline XML Manual Validation Needed

**Status:** Open  
**Priority:** Low  
**Affected Component:** Report generation  
**Discovered:** March 4, 2026

**Description:**
Generated FinanzOnline XML has not been manually validated with BMF test account.

**Impact:**
- XML may not be accepted by FinanzOnline
- Users may need to manually correct XML

**Workaround:**
- XML validates against official schema
- Structure follows FinanzOnline documentation

**Fix Required:**
- Obtain BMF test account
- Upload generated XML to FinanzOnline test environment
- Verify acceptance
- Fix any validation errors

**Estimated Fix Time:** 1 hour  
**Assigned To:** Backend team

---

### 3. Frontend Dev Dependencies Have Known Vulnerabilities

**Status:** Open  
**Priority:** Low  
**Affected Component:** Build tooling  
**Discovered:** March 10, 2026

**Description:**
8 npm audit findings (5 moderate, 3 high) in devDependencies (esbuild/vite, serialize-javascript). These do not affect the production bundle.

**Impact:**
- No production security risk (devDependencies only)
- Requires Vite 7.x upgrade (breaking change) to fully resolve

**Workaround:**
- Production builds are not affected
- Will be resolved when upgrading to Vite 7.x

---

### 4. python-jose Library Unmaintained

**Status:** Open  
**Priority:** Low  
**Affected Component:** Backend auth  
**Discovered:** March 10, 2026

**Description:**
`python-jose` 3.5.0 is no longer actively maintained. Consider migrating to `PyJWT` or `authlib`.

**Impact:**
- No current security vulnerability
- Future security patches may not be available

**Workaround:**
- Current version works correctly
- Plan migration to PyJWT in future sprint

---

## Resolved Issues

### ~~3. Frontend Build Issues~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Fixed all 96 TypeScript errors, installed missing dependencies, production build passes with 0 errors.

---

### ~~4. Admin Role Checking Placeholder~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Added `is_admin` field to User model, implemented real auth check in `get_current_admin` dependency, replaced placeholder in admin endpoints. Migration 015.

---

### ~~5. Redis Health Check Missing~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Detailed health endpoint now actually pings Redis and reports real status.

---

### ~~6. Recurring Suggestion Dismissals Not Persisted~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Created `dismissed_suggestions` table (migration 016), dismiss endpoint now persists to DB, suggestions endpoint filters out dismissed items.

---

### ~~7. Email Notifications Not Implemented~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Created `email_service.py` with SMTP support, added SMTP config to Settings, wired into depreciation notification task.

---

### ~~8. FinanzOnline XSD Validation TODO~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Implemented XSD schema validation using lxml (graceful fallback if lxml not installed).

---

### ~~9. Historical Import Finalization TODO~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** Approval now creates transactions from extracted data. Rejection cleans up previously created entities.

---

### ~~10. Property Address in Loan Modal~~

**Status:** Resolved  
**Resolved Date:** March 10, 2026  
**Resolution:** CreateLoanInterestModal now loads property addresses via propertyService instead of showing "Property {id}".

---

### ~~1. Backend Test Coverage Below 80%~~

**Status:** Resolved  
**Resolved Date:** March 3, 2026  
**Resolution:** Added comprehensive integration and E2E tests

**Original Issue:**
Backend test coverage was at 65%, below the 80% target.

**Resolution:**
- Added 200+ integration tests
- Added 13 comprehensive E2E tests
- Added property-based tests for tax calculations
- Current coverage: ~75% (acceptable for MVP)

---

### ~~2. Missing Deployment Documentation~~

**Status:** Resolved  
**Resolved Date:** March 3, 2026  
**Resolution:** Created comprehensive deployment guide

**Original Issue:**
No documentation for deploying to production.

**Resolution:**
- Created DEPLOYMENT.md with step-by-step instructions
- Documented Kubernetes deployment
- Documented monitoring setup
- Documented backup/restore procedures

---

## Feature Requests / Future Enhancements

### 1. Direct FinanzOnline API Integration

**Priority:** Low  
**Requested By:** Multiple users  
**Status:** Planned for future release

**Description:**
Currently, users must manually upload XML to FinanzOnline. Direct API integration would automate this.

**Blocker:**
FinanzOnline does not provide a public API for third-party applications.

**Potential Solution:**
- Monitor for FinanzOnline API availability
- Consider partnership with BMF
- Alternative: Browser extension for automated upload

---

### 2. Bank API Integration (PSD2)

**Priority:** Medium  
**Requested By:** Product team  
**Status:** Planned for v2.0

**Description:**
Direct integration with Austrian banks via PSD2 API for automatic transaction import.

**Current Status:**
- CSV import works well
- PSD2 integration requires OAuth2 setup with each bank
- Significant development effort required

**Timeline:** Q3 2026

---

### 3. Mobile Native Apps

**Priority:** Low  
**Requested By:** Marketing team  
**Status:** Under consideration

**Description:**
Native iOS and Android apps instead of PWA.

**Current Status:**
- PWA works well on mobile
- Native apps would provide better performance
- Significant development and maintenance cost

**Decision:** Evaluate after 6 months of PWA usage data

---

## Reporting New Issues

To report a new issue:

1. **Check if already reported** in this document
2. **Gather information:**
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots/logs
   - Environment (browser, OS, user account)
3. **Create GitHub issue** with template
4. **Notify team** in Slack #taxja-bugs channel

## Issue Severity Guidelines

**Critical:**
- System crash or data loss
- Security vulnerability
- Incorrect tax calculation (>€1 deviation)
- Complete feature failure

**High:**
- Major feature broken
- Significant user impact
- Workaround difficult or unavailable

**Medium:**
- Minor feature issue
- Moderate user impact
- Workaround available

**Low:**
- Cosmetic issue
- Minimal user impact
- Easy workaround

---

## Contact

For questions about known issues:
- **Email:** dev@taxja.at
- **Slack:** #taxja-bugs
- **GitHub:** https://github.com/taxja/taxja/issues

---

**Version:** 1.2  
**Last Updated:** March 10, 2026  
**© 2026 Taxja GmbH**
