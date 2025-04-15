# Security Policy for AgentVault

## Introduction

The AgentVault project prioritizes security. We appreciate the efforts of security researchers and the community in helping us maintain a secure ecosystem. This document outlines our policy for reporting security vulnerabilities.

## Scope

This policy applies to the following components and repositories within the AgentVault project:

*   **`agentvault` (Core Library):** Located in the `agentvault_library/` directory.
*   **`agentvault-registry` (Registry API):** Located in the `agentvault_registry/` directory.
*   **`agentvault-cli` (CLI Client):** Located in the `agentvault_cli/` directory.
*   **`agentvault-server-sdk` (Server SDK):** Located in the `agentvault_server_sdk/` directory.

Vulnerabilities discovered in third-party agents listed in the registry should be reported directly to the respective agent provider according to their own security policy. The AgentVault registry itself only stores metadata.

## Reporting a Vulnerability

We appreciate responsible disclosure. Please report any suspected security vulnerabilities **privately** to ensure the security of our users and the ecosystem.

**Preferred Method:**

*   **GitHub Private Vulnerability Reporting:** If you are reporting via GitHub, please use the built-in "Report a vulnerability" feature within the main AgentVault repository. This allows for secure communication and tracking. [*Note: Link to GitHub Security Tab needs to be updated once available.*]

**Alternative Method:**

*   **Email:** If you cannot use GitHub's reporting feature, you can email your report to `[CONTACT_EMAIL_PLACEHOLDER]` (*Note: Replace placeholder before production*). Use a clear subject line like "Security Vulnerability Report: AgentVault [Component Name]". **Please use this email address for vulnerability reports ONLY.** Other inquiries will not be addressed here.

**What to Include:**

Please include the following details in your report:

*   **Component:** Which part of AgentVault is affected (library, registry, CLI, SDK)?
*   **Version:** The specific version number or commit hash, if known.
*   **Description:** A clear and concise description of the vulnerability.
*   **Steps to Reproduce:** Detailed steps required to reproduce the vulnerability. Include code snippets, configuration details, or specific API requests if applicable.
*   **Potential Impact:** Your assessment of the potential impact of the vulnerability.
*   **Contact Information:** Your name or alias and contact email address for follow-up.

## Our Commitment

*   We will acknowledge receipt of your vulnerability report, typically within 48 business hours.
*   We will investigate the report promptly and work to validate the vulnerability.
*   We will keep you informed of our progress during the investigation and remediation process.
*   We aim to address critical vulnerabilities as quickly as possible.
*   We will coordinate public disclosure with you after a fix is available, potentially issuing security advisories and crediting you for your discovery (unless you prefer to remain anonymous).

## Safe Harbor

We consider security research and vulnerability reporting activities conducted under this policy to be authorized and beneficial. We will not pursue legal action against individuals who report vulnerabilities in good faith, adhere to this policy, and do not cause harm to AgentVault, its users, or its infrastructure.

Thank you for helping keep AgentVault secure.
