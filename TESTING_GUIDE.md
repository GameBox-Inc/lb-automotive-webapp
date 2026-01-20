# Manual Testing Guide - Dashboard UX Improvements

## Prerequisites
- Backend running on http://localhost:8000
- Frontend running on http://localhost:5173
- Login credentials: admin / admin123

---

## Test 1: Verify No Duplicate Dollar Signs ✅

### Steps:
1. Open http://localhost:5173 in your browser
2. Login if needed (admin / admin123)
3. View the dashboard (should be the default landing page)
4. Look at any appointment cards that display service prices

### Expected Result:
- Price displays with **ONE** dollar sign only
- Example: "$49.99" or "$150.00"
- **NOT**: "$ $49.99" (duplicate dollar sign)

### What Changed:
- Removed `<DollarSign>` icon component
- Kept `formatPrice()` function which already adds $
- Made price bold for better visibility

### Screenshot to Take:
📸 Capture an appointment card showing the price

---

## Test 2: Auto-Status Update After Confirmation ✅

### Steps:
1. Find an appointment with **Pending** status (yellow badge)
2. Click the green **"Confirm"** button
3. **Immediately observe** (no page refresh needed)

### Expected Results:
- ✅ Status badge changes from yellow "Pending" to green "Confirmed" **instantly**
- ✅ "Confirm" button disappears
- ✅ "Start Repair" button (blue) appears
- ✅ "Reschedule" button remains available
- ✅ No page reload occurs

### What Changed:
- Added optimistic UI updates using `currentStatus` state
- Status changes immediately after successful API call
- Falls back gracefully on error

### Screenshots to Take:
📸 Before: Appointment with "Pending" status and "Confirm" button  
📸 After: Same appointment with "Confirmed" status and "Start Repair" button

---

## Test 3: Staff Assignment Workflow ✅

### Steps (Part A - Open Modal):
1. Find an appointment with **Confirmed** status (green badge)
2. Click the blue **"Start Repair"** button
3. Verify modal opens

### Expected Results (Part A):
- ✅ Modal appears with title: "Assign Staff & Start Repair"
- ✅ Dropdown shows list of active staff members
- ✅ Dropdown shows staff name and role: e.g., "Mike Mechanic (mechanic)"
- ✅ "Assign & Start" button is disabled until you select staff
- ✅ "Cancel" button available

### Steps (Part B - Assign Staff):
4. Select any staff member from dropdown
5. Click **"Assign & Start"** button
6. **Immediately observe** (no page refresh)

### Expected Results (Part B):
- ✅ Modal closes automatically
- ✅ Status badge changes to blue "In Progress" **instantly**
- ✅ Text displays: "Assigned to: **[Staff Name]**"
- ✅ No action buttons shown (appointment is now in progress)
- ✅ No page reload occurs

### What Changed:
- Added conditional button rendering based on status
- Created staff assignment modal with dropdown
- Updates appointment with `status: "in_progress"` and `assigned_staff_id`
- Database now has `assigned_staff_id` column with foreign key to staff table

### Screenshots to Take:
📸 Modal opened showing staff dropdown  
📸 After assignment: "In Progress" status with "Assigned to: [Name]"

---

## Test 4: Dark Mode Compatibility (Optional)

### Steps:
1. Enable dark mode in your browser or OS
2. Refresh the dashboard
3. Open the staff assignment modal

### Expected Results:
- ✅ All colors adapt to dark mode
- ✅ Modal background is dark
- ✅ Text is readable (light colored)
- ✅ Status badges have dark mode variants

---

## Test 5: Error Handling (Optional)

### Steps:
1. Stop the backend server
2. Try to confirm an appointment
3. Restart backend

### Expected Results:
- ✅ Error toast appears: "Failed to confirm appointment"
- ✅ Status DOES NOT change (reverts to original)
- ✅ Button remains clickable for retry

---

## Automated Verification (if browser tools work)

If the browser sub-agent becomes functional, use this checklist:

```javascript
// Test 1: Check price format
const priceText = document.querySelector('.font-semibold.text-gray-900')?.textContent
const hasDuplicateDollar = priceText?.match(/\$.*\$/g)
console.log('Duplicate $ found:', !!hasDuplicateDollar) // Should be false

// Test 2: Verify status
const statusBadge = document.querySelector('.px-3.py-1.rounded-full')?.textContent
console.log('Current status:', statusBadge)

// Test 3: Check staff assignment display
const staffAssignment = document.querySelector('strong')?.textContent
console.log('Assigned to:', staffAssignment)
```

---

## Rollback Instructions (if issues found)

If you encounter problems:

1. **Revert database schema:**
   ```bash
   cd python-backend
   # Backup current database
   copy data\lb_automotive.db data\lb_automotive.db.backup
   ```

2. **Check browser console** for errors (F12 → Console tab)

3. **Check backend logs** in terminal for API errors

---

## Success Criteria Summary

All tests must pass:
- [ ] Test 1: No duplicate dollar signs
- [ ] Test 2: Status updates instantly after confirmation
- [ ] Test 3: Staff assignment workflow works end-to-end
- [ ] Test 4: Dark mode compatible (optional)
- [ ] Test 5: Graceful error handling (optional)

---

## Notes

- **Browser Issue:** Automated browser testing currently blocked by system configuration
- **Manual Testing:** All tests can be verified manually in ~5 minutes
- **Performance:** Changes are lightweight - no performance degradation expected
- **Database:** Schema updated with `assigned_staff_id` column

## Questions or Issues?

If you encounter unexpected behavior:
1. Check browser console (F12) for JavaScript errors
2. Check backend terminal for API errors
3. Verify database was re-initialized (run `python database.py`)
4. Try clearing browser cache and hard refresh (Ctrl+Shift+R)
