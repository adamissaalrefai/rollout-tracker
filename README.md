# rollout-tracker

A small Jira-like platform for tracking partner rollout requests (e.g.
"enable 5G Data for Partner X") as they move through a fixed approval
workflow: Draft → Submitted → Testing → Approval → Deployment → Live,
with Rejected and On Hold as side states.

## Setup

```bash
git clone <repo-url>
cd rollout-tracker
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py seed_demo
python manage.py runserver
```

Then visit `http://localhost:8000/requests/`.

## Demo logins

`seed_demo` creates one user per role, all with the password `demo1234`:

| Username           | Role        |
|--------------------|-------------|
| demo_viewer        | Viewer      |
| demo_requester     | Requester   |
| demo_engineer      | Engineer    |
| demo_approver      | Approver    |
| demo_coordinator   | Coordinator |

It also creates 25 fake partners, checklist templates for all five
services, and roughly 120 fake requests spread across every step
(including some Live, Rejected, and On Hold), each with real history
behind it — since they're pushed through the actual transition engine,
not faked directly.

## Running tests

```bash
python manage.py test
```

Covers: role/permission checks, the two request-form validation rules,
the working-days late-detection function (including the Friday→Monday
edge case from the spec), the transition engine against every row of
the rules table, append-only enforcement on the history log, and page-
level tests proving permission checks hold even when a URL is typed
directly rather than just hiding a button.

## What's built

- Data models, roles/permissions, admin
- The transition engine — one central `perform_transition()` function
  that every page (and the admin) must go through to move a request
- Append-only history log
- Two-people-editing protection (optimistic locking via a version
  number), covering both direct edits and transitions
- Request list with search/filter and CSV export
- Request detail: checklist ticking, comments, attachments, permission-
  aware transition buttons, history timeline
- CSV bulk import for creating multiple draft requests at once
- Email notifications (console backend) on every step change
- Late detection (working-days calculation, Saturday/Sunday weekend)

## What's not built yet

- Dashboard
- REST API

## Decisions made along the way

- **Weekend days for late detection**: Saturday/Sunday, matching a
  Western work week — this project's target region uses a
  Friday/Saturday weekend, so this may need revisiting depending on
  which calendar the business actually wants.
- **Late-detection target days per step**: the spec doesn't give real
  numbers for "how many days is too long" per step, so placeholder
  values are used in `core/filters.py` — replace with real numbers once
  confirmed.
- **Service isn't its own database table** — it's a fixed set of
  choices, since the spec gives exactly 5 fixed options with no extra
  data attached to each one.
- **Email notifications are implemented as a Django signal** on the
  `Request` model (firing whenever `current_step` changes and is saved)
  rather than being called directly inside `perform_transition()`. This
  keeps the engine focused on validating and executing the business
  rule, with notification as a separate concern — and it means the
  email fires correctly regardless of what code changes the step.

## Known open items

- The transitions table (`workflow/steps.py`) marks Draft as an
  "active" step, which by a literal reading of the spec would mean
  Draft → On Hold should be allowed — but the transitions table only
  wires On Hold from Submitted onward. Left as-is pending a decision on
  whether holding an unsubmitted draft makes sense.