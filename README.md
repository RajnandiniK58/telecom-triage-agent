# Telecom Triage Agent

An AI-powered support ticket triage agent for telecom customer complaints. Given a free-text complaint, the agent classifies it, assigns a priority, decides which backend system to check, and returns a structured, explainable decision — powered by Google Gemini via LangChain/LangGraph, served through a FastAPI backend, with a Streamlit frontend for demoing.

## How it works

1. A customer complaint (with customer ID and optional location) is sent to the `/triage` API endpoint.
2. A LangGraph-based agent (Gemini 2.5 Flash) analyzes the complaint against a system prompt describing telecom support categories, priority levels (P0/P1/P2), and available lookup tools.
3. The agent returns structured JSON: `category`, `priority`, `next_tool`, `reasoning`, and `why`.
4. The backend then executes the tool the model selected — customer profile lookup, network status lookup, or knowledge base lookup — against local mock data, and returns the combined triage decision + tool result.
5. The Streamlit UI lets you submit a complaint and see the full breakdown: category, priority, selected tool, AI reasoning, and raw tool output.

## Tech stack

- **LLM orchestration:** LangChain (`create_agent`) + LangGraph
- **Model:** Google Gemini 2.5 Flash (`langchain-google-genai`)
- **Backend:** FastAPI
- **Frontend:** Streamlit
- **Validation:** Pydantic
- **Data:** Local JSON files (mock customer, network, and knowledge base records)

## Project structure

```
app/
  main.py       # FastAPI app, exposes POST /triage
  agent.py      # LangGraph agent setup, prompt, JSON parsing, tool dispatch
  llm.py        # Gemini model configuration
  schemas.py    # Pydantic request/response models
  tools.py      # Mock data lookup functions
  data/
    customers.json
    network.json
    knowledge.json
streamlit_app.py # Frontend UI
requirements.txt
```

## Setup

1. Clone the repo and create a virtual environment:
   ```
   git clone https://github.com/RajnandiniK58/telecom-triage-agent.git
   cd telecom-triage-agent
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your Gemini API key:
   ```
   GEMINI_API_KEY=your_key_here
   ```

## Running locally

Start the FastAPI backend:

```
uvicorn app.main:app --reload --port 8000
```

In a separate terminal, start the Streamlit frontend:

```
streamlit run streamlit_app.py
```

Then open the Streamlit URL shown in the terminal (typically `http://localhost:8501`), enter a customer ID, location, and complaint, and click **Analyze Complaint**.

## Example

**Input:** "Network problem since 2 days" (Customer ID: 101, Location: Mumbai)

**Output:**

- Category: `Network Issues`
- Priority: `P0`
- Selected tool: `lookup_network_status`
- Reasoning: the agent identifies a prolonged connectivity issue, checks network status for the given city, and confirms an active outage with degraded signal.

## Notes

- Customer, network, and knowledge base data are mocked via local JSON files for demo purposes — not a live telecom backend.
- The agent's `next_tool` field is produced as structured output from the LLM (not native LangChain tool-calling); the backend then dispatches to the corresponding lookup function based on that field.
