# Information Security Policy

## Purpose
This policy defines the minimum security requirements for employees, contractors,
and systems handling company or customer data.

## Access Control
- Access to production systems requires multi-factor authentication (MFA).
- Access is granted on a least-privilege basis and reviewed quarterly.
- Shared accounts are prohibited; every login must map to an individual identity.
- Access must be revoked within 24 hours of an employee's departure or role change.

## Data Classification
Data is classified into three tiers:
1. **Public** — approved for external release (marketing materials, job postings).
2. **Internal** — for employee use only (internal wikis, roadmaps, meeting notes).
3. **Confidential** — customer data, financial records, credentials. Requires
   encryption at rest and in transit, and access logging.

## Password and Credential Requirements
- Minimum 14 characters, no reuse of the last 10 passwords.
- Credentials must never be committed to source control. Use the company secrets
  manager for all API keys, tokens, and database passwords.
- Personal devices used to access company systems must have disk encryption
  and a screen lock enabled.

## Incident Response
Any suspected security incident (unauthorized access, data leak, lost device,
phishing attempt) must be reported to the Security team within 1 hour of
discovery via the #security-incidents channel or security@company.internal.
Do not attempt to independently investigate or remediate a suspected breach —
escalate immediately so evidence is preserved.

## Third-Party Vendors
Vendors with access to Confidential data must complete a security review and
sign a data processing agreement (DPA) before integration. Vendor access is
reviewed annually.

## Enforcement
Violations of this policy may result in disciplinary action up to and including
termination, and may be reported to law enforcement where required by law.
