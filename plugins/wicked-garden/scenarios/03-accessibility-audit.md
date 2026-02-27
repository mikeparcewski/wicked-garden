---
name: accessibility-audit
title: Accessibility Audit Before Release
description: Conduct WCAG 2.1 AA audit on UI components before production release
type: ux
difficulty: intermediate
estimated_minutes: 10
---

# Accessibility Audit Before Release

This scenario tests wicked-product's accessibility expertise: identifying WCAG violations, prioritizing fixes, and providing actionable remediation guidance.

## Setup

Create a React component with common accessibility issues:

```bash
# Create test project
mkdir -p ~/test-wicked-product/a11y-audit/src/components
cd ~/test-wicked-product/a11y-audit

# Create a modal component with typical a11y problems
cat > src/components/Modal.tsx <<'EOF'
import React, { useState } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Modal({ isOpen, onClose, title, children }: ModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <div className="close-btn" onClick={onClose}>X</div>
        </div>
        <div className="modal-body">
          {children}
        </div>
        <div className="modal-footer">
          <div className="btn btn-secondary" onClick={onClose}>Cancel</div>
          <div className="btn btn-primary" onClick={onClose}>Submit</div>
        </div>
      </div>
    </div>
  );
}
EOF

# Create a form component with a11y issues
cat > src/components/LoginForm.tsx <<'EOF'
import React, { useState } from 'react';

export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = () => {
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    // Submit logic
  };

  return (
    <div className="login-form">
      <img src="/logo.png" />
      <h1 style={{ color: '#999' }}>Welcome Back</h1>

      <input
        type="text"
        placeholder="Email address"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
      />

      {error && <span style={{ color: '#ff6666' }}>{error}</span>}

      <div className="submit-btn" onClick={handleSubmit}>
        Sign In
      </div>

      <p>
        Don't have an account?
        <span style={{ color: 'blue', cursor: 'pointer' }} onClick={() => {}}>
          Sign up here
        </span>
      </p>
    </div>
  );
}
EOF

# Create styles with contrast issues
cat > src/styles.css <<'EOF'
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
}

.modal-title {
  font-size: 18px;
  color: #666;
}

.close-btn {
  cursor: pointer;
  color: #aaa;
}

.btn {
  padding: 10px 20px;
  cursor: pointer;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #eee;
  color: #999;  /* Low contrast */
}

.error-text {
  color: #ff6666;  /* Low contrast on white */
}
EOF
```

## Steps

1. **Run Accessibility Audit**
   ```bash
   /wicked-product:ux-review src/components --focus a11y
   ```

   **Expected**: The a11y-expert should identify:
   - Non-semantic buttons (`<div>` instead of `<button>`)
   - Missing form labels
   - Missing image alt text
   - Color contrast violations
   - Focus management issues with modal

2. **Verify WCAG Mapping**

   Each issue should reference the specific WCAG criterion:
   - 1.1.1 Non-text Content (missing alt)
   - 1.4.3 Contrast (Minimum)
   - 2.1.1 Keyboard
   - 4.1.2 Name, Role, Value

3. **Check Severity Classification**

   Issues should be classified by level:
   - **Critical (Level A)**: Keyboard access, missing names
   - **Major (Level AA)**: Contrast, focus visible
   - **Minor (Level AAA)**: Enhanced requirements

4. **Verify Fix Recommendations**

   Each issue should have a specific fix:
   ```
   Issue: <div> used as button
   Fix: Change to <button> or add role="button" tabIndex={0} onKeyDown handler
   ```

   Not vague like "improve accessibility"

5. **Check Modal-Specific Issues**

   The audit should catch:
   - No focus trap (keyboard can escape modal)
   - No aria-modal or role="dialog"
   - Close button not keyboard accessible
   - Background scroll not locked

## Expected Outcome

- 8-12 specific accessibility issues identified
- Each mapped to WCAG success criterion
- Severity helps prioritize fixes
- Code examples for remediation
- Summary of POUR compliance

## Success Criteria

- [ ] Identifies `<div onClick>` as non-semantic button (at least 4 instances)
- [ ] Catches missing `alt` on img element
- [ ] Flags low contrast text (color: #999 on white)
- [ ] Notes missing `<label>` elements on form inputs
- [ ] Modal focus trap issue identified
- [ ] Each issue has WCAG criterion reference
- [ ] Fixes include actual code, not just descriptions
- [ ] Output organized by severity (Critical > Major > Minor)
- [ ] POUR summary shows which principles have issues

## Value Demonstrated

**Real-world value**: Accessibility issues are often discovered in production by users who can't use your product, leading to both user harm and legal risk. Manual accessibility testing is time-consuming and requires specialized expertise that many teams lack.

wicked-product's `/ux-review --focus a11y` acts as an expert accessibility consultant, catching the common mistakes that automated tools like axe also find, plus contextual issues like modal focus management that require understanding code intent.

The WCAG criterion mapping helps teams understand why something is an issue (not just "screen readers don't work"), and the specific code fixes reduce the "now what?" paralysis that often follows accessibility audits. For teams without dedicated accessibility expertise, this provides professional-level guidance at the speed of AI.
