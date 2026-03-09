# Audit Evidence Checklists: GDPR & PCI DSS

Checklists for GDPR and PCI DSS audit evidence collection.

## GDPR Audit Evidence

### Lawfulness of Processing Evidence

- [ ] Legal basis documentation for each processing activity
- [ ] Consent forms (if consent-based)
- [ ] Consent withdrawal mechanism
- [ ] Records of processing activities (Article 30)
- [ ] Legitimate interest assessments (if applicable)
- [ ] Contracts with data processors
- [ ] Privacy notices
- [ ] Cookie consent mechanism (if applicable)

### Data Subject Rights Evidence

- [ ] Data access request procedures
- [ ] Data portability export capability
- [ ] Data rectification procedures
- [ ] Data erasure procedures
- [ ] Processing restriction procedures
- [ ] Objection handling procedures
- [ ] Automated decision-making disclosures
- [ ] Response time tracking (30-day compliance)

### Data Protection Principles Evidence

- [ ] Data minimization analysis
- [ ] Purpose limitation documentation
- [ ] Data accuracy procedures
- [ ] Storage limitation/retention policies
- [ ] Security measures (Article 32)
- [ ] Accountability documentation
- [ ] Privacy by design assessments
- [ ] Privacy by default configurations

### Security Measures Evidence

- [ ] Pseudonymization/encryption implementations
- [ ] Access control mechanisms
- [ ] Backup and recovery procedures
- [ ] Security testing reports
- [ ] Vulnerability assessments
- [ ] Penetration test results
- [ ] Disaster recovery tests
- [ ] Security incident log

### International Transfers Evidence

- [ ] Adequacy decision documentation
- [ ] Standard contractual clauses (SCC)
- [ ] Binding corporate rules (BCR) if applicable
- [ ] Transfer impact assessments (TIA)
- [ ] Supplementary measures for transfers

### Organizational Evidence

- [ ] DPO appointment (if required)
- [ ] DPO contact information publication
- [ ] Data protection impact assessments (DPIA) for high-risk processing
- [ ] Processor agreements (Article 28)
- [ ] Joint controller agreements (if applicable)
- [ ] Training records

### Breach Response Evidence

- [ ] Breach detection procedures
- [ ] Breach notification procedures (<72 hours)
- [ ] Breach register/log
- [ ] Supervisory authority notifications
- [ ] Individual notifications (if high risk)
- [ ] Breach impact assessments

## PCI DSS Audit Evidence

### Requirement 1 - Firewall Configuration

- [ ] Firewall configuration standards
- [ ] Current firewall rulesets
- [ ] Firewall rule review logs (semi-annual)
- [ ] Network diagram showing CDE boundaries
- [ ] DMZ configuration
- [ ] Wireless access point configurations
- [ ] Quarterly wireless scans

### Requirement 2 - Configuration Management

- [ ] Configuration standards documentation
- [ ] Hardening guides
- [ ] Baseline configurations
- [ ] System inventory
- [ ] Evidence of vendor default changes
- [ ] Unnecessary services disabled
- [ ] Configuration change logs

### Requirement 3 - Data Protection

- [ ] Data retention and disposal policy
- [ ] Data flow diagram
- [ ] Evidence sensitive auth data not stored
- [ ] PAN masking implementation
- [ ] Encryption implementation
- [ ] Key management procedures
- [ ] Cryptographic key inventory
- [ ] Key custodian assignments
- [ ] Key rotation logs

### Requirement 4 - Transmission Encryption

- [ ] Encryption policy for PAN transmission
- [ ] TLS configuration (1.2+ minimum)
- [ ] Certificate inventory
- [ ] Trusted key and certificate management
- [ ] End-user messaging security (no unencrypted PAN)

### Requirement 5 - Anti-Malware

- [ ] Anti-virus software deployment
- [ ] AV definition update logs
- [ ] AV scan logs
- [ ] AV policy and procedures

### Requirement 6 - Secure Systems

- [ ] Patch management procedures
- [ ] Critical patch deployment records (<30 days)
- [ ] Secure coding guidelines
- [ ] Code review procedures
- [ ] Vulnerability management process
- [ ] Change control procedures
- [ ] Development/test/production separation
- [ ] Test data procedures (no live PAN)

### Requirement 7 - Access Restriction

- [ ] Access control policy
- [ ] Need-to-know documentation
- [ ] Access rights based on job function
- [ ] Default deny-all configuration
- [ ] Access authorization records
- [ ] Privilege assignment documentation

### Requirement 8 - Authentication

- [ ] User identification procedures
- [ ] Unique user ID assignment
- [ ] Two-factor authentication implementation (remote + admin)
- [ ] Password policy (7+ chars, complexity)
- [ ] Account lockout configuration (6 attempts)
- [ ] Session timeout (15 min idle)
- [ ] Password history (4 different)
- [ ] Password change every 90 days
- [ ] Shared account prohibition
- [ ] User account review (quarterly)

### Requirement 9 - Physical Access

- [ ] Facility access controls
- [ ] Visitor authorization and logging
- [ ] Badge system
- [ ] Escort procedures for visitors
- [ ] Media storage controls
- [ ] Secure media destruction procedures
- [ ] Media tracking logs
- [ ] Device inventory

### Requirement 10 - Logging and Monitoring

- [ ] Audit log policy
- [ ] Log configuration (what to log)
- [ ] Cardholder data access logs
- [ ] Admin action logs
- [ ] Log integrity protection
- [ ] Daily log review procedures
- [ ] Log review evidence
- [ ] Log retention configuration (1 year, 3 months online)
- [ ] Time synchronization (NTP)

### Requirement 11 - Security Testing

- [ ] Quarterly external vulnerability scans (ASV)
- [ ] Quarterly internal vulnerability scans
- [ ] Scan remediation tracking
- [ ] Annual penetration testing
- [ ] Penetration test results and remediation
- [ ] IDS/IPS deployment and configuration
- [ ] IDS/IPS alert review logs
- [ ] File integrity monitoring (FIM) configuration
- [ ] FIM alerts and review
- [ ] Change detection procedures

### Requirement 12 - Security Policy

- [ ] Information security policy
- [ ] Policy annual review
- [ ] Risk assessment (annual)
- [ ] Acceptable use policies
- [ ] User acknowledgment of policies
- [ ] Security awareness program materials
- [ ] Training completion records
- [ ] Personnel screening procedures
- [ ] Incident response plan
- [ ] Incident response testing
- [ ] Service provider management procedures
- [ ] Service provider list
- [ ] Service provider assessments
