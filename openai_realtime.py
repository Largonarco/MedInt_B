import json
import asyncio
import websocket
import threading
import logging
import os
from typing import Dict, Callable
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIRealtimeManager:
    """Manages communication with the OpenAI Realtime API using websocket-client."""
    
    def __init__(
        self,
        on_text_delta: Callable[[str], None],
        on_text_done: Callable[[str], None],
        on_audio_delta: Callable[[str], None],
        on_audio_done: Callable[[], None],
        on_function_call: Callable[[str, Dict], None]
    ):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        self.ws_app = None
        self.thread = None
        self.connected = False
        self.api_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        
        # Callbacks
        self.on_text_done = on_text_done
        self.on_text_delta = on_text_delta
        self.on_audio_done = on_audio_done
        self.on_audio_delta = on_audio_delta
        self.on_function_call = on_function_call
        
        # Tool definitions
        self.tools = [
            {
                "type": "function",
                "name": "schedule_follow_up",
                "description": "Schedule a follow-up appointment for the patient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patientName": {"type": "string", "description": "The name of the patient"},
                        "reason": {"type": "string", "description": "The reason for the follow-up"},
                        "date": {"type": "string", "description": "The requested date in YYYY-MM-DD format"}
                    },
                    "required": ["patientName", "date"]
                }
            },
            {
                "type": "function",
                "name": "send_lab_order",
                "description": "Send a lab order for the patient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patientName": {"type": "string", "description": "The name of the patient"},
                        "testType": {"type": "string", "description": "The type of lab test ordered"},
                        "urgency": {"type": "string", "enum": ["routine", "urgent", "stat"], "description": "Urgency level"}
                    },
                    "required": ["patientName", "testType"]
                }
            }
        ]
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {str(error)}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.connected = False

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            asyncio.run(self._process_message(data))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
    
    def _on_open(self, ws):
        logger.info("Connected to OpenAI Realtime API")
        create_session_event = {
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "instructions": """You are a Medical Interpreter facilitating communication between a Spanish-speaking patient and an English-speaking doctor. Your task is to translate audio inputs literally and perform specific actions when requested.""",
                "voice": "alloy",
                "tools": self.tools,
                "tool_choice": "auto"
            }
        }
        ws.send(json.dumps(create_session_event))
        self.connected = True
    
    async def connect(self):
        headers = {"Authorization": f"Bearer {self.api_key}", "OpenAI-Beta": "realtime=v1"}
        self.ws_app = websocket.WebSocketApp(
            self.api_url,
            header=headers,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
            on_message=self._on_message,
        )
        self.thread = threading.Thread(target=self.ws_app.run_forever)
        self.thread.daemon = True
        self.thread.start()
        for _ in range(30):
            if self.connected:
                return True
            await asyncio.sleep(0.1)
        if not self.connected:
            raise TimeoutError("Timed out waiting for WebSocket connection")
    
    async def close(self):
        if self.ws_app:
            self.ws_app.close()
            self.connected = False
    
    async def _process_message(self, message: Dict):
        message_type = message.get("type")
        try:
            if message_type == "response.text.delta":
                if self.on_text_delta and "delta" in message:
                    self.on_text_delta(message["delta"])
            elif message_type == "response.text.done":
                if self.on_text_done and "text" in message:
                    self.on_text_done(message["text"])
            elif message_type == "response.audio.delta":
                if self.on_audio_delta and "delta" in message:
                    self.on_audio_delta(message["delta"])
            elif message_type == "response.audio.done":
                if self.on_audio_done:
                    self.on_audio_done()
            elif message_type == "response.function_call_arguments.done":
                if self.on_function_call and "name" in message and "arguments" in message:
                    function_name = message["name"]
                    function_args = json.loads(message["arguments"])
                    self.on_function_call(function_name, function_args)
            elif message_type == "error":
                logger.error(f"OpenAI error: {message.get('message', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error processing message of type {message_type}: {str(e)}")
    
    async def _send_message(self, message: Dict):
        if not self.connected or not self.ws_app:
            raise ValueError("WebSocket connection not established")
        self.ws_app.send(json.dumps(message))
    
    async def process_speech(self, audio_base64: str, last_doctor_message: str):
        """Process speech based on language detection."""
        try:
            create_conversation_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_audio", "audio": audio_base64}]
                }
            }
            await self._send_message(create_conversation_event)
            
            create_response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text"],
                    "instructions": """
                  - Primary Tasks:
                    - When given Spanish audio input, assume it's from the patient and translate it to English text verbatim, without adding your own interpretation.
                    - When given English audio input, assume it's from the doctor and translate it to Spanish text verbatim, without adding your own interpretation.

                  - Additional Tasks:
                    - If the patient says "repite eso" (Spanish for "repeat that"), repeat the doctor's most recent statement in Spanish, based on provided context.
                    - If the doctor says "schedule followup appointment" or "send lab order", call the respective function (`schedule_follow_up` or `send_lab_order`) with appropriate arguments inferred from the conversation.
                  - Output Format: Always return a JSON object in this exact format: {"text": "<translated_text>", "role": "<patient or doctor>"}.
                  - Notes: Audio input language indicates the speaker (Spanish = patient, English = doctor) unless otherwise specified.""",
                    "tools": self.tools,
                    "tool_choice": "auto"
                }
            }
            await self._send_message(create_response_event)
        except Exception as e:
            logger.error(f"Error processing speech: {str(e)}")
            raise
    
    async def generate_summary(self):
        try:
            create_conversation_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Generate a summary of this medical conversation."}]
                }
            }
            await self._send_message(create_conversation_event)
            
            create_response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text"],
                    "instructions": """Generate a concise summary of the medical conversation:
                    - Key medical issues discussed
                    - Recommendations or treatment plans
                    - Follow-up appointments needed
                    - Lab orders needed
                    - Urgent concerns"""
                }
            }
            await self._send_message(create_response_event)
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise
    
    async def send_function_result(self, function_name: str, result: Dict):
        try:
            function_output_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "role": "system",
                    "output": json.dumps(result)
                }
            }
            await self._send_message(function_output_event)
            await self._send_message({"type": "response.create"})
        except Exception as e:
            logger.error(f"Error sending function result: {str(e)}")
            raise
        