package finance

# --- Helper functions ---
is_high_value {
    input.amount > 10000
}

# --- Policies ---

# Allow if amount is small
allow {
    input.amount <= 1000
    not input.is_duplicate
}

# Require CFO approval for high value
allow {
    is_high_value
    input.has_approval == true
}

# Block if it's a known duplicate
allow = false {
    input.is_duplicate == true
}

# Violations reporting for the AI Agent
violations[{"policy_id": "POL-001", "reason": "Amount exceeds $10,000 threshold"}] {
    is_high_value
    not input.has_approval
}

violations[{"policy_id": "POL-004", "reason": "Duplicate payment detected"}] {
    input.is_duplicate == true
}
