TRANSITIONS = {
    ("DRAFT", "SUBMITTED"): {
        "condition": "can_submit",
    },
    ("SUBMITTED", "TESTING"): {
        "condition": "owner_assigned",
    },
    ("TESTING", "APPROVAL"): {
        "condition": "testing_checklist_complete",
    },
    ("APPROVAL", "DEPLOYMENT"): {
        "condition": "approval_checklist_complete",
    },
    ("DEPLOYMENT", "LIVE"): {
        "condition": "deployment_checklist_complete",
    },
    ("SUBMITTED", "REJECTED"): {
        "condition": "valid_rejection_reason",
    },
    ("TESTING", "REJECTED"): {
        "condition": "valid_rejection_reason",
    },
    ("APPROVAL", "REJECTED"): {
        "condition": "valid_rejection_reason",
    },
    ("DEPLOYMENT", "REJECTED"): {
        "condition": "valid_rejection_reason",
    },
}