"""创建本地10个测试账号"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

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
ADMIN_PWD = get_password_hash("Admin123!")

plans = {p.plan_type: p for p in db.query(Plan).all()}
if not plans:
    print("No plans found! Run seed_plans first.")
    sys.exit(1)

free_plan = plans[PlanType.FREE]
plus_plan = plans[PlanType.PLUS]
pro_plan = plans[PlanType.PRO]

accounts = [
    {"email": "admin@taxja.at", "name": "Admin", "plan": pro_plan, "status": "trial", "type": "employee", "lang": "de", "admin": True, "pwd": ADMIN_PWD},
    {"email": "pro1@taxja.at", "name": "DI Maria Steiner", "plan": pro_plan, "status": "active", "type": "self_employed", "lang": "de", "admin": False, "pwd": PWD},
    {"email": "pro2@taxja.at", "name": "Thomas Huber", "plan": pro_plan, "status": "active", "type": "landlord", "lang": "en", "admin": False, "pwd": PWD},
    {"email": "pro3@taxja.at", "name": "Li Wei", "plan": pro_plan, "status": "active", "type": "mixed", "lang": "zh", "admin": False, "pwd": PWD},
    {"email": "plus1@taxja.at", "name": "Anna Berger", "plan": plus_plan, "status": "active", "type": "employee", "lang": "de", "admin": False, "pwd": PWD},
    {"email": "plus2@taxja.at", "name": "Michael Wagner", "plan": plus_plan, "status": "active", "type": "self_employed", "lang": "en", "admin": False, "pwd": PWD},
    {"email": "free1@taxja.at", "name": "Sophie Müller", "plan": free_plan, "status": "active", "type": "employee", "lang": "de", "admin": False, "pwd": PWD},
    {"email": "free2@taxja.at", "name": "Chen Fang", "plan": free_plan, "status": "active", "type": "employee", "lang": "zh", "admin": False, "pwd": PWD},
    {"email": "trial1@taxja.at", "name": "Julia Fischer", "plan": None, "status": "trial", "type": "self_employed", "lang": "de", "admin": False, "pwd": PWD},
    {"email": "trial2@taxja.at", "name": "David Brown", "plan": None, "status": "trial", "type": "employee", "lang": "en", "admin": False, "pwd": PWD},
]

for acc in accounts:
    existing = db.query(User).filter(User.email == acc["email"]).first()
    if existing:
        print(f"  SKIP {acc['email']} (exists)")
        continue

    user = User(
        email=acc["email"], name=acc["name"], hashed_password=acc["pwd"],
        user_type=acc["type"], language=acc["lang"],
        is_admin=acc["admin"], email_verified=True,
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
        sub = Subscription(
            user_id=user.id, plan_id=plan.id, status=SubscriptionStatus.ACTIVE,
            billing_cycle="monthly", current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
        )
        db.add(sub)
        db.commit()
        credits = plan.monthly_credits
        print(f"  {acc['email']}: {plan.plan_type.value} active, {credits} credits")

    cb = CreditBalance(
        user_id=user.id, plan_balance=credits, topup_balance=0,
        overage_enabled=False, overage_credits_used=0,
        has_unpaid_overage=False, unpaid_overage_periods=0,
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
