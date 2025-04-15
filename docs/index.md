# Welcome to AgentVault

**AgentVault is an open-source ecosystem designed to facilitate secure and interoperable communication between AI agents (Agent-to-Agent or A2A).**

In a world with increasingly sophisticated and numerous AI agents, the ability for them to discover each other, communicate reliably, and collaborate securely is paramount. AgentVault provides the foundational infrastructure and tooling to make this possible, fostering a more connected and capable AI landscape.

This documentation serves as the central hub for understanding, using, and contributing to the AgentVault project.

## Why AgentVault?

*   **Interoperability:** Based on emerging open standards like A2A, AgentVault enables agents built by different developers on different platforms to communicate effectively.
*   **Discovery:** The central AgentVault Registry allows users and agents to find other agents based on capabilities, identity, and other metadata described in standardized "Agent Cards".
*   **Security:** Provides tools for secure credential management and incorporates security considerations like TEE awareness into its design.
*   **Developer Experience:** Offers Python libraries (Client & Server SDK), a command-line tool, and testing utilities to simplify the development and integration of A2A-compliant agents.
*   **Open Source:** Licensed under Apache 2.0, encouraging community involvement, transparency, and preventing vendor lock-in.

## Getting Started

1.  **Understand the Concepts:** Familiarize yourself with the [Core Concepts](concepts.md).
2.  **Explore the Architecture:** See how the components fit together in the [Architecture Overview](architecture.md).
3.  **Installation:** Follow the [Installation Guide](installation.md) to set up the CLI or development environment.
4.  **User Guide:** Learn how to use the [Command Line Interface (CLI)](user_guide/cli.md).
5.  **Developer Guides:** Dive into building or interacting with agents using the:
    *   [Client Library (`agentvault`)](developer_guide/library.md)
    *   [Server SDK (`agentvault-server-sdk`)](developer_guide/server_sdk.md)
    *   [Registry API (`agentvault_registry`)](developer_guide/registry.md)
    *   [Testing Utilities (`agentvault-testing-utils`)](developer_guide/testing.md)

## Project Components

*   **[AgentVault Library (`agentvault`)](developer_guide/library.md):** Core Python client library.
*   **[AgentVault CLI (`agentvault_cli`)](user_guide/cli.md):** Command-line tool for users.
*   **[AgentVault Registry (`agentvault_registry`)](developer_guide/registry.md):** Central discovery API and UI.
*   **[AgentVault Server SDK (`agentvault-server-sdk`)](developer_guide/server_sdk.md):** Tools for building A2A agents.
*   **[Testing Utilities (`agentvault-testing-utils`)](developer_guide/testing.md):** Shared testing resources.
*   **[Examples](../../examples/):** Practical usage examples.

*(This documentation is under active development alongside the AgentVault project.)*
