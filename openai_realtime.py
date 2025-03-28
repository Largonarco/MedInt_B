import json
import asyncio
import websocket
import threading
import logging
import os
from typing import Dict, List, Callable, Optional, Any
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
        """Initialize the OpenAI Realtime manager.
        
        Args:
            on_text_delta: Callback when text delta is received
            on_text_done: Callback when text response is complete
            on_audio_delta: Callback when audio delta is received
            on_audio_done: Callback when audio response is complete
            on_function_call: Callback when function call is requested
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        self.api_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        self.websocket = None
        self.ws_app = None
        self.thread = None
        self.connected = False
        
        # Callbacks
        self.on_text_delta = on_text_delta
        self.on_text_done = on_text_done
        self.on_audio_delta = on_audio_delta
        self.on_audio_done = on_audio_done
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
                        "patientName": {
                            "type": "string",
                            "description": "The name of the patient"
                        },
                        "date": {
                            "type": "string",
                            "description": "The requested date for the appointment in YYYY-MM-DD format"
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for the follow-up appointment"
                        }
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
                        "patientName": {
                            "type": "string",
                            "description": "The name of the patient"
                        },
                        "testType": {
                            "type": "string",
                            "description": "The type of lab test ordered"
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["routine", "urgent", "stat"],
                            "description": "The urgency level of the lab order"
                        }
                    },
                    "required": ["patientName", "testType"]
                }
            }
        ]
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            asyncio.run(self._process_message(data))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {str(error)}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection closing."""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    def _on_open(self, ws):
        """Handle WebSocket connection opening."""
        logger.info("Connected to OpenAI Realtime API")
        self.connected = True
    
    async def connect(self):
        """Establish connection with OpenAI Realtime API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            # Create WebSocket with callbacks
            self.ws_app = websocket.WebSocketApp(
                self.api_url,
                header=headers,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Run WebSocket connection in a separate thread
            self.thread = threading.Thread(target=self.ws_app.run_forever)
            self.thread.daemon = True
            self.thread.start()
            
            # Wait for connection to be established
            for _ in range(30):  # Wait up to 3 seconds
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            
            if not self.connected:
                raise TimeoutError("Timed out waiting for WebSocket connection")
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime API: {str(e)}")
            raise
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.ws_app:
            self.ws_app.close()
            self.connected = False
            logger.info("Closed connection to OpenAI Realtime API")
    
    async def _process_message(self, message: Dict):
        """Process a message from OpenAI."""
        message_type = message.get("type")
        
        try:
            if message_type == "response.text.delta":
                # Text response delta
                if self.on_text_delta and "delta" in message:
                    self.on_text_delta(message["delta"])
                    
            elif message_type == "response.text.done":
                # Text response complete
                if self.on_text_done and "text" in message:
                    self.on_text_done(message["text"])
                    
            elif message_type == "response.audio.delta":
                # Audio response delta
                if self.on_audio_delta and "delta" in message:
                    self.on_audio_delta(message["delta"])
                    
            elif message_type == "response.audio.done":
                # Audio response complete
                if self.on_audio_done:
                    self.on_audio_done()
                    
            elif message_type == "response.function_call_arguments.done":
                # Function call request
                if self.on_function_call and "name" in message and "arguments" in message:
                    function_name = message["name"]
                    function_args = json.loads(message["arguments"])
                    self.on_function_call(function_name, function_args)
                    
            elif message_type == "error":
                # Error message
                logger.error(f"OpenAI error: {message.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing message of type {message_type}: {str(e)}")
    
    async def _send_message(self, message: Dict):
        """Send a message to the OpenAI WebSocket."""
        if not self.connected or not self.ws_app:
            raise ValueError("WebSocket connection not established")
        
        try:
            self.ws_app.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    async def process_doctor_speech(self, audio_base64: str):
        """Process doctor's speech (English to Spanish translation)."""
        try:
            # Create conversation item with audio
            create_conversation_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "audio": audio_base64
                        }
                    ]
                }
            }
            
            # Send audio to OpenAI
            await self._send_message(create_conversation_event)
            
            # Request response with translation to Spanish
            create_response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": """You are a medical interpreter. The doctor is speaking English. 
                        Translate what they say accurately to Spanish. 
                        Keep the same tone and level of formality. 
                        Be precise with medical terminology.
                        DO NOT INTEPRET OR ADD ANY COMMENTARY. SIMPLY TRANSLATE AND SAY IN FIRST PERSON""",
                    "tools": self.tools,
                    "tool_choice": "auto"
                }
            }
            
            await self._send_message(create_response_event)
        except Exception as e:
            logger.error(f"Error processing doctor speech: {str(e)}")
            raise
    
    async def process_patient_speech(self, audio_base64: str, last_doctor_message: str):
        """Process patient's speech (Spanish to English translation)."""
        try:
            # Create conversation item with audio
            create_conversation_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "audio": audio_base64
                        }
                    ]
                }
            }
            
            # Send audio to OpenAI
            await self._send_message(create_conversation_event)
            
            # Request response with translation to English
            create_response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": f"""You are a medical interpreter. The patient is speaking Spanish. 
                        Translate what they say accurately to English.
                       
                        Speak in first person as if you are the patient speaking directly to the doctor.
                  
                        The doctor's last message was: {last_doctor_message or "(No previous message)"}
                        DO NOT INTEPRET OR ADD ANY COMMENTARY. SIMPLY TRANSLATE AND SAY IN FIRST PERSON""",
                    "tools": self.tools,
                    "tool_choice": "auto"
                }
            }
            
            await self._send_message(create_response_event)
        except Exception as e:
            logger.error(f"Error processing patient speech: {str(e)}")
            raise
    
    async def generate_summary(self):
        """Generate a summary of the conversation."""
        try:
            # Create conversation item with summary request
            create_conversation_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Generate a summary of this medical conversation, highlighting key points discussed, any actions that need to be taken (like scheduling follow-up appointments or ordering lab tests), and any important patient concerns or medical advice given."
                        }
                    ]
                }
            }
            
            # Send summary request to OpenAI
            await self._send_message(create_conversation_event)
            
            # Request text response with summary
            create_response_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text"],
                    "instructions": """Generate a concise but comprehensive summary of the medical conversation that just occurred.
                        Highlight:
                        1. Key medical issues discussed
                        2. Recommendations or treatment plans
                        3. Any follow-up appointments that need to be scheduled
                        4. Any lab orders that need to be placed
                        5. Any urgent concerns that need attention
                        
                        Format the summary with clear sections and bullet points where appropriate.
                        """
                }
            }
            
            await self._send_message(create_response_event)
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise
    
    async def send_function_result(self, function_name: str, result: Dict):
        """Send function call result back to OpenAI."""
        try:
            # Create function output event
            function_output_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "role": "system",
                    "output": json.dumps(result)
                }
            }
            
            # Send function output to OpenAI
            await self._send_message(function_output_event)
            
            # Request a new response
            await self._send_message({"type": "response.create"})
        except Exception as e:
            logger.error(f"Error sending function result: {str(e)}")
            raise