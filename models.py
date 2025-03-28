from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class ConnectRequest(BaseModel):
    """Request to establish connection with OpenAI."""
    type: str = "connect"

class SpeechRequest(BaseModel):
    """Request with speech audio data."""
    type: str
    audio: str = Field(..., description="Base64-encoded audio data")

class SummaryRequest(BaseModel):
    """Request to generate conversation summary."""
    type: str = "get_summary"

class TextResponse(BaseModel):
    """Text response from the interpreter."""
    type: str
    text: str = Field(..., description="Translated text")

class AudioResponse(BaseModel):
    """Audio response from the interpreter."""
    type: str
    audio: str = Field(..., description="Base64-encoded audio data")

class ErrorResponse(BaseModel):
    """Error response."""
    type: str = "error"
    message: str = Field(..., description="Error message")

class SessionResponse(BaseModel):
    """Session initialization response."""
    type: str = "session"
    session_id: str = Field(..., description="Unique session identifier")

class ConnectionResponse(BaseModel):
    """OpenAI connection status response."""
    type: str = "openai_connected"

class TextDeltaResponse(BaseModel):
    """Streaming text delta response."""
    type: str = "text_response_delta"
    delta: str = Field(..., description="Text delta chunk")

class TextDoneResponse(BaseModel):
    """Complete text response."""
    type: str = "text_response_done"
    text: str = Field(..., description="Complete translated text")

class AudioDeltaResponse(BaseModel):
    """Streaming audio delta response."""
    type: str = "audio_response_delta"
    delta: str = Field(..., description="Base64-encoded audio delta chunk")

class AudioDoneResponse(BaseModel):
    """Complete audio response notification."""
    type: str = "audio_response_done"

class ActionExecutedResponse(BaseModel):
    """Notification of action execution."""
    type: str = "action_executed"
    action: str = Field(..., description="Action type that was executed")
    details: Dict[str, Any] = Field(..., description="Action execution details")

class FollowUpParams(BaseModel):
    """Parameters for scheduling a follow-up appointment."""
    patientName: str = Field(..., description="The name of the patient")
    date: str = Field(..., description="The requested date for the appointment in YYYY-MM-DD format")
    reason: Optional[str] = Field(None, description="The reason for the follow-up appointment")

class LabOrderParams(BaseModel):
    """Parameters for sending a lab order."""
    patientName: str = Field(..., description="The name of the patient")
    testType: str = Field(..., description="The type of lab test ordered")
    urgency: Optional[str] = Field("routine", description="The urgency level of the lab order (routine, urgent, stat)")

class WebSocketMessage(BaseModel):
    """Generic WebSocket message."""
    type: str = Field(..., description="Message type")
    content: Optional[Dict[str, Any]] = Field(None, description="Message content")