# Security Documentation

## Overview

This document outlines the security architecture, best practices, and compliance guidelines for the Nabavki Public Procurement Platform.

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [OWASP Top 10 Protection](#owasp-top-10-protection)
3. [Security Features](#security-features)
4. [Security Best Practices](#security-best-practices)
5. [Vulnerability Reporting](#vulnerability-reporting)
6. [Security Checklist](#security-checklist)
7. [Compliance Guidelines](#compliance-guidelines)

---

## Security Architecture

### Defense in Depth

The platform implements multiple layers of security:

```
┌─────────────────────────────────────┐
│ Layer 1: Network Security           │
│ - Firewall (UFW/iptables)           │
│ - DDoS Protection                   │
│ - Rate Limiting                     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Layer 2: Transport Security         │
│ - TLS 1.2/1.3                       │
│ - Strong Cipher Suites              │
│ - HSTS                              │
│ - Certificate Pinning               │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Layer 3: Application Security       │
│ - CSP Headers                       │
│ - CORS Policy                       │
│ - Security Headers                  │
│ - Input Validation                  │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Layer 4: Authentication & Access    │
│ - JWT Tokens                        │
│ - RBAC                              │
│ - Password Hashing (Argon2)         │
│ - MFA (Optional)                    │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Layer 5: Data Security              │
│ - Encryption at Rest                │
│ - Encryption in Transit             │
│ - SQL Injection Prevention          │
│ - XSS Prevention                    │
└─────────────────────────────────────┘
```

---

## OWASP Top 10 Protection

### A01:2021 - Broken Access Control

**Protection Measures:**
- Role-based access control (RBAC) on all endpoints
- JWT-based authentication with short expiration
- Permission validation at API and database level
- Audit logging of all access attempts

### A02:2021 - Cryptographic Failures

**Protection Measures:**
- TLS 1.2+ for all communications
- Argon2 for password hashing
- AES-256 encryption for sensitive data at rest
- Secure key management with rotation

### A03:2021 - Injection

**Protection Measures:**
- SQLAlchemy ORM with parameterized queries
- Input validation using Pydantic models
- Output encoding for all user-generated content
- Content Security Policy (CSP)

### A04:2021 - Insecure Design

**Protection Measures:**
- Security requirements in design phase
- Threat modeling for critical features
- Security architecture review
- Principle of least privilege

### A05:2021 - Security Misconfiguration

**Protection Measures:**
- Automated security scanning in CI/CD
- Hardened default configurations
- Minimal attack surface (disabled unnecessary features)
- Regular security audits

### A06:2021 - Vulnerable and Outdated Components

**Protection Measures:**
- Automated dependency scanning (Dependabot)
- Regular dependency updates
- Security advisories monitoring
- Component inventory maintenance

### A07:2021 - Identification and Authentication Failures

**Protection Measures:**
- Multi-factor authentication support
- Strong password policy enforcement
- Account lockout after failed attempts
- Secure session management

### A08:2021 - Software and Data Integrity Failures

**Protection Measures:**
- Code signing for deployments
- Integrity checks for critical data
- Audit trails for all modifications
- Backup verification

### A09:2021 - Security Logging and Monitoring Failures

**Protection Measures:**
- Comprehensive logging with ELK stack
- Real-time alerting for security events
- Log integrity protection
- Regular log review

### A10:2021 - Server-Side Request Forgery (SSRF)

**Protection Measures:**
- URL validation and whitelisting
- Network segmentation
- Disable unnecessary protocols
- Input sanitization

---

## Security Features

### 1. Content Security Policy (CSP)

**Location:** `backend/security/csp.py`

**Features:**
- Nonce-based inline script/style protection
- Strict CSP directives
- Report-only mode for testing
- Automatic nonce generation per request

**Configuration:**
```python
from backend.security.csp import CSPMiddleware, CSPConfig

config = CSPConfig(
    report_only=False,
    report_uri="/api/csp-report"
)
app.add_middleware(CSPMiddleware, config=config)
```

### 2. Rate Limiting

**Location:** `backend/security/rate_limiter.py`

**Features:**
- Sliding window algorithm
- Per-endpoint limits
- IP-based and user-based tracking
- Redis backend for distributed systems

**Limits:**
- Login: 5 requests/minute
- Registration: 3 requests/minute
- API calls: 100 requests/minute (free tier)
- Export: 5 requests/5 minutes

### 3. CORS Configuration

**Location:** `backend/security/cors.py`

**Features:**
- Whitelist-based origin validation
- Credential handling
- Preflight caching
- Environment-specific configuration

**Allowed Origins (Production):**
- `https://nabavki.gov.si`
- `https://www.nabavki.gov.si`
- `https://api.nabavki.gov.si`

### 4. Security Headers

**Location:** `backend/security/headers.py`

**Implemented Headers:**
- `Strict-Transport-Security`: Force HTTPS
- `X-Frame-Options`: Prevent clickjacking
- `X-Content-Type-Options`: Prevent MIME sniffing
- `Referrer-Policy`: Control referrer information
- `Permissions-Policy`: Restrict browser features

---

## Security Best Practices

### For Developers

1. **Input Validation**
   - Validate all user input at API boundary
   - Use Pydantic models for type safety
   - Sanitize data before database operations
   - Never trust client-side validation

2. **Authentication & Authorization**
   - Always verify JWT tokens
   - Check permissions before data access
   - Use secure session management
   - Implement proper logout

3. **Data Protection**
   - Never log sensitive data (passwords, tokens)
   - Encrypt sensitive data at rest
   - Use parameterized queries
   - Implement data retention policies

4. **Error Handling**
   - Never expose stack traces to users
   - Log errors securely
   - Return generic error messages
   - Monitor error patterns

5. **Dependencies**
   - Keep dependencies updated
   - Review security advisories
   - Use lock files (requirements.txt, package-lock.json)
   - Scan for vulnerabilities regularly

### For Operations

1. **Server Hardening**
   - Apply firewall rules (`security/firewall-rules.sh`)
   - Configure SSL/TLS properly (`security/ssl-config.conf`)
   - Harden Nginx (`security/nginx-hardening.conf`)
   - Disable unnecessary services

2. **Monitoring**
   - Enable security logging
   - Set up alerts for suspicious activity
   - Monitor rate limit violations
   - Track failed authentication attempts

3. **Backup & Recovery**
   - Automated daily backups
   - Encrypted backup storage
   - Regular restore testing
   - Offsite backup copies

4. **Incident Response**
   - Document incident response plan
   - Define escalation procedures
   - Maintain contact list
   - Conduct regular drills

---

## Vulnerability Reporting

### Responsible Disclosure

We take security seriously. If you discover a security vulnerability, please follow responsible disclosure:

**DO:**
- Report via email: security@nabavki.gov.si
- Provide detailed reproduction steps
- Allow reasonable time for fix (90 days)
- Keep findings confidential until patched

**DON'T:**
- Publicly disclose before fix
- Test on production systems
- Access user data
- Perform denial of service

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)
- Your contact information

### Response Timeline

- **24 hours:** Initial acknowledgment
- **7 days:** Vulnerability assessment
- **30 days:** Fix development
- **90 days:** Public disclosure (coordinated)

---

## Security Checklist

### Pre-Deployment

- [ ] All dependencies updated and scanned
- [ ] Security headers configured
- [ ] CSP policy tested
- [ ] Rate limiting configured
- [ ] CORS whitelist verified
- [ ] SSL/TLS certificates valid
- [ ] Firewall rules applied
- [ ] Secrets rotated
- [ ] Database encrypted
- [ ] Backups configured

### Post-Deployment

- [ ] Security monitoring active
- [ ] Logs being collected
- [ ] Alerts configured
- [ ] Incident response plan ready
- [ ] Security team trained
- [ ] Penetration testing completed
- [ ] Compliance review done
- [ ] Documentation updated

### Regular Maintenance

- [ ] Weekly dependency updates
- [ ] Monthly security reviews
- [ ] Quarterly penetration tests
- [ ] Annual compliance audits
- [ ] Continuous monitoring
- [ ] Log analysis
- [ ] Backup verification
- [ ] Incident drills

---

## Compliance Guidelines

### GDPR Compliance

1. **Data Minimization**
   - Collect only necessary data
   - Implement data retention policies
   - Regular data cleanup

2. **User Rights**
   - Data access requests
   - Right to deletion
   - Data portability
   - Consent management

3. **Data Protection**
   - Encryption at rest and in transit
   - Access controls
   - Audit logging
   - Breach notification procedures

### ISO 27001 Alignment

- Information security policies
- Risk assessment procedures
- Access control policies
- Incident management
- Business continuity planning

### Government Standards

Follow Slovenian government IT security standards:
- SI-CERT guidelines
- National cybersecurity framework
- Public procurement regulations
- Data protection laws

---

## Additional Resources

### Security Tools

- **OWASP ZAP:** Security scanning
- **Trivy:** Container vulnerability scanning
- **Bandit:** Python security linting
- **npm audit:** JavaScript dependency scanning

### Documentation

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Contact

- **Security Team:** security@nabavki.gov.si
- **Incident Response:** incident@nabavki.gov.si
- **General Inquiries:** info@nabavki.gov.si

---

**Last Updated:** 2025-11-22
**Version:** 1.0
**Maintainer:** Security Team
