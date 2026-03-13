#!/usr/bin/env python3
"""
Script to create UAT test accounts for landlord testing.

Usage:
    python backend/scripts/create_uat_accounts.py --count 10
    python backend/scripts/create_uat_accounts.py --count 5 --output accounts.txt
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from tests.uat.uat_test_data import create_uat_test_accounts, generate_uat_welcome_email


def main():
    parser = argparse.ArgumentParser(description='Create UAT test accounts')
    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of test accounts to create (default: 10)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for account credentials (optional)'
    )
    parser.add_argument(
        '--email-format',
        action='store_true',
        help='Output in email format for sending to participants'
    )
    
    args = parser.parse_args()
    
    print(f"Creating {args.count} UAT test accounts...")
    
    db = SessionLocal()
    
    try:
        accounts = create_uat_test_accounts(db, count=args.count)
        
        if not accounts:
            print("No new accounts created (accounts may already exist)")
            return
        
        print(f"\n✓ Successfully created {len(accounts)} test accounts\n")
        
        # Prepare output
        output_lines = []
        
        if args.email_format:
            # Email format for sending to participants
            for account in accounts:
                email_content = generate_uat_welcome_email(account)
                output_lines.append(email_content)
                output_lines.append("\n" + "="*80 + "\n")
        else:
            # Simple credentials format
            output_lines.append("UAT Test Accounts\n")
            output_lines.append("="*80 + "\n\n")
            
            for account in accounts:
                output_lines.append(f"Email: {account['email']}\n")
                output_lines.append(f"Password: {account['password']}\n")
                output_lines.append(f"User ID: {account['user_id']}\n")
                output_lines.append("-"*80 + "\n")
        
        # Output to file or console
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.writelines(output_lines)
            print(f"✓ Account credentials saved to: {args.output}")
        else:
            print("".join(output_lines))
        
        # Print summary
        print("\nNext Steps:")
        print("1. Deploy application to staging environment")
        print("2. Send credentials to UAT participants")
        print("3. Share UAT test plan: backend/tests/uat/LANDLORD_UAT_TEST_PLAN.md")
        print("4. Monitor feedback at: /api/v1/uat/feedback/summary")
        
    except Exception as e:
        print(f"✗ Error creating accounts: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
