# AgentVault TEE Profile (v0.1 - Declarative)

This document outlines the initial support for Trusted Execution Environments (TEEs) within the AgentVault ecosystem, focusing on declaration and discovery.

**Version:** 0.1 (Declarative Phase)

## Overview

Trusted Execution Environments (TEEs) like Intel SGX, AMD SEV, AWS Nitro Enclaves, etc., provide hardware-level isolation to protect the confidentiality and integrity of code and data being processed. Leveraging TEEs can significantly enhance the security posture of AI agents, especially when handling sensitive information or performing critical tasks.

AgentVault aims to facilitate the use of TEEs by allowing agents to declare their TEE usage and enabling clients to discover agents based on this capability.

## Agent Card Declaration

Agents running within a TEE can declare this capability in their `agent-card.json` file within the `capabilities` object, using the optional `teeDetails` field.

**Schema:**

*   **`capabilities.teeDetails`** (Optional Object): Contains details about the TEE. If present, indicates the agent utilizes a TEE.
    *   **`type`** (String, Required if `teeDetails` is present): An identifier for the specific TEE technology used. Examples: `"Intel SGX"`, `"AMD SEV-SNP"`, `"AWS Nitro Enclaves"`, `"Azure Confidential Computing"`, `"Confidential Space"`. Standardized identifiers are preferred, but custom strings are allowed.
    *   **`attestationEndpoint`** (String, Optional, Format: URL): A URL where clients can potentially obtain or verify an attestation document for the specific TEE instance hosting the agent. The format and verification process for the attestation document are specific to the TEE type and are **outside the scope of this profile version**.
    *   **`publicKey`** (String, Optional): A public key associated with the TEE instance, potentially used for establishing secure channels or verifying attestations. The format (e.g., PEM, JWK) depends on the TEE type and attestation protocol.
    *   **`description`** (String, Optional): A human-readable description of the TEE setup, its purpose, or the guarantees it provides for this agent.

**Example `agent-card.json` Snippet:**

```json
{
  "schemaVersion": "1.0",
  // ... other fields ...
  "capabilities": {
    "a2aVersion": "1.0",
    // ... other capabilities ...
    "teeDetails": {
      "type": "AWS Nitro Enclaves",
      "attestationEndpoint": "https://attestation.example-agent.com/verify",
      "description": "Agent runs within an AWS Nitro Enclave for enhanced data confidentiality during processing."
    }
  },
  // ... other fields ...
}
```

## Discovery via Registry

The AgentVault Registry API (`agentvault_registry`) supports filtering agents based on their TEE declaration:

*   **`GET /api/v1/agent-cards/?has_tee=true`**: Returns only agents whose Agent Card includes the `capabilities.teeDetails` object (regardless of its content).
*   **`GET /api/v1/agent-cards/?has_tee=false`**: Returns only agents whose Agent Card *does not* include the `capabilities.teeDetails` object.
*   **`GET /api/v1/agent-cards/?tee_type=<type_string>`**: Returns only agents where `capabilities.teeDetails.type` matches the provided `<type_string>` (case-insensitive comparison recommended for the registry implementation). Example: `?tee_type=AWS%20Nitro%20Enclaves`.

The public Registry Web UI also includes a filter option to show only TEE-enabled agents.

## Current Scope & Limitations (v0.1)

*   **Declarative Only:** This version focuses solely on allowing agents to *declare* their TEE usage and enabling *discovery* based on that declaration.
*   **No Automated Verification:** AgentVault clients (library, CLI) **do not** automatically perform TEE attestation verification based on the `attestationEndpoint` or `publicKey`. Implementing robust and generic attestation verification is complex due to the variety of TEE technologies and attestation protocols.
*   **Client Responsibility:** Clients wishing to verify an agent's TEE status must currently implement the verification logic themselves, specific to the declared `teeDetails.type` and using the provided `attestationEndpoint` or other out-of-band mechanisms.
*   **No Secure Channel Guarantee:** Declaring TEE usage does not automatically establish a TEE-secured communication channel. Standard transport security (HTTPS) is still required.

## Future Work

*   Researching and potentially integrating standardized TEE attestation verification libraries or protocols into the `agentvault` client library.
*   Defining mechanisms for establishing secure communication channels directly with TEE enclaves, possibly leveraging the declared `publicKey`.
*   Standardizing `teeDetails.type` identifiers.
