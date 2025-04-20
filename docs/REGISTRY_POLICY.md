# AgentVault Registry Policy

## 1. Purpose of the Registry

The AgentVault Registry serves as a **public discovery hub** for AI agents compatible with the AgentVault ecosystem and the Agent-to-Agent (A2A) protocol. Its primary purpose is to store and serve standardized **Agent Card metadata** submitted by agent developers.

**The Registry DOES NOT:**

*   Execute or host third-party agents.
*   Handle, store, or process end-user API keys (like OpenAI, Anthropic keys).
*   Proxy or monitor A2A communication between clients and agents.
*   Guarantee the functionality, security, safety, or ethical behavior of the agents listed.

## 2. Agent Card Submissions

*   **Eligibility:** Only authenticated developers who have registered with the AgentVault Registry service (process TBD, currently via API key assigned by maintainers) can submit, update, or deactivate Agent Cards.
*   **Responsibility:** Developers are solely responsible for the accuracy and completeness of the information provided in their submitted Agent Cards, including endpoint URLs, authentication details, descriptions, and links to their own policies.

## 3. Vetting Process

*   **Automated Validation:** Submitted Agent Cards undergo automated validation against the official A2A Agent Card schema (`agentvault.models.AgentCard`) to ensure structural correctness. Basic checks may also be performed to verify the format of the specified A2A endpoint URL.
*   **No Behavioral Vetting:** The AgentVault Registry **does not perform manual reviews or vetting** of the underlying agent's functionality, security practices, data handling procedures, or ethical alignment. Listing in the registry does not imply endorsement or certification by the AgentVault project.

## 4. Content Guidelines (Summary)

Agent Card metadata submitted to the registry must not:

*   Promote or facilitate illegal activities.
*   Contain hateful, discriminatory, or harassing content.
*   Be intentionally deceptive or misleading about the agent's capabilities or purpose.
*   Infringe on the intellectual property rights of others.
*   Link to malicious websites or resources.

(A more detailed content policy may be developed later).

## 5. Reporting Problematic Agents

Users who encounter Agent Cards that appear to violate the Content Guidelines, are misleading, link to non-functional or malicious endpoints, or represent agents engaging in harmful activities are encouraged to report them.

*   **How to Report:** Please send a detailed report including the Agent Card ID (the UUID) and a description of the issue to:

    **`[AgentVault@proton.me]`**



*   **Review Process:** Reports will be reviewed by the AgentVault maintainers based on this policy.

## 6. Enforcement

AgentVault maintainers reserve the right, at their sole discretion, to:

*   Deactivate (soft delete, making `is_active=False`) any Agent Card found to violate the Registry Policy or Content Guidelines.
*   Temporarily or permanently suspend a developer's ability to submit or manage Agent Cards in response to repeated or severe violations.
*   Remove Agent Cards linking to endpoints that are consistently unavailable or return errors indicative of non-compliance with the A2A protocol.

## 7. Disclaimer

The AgentVault Registry is provided "as is". Users interact with third-party agents discovered through this registry **at their own risk**. The AgentVault project makes no warranties regarding the agents listed and is not liable for any damages or issues arising from interactions with those agents. Please review the agent provider's own Terms of Service and Privacy Policy before use.
