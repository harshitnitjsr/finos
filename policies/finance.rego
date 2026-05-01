package finance.compliance

import rego.v1

default allow := false

# Main entry point to get all violations
violations contains {"policy_id": "POL-001", "policy_name": "High-Value Approval", "reason": "Transaction > 5000 requires explicit approval", "action": "review"} if {
    input.amount > 5000
    not input.has_approval
}

violations contains {"policy_id": "POL-002", "policy_name": "Unknown Vendor Block", "reason": "Vendor risk score is too high", "action": "review"} if {
    input.vendor_risk_score > 50
}

violations contains {"policy_id": "POL-003", "policy_name": "Spend Spike Alert", "reason": "Amount is 3x above category average", "action": "review"} if {
    input.amount > (input.category_average * 3)
}

violations contains {"policy_id": "POL-004", "policy_name": "Duplicate Payment Block", "reason": "Invoice marked as duplicate in DB", "action": "reject"} if {
    input.is_duplicate == true
}

violations contains {"policy_id": "POL-005", "policy_name": "International Payment Review", "reason": "International transaction over 1000", "action": "review"} if {
    input.is_international == true
    input.amount > 1000
}

# If there are no violations, it's allowed
allow if {
    count(violations) == 0
}
