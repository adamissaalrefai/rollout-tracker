TRANSITIONS = {

    ("DRAFT", "SUBMITTED"): {
        "condition": "can_submit",
        "allowed_roles": ["Requester", "Coordinator"],
    },

    ("SUBMITTED", "TESTING"): {
        "condition": "owner_assigned",
        "allowed_roles": ["Coordinator"],
    },

    ("TESTING", "APPROVAL"): {
        "condition": "testing_checklist_complete",
        "allowed_roles": ["Engineer", "Coordinator"],
    },

    ("APPROVAL", "DEPLOYMENT"): {
        "condition": "approval_checklist_complete",
        "allowed_roles": ["Approver"],
    },

    ("DEPLOYMENT", "LIVE"): {
        "condition": "deployment_checklist_complete",
        "allowed_roles": ["Engineer", "Coordinator"],
    },

    ("SUBMITTED", "REJECTED"): {
        "condition": "valid_rejection_reason",
        "allowed_roles": ["Approver", "Coordinator"],
    },

    ("TESTING", "REJECTED"): {
        "condition": "valid_rejection_reason",
        "allowed_roles": ["Approver", "Coordinator"],
    },

    ("APPROVAL", "REJECTED"): {
        "condition": "valid_rejection_reason",
        "allowed_roles": ["Approver", "Coordinator"],
    },

    ("DEPLOYMENT", "REJECTED"): {
        "condition": "valid_rejection_reason",
        "allowed_roles": ["Approver", "Coordinator"],
    },

    ("SUBMITTED", "ON_HOLD"): {
        "allowed_roles": ["Coordinator"],
    },

    ("TESTING", "ON_HOLD"): {
        "allowed_roles": ["Coordinator"],
    },

    ("APPROVAL", "ON_HOLD"): {
        "allowed_roles": ["Coordinator"],
    },

    ("DEPLOYMENT", "ON_HOLD"): {
        "allowed_roles": ["Coordinator"],
    },

}