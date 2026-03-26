"""创建9个测试账号（加上已有的admin共10个）"""
import paramiko

SERVER_IP = '46.62.227.62'
SSH_KEY = r'C:\Users\yk1e25\taxja-server-nopass'

script = r'''
import sys
sys.path.insert(0, "/app")
from app.db.base import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.models.plan import Plan, PlanType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.credit_balance import CreditBalance
from app.services.trial_service import TrialService
from datetime import datetime, timedelta

db = SessionLocal()
PWD = get_password_hash("Test123!")

plans = {p.plan_type: p for p in db.query(Plan).all()}
free_plan = plans[PlanType.FREE]
plus_plan = plans[PlanType.PLUS]
pro_plan = plans[PlanType.PRO]

accounts = [
    # 3 Pro
    {"email": "pro1@taxja.at", "name": "Pro User 1", "plan": pro_plan, "status": "active", "type": "self_employed", "lang": "de"},
    {"email": "pro2@taxja.at", "name": "Pro User 2", "plan": pro_plan, "status": "active", "type": "landlord", "lang": "en"},
    {"email": "pro3@taxja.at", "name": "Pro User 3", "plan": pro_plan, "status": "active", "type": "mixed", "lang": "zh"},
    # 2 Plus
    {"email": "plus1@taxja.at", "name": "Plus User 1", "plan": plus_plan, "status": "active", "type": "employee", "lang": "de"},
    {"email": "plus2@taxja.at", "name": "Plus User 2", "plan": plus_plan, "status": "active", "type": "self_employed", "lang": "en"},
    # 2 Free
    {"email": "free1@taxja.at", "name": "Free User 1", "plan": free_plan, "status": "active", "type": "employee", "lang": "de"},
    {"email": "free2@taxja.at", "name": "Free User 2", "plan": free_plan, "status": "active", "type": "employee", "lang": "zh"},
    # 2 Trial (Pro trial, 14 days)
    {"email": "trial1@taxja.at", "name": "Trial User 1", "plan": None, "status": "trial", "type": "self_employed", "lang": "de"},
    {"email": "trial2@taxja.at", "name": "Trial User 2", "plan": None, "status": "trial", "type": "employee", "lang": "en"},
]

for acc in accounts:
    existing = db.query(User).filter(User.email == acc["email"]).first()
    if existing:
        print(f"  SKIP {acc['email']} (exists)")
        continue

    user = User(
        email=acc["email"],
        name=acc["name"],
        hashed_password=PWD,
        user_type=acc["type"],
        language=acc["lang"],
        is_admin=False,
        email_verified=True,
        trial_used=(acc["status"] != "trial"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if acc["status"] == "trial":
        try:
            sub = TrialService(db).activate_trial(user.id)
            print(f"  {acc['email']}: trial until {sub.current_period_end.strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"  {acc['email']}: trial err: {e}")
        credits = pro_plan.monthly_credits
    else:
        plan = acc["plan"]
        now = datetime.utcnow()
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db.add(sub)
        db.commit()
        credits = plan.monthly_credits
        print(f"  {acc['email']}: {plan.plan_type.value} active, {credits} credits")

    cb = CreditBalance(
        user_id=user.id,
        plan_balance=credits,
        topup_balance=0,
        overage_enabled=False,
        overage_credits_used=0,
        has_unpaid_overage=False,
        unpaid_overage_periods=0,
    )
    db.add(cb)
    db.commit()

print("\n=== All accounts ===")
for u in db.query(User).order_by(User.id).all():
    sub = db.query(Subscription).filter(Subscription.user_id == u.id).first()
    cb = db.query(CreditBalance).filter(CreditBalance.user_id == u.id).first()
    plan_name = sub.plan.name if sub and sub.plan else "-"
    status = sub.status.value if sub else "none"
    credits = (cb.plan_balance + cb.topup_balance) if cb else 0
    print(f"  {u.id:2d} | {u.email:20s} | {plan_name:5s} | {status:8s} | {credits:5d} credits")

db.close()
'''

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER_IP, username='root', key_filename=SSH_KEY, timeout=30)

sftp = client.open_sftp()
with sftp.open('/tmp/create_accounts.py', 'w') as f:
    f.write(script)
sftp.close()

print('上传脚本...')
stdin, stdout, stderr = client.exec_command(
    'docker cp /tmp/create_accounts.py taxja-backend:/tmp/create_accounts.py && '
    'docker exec taxja-backend python3 /tmp/create_accounts.py',
    timeout=60
)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print(out)
if err and 'CSRF' not in err and 'warning' not in err.lower():
    print(f'ERR: {err[-300:]}')

client.close()
