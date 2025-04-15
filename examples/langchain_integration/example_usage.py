import asyncio
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add project root to path to find agentvault library if running directly
# This might be needed depending on how you run the example
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent.parent
# sys.path.insert(0, str(project_root)) # Uncomment if needed

try:
    from langchain_core.runnables import RunnableLambda
    from a2a_tool import A2AAgentTool
except ImportError:
    print("Please install required packages: pip install -r requirements.txt")
    exit(1)

# --- Configuration ---
# Replace with a valid agent reference (ID from registry, URL, or local file path)
# For testing, you might use a mock agent ID if your mock server is running
# or a path to a local agent-card.json file for a test agent.
# Ensure any required API keys (e.g., for 'mock-service-id') are configured
# using `agentvault config set mock-service-id --keyring` or environment variables.
# EXAMPLE_AGENT_REF = "test-org/mock-run-agent" # Example ID
EXAMPLE_AGENT_REF = "http://localhost:8001/agent-card.json" # Example URL (if running a local agent)
# EXAMPLE_AGENT_REF = "./path/to/your/agent-card.json" # Example file path

# Optional: Set registry URL if using an agent ID
# os.environ["AGENTVAULT_REGISTRY_URL"] = "http://localhost:8000"

async def main():
    print("--- AgentVault LangChain Tool Example ---")

    if not EXAMPLE_AGENT_REF:
        print("Error: Please set EXAMPLE_AGENT_REF in example_usage.py")
        return

    # Instantiate the tool
    # You can pass the registry URL if needed, otherwise it uses the default
    a2a_tool = A2AAgentTool(registry_url=os.environ.get("AGENTVAULT_REGISTRY_URL", "http://localhost:8000"))

    # Prepare the input for the tool
    tool_input = {
        "agent_ref": EXAMPLE_AGENT_REF,
        "input_text": "Explain the AgentVault A2A protocol in simple terms."
    }

    print(f"\nInvoking tool '{a2a_tool.name}' with input:")
    print(f"  Agent Ref: {tool_input['agent_ref']}")
    print(f"  Input Text: {tool_input['input_text']}")

    try:
        # Invoke the tool directly
        # In a real LangChain app, this would likely be part of a chain or agent
        result = await a2a_tool.ainvoke(tool_input)

        print("\n--- Tool Result ---")
        print(result)
        print("-------------------\n")

    except Exception as e:
        print(f"\n--- Error invoking tool ---")
        logging.exception(f"Error: {e}")
        print("---------------------------\n")

if __name__ == "__main__":
    # Ensure environment variables are loaded if using .env
    # from dotenv import load_dotenv
    # load_dotenv() # Load .env from current directory or parent

    asyncio.run(main())
