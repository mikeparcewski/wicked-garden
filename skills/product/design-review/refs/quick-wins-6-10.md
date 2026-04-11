# Quick Wins 6-10: Errors, Empty States, Spacing, Hover, Components

Fast design improvements with high visual impact. Five quick wins covering UX polish and component consolidation.

## 6. Improve Error Messages (1-2 hours)

**Impact**: Better UX, reduced support tickets

**Before:**
```jsx
<div className="error">Error</div>
<div className="error">Invalid</div>
<div className="error">Failed</div>
```

**After:**
```jsx
<Alert severity="error">
  <AlertTitle>Upload Failed</AlertTitle>
  File size exceeds 5MB limit. Please compress your image and try again.
  <Button variant="text" onClick={handleRetry}>Retry</Button>
</Alert>

<Alert severity="error">
  <AlertTitle>Invalid Email</AlertTitle>
  Please enter a valid email address (e.g., user@example.com)
</Alert>
```

**Error message formula:**
1. **What happened**: "Upload failed"
2. **Why**: "File size exceeds 5MB"
3. **What to do**: "Please compress and try again"
4. **Action**: Retry button

**Steps:**
1. Audit all error messages (20 minutes)
2. Rewrite with formula above (40 minutes)
3. Add helpful actions where possible (30 minutes)
4. Test error flows (20 minutes)

---

## 7. Add Empty States (1-2 hours)

**Impact**: Reduces confusion, guides users

**Before:**
```jsx
{items.length === 0 && null}
```

**After:**
```jsx
{items.length === 0 ? (
  <EmptyState
    icon={<InboxIcon />}
    title="No items yet"
    description="Get started by creating your first item"
    action={
      <Button onClick={handleCreate}>
        Create Item
      </Button>
    }
  />
) : (
  <ItemList items={items} />
)}
```

**Empty state formula:**
1. **Icon**: Visual representation
2. **Title**: Clear statement of empty state
3. **Description**: Why it's empty or what it's for
4. **Action**: How to add first item

**Steps:**
1. Find all lists/collections (15 minutes)
2. Create EmptyState component (30 minutes)
3. Add to each list (30 minutes)
4. Test (15 minutes)

---

## 8. Standardize Spacing (2-3 hours)

**Impact**: Visual rhythm, professional polish

**Before:**
```css
.card { padding: 17px; margin-bottom: 23px; }
.section { padding: 35px 19px; }
.list-item { margin-bottom: 11px; }
```

**After:**
```css
.card {
  padding: var(--space-4);        /* 16px */
  margin-bottom: var(--space-5);  /* 24px */
}

.section {
  padding: var(--space-8) var(--space-4);  /* 48px 16px */
}

.list-item {
  margin-bottom: var(--space-3);  /* 12px */
}
```

**Steps:**
1. Find all spacing values (30 minutes)
   ```bash
   wicked-garden:search "(padding|margin):\s*[0-9]+(px|rem)" --type css
   ```
2. Create spacing scale (10 minutes)
3. Round to nearest scale value (60 minutes)
4. Visual QA (30 minutes)

**Scale recommendation**: 4px base or 8px base

---

## 9. Add Hover States (1 hour)

**Impact**: Interactivity feedback, modern feel

**Before:**
```css
.card {
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
/* No hover! */
```

**After:**
```css
.card {
  background: white;
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-base);
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

**Elements to add hover to:**
- Clickable cards
- Buttons (if missing)
- Links
- Icon buttons
- List items (if interactive)

**Steps:**
1. Identify interactive elements (10 minutes)
2. Add hover styles (30 minutes)
3. Add smooth transitions (10 minutes)
4. Test (10 minutes)

---

## 10. Consolidate Similar Components (2-3 hours)

**Impact**: Easier maintenance, consistency

**Before:**
```jsx
<PrimaryButton>Submit</PrimaryButton>
<SecondaryButton>Cancel</SecondaryButton>
<BlueButton>Submit</BlueButton>
<LargeButton>Continue</LargeButton>
```

**After:**
```jsx
<Button variant="primary">Submit</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="primary">Submit</Button>
<Button variant="primary" size="lg">Continue</Button>
```

**Steps:**
1. Identify duplicate components (20 minutes)
2. Design unified API (20 minutes)
3. Create consolidated component (60 minutes)
4. Migrate usage (45 minutes)
5. Test (30 minutes)
6. Delete old components (15 minutes)
