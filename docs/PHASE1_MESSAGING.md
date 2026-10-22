# Phase 1: Proposal Communication System ✅

**Status:** Complete & Ready for Testing  
**Date:** 2026-10-15  
**Branch:** main

## What Was Built

### 1. Database Layer

**Migration: `0005_proposal_messaging`** (Applied ✅)

Three new tables:

#### `proposal_messages`
- Two-way async messaging between CSR and NGO
- Columns: id, proposal_id, sender_id, sender_type (CSR/NGO), content, created_at, read_at
- Indexed on: proposal_id, sender_id, created_at

#### `proposal_timelines`
- Tracks activity state per proposal
- Columns: id, proposal_id, last_activity_at, reply_deadline, waiting_on, updated_at
- Unique constraint on proposal_id (one timeline per proposal)

#### `proposal_escalations` (Foundation for Phase 2)
- Tracks when no reply for extended periods
- Columns: id, proposal_id, reason, escalated_at, admin_notes, status, resolved_at
- Indexed on: proposal_id, status

---

### 2. Backend API

**Location:** `backend/app/routers/proposals.py`  
**Models:** Added to `backend/app/models.py`  
**Schemas:** Added to `backend/app/schemas.py`

#### New Endpoints

```
GET  /proposals/{proposal_id}/messages
     Returns: List[ProposalMessageOut]
     Get all messages in a proposal thread
     
POST /proposals/{proposal_id}/messages
     Payload: ProposalMessageIn { content: str }
     Returns: ProposalMessageOut
     Send a new message (auto-updates timeline)
     
GET  /proposals/{proposal_id}/timeline
     Returns: ProposalTimelineOut
     Get timeline info + escalation status
     - days_since_activity: int
     - waiting_on: "CSR" | "NGO"
     - is_overdue: bool
```

#### Features

✅ **Message Persistence** - All messages saved to DB  
✅ **Timeline Auto-Update** - last_activity_at updated on every message  
✅ **Sender Tracking** - Automatic detection of sender type (CSR vs NGO)  
✅ **Access Control** - Only CSR/NGO members can message on their proposals  
✅ **Audit Logging** - Every message logged in audit trail  

---

### 3. Frontend Components

#### `components/ProposalMessages.tsx`
Reusable message thread component with:
- Message list (scrollable, auto-scrolls to latest)
- Message input box
- Timeline bar (shows "Waiting for X for Y days")
- Auto-refresh every 10 seconds
- Send status feedback
- Error handling

#### `/ngo/proposals/[id]/page.tsx` (New)
NGO proposal detail page with:
- Full proposal text (problem, solution, outcomes, timeline)
- Budget & metadata
- Embedded message thread
- Status badge
- "Update Proposal" button if changes requested
- Back navigation

#### `/csr/proposals/[id]/page.tsx` (New)
CSR proposal review page with:
- Full proposal review section
- Embedded message thread
- Decision section (Approve / Request Changes)
- Status tracking
- Navigation to approve/request-changes pages

---

## Data Flow

```
CSR creates Opportunity → NGO shortlisted → NGO submits Proposal
                                              ↓
                                    [NEW] Message Thread Opens
                                    CSR can ask questions
                                    NGO can clarify
                                    Timeline tracked
                                              ↓
                                    CSR Approves or Requests Changes
                                    (Approved → Commitment created)
```

## How to Test

### 1. Create Test Data

```bash
# Login as CSR → Create an Opportunity
# Login as NGO → Create a Proposal
```

### 2. Test Messaging

**CSR Side:**
1. Go to `/csr/proposals`
2. Click "Review Details" on a proposal
3. See the message thread section
4. Type a message and hit Send
5. Verify message appears immediately

**NGO Side:**
1. Go to `/ngo/proposals`
2. Click "View Details" on the same proposal
3. See the CSR's message
4. Send a reply
5. Verify timeline updates ("Waiting for CSR")

### 3. Test Timeline

- Send message as CSR
- Check timeline shows "Waiting for NGO"
- Switch to NGO
- Check it shows days_since_activity

### 4. Verify in Database

```sql
-- Check messages
SELECT * FROM proposal_messages;

-- Check timeline
SELECT * FROM proposal_timelines;

-- Check audit logs
SELECT * FROM audit_events WHERE action = 'proposal.message_sent';
```

---

## API Testing

### Using cURL

```bash
# Get messages
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/proposals/PROPOSAL_ID/messages

# Send message
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}' \
  http://localhost:8000/proposals/PROPOSAL_ID/messages

# Get timeline
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/proposals/PROPOSAL_ID/timeline
```

---

## Files Changed/Created

### Backend
- ✅ `backend/migrations/versions/0005_proposal_messaging.py` - Migration
- ✅ `backend/app/models.py` - Added 3 new models
- ✅ `backend/app/schemas.py` - Added 3 new schemas
- ✅ `backend/app/routers/proposals.py` - Added 3 endpoints

### Frontend
- ✅ `frontend/components/ProposalMessages.tsx` - New component
- ✅ `frontend/app/ngo/proposals/[id]/page.tsx` - New page
- ✅ `frontend/app/csr/proposals/[id]/page.tsx` - New page

---

## What's Next (Phase 2 & 3)

### Phase 2: Notifications
- Notification table
- Trigger notifications on new message
- Notification center UI

### Phase 3: Admin Escalation
- Auto-create escalation record if no reply for 5+ days
- Admin dashboard showing pending escalations
- Admin can message directly
- Auto-reminders

### Phase 4: AI (Optional)
- Auto-suggest next reply
- Summarize conversation threads
- Sentiment detection
- Draft responses

---

## Known Limitations

1. **Messages are plain text** - No markdown or rich text yet
2. **No file attachments** - Can be added in Phase 2
3. **No read receipts** - read_at field exists but not shown in UI
4. **No typing indicators** - Could be added with WebSockets
5. **No message editing/deletion** - Immutable for now (audit trail)

---

## Architecture Decisions

| Decision | Reasoning |
|----------|-----------|
| ProposalTimeline in separate table | Allows efficient queries for overdue proposals |
| sender_type as string | Simpler than join, no enum needed |
| read_at nullable | Optional read receipts without UI complexity |
| Auto-update timeline | Activity tracking requires minimal effort |
| 10s auto-refresh | Balance between freshness and server load |
| Messages immutable | Audit trail integrity |

---

## Testing Checklist

- [ ] Migration applied without errors
- [ ] Backend starts without import errors
- [ ] Frontend starts and compiles
- [ ] Can navigate to CSR proposal detail page
- [ ] Can see message thread component
- [ ] Can send message as CSR
- [ ] Can see message as NGO
- [ ] Timeline shows correct wait-on state
- [ ] days_since_activity calculates correctly
- [ ] Audit logs record all actions
- [ ] Access control prevents unauthorized messaging

---

**Ready to proceed to Phase 2?** Let me know when you want to add notifications and admin escalation!
