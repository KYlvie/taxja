"""
Verification script for Celery Beat schedule configuration.

This script validates that the celery_app.py file is properly configured
without requiring a full environment setup.
"""
import re
import sys


def verify_celery_beat_configuration():
    """Verify Celery Beat configuration in celery_app.py"""
    
    print("=" * 70)
    print("Celery Beat Schedule Configuration Verification")
    print("=" * 70)
    
    # Read the celery_app.py file
    try:
        with open('backend/app/celery_app.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ ERROR: backend/app/celery_app.py not found")
        return False
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: beat_schedule configuration exists
    checks_total += 1
    if "celery_app.conf.beat_schedule" in content:
        print("✓ beat_schedule configuration found")
        checks_passed += 1
    else:
        print("❌ beat_schedule configuration NOT found")
    
    # Check 2: Annual depreciation task is scheduled
    checks_total += 1
    if "'generate-annual-depreciation'" in content:
        print("✓ 'generate-annual-depreciation' schedule entry found")
        checks_passed += 1
    else:
        print("❌ 'generate-annual-depreciation' schedule entry NOT found")
    
    # Check 3: Task name is correct
    checks_total += 1
    if "'task': 'property.generate_annual_depreciation'" in content:
        print("✓ Task name 'property.generate_annual_depreciation' configured")
        checks_passed += 1
    else:
        print("❌ Task name NOT correctly configured")
    
    # Check 4: Schedule timing - December 31 at 23:00
    checks_total += 1
    schedule_pattern = r"'schedule':\s*\{[^}]*'minute':\s*'0'[^}]*'hour':\s*'23'[^}]*'day_of_month':\s*'31'[^}]*'month_of_year':\s*'12'"
    if re.search(schedule_pattern, content, re.DOTALL):
        print("✓ Schedule timing: December 31 at 23:00 (Vienna time)")
        checks_passed += 1
    else:
        print("❌ Schedule timing NOT correctly configured")
    
    # Check 5: High priority configured
    checks_total += 1
    if "'priority': 9" in content:
        print("✓ High priority (9) configured")
        checks_passed += 1
    else:
        print("❌ Priority NOT configured")
    
    # Check 6: Task expiration configured
    checks_total += 1
    if "'expires': 3600 * 2" in content or "'expires': 7200" in content:
        print("✓ Task expiration (2 hours) configured")
        checks_passed += 1
    else:
        print("❌ Task expiration NOT configured")
    
    # Check 7: Timezone configuration
    checks_total += 1
    if "timezone=\"Europe/Vienna\"" in content:
        print("✓ Timezone set to Europe/Vienna")
        checks_passed += 1
    else:
        print("❌ Timezone NOT correctly configured")
    
    # Check 8: Task tracking enabled
    checks_total += 1
    if "task_track_started=True" in content:
        print("✓ Task tracking enabled")
        checks_passed += 1
    else:
        print("❌ Task tracking NOT enabled")
    
    # Check 9: Result backend configuration
    checks_total += 1
    if "result_expires=3600 * 24 * 7" in content and "result_extended=True" in content:
        print("✓ Result backend configured (7 day retention)")
        checks_passed += 1
    else:
        print("❌ Result backend NOT properly configured")
    
    # Check 10: Task execution settings
    checks_total += 1
    if all(x in content for x in ["task_acks_late=True", "task_reject_on_worker_lost=True", "worker_prefetch_multiplier=1"]):
        print("✓ Task execution settings configured")
        checks_passed += 1
    else:
        print("❌ Task execution settings NOT properly configured")
    
    # Check 11: Monitoring signal handlers
    checks_total += 1
    signal_handlers = [
        "task_prerun_handler",
        "task_postrun_handler",
        "task_success_handler",
        "task_failure_handler"
    ]
    if all(handler in content for handler in signal_handlers):
        print("✓ All monitoring signal handlers defined")
        checks_passed += 1
    else:
        print("❌ Some monitoring signal handlers missing")
    
    # Check 12: Structured logging in signal handlers
    checks_total += 1
    if "logger.info" in content and "'event':" in content:
        print("✓ Structured logging configured")
        checks_passed += 1
    else:
        print("❌ Structured logging NOT properly configured")
    
    # Check 13: Special handling for annual depreciation in success handler
    checks_total += 1
    if "'property.generate_annual_depreciation'" in content and "'annual_depreciation_success'" in content:
        print("✓ Special logging for annual depreciation task")
        checks_passed += 1
    else:
        print("❌ Special logging for annual depreciation NOT configured")
    
    # Check 14: Critical alert for annual depreciation failures
    checks_total += 1
    if "logger.critical" in content and "'annual_depreciation_failure'" in content:
        print("✓ Critical alert for annual depreciation failures")
        checks_passed += 1
    else:
        print("❌ Critical alert for failures NOT configured")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"Verification Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 70)
    
    if checks_passed == checks_total:
        print("\n✅ SUCCESS: All Celery Beat configuration checks passed!")
        print("\nConfiguration Summary:")
        print("  • Schedule: December 31 at 23:00 Vienna time")
        print("  • Task: property.generate_annual_depreciation")
        print("  • Priority: High (9)")
        print("  • Expiration: 2 hours")
        print("  • Monitoring: Full signal handlers with structured logging")
        print("  • Timezone: Europe/Vienna")
        print("  • Result retention: 7 days")
        return True
    else:
        print(f"\n❌ FAILURE: {checks_total - checks_passed} checks failed")
        return False


if __name__ == "__main__":
    success = verify_celery_beat_configuration()
    sys.exit(0 if success else 1)
