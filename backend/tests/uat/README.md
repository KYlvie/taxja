# UAT (User Acceptance Testing) Setup Guide

## Overview

This directory contains all resources needed to conduct User Acceptance Testing for the Property Asset Management feature with real landlord users.

## Files

- `LANDLORD_UAT_TEST_PLAN.md` - Comprehensive test plan with scenarios and success criteria
- `feedback_form.py` - Database models and Pydantic schemas for feedback collection
- `feedback_api.py` - FastAPI endpoints for feedback and metrics tracking
- `uat_test_data.py` - Test data generators for realistic scenarios
- `README.md` - This file

## Setup Instructions

### 1. Database Migration

Create and run the migration for UAT feedback tables:

```bash
cd backend

# Create migration
alembic revision --autogenerate -m "Add UAT feedback tables"

# Review the migration file in alembic/versions/

# Run migration
alembic upgrade head
```

### 2. Register API Endpoints

Add the UAT feedback router to your FastAPI application:

```python
# In backend/app/main.py or backend/app/api/v1/api.py

from tests.uat.feedback_api import router as uat_router

app.include_router(uat_router)
```

### 3. Create Test Accounts

Run the test account creation script:

```python
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from tests.uat.uat_test_data import create_uat_test_accounts, generate_uat_welcome_email

db = SessionLocal()

# Create 10 test accounts
accounts = create_uat_test_accounts(db, count=10)

# Print credentials and welcome emails
for account in accounts:
    print(f"\n{'='*60}")
    print(generate_uat_welcome_email(account))
    print(f"{'='*60}\n")

db.close()
```

Or create a script:

```bash
# backend/scripts/create_uat_accounts.py
python backend/scripts/create_uat_accounts.py
```

### 4. Deploy to Staging

Deploy the application to your staging environment:

```bash
# Build and deploy
docker-compose -f docker-compose.staging.yml up -d

# Or use your deployment script
./scripts/deploy_staging.sh
```

### 5. Send Invitations

Send welcome emails to UAT participants with:
- Staging URL
- Login credentials
- Link to test plan
- Feedback instructions

## Frontend Integration

### Add Feedback Widget to Property Pages

```tsx
// In your property management pages
import { UATFeedbackWidget } from '@/components/uat/UATFeedbackWidget';

export const PropertyDetailPage = () => {
  return (
    <div>
      {/* Your page content */}
      
      {/* Add feedback widget */}
      <UATFeedbackWidget 
        testScenario="property_registration"
        onSubmit={() => console.log('Feedback submitted')}
      />
    </div>
  );
};
```

### Add Progress Page to Routes

```tsx
// In your router configuration
import { UATProgressPage } from '@/pages/UATProgressPage';

const routes = [
  // ... other routes
  {
    path: '/uat/progress',
    element: <UATProgressPage />,
  },
];
```

### Add i18n Translations

Add translations for UAT components:

```json
// frontend/src/i18n/de.json
{
  "uat": {
    "feedback": {
      "button": "Feedback geben",
      "title": "Ihr Feedback",
      "category": "Kategorie",
      "rating": "Bewertung",
      "comment": "Kommentar",
      "submit": "Absenden",
      "success": "Vielen Dank für Ihr Feedback!",
      "categories": {
        "usability": "Benutzerfreundlichkeit",
        "functionality": "Funktionalität",
        "value": "Nutzen",
        "bug_report": "Fehler melden",
        "feature_request": "Feature-Wunsch"
      }
    },
    "progress": {
      "title": "UAT Fortschritt",
      "scenariosCompleted": "Szenarien abgeschlossen",
      "minutesSpent": "Minuten investiert",
      "feedbackSubmitted": "Feedback abgegeben",
      "bugsReported": "Fehler gemeldet"
    }
  }
}
```

## Monitoring UAT Progress

### View Feedback Summary

```bash
curl -X GET "https://staging.taxja.at/api/v1/uat/feedback/summary"
```

### View Metrics Summary

```bash
curl -X GET "https://staging.taxja.at/api/v1/uat/metrics/summary"
```

### Export Feedback Data

```python
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from tests.uat.feedback_form import UATFeedback
import csv

db = SessionLocal()

# Query all feedback
feedback = db.query(UATFeedback).all()

# Export to CSV
with open('uat_feedback.csv', 'w', newline='') as csvfile:
    fieldnames = ['id', 'test_scenario', 'category', 'rating', 'comment', 'severity', 'created_at']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for item in feedback:
        writer.writerow({
            'id': item.id,
            'test_scenario': item.test_scenario.value,
            'category': item.category.value,
            'rating': item.rating,
            'comment': item.comment,
            'severity': item.severity.value if item.severity else None,
            'created_at': item.created_at,
        })

db.close()
```

## Test Scenarios

### Scenario 1: Property Registration
- **Test Scenario ID**: `property_registration`
- **Pages**: Properties List, Property Form
- **Duration**: ~5 minutes

### Scenario 2: Historical Backfill
- **Test Scenario ID**: `historical_backfill`
- **Pages**: Property Detail, Backfill Modal
- **Duration**: ~5 minutes

### Scenario 3: Transaction Linking
- **Test Scenario ID**: `transaction_linking`
- **Pages**: Transactions List, Property Detail
- **Duration**: ~10 minutes

### Scenario 4: Property Metrics
- **Test Scenario ID**: `property_metrics`
- **Pages**: Property Detail, Dashboard
- **Duration**: ~5 minutes

### Scenario 5: Report Generation
- **Test Scenario ID**: `report_generation`
- **Pages**: Property Detail, Reports
- **Duration**: ~5 minutes

### Scenario 6: Multi-Property Management
- **Test Scenario ID**: `multi_property`
- **Pages**: Properties List, Comparison View
- **Duration**: ~10 minutes

### Scenario 7: Property Archival
- **Test Scenario ID**: `property_archival`
- **Pages**: Property Detail, Archive Modal
- **Duration**: ~5 minutes

## Success Criteria

UAT is considered successful when:

- ✅ At least 5 landlords complete all test scenarios
- ✅ Task completion rate > 90%
- ✅ Average user satisfaction rating > 4.0/5.0
- ✅ All critical and high severity bugs are fixed
- ✅ Feature adoption rate > 80%

## Timeline

- **Week 1**: Setup and participant recruitment
- **Week 2-3**: Active testing period
- **Week 4**: Feedback analysis and prioritization
- **Week 5**: Bug fixes and iteration

## Support

For UAT support questions:
- Email: uat-support@taxja.at
- Slack: #uat-property-management
- Documentation: https://docs.taxja.at/uat

## Post-UAT Actions

After UAT completion:

1. **Analyze Feedback**
   ```bash
   python backend/scripts/analyze_uat_feedback.py
   ```

2. **Prioritize Bugs**
   - Critical: Fix immediately
   - High: Fix before production
   - Medium: Add to backlog
   - Low: Consider for future releases

3. **Update Documentation**
   - Revise user guide based on confusion points
   - Add FAQ entries for common questions
   - Create video tutorials for complex workflows

4. **Prepare for Production**
   - Deploy fixes to staging
   - Re-test critical workflows
   - Get product owner approval
   - Schedule production deployment

## Troubleshooting

### Feedback Widget Not Appearing

Check that:
1. Component is imported correctly
2. CSS file is loaded
3. API endpoint is accessible
4. No console errors

### Test Accounts Not Working

Verify:
1. Migration ran successfully
2. Users created in database
3. Passwords are correct
4. Users are marked as active and verified

### Metrics Not Tracking

Ensure:
1. API endpoints are registered
2. Frontend is calling metric tracking
3. Database tables exist
4. No CORS issues

---

**Last Updated**: 2026-03-08  
**Version**: 1.0
