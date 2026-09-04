# FreeShop — Location, Messaging, Needs, Temporary Lending & Emergency Aid

You are working inside the existing **FreeShop** repository.

Before making changes, inspect the repository carefully, especially:

- `plan.md`
- backend models, migrations, schemas, services and API routes
- frontend routes, pages, stores and API client
- admin panel implementation
- authentication / phone verification
- existing product/listing request flow
- AZ/EN i18n implementation
- existing tests and smoke tests

Do **not** rewrite the application from scratch.

Extend the existing architecture and conventions.

The current application is a community give-away board. Preserve this fundamental rule:

- no payment processing
- no checkout
- users arrange handover/contact themselves
- admin moderation remains part of the platform
- phone verification/security rules must continue working
- existing functionality must remain backward-compatible

Implement the following features.

---

# 1. LOCATION SUPPORT

Every listing must have a location so users know where the item is located before requesting it.

Example:

> Lənkəran, Azərbaycan

The exact private address must **not** be publicly exposed.

Use a location model suitable for proximity calculations.

Suggested fields:

```text
country
region
city
district nullable
latitude nullable
longitude nullable
location_precision
```

Prefer city/district coordinates rather than the user's exact home coordinates unless the existing architecture has a privacy-safe alternative.

Users should be able to save a default location in their profile.

When creating an item, prefill the user's location but allow changing it.

Display location clearly:

- listing cards
- listing detail page
- need cards
- lending listings
- emergency aid requests

Examples:

```text
📍 Lənkəran
📍 3.4 km uzaqlıqda
```

Never expose exact coordinates through the public API unless required internally.

---

# 2. NEARBY DISCOVERY AND SORTING

Users should be able to discover items near them.

Add sorting/filter options such as:

```text
Yaxınlıqdakı
Ən yeni
Ən çox tələb olunan
```

English:

```text
Nearby
Newest
Most requested
```

If coordinates are available, calculate distance using a reasonable geographic distance algorithm such as Haversine.

The API should support something similar to:

```http
GET /api/v1/products?sort=nearby&lat=...&lng=...&radius_km=...
```

Do not blindly implement this exact API if the existing project has a better pattern. Follow existing conventions.

Recommended radius options:

```text
5 km
10 km
25 km
50 km
100 km
All
```

When a signed-in user has a saved location, use it automatically.

When location is unavailable:

- do not break the page
- fall back to normal/newest ordering
- explain that location can be added to improve nearby results

Privacy rule:

The backend may calculate distance, but clients should not receive another user's precise residential coordinates.

---

# 3. BUYER / GIVER MESSAGING

Add internal messaging between users involved with an item.

Although existing code may use concepts such as seller/buyer internally, keep user-facing terminology consistent with FreeShop's community/give-away positioning.

Users should be able to message each other from:

- listing detail
- an accepted item request
- a need/request post
- a temporary lending listing
- an emergency assistance case where appropriate

Implement conversation/thread based messaging.

Suggested models:

```text
Conversation
- id
- type
- listing_id nullable
- need_id nullable
- lending_id nullable
- emergency_case_id nullable
- created_at

ConversationParticipant
- conversation_id
- user_id
- last_read_at

Message
- id
- conversation_id
- sender_id
- body
- created_at
- edited_at nullable
- deleted_at nullable
```

Prevent arbitrary users from joining conversations.

Only authorized participants should see messages.

Minimum functionality:

- conversation list
- unread count
- send message
- read conversation
- timestamps
- empty state
- pagination for long conversations

Do not implement WebSockets unless the existing architecture supports them cleanly.

Polling or manual refresh is acceptable for the first version.

Protect message endpoints with proper authorization and rate limiting where appropriate.

---

# 4. "MƏNƏ LAZIMDIR" / NEEDS BOARD

Add the reverse side of FreeShop.

Currently users mainly publish things they have.

Users must also be able to publish things they **need**.

Example:

```text
Mənə uşaq arabası lazımdır.
Lənkərandayam.
```

Create a dedicated entity such as:

```text
NeedRequest
```

Suggested fields:

```text
id
user_id
title
description
category_id
status
location fields
quantity_needed
created_at
updated_at
expires_at nullable
moderation_status
```

Possible statuses:

```text
open
partially_fulfilled
fulfilled
closed
expired
```

A user should be able to:

- create a need
- edit their open need
- close it
- mark it fulfilled
- see people offering help
- communicate with potential helpers

Needs should go through moderation before becoming publicly visible unless the existing project architecture strongly suggests another safe approach.

Create a public section:

```text
Ehtiyaclar
Needs
```

Users should be able to browse needs nearby.

Examples:

```text
Yaxınlıqda 7 nəfər uşaq arabası axtarır
Yaxınlıqda 3 nəfərə masa lazımdır
```

---

# 5. WHEN MULTIPLE PEOPLE REQUEST THE SAME ITEM

This is an important FreeShop feature.

Example:

A listing exists for one ladder.

10 people request it.

Only one person can receive it.

When the item is assigned/completed for one person, the other 9 users still represent real local demand.

Do **not** simply delete or hide this information.

Create a mechanism that can convert or represent unsuccessful requests as active demand.

Preferred UX:

After the giver selects the recipient / marks the listing handed over:

- successful request → completed
- remaining requesters → allow their request to appear in the local Needs ecosystem

Do this with user consent.

For example:

```text
Bu əşyanı ala bilmədiniz.
Yaxınlıqda başqa biri eyni əşyanı verəndə sizə xəbər verə bilərik.

[ Ehtiyac kimi saxla ]
[ Bağla ]
```

If the user chooses **Ehtiyac kimi saxla**, create or activate an appropriate `NeedRequest`.

Avoid creating duplicate needs repeatedly for the same user/category/item.

The nearby community should then be able to see aggregated demand.

Example:

```text
Nərdivan
Yaxınlıqda 9 nəfərə lazımdır
```

Do not expose the identities of all requesters publicly.

Show aggregate counts publicly.

Individual identity/contact should only become available through an explicit interaction/authorized conversation.

---

# 6. MATCHING ITEMS WITH NEEDS

When someone creates a new item listing, check whether similar open needs exist nearby.

Do not over-engineer AI matching for v1.

Start with deterministic matching based on:

- category
- normalized title/keywords where reasonable
- geographic distance
- open status

Example:

Someone publishes:

```text
Uşaq arabası
```

The system may show:

```text
Yaxınlıqda 4 nəfər bu tip əşya axtarır.
```

Allow the giver to inspect matching needs.

Likewise, when viewing a need, show potentially matching available listings nearby.

Keep matching logic in a dedicated backend service so it can later be replaced or enhanced.

Example:

```text
app/services/matching.py
```

Avoid putting complex matching rules directly inside API controllers.

---

# 7. TEMPORARY LENDING / BORROWING

Add the ability to lend something temporarily instead of permanently giving it away.

Example:

> I don't need my ladder this week, so another neighbour can borrow it.

Add listing transfer type:

```text
giveaway
loan
```

Existing listings should default to:

```text
giveaway
```

A loan listing may include:

```text
available_from
available_until
max_borrow_days nullable
```

Example UI:

```text
Verilir
Müvəqqəti verilir
```

English:

```text
Give away
Lend temporarily
```

For loan listings, a borrower sends a request.

The owner can approve one borrower.

Track the lifecycle.

Suggested statuses:

```text
available
reserved
borrowed
returned
cancelled
```

Store:

```text
borrowed_at
expected_return_at
returned_at
```

Do not implement money deposits or online payments.

The parties arrange physical handover themselves.

Clearly distinguish temporary loans visually from permanent give-away listings.

Example badge:

```text
Müvəqqəti
```

---

# 8. EMERGENCY / COMMUNITY AID MODE

Add a special admin-controlled assistance feature.

Scenario:

A person's house burns down or another serious local emergency occurs.

The person contacts the admin.

The admin verifies the situation outside the platform according to operational policy.

The admin then creates a special aid case.

Only admins can create/publish an official emergency aid case.

Suggested model:

```text
EmergencyAidCase
```

Fields:

```text
id
title
description
beneficiary_display_name
location
status
verification_note_internal
created_by_admin_id
created_at
updated_at
published_at
closed_at
```

Do not expose private/internal verification information publicly.

Possible statuses:

```text
draft
active
paused
completed
cancelled
```

Each case can contain required items.

Example:

```text
EmergencyAidItem
- emergency_case_id
- title
- category_id nullable
- quantity_needed
- quantity_committed
- quantity_received
- priority
- notes
```

Public example:

```text
Təcili yardım

Lənkəranda yanğın nəticəsində evini itirmiş ailəyə yardım lazımdır.

Lazım olanlar:
✓ 2 yorğan
○ 1 soyuducu
○ uşaq geyimləri
○ masa və stullar
```

Community members should be able to click:

```text
Kömək edə bilərəm
```

and select what they can provide.

Create commitments/offers rather than immediately marking an item received.

Suggested statuses:

```text
offered
accepted
received
cancelled
```

Admin should be able to manage these from the admin panel.

Display progress but avoid manipulative gamification.

This is community aid, not fundraising.

Do not add monetary donations/payments in this task.

---

# 9. HOME / DISCOVERY EXPERIENCE

Update the main browsing experience without making it cluttered.

Potential sections:

```text
Yaxınlıqdakı əşyalar

Yaxınlıqdakı ehtiyaclar

Müvəqqəti verilənlər

Təcili yardım
```

Do not display every section if empty.

Use existing visual design system.

Do not create a second design language.

Preserve the existing Quiet Glass styling, spacing, components and responsive patterns.

Mobile UX is important.

---

# 10. USER PROFILE

Extend user profile with:

```text
My listings
My needs
My loaned items
My borrowed items
My conversations
My aid commitments
Location
```

Existing profile flows must keep working.

---

# 11. ADMIN PANEL

Extend the existing admin panel rather than creating a separate admin application.

Add management areas for:

```text
Needs moderation
Emergency aid cases
Emergency aid commitments
Reported conversations/messages if reporting is implemented
Loan disputes/status correction if necessary
```

Reuse existing table, form, status and moderation patterns.

Emergency cases must have:

- create
- edit
- publish
- pause
- complete
- manage needed items
- view community offers
- mark an offered item received

---

# 12. NOTIFICATIONS

If the project already has a notification abstraction, extend it.

Otherwise implement at least in-app notifications where reasonably possible.

Useful events:

```text
Someone messaged you
Your item request was accepted
Your item request was not selected
Someone nearby posted an item matching your need
Someone needs an item similar to one you posted
Your loan request was accepted
Item return date is approaching
Emergency aid offer was accepted
```

Do not add an external push/SMS dependency unless already supported.

Keep notification architecture extensible.

---

# 13. DATABASE AND MIGRATIONS

Use Alembic migrations.

Do not manually mutate the production database.

Maintain compatibility with existing data.

Existing products/listings must continue working after migration.

Where new fields are added to existing tables, provide safe defaults/nullability during migration.

Avoid destructive migrations.

Review indexes carefully.

Add indexes useful for:

- moderation status
- active status
- creation date
- category
- location filtering where practical
- conversation participants
- unread/query patterns

SQLite remains the current database, so do not introduce PostGIS-specific requirements.

Design the location abstraction so moving to PostgreSQL/PostGIS later remains possible.

---

# 14. API QUALITY

Follow existing FastAPI conventions.

Keep:

```text
router
schema
service
model/repository
```

responsibilities appropriately separated according to the existing codebase.

Do not place all business logic in route functions.

Authorization must be enforced server-side.

Never rely only on frontend hiding.

Add API error codes/messages consistent with existing patterns.

Regenerate frontend OpenAPI types if this repo already does so.

---

# 15. SECURITY AND PRIVACY

Pay special attention to location and messaging privacy.

Requirements:

- do not publish exact home addresses
- do not expose raw private coordinates unnecessarily
- users cannot read conversations they do not participate in
- users cannot alter another user's needs/listings
- only admins can create official emergency cases
- emergency internal verification notes are admin-only
- rate-limit messaging/spam-sensitive endpoints where appropriate
- sanitize/validate user-generated text according to existing project patterns
- respect soft-delete/history patterns already used by the project
- preserve phone verification requirements where appropriate

Avoid exposing phone numbers directly in public listing APIs.

Contact data should only be returned where the existing authorization/business rules permit it.

---

# 16. INTERNATIONALIZATION

Every new user-facing string must exist in both:

```text
AZ
EN
```

Use the project's existing flat dot-namespaced translation system.

Do not hardcode Azerbaijani or English strings inside components.

Ensure:

```bash
npm run i18n:check
```

passes.

Azerbaijani terminology should be natural.

Suggested terminology:

```text
Nearby → Yaxınlıqdakı
Newest → Ən yeni
Needs → Ehtiyaclar
I need this → Mənə lazımdır
Temporary loan → Müvəqqəti vermə
Borrow → Müvəqqəti götür
Return → Qaytar
Emergency aid → Təcili yardım
I can help → Kömək edə bilərəm
Messages → Mesajlar
Distance → Məsafə
```

Adjust wording where better Azerbaijani UX copy is appropriate.

---

# 17. FRONTEND

Use existing:

- React
- TypeScript
- routing
- stores/state patterns
- API client
- Tailwind/design tokens
- shared components

Do not introduce a new frontend framework or large state library unless absolutely necessary.

Implement responsive views for:

```text
mobile
tablet
desktop
```

Important components likely include:

```text
LocationPicker
DistanceBadge
SortSelector
NeedCard
NeedForm
ConversationList
ConversationThread
MessageComposer
LoanBadge
LoanRequestPanel
EmergencyAidCard
EmergencyAidDetail
AidCommitmentForm
```

Names are suggestions; conform to existing naming conventions.

---

# 18. TESTS

Do not consider the work finished without tests.

Backend tests should cover at minimum:

### Location

- location validation
- nearby ordering
- radius filtering
- privacy of coordinates

### Messaging

- create/open authorized conversation
- send message
- unauthorized user cannot read conversation
- unread state

### Needs

- create need
- moderation
- public visibility
- nearby filtering
- fulfillment
- conversion of unsuccessful product request into need

### Matching

- same/similar category match
- distance constraint
- closed needs excluded

### Loan

- loan listing creation
- request
- approval
- borrowed state
- return state
- invalid state transitions rejected

### Emergency aid

- only admin creates official case
- public user can view active case
- user can offer help
- admin accepts/marks received
- internal admin fields remain private

Frontend tests should cover critical interaction flows.

Extend smoke tests to cover at least one happy path for each major new area.

---

# 19. QUALITY GATES

Before considering the implementation complete, run all relevant project checks.

Backend:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Frontend:

```bash
npm run lint
npm run typecheck
npm test
npm run i18n:check
npm run build
```

If the application can be run locally, also execute the relevant smoke tests.

Do not silence failing tests or weaken type checking just to make CI green.

Fix root causes.

---

# 20. IMPLEMENTATION PROCESS

Work in this order:

## Phase 1 — Repository analysis

Inspect the existing architecture and produce a concise implementation plan.

Identify:

- existing models to extend
- existing request lifecycle
- auth rules
- moderation patterns
- frontend routing
- reusable UI components
- migration strategy

Do not start coding until you understand these.

## Phase 2 — Domain model

Implement migrations/models for:

- location/profile extension
- needs
- messaging
- lending
- emergency aid

Keep models normalized and avoid unnecessary duplication.

## Phase 3 — Services and API

Implement domain logic, authorization and endpoints.

## Phase 4 — Frontend

Implement user flows and admin flows.

## Phase 5 — Matching and nearby ranking

Add location-based discovery and needs/listing matching.

## Phase 6 — Tests and hardening

Run all quality gates and fix regressions.

---

# 21. IMPORTANT PRODUCT RULES

Use these rules when implementation details are ambiguous.

### Rule A

FreeShop remains a community exchange/give-away platform, not an ecommerce marketplace.

### Rule B

Location is primarily for determining whether handover is practical.

Do not expose private residential location.

### Rule C

Demand is valuable.

When one item has multiple requesters, unsuccessful requests should be capable of becoming visible local demand instead of disappearing.

### Rule D

A temporary loan is different from giving an item permanently.

Model the lifecycle explicitly.

### Rule E

Emergency assistance is admin-verified and admin-controlled.

Ordinary users cannot label their own posts as official emergency cases.

### Rule F

Public pages should expose aggregated demand, not unnecessarily expose vulnerable people's identities.

### Rule G

Do not implement payments.

### Rule H

Preserve all existing behavior unless a migration/change is explicitly necessary for these features.

---

# 22. DELIVERABLES

At the end, provide:

1. Summary of architecture changes.
2. Database tables/columns added or changed.
3. API endpoints added or changed.
4. Frontend routes/pages/components added.
5. Security/privacy decisions.
6. Matching/location algorithm used.
7. Migration notes.
8. Tests added.
9. Commands run and their results.
10. Any remaining limitations or recommended follow-up work.

Also update `plan.md` so the authoritative project specification accurately describes the new functionality, data model, API and design decisions.

Do not leave important architecture decisions only in code comments.

---

# SUCCESS CRITERIA

The implementation is successful when this scenario works end-to-end:

1. A user in Lənkəran publishes an item.
2. Nearby users see that it is located in Lənkəran and can sort by proximity.
3. A user can message the giver.
4. Several people request the item.
5. The giver chooses one person.
6. Other requesters may convert their unsuccessful request into an active need.
7. Nearby people can see aggregated local demand for that item/category.
8. A future matching item can be connected to those needs.
9. A user can alternatively publish an item as a temporary loan.
10. The loan can move through request → approved → borrowed → returned.
11. An admin can publish an emergency assistance case listing specific required items.
12. Community members can commit items and communicate about delivery.
13. Exact private addresses and private conversations remain protected.
14. All functionality works in both Azerbaijani and English.
15. Existing FreeShop functionality and tests remain working.

When a requirement conflicts with the current repository architecture, prefer the existing architectural conventions, explain the conflict, and implement the smallest clean extension rather than introducing a parallel system.