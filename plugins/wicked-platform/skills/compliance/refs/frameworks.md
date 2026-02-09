# Compliance Frameworks Reference

Detailed framework-specific requirements and controls.

## SOC2 Type II

Service Organization Control 2 - Trust Services Criteria

### Common Criteria

**CC6.1 - Logical and Physical Access Controls**:
- Implement authentication mechanisms
- Enforce authorization checks (RBAC)
- Apply least privilege principle
- Segregate duties where appropriate
- Review access rights periodically

**CC6.6 - Encryption of Confidential Information**:
- Encrypt data at rest (AES-256 recommended)
- Use secure key management systems
- Rotate encryption keys regularly
- Document encryption standards

**CC6.7 - Transmission of Data**:
- Use TLS 1.2+ for data in transit
- Validate certificates
- Disable weak ciphers
- Implement secure API authentication

**CC7.2 - System Monitoring**:
- Log security events
- Monitor for anomalies
- Alert on suspicious activities
- Retain logs per policy (90+ days typical)

### Evidence Requirements

- Access control policies and implementation
- Encryption verification (code + config)
- Network security configurations
- Monitoring and alerting setup
- Log retention policies

## HIPAA

Health Insurance Portability and Accountability Act

### Administrative Safeguards (§164.308)

**164.308(a)(3) - Workforce Security**:
- Authorization and supervision
- Clearance procedures
- Termination procedures

**164.308(a)(4) - Information Access Management**:
- Isolate healthcare clearinghouse functions
- Access authorization
- Access establishment and modification

### Physical Safeguards (§164.310)

**164.310(d) - Device and Media Controls**:
- Disposal procedures
- Media re-use procedures
- Accountability tracking
- Data backup and storage

### Technical Safeguards (§164.312)

**164.312(a) - Access Control**:
- Unique user identification (required)
- Emergency access procedure (required)
- Automatic logoff (addressable)
- Encryption and decryption (addressable)

**164.312(b) - Audit Controls**:
- Implement hardware/software to record and examine activity
- Track access to PHI

**164.312(c) - Integrity**:
- Mechanism to authenticate ePHI
- Ensure data not improperly altered/destroyed

**164.312(d) - Person/Entity Authentication**:
- Verify identity before access

**164.312(e) - Transmission Security**:
- Integrity controls (addressable)
- Encryption (addressable)

### PHI Handling

Protected Health Information includes:
- Individual health information
- Treatment records
- Payment information
- Healthcare operations data
- Any individually identifiable health data

### Business Associate Agreements (BAA)

Required when third parties access PHI:
- Define permitted uses
- Safeguard requirements
- Reporting obligations
- Termination provisions

## GDPR

General Data Protection Regulation (EU)

### Core Principles (Article 5)

**Lawfulness, Fairness, Transparency**:
- Valid legal basis for processing
- Clear privacy notices
- Transparent data practices

**Purpose Limitation**:
- Collect for specific purposes
- Don't process incompatibly

**Data Minimization**:
- Adequate and relevant only
- Limited to necessary

**Accuracy**:
- Keep data accurate
- Allow corrections

**Storage Limitation**:
- Keep only as long as needed
- Define retention periods

**Integrity and Confidentiality**:
- Appropriate security measures
- Protect against unauthorized processing

### Key Rights

**Article 15 - Right of Access**: Provide copy of data
**Article 16 - Right to Rectification**: Correct inaccurate data
**Article 17 - Right to Erasure**: Delete data ("right to be forgotten")
**Article 18 - Right to Restriction**: Limit processing
**Article 20 - Data Portability**: Provide in machine-readable format
**Article 21 - Right to Object**: Stop processing

### Security Requirements (Article 32)

**Technical Measures**:
- Pseudonymization and encryption
- Ongoing confidentiality, integrity, availability
- Restore availability after incident
- Regular testing and evaluation

**Organizational Measures**:
- Data protection by design
- Data protection by default
- Data protection impact assessments (DPIA)
- Data Protection Officer (DPO) where required

### Breach Notification

**72-hour rule** (Article 33):
- Notify supervisory authority within 72 hours
- Document nature of breach
- Describe likely consequences
- Outline remediation measures

**Individual notification** (Article 34):
- When high risk to rights and freedoms
- Clear and plain language
- Timely notification

## PCI DSS

Payment Card Industry Data Security Standard

### Build and Maintain Secure Network

**Req 1 - Firewalls**:
- Install and maintain firewall configuration
- Restrict connections between untrusted networks
- Prohibit direct public access to cardholder data

**Req 2 - Configuration**:
- Don't use vendor defaults
- Remove unnecessary services
- Document and implement security configurations

### Protect Cardholder Data

**Req 3 - Stored Data Protection**:
- Keep cardholder data storage to minimum
- Don't store sensitive auth data after authorization
- Mask PAN when displayed (show only first 6 and last 4)
- Render PAN unreadable (encryption, truncation, hashing)
- Document and implement key management

**Req 4 - Transmission Encryption**:
- Use strong cryptography (TLS 1.2+)
- Never send unprotected PANs via email, IM, SMS
- Document encryption policies

### Maintain Vulnerability Management

**Req 5 - Anti-Virus**:
- Deploy on all systems commonly affected by malware
- Keep definitions current
- Generate logs and review periodically

**Req 6 - Secure Development**:
- Patch critical vulnerabilities within one month
- Develop applications based on secure coding guidelines
- Separate development/test from production
- Review custom code for vulnerabilities

### Implement Strong Access Control

**Req 7 - Need-to-Know**:
- Limit access to business need-to-know
- Implement access control systems
- Default "deny-all" setting

**Req 8 - Unique IDs**:
- Assign unique ID to each person
- Implement two-factor authentication
- Use strong passwords/passphrases
- Lock out after max failed attempts

**Req 9 - Physical Access**:
- Control physical access to cardholder data
- Distinguish employees from visitors
- Log and monitor physical access

### Monitor and Test Networks

**Req 10 - Logging**:
- Log all access to cardholder data
- Log privileged user actions
- Secure audit logs
- Review logs daily
- Retain logs at least one year (3+ months immediately available)

**Req 11 - Security Testing**:
- Test for wireless access points quarterly
- Run internal/external vulnerability scans quarterly
- Perform penetration testing annually
- Use intrusion detection/prevention systems

### Maintain Information Security Policy

**Req 12 - Policy**:
- Establish, publish, maintain security policy
- Implement risk assessment process
- Develop usage policies for technologies
- Assign information security responsibilities
- Implement security awareness program

## Cardholder Data Environment (CDE)

Scope includes:
- Systems that store, process, or transmit cardholder data
- Systems that provide security services (auth, logging, etc.)
- Systems that impact security of above

### Data Elements

**Cardholder Data**:
- Primary Account Number (PAN)
- Cardholder Name
- Expiration Date
- Service Code

**Sensitive Authentication Data** (NEVER store post-auth):
- Full magnetic stripe data
- CAV2/CVC2/CVV2/CID
- PINs/PIN blocks
