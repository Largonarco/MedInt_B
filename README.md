# Medical Interpreter API

This is a backend API for a web-based Language Interpreter agent designed to facilitate communication between English-speaking clinicians and Spanish-speaking patients during in-person medical visits. The system uses real-time speech translation powered by OpenAI's Realtime API and includes tools for scheduling follow-up appointments and sending lab orders.

## Problem Statement

Non-English speaking patients often face communication barriers with clinicians who do not speak their language. Healthcare providers typically need to hire in-person or virtual interpreters to bridge this gap, which can be costly and logistically challenging.

## Goals

The Medical Interpreter API aims to:

- Interpret speech between an English-speaking clinician and a Spanish-speaking patient in real-time using audio input and text output.
- Support special patient requests, such as "repeat that" ("repite eso" in Spanish), to repeat the clinician's most recent statement.
- Generate a conversation summary at the end of the session, including key medical issues, recommendations, and any detected actions (e.g., scheduling follow-up appointments or sending lab orders).
- Execute actions like scheduling follow-ups and sending lab orders using external tools, simulated via webhook.site.

## Features

- **Real-Time Translation**: Translates Spanish patient audio to English text and English clinician audio to Spanish text verbatim.
- **Special Commands**: Recognizes patient requests like "repite eso" to repeat the clinician's last statement.
- **Conversation Summary**: Provides a summary of the conversation, including medical issues, treatment plans, follow-ups, and lab orders.
- **Action Execution**: Supports scheduling follow-up appointments and sending lab orders via webhook integration.
- **WebSocket Communication**: Uses WebSocket for real-time bidirectional communication between the client and server.

## Technology Stack

- **Python 3.9+**: Core programming language.
- **FastAPI**: Web framework for building the API and handling WebSocket connections.
- **OpenAI Realtime API**: Provides real-time speech-to-text translation and function-calling capabilities.
- **Pydantic**: Data validation and modeling for request/response structures.
- **aiohttp**: Asynchronous HTTP client for sending webhook requests.
- **websocket-client**: WebSocket client for connecting to OpenAI's Realtime API.
- **dotenv**: Environment variable management.

## Project Structure

```
medical-interpreter-api/
├── models.py          # Pydantic models for request/response validation
├── openai_realtime.py # OpenAI Realtime API manager for WebSocket communication
├── server.py          # FastAPI server with WebSocket endpoint
├── tools.py           # ToolManager for executing actions (e.g., follow-ups, lab orders)
├── .env.example       # Example environment variable file
└── README.md          # This file
```

## Setup Instructions

### Prerequisites

- Python 3.9 or higher
- An OpenAI API key with access to the Realtime API (model: gpt-4o-realtime-preview-2024-10-01)
- (Optional) A webhook.site URL for testing action execution

### Installation

1. **Clone the Repository**:

   ```bash
   git clone <repository-url>
   cd medical-interpreter-api
   ```

2. **Create a Virtual Environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   Required packages:

   - fastapi
   - uvicorn
   - pydantic
   - websocket-client
   - python-dotenv
   - aiohttp

4. **Configure Environment Variables**:

   - Copy .env.example to .env:
     ```bash
     cp .env.example .env
     ```
   - Edit .env with your credentials:
     ```
     OPENAI_API_KEY=your-openai-api-key
     WEBHOOK_URL=https://webhook.site/your-webhook-id  # Optional, defaults to webhook.site
     ```

5. **Run the Server**:

   ```bash
   uvicorn server:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at http://localhost:8000, with WebSocket endpoint at ws://localhost:8000/ws.

## Usage

### WebSocket Connection

- Connect to the WebSocket endpoint (`/ws`) to initiate a session.
- Send JSON messages based on the models.py schemas to interact with the interpreter.

### Example Workflow

1. **Connect to OpenAI**:

   ```json
   { "type": "connect" }
   ```

   Response: `{"type": "openai_connected"}`

2. **Send Speech Audio**:

   ```json
   {
   	"type": "begin_conversation",
   	"audio": "<base64-encoded-audio>"
   }
   ```

   Response: Translated text as `text_response_delta` and `text_response_done` messages.

3. **Request Summary**:

   ```json
   { "type": "get_summary" }
   ```

   Response: Summary text via `text_response_done`.

4. **Action Execution**:
   - Doctor says "schedule followup appointment": Triggers schedule_follow_up function.
   - Doctor says "send lab order": Triggers send_lab_order function.
   - Response: `{"type": "action_executed", "action": "<function_name>", "details": {...}}`

### Supported Actions

- **Schedule Follow-Up**: Requires `patientName` and `date` (optional: `reason`).
- **Send Lab Order**: Requires `patientName` and `testType` (optional: `urgency`).

## API Endpoints

- **GET /**: Health check endpoint (`{"status": "online", "service": "Medical Interpreter API"}`).
- **WebSocket /ws**: Real-time communication endpoint.

## Notes

- Audio input must be base64-encoded.
- The system assumes Spanish audio is from the patient and English audio is from the doctor.
- Webhook responses are logged but not processed further; replace WEBHOOK_URL with a real service for production use.
