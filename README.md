# Medical Interpreter API

A FastAPI-based backend service designed to facilitate real-time communication between Spanish-speaking patients and English-speaking doctors. This API leverages OpenAI's Realtime API for speech-to-text translation and integrates tools for scheduling follow-up appointments and sending lab orders.

## Features

- **Real-Time Translation**: Translates audio input from Spanish (patient) to English (doctor) and vice versa using OpenAI's Realtime API.
- **WebSocket Support**: Handles real-time bidirectional communication for audio and text streaming.
- **Conversation History**: Maintains session-based conversation logs for doctors and patients.
- **Action Tools**: Supports scheduling follow-up appointments and sending lab orders via configurable webhooks.
- **Summary Generation**: Generates concise summaries of medical conversations on demand.
- **CORS Enabled**: Allows cross-origin requests for flexible frontend integration.

## Prerequisites

- Python 3.9+
- An OpenAI API key with access to the Realtime API (model: gpt-4o-realtime-preview-2024-10-01)
- Optional: A webhook URL for testing tool actions (e.g., webhook.site)

## Installation

1. **Clone the Repository**

```bash
git clone https://github.com/yourusername/medical-interpreter-api.git
cd medical-interpreter-api
```

2. **Set Up a Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**

```bash
pip install -r requirements.txt
```

Note: Create a requirements.txt file with the following dependencies:

```
fastapi==0.115.0
uvicorn==0.31.0
websocket-client==1.8.0
python-dotenv==1.0.1
aiohttp==3.10.5
pydantic==2.9.2
```

4. **Configure Environment Variables**

Create a `.env` file in the root directory and add your OpenAI API key:

```
OPENAI_API_KEY=your-openai-api-key
WEBHOOK_URL=https://webhook.site/your-webhook-id  # Optional, defaults to webhook.site
```

## Running the Application

1. **Start the FastAPI Server**

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: Enables auto-reloading during development.
- The server will be accessible at http://localhost:8000.

2. **Verify the Health Check**

Open a browser or use curl to check the root endpoint:

```bash
curl http://localhost:8000/
```

Expected response:

```json
{ "status": "online", "service": "Medical Interpreter API" }
```

## Usage

### WebSocket Endpoint

Connect to the WebSocket endpoint at `ws://localhost:8000/ws` for real-time communication.

### Message Types

- **connect**: Establishes a connection to OpenAI's Realtime API.

```json
{ "type": "connect" }
```

- **begin_conversation**: Sends audio for translation.

```json
{ "type": "begin_conversation", "audio": "<base64-encoded-audio>" }
```

- **get_summary**: Requests a summary of the conversation.

```json
{ "type": "get_summary" }
```

### Responses

- **session**: Returns a unique session ID.

```json
{ "type": "session", "session_id": "<uuid>" }
```

- **openai_connected**: Confirms OpenAI connection.

```json
{ "type": "openai_connected" }
```

- **text_done**: Translated text response.

```json
{ "type": "text_done", "text": "<translated-text>" }
```

- **audio_response_delta**: Streaming audio chunk.

```json
{ "type": "audio_response_delta", "delta": "<base64-audio-chunk>" }
```

- **response_done**: Final translated response with role.

```json
{ "type": "response_done", "text": "<translated-text>", "role": "doctor|patient" }
```

- **action_executed**: Tool action result.

```json
{"type": "action_executed", "action": "schedule_follow_up", "details": {...}}
```

- **error**: Error message.

```json
{ "type": "error", "message": "<error-message>" }
```

### Example Workflow

1. Connect to the WebSocket and receive a session_id.
2. Send a connect message to initialize OpenAI.
3. Send audio via begin_conversation for translation.
4. Receive translated text and audio responses in real-time.
5. Request a summary with get_summary when needed.

### Tools

- **schedule_follow_up**: Schedules a follow-up appointment.

  - Parameters: patientName (str), date (YYYY-MM-DD), reason (str, optional).
  - Trigger: Doctor says "schedule followup appointment".

- **send_lab_order**: Sends a lab order.
  - Parameters: patientName (str), testType (str), urgency (str: routine, urgent, stat, optional).
  - Trigger: Doctor says "send lab order".

Results are sent to the configured WEBHOOK_URL.

## Project Structure

```
medical-interpreter-api/
├── server.py              # Main FastAPI application
├── openai_realtime.py     # OpenAI Realtime API integration
├── tools.py               # Tool execution logic
├── models.py              # Pydantic models for requests/responses
├── .env                   # Environment variables
└── README.md              # This file
```
