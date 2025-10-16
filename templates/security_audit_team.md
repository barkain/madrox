# Security Audit Team Template

## Overview

Deploy a comprehensive security team that performs application security assessment across multiple attack surfaces: static code analysis, dependency vulnerabilities, authentication/authorization, API security, and cryptography implementation.

**Best for**: Pre-release security reviews, compliance assessments (SOC2, HIPAA), penetration testing preparation, security hardening

**Team Size**: 7 instances (1 supervisor + 6 workers)

**Estimated Duration**: 2-4 hours depending on codebase size

---

## Team Structure

### Security Lead (Supervisor)
**Role**: `security_analyst`
**Enable Madrox**: ✅ Required (must spawn team members)

**Responsibilities**:
- Define audit scope and objectives
- Spawn and manage security specialists
- Coordinate parallel security assessments
- Aggregate findings by severity (CVSS scores)
- Produce executive summary and technical report
- Prioritize remediation recommendations

### Team Members (Workers)

All team members must be spawned with `parent_instance_id` set to the Security Lead's instance ID.

#### 1. SAST Analyzer
**Role**: `security_analyst`
**Focus**: Static Application Security Testing
**Deliverables**:
- Code vulnerability scan results
- Hardcoded secrets detection
- SQL injection, XSS, CSRF vulnerabilities
- Insecure coding patterns
- CVSS scored findings

#### 2. Dependency Auditor
**Role**: `security_analyst`
**Focus**: Third-party package vulnerabilities
**Deliverables**:
- Vulnerable package inventory
- CVE mapping for dependencies
- Supply chain risk assessment
- Outdated package identification
- Recommended updates and patches

#### 3. Authentication Specialist
**Role**: `security_analyst`
**Focus**: Authentication and authorization mechanisms
**Deliverables**:
- Authentication flow analysis
- Authorization logic review
- Session management assessment
- Password policy evaluation
- MFA implementation review

#### 4. API Security Specialist
**Role**: `security_analyst`
**Focus**: REST/GraphQL API vulnerabilities
**Deliverables**:
- API endpoint vulnerability scan
- Rate limiting and throttling review
- Input validation assessment
- API authentication (JWT, OAuth) review
- CORS and security headers evaluation

#### 5. Cryptography Analyst
**Role**: `security_analyst`
**Focus**: Encryption and cryptographic implementations
**Deliverables**:
- Encryption algorithm review
- Key management assessment
- TLS/SSL configuration review
- Hashing and salting evaluation
- Cryptographic library usage analysis

#### 6. Security Reporter
**Role**: `technical_writer`
**Focus**: Security report compilation and remediation guidance
**Deliverables**:
- Executive summary with risk scores
- Detailed technical findings report
- Remediation steps for each vulnerability
- Compliance mapping (OWASP Top 10, CWE)
- Prioritized action plan

---

## Workflow Phases

### Phase 1: Audit Planning (10-15 minutes)

**Supervisor Actions**:
1. Spawn Security Lead with `enable_madrox=True`
2. Security Lead spawns 6 security specialists with `parent_instance_id`
3. Define audit scope: codebase paths, API endpoints, dependencies
4. Assign audit domains to each specialist
5. Establish severity criteria (CVSS scoring)

**Communication Pattern**:
- Use `broadcast_to_children` to share audit objectives and scope
- Workers acknowledge using `reply_to_caller` with audit plan

**Success Criteria**:
- All 6 specialists spawned and acknowledged
- Audit scope clearly defined
- CVSS scoring criteria established

### Phase 2: Parallel Security Assessment (60-90 minutes)

**Supervisor Actions**:
1. All 6 specialists perform simultaneous security audits
2. Use `coordinate_instances` with `coordination_type="parallel"`
3. Security Lead monitors progress every 15 minutes
4. Workers report findings in real-time as discovered

**Communication Pattern**:
- Workers use `reply_to_caller` immediately when critical vulnerabilities found
- Security Lead polls `get_pending_replies` every 15 minutes for updates
- Critical findings (CVSS 9.0+) trigger immediate alerts

**Audit Activities by Specialist**:
- **SAST Analyzer**: Scan codebase with pattern matching, AST analysis
- **Dependency Auditor**: Check package.json, requirements.txt, go.mod against vulnerability databases
- **Auth Specialist**: Review authentication code, session handling, authorization logic
- **API Security**: Test API endpoints, review OpenAPI specs, check security headers
- **Crypto Analyst**: Review encryption implementations, key storage, TLS configs
- **Security Reporter**: Begin compiling findings as they arrive

**Success Criteria**:
- All security domains assessed
- Findings categorized by severity
- Critical vulnerabilities reported immediately

### Phase 3: Findings Aggregation (20-30 minutes)

**Supervisor Actions**:
1. Security Lead collects all findings using `get_pending_replies`
2. Aggregate findings by severity: Critical, High, Medium, Low
3. Remove duplicates across specialist reports
4. Calculate aggregate risk score
5. Identify priority vulnerabilities

**Communication Pattern**:
- Use `broadcast_to_children` to share preliminary findings for cross-validation
- Workers use `reply_to_caller` to flag duplicates or related findings

**Success Criteria**:
- All findings aggregated and deduplicated
- Severity distribution calculated
- Priority vulnerabilities identified

### Phase 4: Remediation Planning (30-40 minutes)

**Supervisor Actions**:
1. For each vulnerability, assign to specialist for remediation guidance
2. Specialists provide specific fix recommendations
3. Security Lead reviews and approves remediation plans
4. Estimate effort and timeline for each fix

**Communication Pattern**:
- Use `send_to_instance` to assign remediation planning to specific specialists
- Workers use `reply_to_caller` with remediation details

**Remediation Details**:
- Vulnerable code location
- Recommended fix (code patch or configuration change)
- Alternative approaches
- Effort estimate (hours)
- Priority level

**Success Criteria**:
- All vulnerabilities have remediation plans
- Effort estimates provided
- Prioritized action plan created

### Phase 5: Report Generation (20-30 minutes)

**Supervisor Actions**:
1. Security Reporter compiles comprehensive security report
2. Security Lead reviews and approves final report
3. Generate executive summary with risk scores
4. Deliver final security audit package

**Communication Pattern**:
- Use `send_to_instance` to pass all findings to Security Reporter
- Security Reporter uses `reply_to_caller` to submit draft report
- Security Lead provides final approval

**Success Criteria**:
- Complete security report delivered
- Executive summary with aggregate risk scores
- Detailed technical findings with CVSS scores
- Prioritized remediation roadmap

---

## Communication Protocols

### Real-Time Critical Alerts
**Pattern**: Workers report critical vulnerabilities (CVSS 9.0+) immediately

**Worker Action**:
1. Worker discovers critical vulnerability
2. Worker calls `reply_to_caller` with "[CRITICAL]" prefix
3. Security Lead immediately processes alert

**Example**: "[CRITICAL] SQL Injection in /api/users endpoint (CVSS 9.8)"

### Progress Monitoring
**Pattern**: Security Lead polls every 15 minutes using `get_pending_replies`

**Status Update Format**:
- SAST Analyzer: "Scanned 15 files, found 8 issues: 1 high, 4 medium, 3 low"
- Dependency Auditor: "Audited 42 packages, found 3 vulnerable: 1 critical (CVE-2023-1234)"
- Auth Specialist: "Reviewed authentication flow, found 2 issues: weak password policy, missing MFA"

### Parallel Coordination
**Tool**: `coordinate_instances` with `coordination_type="parallel"`

All 6 specialists work simultaneously during Phase 2, enabling fast comprehensive assessment.

---

## Severity Classification

### CVSS Scoring Guidelines

| Severity | CVSS Range | Priority | Response Time |
|----------|------------|----------|---------------|
| **Critical** | 9.0 - 10.0 | P0 | Immediate fix required |
| **High** | 7.0 - 8.9 | P1 | Fix before release |
| **Medium** | 4.0 - 6.9 | P2 | Fix in next sprint |
| **Low** | 0.1 - 3.9 | P3 | Backlog item |

### CVSS Factors
- **Attack Vector**: Network, Adjacent, Local, Physical
- **Attack Complexity**: Low, High
- **Privileges Required**: None, Low, High
- **User Interaction**: None, Required
- **Scope**: Unchanged, Changed
- **Impact**: Confidentiality, Integrity, Availability (High, Low, None)

---

## Error Handling Strategies

### False Positives
**Symptoms**: Worker reports vulnerability that is not exploitable

**Actions**:
1. Security Lead requests additional validation from specialist
2. Specialist provides detailed analysis of exploitability
3. If false positive confirmed, mark as "Not Applicable" with justification
4. Document false positive for future reference

### Incomplete Assessment
**Symptoms**: Specialist unable to fully assess security domain

**Actions**:
1. Identify missing information or access required
2. Request additional codebase access or documentation
3. Document limitations in final report
4. Recommend manual review for incomplete areas

### Specialist Overload
**Symptoms**: One specialist reports significantly more findings than others

**Actions**:
1. Use `interrupt_instance` to pause overloaded specialist
2. Spawn additional specialist for same domain
3. Distribute findings across specialists
4. Resume with parallel assessment

### Conflicting Recommendations
**Symptoms**: Two specialists provide conflicting remediation advice

**Actions**:
1. Security Lead coordinates discussion via `send_to_instance` to both specialists
2. Specialists use `reply_to_caller` to justify recommendations
3. Security Lead makes final decision based on best practice and context

---

## Vulnerability Categories

### OWASP Top 10 (2021) Coverage

| OWASP Category | Assigned Specialist | Detection Method |
|----------------|---------------------|------------------|
| **Broken Access Control** | Auth Specialist | Code review, endpoint analysis |
| **Cryptographic Failures** | Crypto Analyst | Encryption implementation review |
| **Injection** | SAST Analyzer | Pattern matching, input validation review |
| **Insecure Design** | Security Lead | Architecture review |
| **Security Misconfiguration** | API Security | Configuration review, security headers |
| **Vulnerable Components** | Dependency Auditor | CVE database matching |
| **Authentication Failures** | Auth Specialist | Authentication flow analysis |
| **Data Integrity Failures** | Crypto Analyst | Signature verification, integrity checks |
| **Logging Failures** | SAST Analyzer | Logging pattern review |
| **SSRF** | API Security | Request validation review |

---

## Assessment Examples

### Web Application Audit
**Target**: React + Node.js SaaS application

**Scope**:
- Frontend: React components, client-side routing
- Backend: Express API, PostgreSQL database
- Dependencies: npm packages
- Authentication: JWT-based auth
- APIs: 25 REST endpoints

**Expected Findings**: 10-20 vulnerabilities (typical distribution: 1-2 critical, 3-5 high, 5-10 medium, 2-5 low)

**Duration**: 3 hours

### API Security Audit
**Target**: Public REST API

**Scope**:
- 50 API endpoints
- Rate limiting and throttling
- Input validation
- Authentication (OAuth 2.0)
- CORS configuration

**Expected Findings**: 5-15 vulnerabilities

**Duration**: 2 hours

### Microservices Security Audit
**Target**: Microservices architecture (5 services)

**Scope**:
- Inter-service authentication
- API gateway configuration
- Service-to-service communication
- Secrets management
- Container security

**Expected Findings**: 15-30 vulnerabilities across all services

**Duration**: 4 hours

---

## Resource Constraints

### Per-Worker Limits
- **Max Tokens**: 100,000 tokens per worker
- **Max Cost**: $5.00 per worker ($35 total)
- **Timeout**: 240 minutes (4 hours) per worker
- **Max Codebase Size**: 50,000 lines per worker

### Team-Wide Limits
- **Max Instances**: 7 (1 lead + 6 workers)
- **Total Duration**: 4 hours maximum
- **Total Cost**: $35 maximum
- **Concurrent Assessments**: 6 specialists in parallel

### Audit Scope Limits
- **Codebase Size**: Up to 300,000 lines total
- **API Endpoints**: Up to 100 endpoints
- **Dependencies**: Up to 500 packages

---

## Success Metrics

### Coverage Metrics
- ✅ All OWASP Top 10 categories assessed
- ✅ All dependencies audited against CVE databases
- ✅ All API endpoints reviewed
- ✅ All authentication flows analyzed
- ✅ All cryptographic implementations reviewed

### Finding Metrics
- ✅ All findings have CVSS scores
- ✅ All findings have remediation guidance
- ✅ Findings categorized by OWASP/CWE
- ✅ False positives documented

### Report Quality Metrics
- ✅ Executive summary with aggregate risk score
- ✅ Detailed technical findings report
- ✅ Remediation roadmap with effort estimates
- ✅ Compliance mapping (OWASP, CWE, CVE)
- ✅ Priority action plan

### Timeline Metrics
- ✅ Planning: <15 minutes
- ✅ Assessment: <90 minutes
- ✅ Aggregation: <30 minutes
- ✅ Remediation planning: <40 minutes
- ✅ Report generation: <30 minutes
- ✅ Total: <4 hours

---

## Network Topology

```
Security Lead (Supervisor)
├── SAST Analyzer (Worker)
├── Dependency Auditor (Worker)
├── Authentication Specialist (Worker)
├── API Security Specialist (Worker)
├── Cryptography Analyst (Worker)
└── Security Reporter (Worker)
```

**Hierarchy**: Single-level supervised network
**Communication**: Bidirectional (supervisor ↔ workers)
**Coordination**: Parallel assessment with real-time critical alerts

---

## Compliance Frameworks

### SOC 2 Type II
**Relevant Controls**: Access control, encryption, logging, monitoring
**Specialists**: Auth Specialist, Crypto Analyst, SAST Analyzer

### HIPAA
**Relevant Controls**: Data encryption, access controls, audit logging
**Specialists**: Crypto Analyst, Auth Specialist, SAST Analyzer

### PCI DSS
**Relevant Controls**: Network security, encryption, access control
**Specialists**: API Security, Crypto Analyst, Auth Specialist

### GDPR
**Relevant Controls**: Data protection, encryption, access logging
**Specialists**: Crypto Analyst, SAST Analyzer, Auth Specialist

---

## Common Pitfalls

### ❌ Ignoring False Positives
**Result**: Report bloated with non-exploitable issues
**Solution**: Security Lead validates critical/high findings, documents false positives

### ❌ Incomplete Dependency Audit
**Result**: Missing vulnerable transitive dependencies
**Solution**: Dependency Auditor checks full dependency tree, not just direct dependencies

### ❌ No Remediation Guidance
**Result**: Developers don't know how to fix vulnerabilities
**Solution**: Each finding includes specific remediation steps and code examples

### ❌ Missing CVSS Scores
**Result**: Unable to prioritize fixes
**Solution**: All findings scored using CVSS 3.1 calculator

### ❌ No Executive Summary
**Result**: Leadership lacks visibility into security posture
**Solution**: Security Reporter creates clear executive summary with aggregate risk metrics

---

## Advanced Variations

### Penetration Testing Mode
Add **Exploitation Specialist** worker to actively test vulnerabilities:

```
Security Lead (Supervisor)
├── SAST Analyzer (Worker)
├── Dependency Auditor (Worker)
├── Authentication Specialist (Worker)
├── API Security Specialist (Worker)
├── Cryptography Analyst (Worker)
├── Exploitation Specialist (Worker) [NEW]
└── Security Reporter (Worker)
```

**Team Size**: 8 instances
**Duration**: 5-6 hours
**Focus**: Active exploitation and proof-of-concept development

### Continuous Security Monitoring
Simplified 3-worker team for ongoing security checks:

```
Security Lead (Supervisor)
├── SAST Analyzer (Worker)
├── Dependency Auditor (Worker)
└── Security Reporter (Worker)
```

**Team Size**: 4 instances
**Duration**: 1 hour
**Use Case**: Weekly security scans, CI/CD integration

---

## Template Version

**Version**: 1.0
**Last Updated**: October 2025
**Tested With**: Madrox v1.0, Claude Sonnet 3.5
