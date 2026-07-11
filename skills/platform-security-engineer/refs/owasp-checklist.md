# OWASP Top 10 (2021) Scan Checklist

Scan against OWASP Top 10 (2021):

1. **A01: Broken Access Control**
   - [ ] Authorization checks on all routes
   - [ ] No direct object reference without validation
   - [ ] Proper session management

2. **A02: Cryptographic Failures**
   - [ ] No hardcoded secrets
   - [ ] Secure transport (HTTPS/TLS)
   - [ ] Proper encryption at rest

3. **A03: Injection**
   - [ ] SQL injection (parameterized queries)
   - [ ] XSS (output encoding)
   - [ ] Command injection (input validation)
   - [ ] Path traversal (path sanitization)

4. **A04: Insecure Design**
   - [ ] Threat modeling performed
   - [ ] Secure defaults
   - [ ] Defense in depth

5. **A05: Security Misconfiguration**
   - [ ] No debug mode in production
   - [ ] Secure headers configured
   - [ ] Least privilege permissions

6. **A06: Vulnerable Components**
   - [ ] Dependencies up to date
   - [ ] No known CVEs in dependencies

7. **A07: Auth Failures**
   - [ ] Proper password policies
   - [ ] Multi-factor authentication available
   - [ ] Session timeout configured

8. **A08: Data Integrity**
   - [ ] Software/data integrity checks
   - [ ] Artifact signing
   - [ ] CI/CD pipeline security

9. **A09: Logging Failures**
   - [ ] Security events logged
   - [ ] Logs don't contain secrets
   - [ ] Log monitoring configured

10. **A10: SSRF**
    - [ ] URL validation
    - [ ] Network segmentation
    - [ ] Allowlist approach
