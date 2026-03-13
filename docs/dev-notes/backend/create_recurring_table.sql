-- Create recurring_transactions table if not exists
CREATE TABLE IF NOT EXISTS recurring_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recurring_type recurringtransactiontype NOT NULL,
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    loan_id INTEGER REFERENCES property_loans(id) ON DELETE CASCADE,
    description VARCHAR(500) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    category VARCHAR(100) NOT NULL,
    frequency recurrencefrequency NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE CHECK (end_date IS NULL OR end_date >= start_date),
    day_of_month INTEGER CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)),
    is_active BOOLEAN NOT NULL DEFAULT true,
    paused_at TIMESTAMP,
    last_generated_date DATE,
    next_generation_date DATE,
    notes VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT check_source_entity_required CHECK (
        (recurring_type = 'rental_income' AND property_id IS NOT NULL) OR
        (recurring_type = 'loan_interest' AND loan_id IS NOT NULL) OR
        (recurring_type = 'depreciation' AND property_id IS NOT NULL) OR
        (recurring_type = 'manual')
    )
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_id ON recurring_transactions(id);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_user_id ON recurring_transactions(user_id);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_recurring_type ON recurring_transactions(recurring_type);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_property_id ON recurring_transactions(property_id);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_loan_id ON recurring_transactions(loan_id);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_is_active ON recurring_transactions(is_active);
CREATE INDEX IF NOT EXISTS ix_recurring_transactions_next_generation_date ON recurring_transactions(next_generation_date);
