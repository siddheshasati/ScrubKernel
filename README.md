# ScrubKernel

A small agentic AI OS automation project providing sample components and demo workspaces.

**Architecture**
- Core app modules live in the `app/` package (agents, auth, UI, workspace helpers).
- `demo_workspace/` contains a minimal FastAPI demo service used for quick verification.
- `generated_projects/` contains example generated project templates.

**Tech stack**
- Python 3.11+
- FastAPI for demo microservices
- Simple file-based project templates for examples

**Workflow**
**Current status & Future work**
- In progress: centralizing agent manifests, improving auth flows, adding runtime orchestration dashboard.
- Planned features: automated test harnesses, CI/CD templates, containerization (Docker + k8s manifests).
- Constraints: secrets must never be committed (this repo excludes `.venv` and caches), large binary artifacts should be stored externally.

If you want, I can add a short CONTRIBUTING.md with developer setup steps and tests.
# ScrubKernel: Agentic-AI-OS-Automation

An enterprise-style autonomous agent system designed for secure OS-level task automation inside a governed local workspace.

This project demonstrates how AI agents can safely interact with files, execute controlled operations, maintain audit visibility, and follow human-approved workflows using the Perceive → Plan → Execute → Reflect architecture.

🚀 Overview

Traditional chatbots only respond with text.

This system goes beyond conversation by enabling an AI agent to:
- Understand user intent
- Reason about actions
- Use tools securely
- Interact with a controlled workspace
- Request approval for sensitive operations
- Maintain complete operational audit trails

The application focuses on safe autonomous execution, combining AI reasoning with enterprise-grade governance and sandboxed automation.

✨ Core Capabilities
- Secure file inspection and workspace interaction
- Autonomous task planning and execution
- Human-in-the-loop approval workflows
- Real-time reasoning and streaming responses
- Enterprise audit logging
- Protocol-driven tool invocation
- Sandboxed execution environment
- Security boundary enforcement
- Path traversal and unsafe access protection

🧠 Agent Workflow

The system follows an iterative autonomous execution loop:

Perceive → Plan → Execute → Reflect

1. Perceive

The agent analyzes the user request and understands the required operation.

2. Plan

The agent determines:
- which tool should be used?
- whether the action is allowed?
- whether approval is required?

3. Execute

The system securely executes the requested operation inside the sandboxed workspace.

4. Reflect

The agent summarizes the result, updates logs, and returns the final response.


🔐 Security & Governance

Security is built into every layer of execution.

1. Sandboxed Workspace

All operations are isolated within a controlled local environment.

2. Protected Operations

The system blocks:
- Path traversal attacks
- Unauthorized file access
- Unsafe external operations
- Destructive actions without approval
- Human Approval Layer
- Sensitive actions can require explicit user approval before execution.

3. Audit Logging

Every tool invocation is recorded with:
- timestamp
- execution status
- operation details
- protocol metadata

⚙️ System Design

The platform combines:
- conversational AI
- protocol-based tool execution
- secure workspace management
- real-time UI streaming
- governance controls

The architecture is designed to simulate how enterprise AI agents can safely automate operational workflows while maintaining transparency and control.

📡 Execution Flow

User Request
      ↓
Intent Understanding
      ↓
Reasoning & Planning
      ↓
Security Validation
      ↓
Tool Execution
      ↓
Audit Logging
      ↓
Response Reflection
      ↓
Final Output


🛠️ Technology Stack
1. Layer Technology
- AI Model: Groq Llama 3.3 70B
- Agent Framework	LangChain
2. Frontend Interface:	Streamlit
3. Backend:	Python
4. Protocol Layer:  MCP-style JSON-RPC execution
5. Runtime:	Local sandboxed workspace


📌 Key Highlights
- Autonomous AI agent execution
- Enterprise-style governance model
- Secure protocol-driven automation
- Human-in-the-loop safety controls
- Real-time streaming interactions
- Auditable AI operations
- Modular and extensible architecture

🎯 Example Use Cases
- Intelligent workspace management
- Automated operational assistance
- AI-driven file inspection
- Secure autonomous workflows
- Governance-aware AI systems
- Enterprise AI agent demonstrations
- Human-supervised automation systems

🔮 Future Enhancements
- Multi-agent orchestration
- Extended protocol integrations
- Cloud execution nodes
- Advanced policy engines
- Persistent memory systems
- Workflow scheduling
- Cross-platform automation support


📄 License

This project is intended for educational, research, and demonstration purposes.
