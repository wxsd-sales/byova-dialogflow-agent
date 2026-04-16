"""Google Dialogflow CX connector for the BYOVA gateway."""

import logging
import os
import uuid
from typing import Dict, Any, Generator, Optional, Tuple
import threading
import struct

# Try to import audioop (deprecated in Python 3.13)
try:
    import audioop
    AUDIOOP_AVAILABLE = True
except ImportError:
    AUDIOOP_AVAILABLE = False
    audioop = None

try:
    from google.cloud import dialogflowcx_v3 as dialogflow
    from google.api_core import exceptions as google_exceptions
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials as OAuth2Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle
    DIALOGFLOW_AVAILABLE = True
except ImportError:
    DIALOGFLOW_AVAILABLE = False
    dialogflow = None
    google_exceptions = None
    service_account = None
    OAuth2Credentials = None
    InstalledAppFlow = None
    Request = None

from .i_vendor_connector import IVendorConnector


class DialogflowCXConnector(IVendorConnector):
    """Dialogflow CX connector. Auth: WIF (GOOGLE_APPLICATION_CREDENTIALS), access token,
    service account key, OAuth (oauth_client_id/secret + token file), or ADC.
    See config keys: project_id, location, agent_id, api_endpoint, force_input_format, barge_in_enabled.
    """

    @staticmethod
    def _dialogflow_cx_api_endpoint(location: str, explicit: Optional[str]) -> Optional[str]:
        """
        Regional Dialogflow CX API host. None = client default (global endpoint).

        See: https://cloud.google.com/dialogflow/cx/docs/concept/region
        """
        if explicit is not None and str(explicit).strip():
            return str(explicit).strip()
        loc = (location or "global").strip().lower()
        if loc == "global":
            return None
        return f"{loc}-dialogflow.googleapis.com"

    def __init__(self, config: Dict[str, Any]):
        if not DIALOGFLOW_AVAILABLE:
            raise ImportError(
                "google-cloud-dialogflow-cx package not installed. "
                "Install it with: pip install google-cloud-dialogflow-cx"
            )
        
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        self.project_id = config.get("project_id")
        self.location = config.get("location", "global")
        self.agent_id = config.get("agent_id")
        
        if not all([self.project_id, self.agent_id]):
            raise ValueError(
                "Missing required configuration: project_id and agent_id are required"
            )
        
        self.language_code = config.get("language_code", "en-US")
        self.sample_rate_hertz = config.get("sample_rate_hertz", 8000)
        self.audio_encoding = config.get("audio_encoding", "AUDIO_ENCODING_MULAW")
        self.agents = config.get("agents", ["Dialogflow CX Agent OAuth"])

        self.barge_in_enabled = bool(config.get("barge_in_enabled", True))
        self.force_input_format = config.get("force_input_format", "").lower()
        self.min_audio_seconds = config.get("min_audio_seconds", 2.5)
        self.max_audio_seconds = config.get("max_audio_seconds", 5.0)

        access_token = config.get("access_token") or os.environ.get("GCP_ACCESS_TOKEN")
        oidc_token = config.get("oidc_token") or os.environ.get("GCP_OIDC_TOKEN")
        wif_config_path = config.get("wif_config_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        service_account_key_path = config.get("service_account_key")
        oauth_client_id = config.get("oauth_client_id")
        oauth_client_secret = config.get("oauth_client_secret")
        oauth_token_file = config.get("oauth_token_file", "oauth_token.pickle")
        
        if access_token:
            token_source = "config file" if config.get("access_token") else "GCP_ACCESS_TOKEN env var"
            masked_token = f"{access_token[:10]}...{access_token[-5:]}" if len(access_token) > 15 else "***"
            self.logger.info(f"Access token found from {token_source}: {masked_token}")
        if oidc_token:
            token_source = "config file" if config.get("oidc_token") else "GCP_OIDC_TOKEN env var"
            masked_token = f"{oidc_token[:10]}...{oidc_token[-5:]}" if len(oidc_token) > 15 else "***"
            self.logger.info(f"OIDC token found from {token_source}: {masked_token}")
        
        self.credentials = None
        auth_method = None

        if wif_config_path and os.path.exists(wif_config_path):
            self.logger.info(f"Using Workload Identity Federation from: {wif_config_path}")
            try:
                import google.auth
                from google.auth.transport.requests import Request
                
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = wif_config_path
                os.environ['GOOGLE_CLOUD_PROJECT'] = self.project_id

                self.credentials, project = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                
                if not self.credentials.valid:
                    self.logger.info("Refreshing WIF credentials...")
                    self.credentials.refresh(Request())
                
                auth_method = f"Workload Identity Federation (WIF)"
                self.logger.info(f"WIF authentication successful!")
                self.logger.info(f"Project: {project}")
                self.logger.info(f"Token valid: {self.credentials.valid}")
                
            except Exception as e:
                self.logger.error(f"Failed to authenticate with WIF: {e}")
                self.logger.error(f"WIF config: {wif_config_path}")
                self.logger.error(f"Make sure oidc_token.json exists and contains valid JWT")
                raise
        
        elif access_token:
            from google.oauth2.credentials import Credentials
            self.credentials = Credentials(token=access_token, quota_project_id=self.project_id)
            auth_method = "Direct Access Token (expires in ~1 hour, no auto-refresh)"
            self.logger.info("Using direct access token")
            self.logger.info(f"Quota project set to: {self.project_id}")
            self.logger.warning("⚠️  Access token will expire in ~1 hour without refresh!")
            
        elif service_account_key_path and os.path.exists(service_account_key_path):
            self.credentials = service_account.Credentials.from_service_account_file(
                service_account_key_path
            )
            auth_method = f"Service Account Key: {service_account_key_path}"
            self.logger.info(f"Loaded service account from {service_account_key_path}")
            
        elif oauth_client_id and oauth_client_secret:
            self.credentials = self._get_oauth_credentials(
                oauth_client_id, 
                oauth_client_secret, 
                oauth_token_file
            )
            auth_method = f"OAuth 2.0: {oauth_token_file}"
            self.logger.info(f"Using OAuth 2.0 credentials from {oauth_token_file}")
            
        else:
            auth_method = "Application Default Credentials (ADC)"
            self.logger.info("Using Application Default Credentials (ADC)")
        
        try:
            from google.api_core import client_options as client_options_lib

            cx_api_endpoint = self._dialogflow_cx_api_endpoint(
                self.location, config.get("api_endpoint")
            )
            opts_kwargs: Dict[str, Any] = {"quota_project_id": self.project_id}
            if cx_api_endpoint:
                opts_kwargs["api_endpoint"] = cx_api_endpoint
            client_opts = client_options_lib.ClientOptions(**opts_kwargs)

            self.logger.info(
                "Dialogflow CX API endpoint: %s",
                cx_api_endpoint or "dialogflow.googleapis.com (default for location=global)",
            )

            if self.credentials:
                self.sessions_client = dialogflow.SessionsClient(
                    credentials=self.credentials,
                    client_options=client_opts
                )
            else:
                self.sessions_client = dialogflow.SessionsClient(
                    client_options=client_opts
                )
            
            self.logger.info(f"Dialogflow CX SessionsClient initialized successfully using {auth_method}")
            self.logger.info(f"Quota project configured: {self.project_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Dialogflow CX client: {e}")
            raise
        
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.sessions_lock = threading.Lock()
        
        self.streaming_sessions: Dict[str, Any] = {}
        self.audio_queues: Dict[str, list] = {}
        
        self.detected_formats: Dict[str, Tuple[int, str]] = {}
        self.agent_path = f"projects/{self.project_id}/locations/{self.location}/agents/{self.agent_id}"
        audio_lib = "audioop (native)" if AUDIOOP_AVAILABLE else "fallback (Python 3.13+)"
        
        self.logger.info(
            f"DialogflowCXConnector initialized for agent: {self.agent_path}"
        )
        self.logger.info(
            f"Audio conversion: {audio_lib} | Auto-detection: enabled"
        )

    def _get_oauth_credentials(self, client_id: str, client_secret: str, token_file: str) -> OAuth2Credentials:
        """Load, refresh, or obtain OAuth2 user credentials (browser flow if needed)."""
        SCOPES = ['https://www.googleapis.com/auth/dialogflow']
        
        creds = None
        
        # Try to load existing token
        if os.path.exists(token_file):
            try:
                with open(token_file, 'rb') as token:
                    creds = pickle.load(token)
                self.logger.info(f"Loaded OAuth credentials from {token_file}")
            except Exception as e:
                self.logger.warning(f"Failed to load token file: {e}")
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    self.logger.info("Refreshing expired OAuth token...")
                    creds.refresh(Request())
                    self.logger.info("OAuth token refreshed successfully")
                except Exception as e:
                    self.logger.error(f"Failed to refresh token: {e}")
                    creds = None
            
            # If refresh failed or no creds, start OAuth flow
            if not creds:
                self.logger.info("Starting OAuth 2.0 authorization flow...")
                
                # Create OAuth client config
                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost:8090/"]
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                
                # Run local server flow (opens browser)
                # Using fixed port 8090 for consistent redirect URI
                try:
                    creds = flow.run_local_server(port=8090, open_browser=True)
                    self.logger.info("OAuth authorization successful!")
                except Exception as e:
                    self.logger.error(f"OAuth flow failed: {e}")
                    self.logger.info("Trying console-based OAuth flow...")
                    # Fallback to console-based flow
                    creds = flow.run_console()
            
            # Save credentials for next run
            try:
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)
                self.logger.info(f"OAuth credentials saved to {token_file}")
            except Exception as e:
                self.logger.warning(f"Failed to save OAuth token: {e}")
        
        return creds

    def get_available_agents(self):
        """
        Return list of available agent IDs.
        
        Returns:
            List of agent display names
        """
        return self.agents

    def start_conversation(self, conversation_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new conversation with Dialogflow CX.
        
        Args:
            conversation_id: Unique conversation identifier
            request_data: Initial request data from WxCC
            
        Returns:
            Initial response dictionary
        """
        self.logger.info(f"Starting Dialogflow CX conversation: {conversation_id}")
        
        try:
            # Create a unique session ID
            session_id = str(uuid.uuid4())
            session_path = f"{self.agent_path}/sessions/{session_id}"
            
            # Store session information
            with self.sessions_lock:
                self.active_sessions[conversation_id] = {
                    "session_id": session_id,
                    "session_path": session_path,
                }
                # Initialize audio queue for this conversation
                self.audio_queues[conversation_id] = []
            
            self.logger.info(
                f"[START] Conversation {conversation_id} started with session: {session_path}"
            )
            
            # Send initial "hi" text to Dialogflow
            text_input = dialogflow.TextInput(text="hi")
            query_input = dialogflow.QueryInput(
                text=text_input,
                language_code=self.language_code
            )
            
            # Configure output audio (for WxCC to hear agent responses)
            # WxCC expects 8kHz MULAW for telephony
            output_audio_config = dialogflow.OutputAudioConfig(
                audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_MULAW,
                sample_rate_hertz=8000,
                synthesize_speech_config=dialogflow.SynthesizeSpeechConfig(
                    speaking_rate=1.0,  # Normal speed
                    pitch=0.0,  # Normal pitch
                    volume_gain_db=0.0  # Normal volume
                )
            )
            
            request = dialogflow.DetectIntentRequest(
                session=session_path,
                query_input=query_input,
                output_audio_config=output_audio_config  # Request audio output for welcome message!
            )
            
            self.logger.info(f"[START] Sending initial 'hi' to Dialogflow CX")
            response = self.sessions_client.detect_intent(request=request)
            
            # Extract response text
            response_text = "Connected to Dialogflow CX agent"
            audio_content = b""
            
            for message in response.query_result.response_messages:
                if message.text:
                    response_text = " ".join(message.text.text)
                    self.logger.info(f"[START] Agent welcome response: '{response_text}'")
                    break
            
            # Extract audio output from welcome response
            if response.output_audio and len(response.output_audio) > 0:
                audio_content = response.output_audio
                self.logger.info(
                    f"[START] Received welcome audio: {len(audio_content)} bytes (8kHz MULAW)"
                )
            else:
                self.logger.warning(
                    f"[START] No audio in welcome response! Check agent's text-to-speech settings."
                )
            
            return self.create_session_start_response(
                conversation_id=conversation_id,
                text=response_text,
                audio_content=audio_content,
                language_code=self.language_code,
            )
            
        except Exception as e:
            self.logger.error(f"Error starting conversation {conversation_id}: {e}", exc_info=True)
            # Return error response using create_response
            return self.create_response(
                conversation_id=conversation_id,
                message_type="error",
                text=f"Failed to start conversation: {str(e)}",
                audio_content=b"",
                barge_in_enabled=False,
                response_type="final",
                language_code=self.language_code,
            )

    def send_message(self, conversation_id: str, message_data: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Send audio or text message to Dialogflow CX and yield responses.
        
        Args:
            conversation_id: Unique conversation identifier
            message_data: Message data containing audio or text
            
        Yields:
            Response dictionaries from Dialogflow CX
        """
        self.logger.debug(f"Sending message for conversation: {conversation_id}")
        
        # Get session information
        with self.sessions_lock:
            session_info = self.active_sessions.get(conversation_id)
            active_ids = list(self.active_sessions.keys())
        
        if not session_info:
            self.logger.error(
                f"[ERROR] No active session found for conversation: {conversation_id} | "
                f"Active sessions: {active_ids if active_ids else 'NONE'} | "
                f"This usually means audio arrived for an ended or never-started conversation."
            )
            # Don't yield error response for stale packets - just log and return
            return
        
        try:
            # Log incoming message for debugging
            #rkanthet
            # self.logger.info(
            #     f"[{conversation_id}] [MSG] Received message - keys: {list(message_data.keys())}"
            # )
            
            # Handle different message types
            # Check input_type (from gateway) or type (from direct calls)
            message_type = message_data.get("input_type") or message_data.get("type", "audio")
            #rkanthet
            # self.logger.info(
            #     f"[{conversation_id}] [TYPE] Message type: {message_type}"
            # )
            
            if message_type == "audio":
                # Handle audio input
                yield from self._handle_audio_input(conversation_id, session_info, message_data)
            elif message_type == "text":
                # Handle text input
                yield from self._handle_text_input(conversation_id, session_info, message_data)
            elif message_type == "event":
                # Handle event input
                yield from self._handle_event_input(conversation_id, session_info, message_data)
            else:
                self.logger.warning(f"[{conversation_id}] Unknown message type: {message_type}")
                yield self.create_response(
                    conversation_id=conversation_id,
                    message_type="error",
                    text=f"Unknown message type: {message_type}",
                    audio_content=b"",
                    barge_in_enabled=False,
                    response_type="final"
                )
                
        except Exception as e:
            self.logger.error(f"Error processing message for {conversation_id}: {e}", exc_info=True)
            yield self.create_response(
                conversation_id=conversation_id,
                message_type="error",
                text=f"Error processing message: {str(e)}",
                audio_content=b"",
                barge_in_enabled=False,
                response_type="final"
            )

    def _handle_audio_input(
    self, 
    conversation_id: str, 
    session_info: Dict[str, Any], 
    message_data: Dict[str, Any]
) -> Generator[Dict[str, Any], None, None]:
        """
        Handle audio input to Dialogflow CX (simplified version).
        """
        try:
            # Get audio data
            audio_data_raw = message_data.get("audio") or message_data.get("audio_data", b"")
            audio_chunk = self.extract_audio_data(audio_data_raw, conversation_id, self.logger)
            
            if not audio_chunk:
                return
            
            self.logger.debug(
                f"[{conversation_id}] [AUDIO] Received audio chunk: {len(audio_chunk)} bytes"
            )
            
            # Auto-detect format on first chunk and convert if needed
            detected_rate, detected_encoding, detected_dialogflow_encoding = self._detect_audio_format(
                audio_chunk, conversation_id
            )
            
            # Convert audio to config format if different
            target_rate = self.sample_rate_hertz
            target_encoding = "LINEAR_16" if "LINEAR" in self.audio_encoding else "MULAW"
            
            if detected_rate != target_rate or detected_encoding != target_encoding:
                audio_chunk = self._convert_audio_format(
                    audio_chunk,
                    from_rate=detected_rate,
                    from_encoding=detected_encoding,
                    to_rate=target_rate,
                    to_encoding=target_encoding,
                    conversation_id=conversation_id
                )
            
            session_path = session_info["session_path"]
            
            # Accumulate audio (now in converted format)
            with self.sessions_lock:
                if conversation_id not in self.audio_queues:
                    self.audio_queues[conversation_id] = []
                self.audio_queues[conversation_id].append(audio_chunk)
                
                total_audio_size = sum(len(chunk) for chunk in self.audio_queues[conversation_id])
                
                # Calculate minimum audio size based on TARGET sample rate (after conversion)
                # Use configurable thresholds for better utterance capture
                # At 8kHz MULAW: 8000 bytes/sec * min_audio_seconds
                # At 16kHz LINEAR_16: 16000 samples/sec * 2 bytes/sample * min_audio_seconds
                SECONDS_TO_ACCUMULATE = self.min_audio_seconds
                
                # Calculate bytes per second based on target format
                if target_encoding == "MULAW":
                    bytes_per_second = target_rate  # 1 byte per sample for MULAW
                else:  # LINEAR_16
                    bytes_per_second = target_rate * 2  # 2 bytes per sample for 16-bit
                
                MIN_AUDIO_SIZE = int(bytes_per_second * SECONDS_TO_ACCUMULATE)
                MAX_AUDIO_SIZE = int(bytes_per_second * self.max_audio_seconds)
                
                self.logger.debug(
                    f"[{conversation_id}] [QUEUE] Audio queue: {total_audio_size} bytes "
                    f"({total_audio_size/bytes_per_second:.2f}s) | "
                    f"Min: {MIN_AUDIO_SIZE} bytes ({self.min_audio_seconds}s) | "
                    f"Max: {MAX_AUDIO_SIZE} bytes ({self.max_audio_seconds}s) | "
                    f"Format: {target_rate}Hz {target_encoding}"
                )
                
                # Only process if we have minimum audio (unless we've exceeded maximum)
                if total_audio_size < MIN_AUDIO_SIZE:
                    # Check if we've exceeded maximum - force processing to avoid long delays
                    if total_audio_size >= MAX_AUDIO_SIZE:
                        self.logger.info(
                            f"[{conversation_id}] [MAX_AUDIO] Exceeded max buffer ({total_audio_size/bytes_per_second:.2f}s), "
                            "forcing processing to avoid delay"
                        )
                        # Continue to processing below
                    else:
                        return  # Not enough audio yet, keep accumulating
                
                # Combine queued audio
                combined_audio = b''.join(self.audio_queues[conversation_id])
                # Clear queue after combining
                self.audio_queues[conversation_id] = []
            
            # Get detected format for logging
            detected_rate, detected_encoding = self.detected_formats.get(
                conversation_id, (target_rate, target_encoding)
            )
            
            self.logger.info(
                f"[{conversation_id}] [PROCESS] Processing {len(combined_audio)} bytes ({len(combined_audio)/bytes_per_second:.2f}s) | "
                f"Received: {detected_rate}Hz {detected_encoding} | Sending to Dialogflow: {target_rate}Hz {target_encoding}"
            )
            
            # Create audio config
            # single_utterance=False allows Dialogflow to handle pauses within utterances
            # This helps capture complete multi-phrase utterances
            audio_config = dialogflow.InputAudioConfig(
                audio_encoding=self._get_audio_encoding(),
                sample_rate_hertz=self.sample_rate_hertz,
                single_utterance=False,  # Changed to False to capture complete utterances
            )
            
            # Create AudioInput (not audio_config in QueryInput)
            audio_input = dialogflow.AudioInput(
                config=audio_config,
                audio=combined_audio
            )
            
            # Create QueryInput with audio (not audio_config)
            query_input = dialogflow.QueryInput(
                audio=audio_input,  # Use 'audio', not 'audio_config'
                language_code=self.language_code
            )
            
            # Configure output audio (for WxCC to hear agent responses)
            # WxCC expects 8kHz MULAW for telephony
            output_audio_config = dialogflow.OutputAudioConfig(
                audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_MULAW,
                sample_rate_hertz=8000,
                synthesize_speech_config=dialogflow.SynthesizeSpeechConfig(
                    speaking_rate=1.0,  # Normal speed
                    pitch=0.0,  # Normal pitch
                    volume_gain_db=0.0  # Normal volume
                )
            )
            
            # Create the request with output audio config
            request = dialogflow.DetectIntentRequest(
                session=session_path,
                query_input=query_input,
                output_audio_config=output_audio_config  # Request audio output!
            )
            
            # Send to Dialogflow
            # self.logger.info(f"[{conversation_id}] [API] Sending audio to Dialogflow CX API...")
            response = self.sessions_client.detect_intent(request=request)
            # self.logger.info(f"[{conversation_id}] [API] Received response from Dialogflow CX")
            
            # Log transcript
            transcript = response.query_result.transcript.strip() if response.query_result.transcript else ""
            
            # Filter out empty or meaningless transcripts
            # These are often artifacts from silence/noise and shouldn't trigger agent responses
            meaningless_phrases = [
                "",
                "empty user input",
                "...",
                ".",
                " ",
            ]
            
            if not transcript or transcript.lower() in meaningless_phrases or len(transcript) < 2:
                self.logger.debug(
                    f"[{conversation_id}] [NO_SPEECH] Empty or meaningless transcript ('{transcript}') - "
                    f"ignoring to avoid false triggers"
                )
                # Don't yield anything - just return silently
                # This prevents triggering unnecessary agent responses for silence/noise
                return
            
            # Valid speech detected - log it
            self.logger.info(
                f"[{conversation_id}] [USER] Said: '{transcript}'"
            )
            
            # Log intent
            if response.query_result.intent:
                intent_name = response.query_result.intent.display_name
                confidence = response.query_result.intent_detection_confidence
                self.logger.info(
                    f"[{conversation_id}] [INTENT] {intent_name} (confidence: {confidence:.2%})"
                )
            
            # Process response messages (first text chunk carries user_transcript for session_transcript)
            first_text_response = True
            for message in response.query_result.response_messages:
                if message.text:
                    text_content = " ".join(message.text.text)
                    self.logger.info(
                        f"[{conversation_id}] [AGENT] Response: '{text_content}'"
                    )
                    extra: Dict[str, Any] = {"language_code": self.language_code}
                    if first_text_response:
                        extra["user_transcript"] = transcript
                        first_text_response = False
                    yield self.create_response(
                        conversation_id=conversation_id,
                        message_type="agent_response",
                        text=text_content,
                        barge_in_enabled=self.barge_in_enabled,
                        response_type="final",
                        **extra,
                    )
            
            # Handle output audio (agent's synthesized speech)
            if response.output_audio and len(response.output_audio) > 0:
                self.logger.info(
                    f"[{conversation_id}] [AUDIO_OUT] Sending {len(response.output_audio)} bytes "
                    f"(8kHz MULAW) to caller - Agent speaking!"
                )
                yield self.create_response(
                    conversation_id=conversation_id,
                    message_type="audio",
                    audio_content=response.output_audio,  # Fixed: was 'audio=', should be 'audio_content='
                    barge_in_enabled=self.barge_in_enabled,
                    response_type="final"
                )
            else:
                self.logger.warning(
                    f"[{conversation_id}] [NO_AUDIO] Dialogflow returned text but no audio! "
                    "Check agent's text-to-speech settings."
                )
                        
        except google_exceptions.GoogleAPICallError as e:
            self.logger.error(f"[{conversation_id}] Dialogflow API error: {e}", exc_info=True)
            # Use the correct method name from base class
            yield {
                "conversation_id": conversation_id,
                "message_type": "error",
                "error": str(e),
                "response_type": "final"
            }
        except Exception as e:
            self.logger.error(f"[{conversation_id}] Error handling audio input: {e}", exc_info=True)
            # Use the correct method name from base class
            yield {
                "conversation_id": conversation_id,
                "message_type": "error",
                "error": str(e),
                "response_type": "final"
            }

    def _handle_text_input(
        self, 
        conversation_id: str, 
        session_info: Dict[str, Any], 
        message_data: Dict[str, Any]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Handle text input to Dialogflow CX.
        
        Args:
            conversation_id: Unique conversation identifier
            session_info: Session information dictionary
            message_data: Text message data
            
        Yields:
            Response dictionaries from Dialogflow CX
        """
        try:
            text = message_data.get("text", "")
            if not text:
                return
            
            session_path = session_info["session_path"]
            
            # Create text input
            text_input = dialogflow.TextInput(text=text)
            query_input = dialogflow.QueryInput(
                text=text_input,
                language_code=self.language_code
            )
            
            # Configure output audio (same as audio input handling)
            output_audio_config = dialogflow.OutputAudioConfig(
                audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_MULAW,
                sample_rate_hertz=8000,
                synthesize_speech_config=dialogflow.SynthesizeSpeechConfig(
                    speaking_rate=1.0,
                    pitch=0.0,
                    volume_gain_db=0.0
                )
            )
            
            # Detect intent with audio output
            request = dialogflow.DetectIntentRequest(
                session=session_path,
                query_input=query_input,
                output_audio_config=output_audio_config
            )
            
            response = self.sessions_client.detect_intent(request=request)
            
            # Process text response (user's typed/DTMF text on first agent reply for transcript)
            first_text_response = True
            for message in response.query_result.response_messages:
                if message.text:
                    text_content = " ".join(message.text.text)
                    self.logger.info(f"[{conversation_id}] [AGENT] Text response: '{text_content}'")
                    extra: Dict[str, Any] = {"language_code": self.language_code}
                    if first_text_response:
                        extra["user_transcript"] = text
                        first_text_response = False
                    yield self.create_response(
                        conversation_id=conversation_id,
                        message_type="agent_response",
                        text=text_content,
                        barge_in_enabled=self.barge_in_enabled,
                        response_type="final",
                        **extra,
                    )
            
            # Process audio response
            if response.output_audio and len(response.output_audio) > 0:
                self.logger.info(
                    f"[{conversation_id}] [AUDIO_OUT] Sending {len(response.output_audio)} bytes "
                    f"(8kHz MULAW) to caller"
                )
                yield self.create_response(
                    conversation_id=conversation_id,
                    message_type="audio",
                    audio_content=response.output_audio,  # Fixed: was 'audio=', should be 'audio_content='
                    barge_in_enabled=self.barge_in_enabled,
                    response_type="final"
                )
                    
        except Exception as e:
            self.logger.error(f"Error handling text input: {e}", exc_info=True)
            yield self.create_response(
                conversation_id=conversation_id,
                message_type="error",
                text=f"Error handling text: {str(e)}",
                audio_content=b"",
                barge_in_enabled=False,
                response_type="final"
            )

    def _handle_event_input(
        self, 
        conversation_id: str, 
        session_info: Dict[str, Any], 
        message_data: Dict[str, Any]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Handle event input to Dialogflow CX.
        
        Args:
            conversation_id: Unique conversation identifier
            session_info: Session information dictionary
            message_data: Event message data
            
        Yields:
            Response dictionaries from Dialogflow CX
        """
        try:
            event_name = message_data.get("event", "")
            if not event_name:
                return
            
            session_path = session_info["session_path"]
            
            # Create event input
            event_input = dialogflow.EventInput(event=event_name)
            query_input = dialogflow.QueryInput(
                event=event_input,
                language_code=self.language_code
            )
            
            # Detect intent
            request = dialogflow.DetectIntentRequest(
                session=session_path,
                query_input=query_input
            )
            
            response = self.sessions_client.detect_intent(request=request)
            
            # Process response
            for message in response.query_result.response_messages:
                if message.text:
                    yield self.create_response(
                        conversation_id=conversation_id,
                        message_type="agent_response",
                        text=" ".join(message.text.text),
                        response_type="final"
                    )
                    
        except Exception as e:
            self.logger.error(f"Error handling event input: {e}", exc_info=True)
            yield self.create_response(
                conversation_id=conversation_id,
                message_type="error",
                text=f"Error handling event: {str(e)}",
                audio_content=b"",
                barge_in_enabled=False,
                response_type="final"
            )

    def _get_audio_encoding(self):
        """
        Get Dialogflow audio encoding enum from config string.
        
        Returns:
            Dialogflow AudioEncoding enum value
        """
        encoding_map = {
            "AUDIO_ENCODING_LINEAR_16": dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16,
            "AUDIO_ENCODING_FLAC": dialogflow.AudioEncoding.AUDIO_ENCODING_FLAC,
            "AUDIO_ENCODING_MULAW": dialogflow.AudioEncoding.AUDIO_ENCODING_MULAW,
            "AUDIO_ENCODING_AMR": dialogflow.AudioEncoding.AUDIO_ENCODING_AMR,
            "AUDIO_ENCODING_AMR_WB": dialogflow.AudioEncoding.AUDIO_ENCODING_AMR_WB,
            "AUDIO_ENCODING_OGG_OPUS": dialogflow.AudioEncoding.AUDIO_ENCODING_OGG_OPUS,
            "AUDIO_ENCODING_SPEEX_WITH_HEADER_BYTE": dialogflow.AudioEncoding.AUDIO_ENCODING_SPEEX_WITH_HEADER_BYTE,
        }
        
        return encoding_map.get(
            self.audio_encoding,
            dialogflow.AudioEncoding.AUDIO_ENCODING_MULAW
        )

    @staticmethod
    def _mulaw_to_linear(mulaw_data: bytes) -> bytes:
        """
        Convert MULAW to LINEAR_16 (fallback for Python 3.13+).
        
        Args:
            mulaw_data: MULAW encoded audio bytes
            
        Returns:
            LINEAR_16 encoded audio bytes
        """
        # MULAW decompression table
        MULAW_BIAS = 33
        MULAW_MAX = 0x1FFF
        
        linear_data = []
        for mulaw_byte in mulaw_data:
            # Invert bits
            mulaw_byte = ~mulaw_byte & 0xFF
            
            # Extract sign, segment, and quantization
            sign = (mulaw_byte & 0x80) >> 7
            segment = (mulaw_byte & 0x70) >> 4
            quantization = mulaw_byte & 0x0F
            
            # Calculate linear value
            linear = ((quantization << 1) + MULAW_BIAS) << segment
            linear = min(linear, MULAW_MAX)
            
            # Apply sign
            if sign:
                linear = -linear
            
            # Pack as 16-bit signed integer
            linear_data.append(struct.pack('<h', linear))
        
        return b''.join(linear_data)

    @staticmethod
    def _resample_audio(audio_data: bytes, from_rate: int, to_rate: int, sample_width: int) -> bytes:
        """
        Simple linear resampling (fallback for Python 3.13+).
        
        Args:
            audio_data: Audio bytes
            from_rate: Source sample rate
            to_rate: Target sample rate
            sample_width: Bytes per sample (1 or 2)
            
        Returns:
            Resampled audio bytes
        """
        # Calculate ratio
        ratio = from_rate / to_rate
        
        # Unpack samples
        if sample_width == 1:
            samples = list(audio_data)
        else:  # sample_width == 2
            samples = list(struct.unpack(f'<{len(audio_data)//2}h', audio_data))
        
        # Resample using linear interpolation
        resampled = []
        num_output_samples = int(len(samples) / ratio)
        
        for i in range(num_output_samples):
            src_index = i * ratio
            src_index_int = int(src_index)
            fraction = src_index - src_index_int
            
            if src_index_int + 1 < len(samples):
                # Linear interpolation
                sample = int(samples[src_index_int] * (1 - fraction) + 
                           samples[src_index_int + 1] * fraction)
            else:
                sample = samples[src_index_int]
            
            resampled.append(sample)
        
        # Pack back to bytes
        if sample_width == 1:
            return bytes(resampled)
        else:
            return struct.pack(f'<{len(resampled)}h', *resampled)

    def _detect_audio_format(self, audio_chunk: bytes, conversation_id: str) -> Tuple[int, str, str]:
        """
        Auto-detect audio format based on chunk characteristics.
        
        WxCC sends 8kHz MULAW in 640-byte chunks (80ms) - but may send tiny chunks initially.
        Test files send 16kHz LINEAR_16 in variable larger chunks.
        
        Args:
            audio_chunk: Raw audio bytes
            conversation_id: Conversation ID for caching detection
            
        Returns:
            Tuple of (sample_rate, encoding_name, encoding_dialogflow)
        """
        # Check if format is forced via config
        if self.force_input_format:
            if self.force_input_format == "wxcc":
                self.detected_formats[conversation_id] = (8000, "MULAW")
                # self.logger.info(
                #     f"[{conversation_id}] [FORCED] Using WxCC format: 8000Hz MULAW (force_input_format='wxcc')"
                # )
                return 8000, "MULAW", "AUDIO_ENCODING_MULAW"
            elif self.force_input_format == "test":
                rate = self.sample_rate_hertz
                enc = "LINEAR_16" if rate >= 16000 else "MULAW"
                self.detected_formats[conversation_id] = (rate, enc)
                # self.logger.info(
                #     f"[{conversation_id}] [FORCED] Using test format: {rate}Hz {enc} (force_input_format='test')"
                # )
                return rate, enc, f"AUDIO_ENCODING_{enc}"
        
        # Check if we've already detected format for this conversation
        if conversation_id in self.detected_formats:
            sample_rate, encoding = self.detected_formats[conversation_id]
            encoding_dialogflow = "AUDIO_ENCODING_MULAW" if sample_rate == 8000 else "AUDIO_ENCODING_LINEAR_16"
            return sample_rate, encoding, encoding_dialogflow
        
        chunk_size = len(audio_chunk)
        
        # Skip very small chunks (< 100 bytes) - these are control/initialization chunks
        # Wait for a substantial audio chunk before making detection decision
        if chunk_size < 100:
            self.logger.debug(
                f"[{conversation_id}] [AUTO-DETECT] Skipping tiny chunk ({chunk_size} bytes), "
                f"waiting for substantial audio..."
            )
            # Default to WxCC format for now (most common use case)
            sample_rate = 8000
            encoding = "MULAW"
            encoding_dialogflow = "AUDIO_ENCODING_MULAW"
            # Don't cache yet - wait for bigger chunk
            return sample_rate, encoding, encoding_dialogflow
        
        # WxCC typically sends 640-byte chunks for 8kHz MULAW (80ms of audio)
        # 8000 samples/sec * 1 byte/sample * 0.08 sec = 640 bytes
        # Range: 600-800 bytes (allowing for some variation)
        if 600 <= chunk_size <= 800:
            # Likely WxCC format
            sample_rate = 8000
            encoding = "MULAW"
            encoding_dialogflow = "AUDIO_ENCODING_MULAW"
            self.logger.info(
                f"[{conversation_id}] [AUTO-DETECT] WxCC telephony format detected: "
                f"{sample_rate}Hz {encoding} (chunk: {chunk_size} bytes) ✓"
            )
        # Large chunks (> 1000 bytes) are likely test files with 16-bit samples
        elif chunk_size > 1000:
            # Likely test file format (larger chunks, 16-bit samples)
            sample_rate = self.sample_rate_hertz  # Use config
            encoding = "LINEAR_16" if sample_rate >= 16000 else "MULAW"
            encoding_dialogflow = f"AUDIO_ENCODING_{encoding}"
            self.logger.info(
                f"[{conversation_id}] [AUTO-DETECT] Test file format detected: "
                f"{sample_rate}Hz {encoding} (chunk: {chunk_size} bytes) ✓"
            )
        else:
            # Ambiguous size (100-599 or 801-1000) - default to WxCC (more common)
            sample_rate = 8000
            encoding = "MULAW"
            encoding_dialogflow = "AUDIO_ENCODING_MULAW"
            self.logger.warning(
                f"[{conversation_id}] [AUTO-DETECT] Ambiguous chunk size ({chunk_size} bytes), "
                f"defaulting to WxCC format: {sample_rate}Hz {encoding}"
            )
        
        # Cache the detection
        self.detected_formats[conversation_id] = (sample_rate, encoding)
        
        return sample_rate, encoding, encoding_dialogflow

    def _convert_audio_format(
        self, 
        audio_data: bytes, 
        from_rate: int, 
        from_encoding: str,
        to_rate: int, 
        to_encoding: str,
        conversation_id: str
    ) -> bytes:
        """
        Convert audio from one format to another.
        
        Supports both audioop (Python <3.13) and fallback implementation (Python 3.13+).
        
        Args:
            audio_data: Raw audio bytes
            from_rate: Source sample rate
            from_encoding: Source encoding ('MULAW' or 'LINEAR_16')
            to_rate: Target sample rate
            to_encoding: Target encoding ('MULAW' or 'LINEAR_16')
            conversation_id: For logging
            
        Returns:
            Converted audio bytes
        """
        try:
            converted_audio = audio_data
            
            # Step 1: Convert encoding MULAW -> LINEAR_16
            if from_encoding == "MULAW" and to_encoding == "LINEAR_16":
                # MULAW is 8-bit, LINEAR_16 is 16-bit
                if AUDIOOP_AVAILABLE:
                    converted_audio = audioop.ulaw2lin(audio_data, 2)  # 2 = 16-bit
                else:
                    # Fallback for Python 3.13+
                    converted_audio = self._mulaw_to_linear(audio_data)
                
                self.logger.debug(
                    f"[{conversation_id}] [CONVERT] MULAW -> LINEAR_16: {len(audio_data)} -> {len(converted_audio)} bytes"
                )
            elif from_encoding == "LINEAR_16" and to_encoding == "MULAW":
                if AUDIOOP_AVAILABLE:
                    converted_audio = audioop.lin2ulaw(audio_data, 2)
                else:
                    # Fallback: LINEAR_16 to MULAW not implemented (rarely needed)
                    self.logger.warning(f"[{conversation_id}] LINEAR_16 -> MULAW not supported in Python 3.13+")
                    converted_audio = audio_data  # Keep as-is
                
                self.logger.debug(
                    f"[{conversation_id}] [CONVERT] LINEAR_16 -> MULAW: {len(audio_data)} -> {len(converted_audio)} bytes"
                )
            
            # Step 2: Resample if sample rates different
            if from_rate != to_rate:
                width = 2 if to_encoding == "LINEAR_16" else 1
                
                if AUDIOOP_AVAILABLE:
                    # Use audioop for high-quality resampling
                    converted_audio, _ = audioop.ratecv(
                        converted_audio, width, 1, from_rate, to_rate, None
                    )
                else:
                    # Fallback: Simple linear resampling
                    converted_audio = self._resample_audio(
                        converted_audio, from_rate, to_rate, width
                    )
                
                self.logger.debug(
                    f"[{conversation_id}] [RESAMPLE] {from_rate}Hz -> {to_rate}Hz: {len(audio_data)} -> {len(converted_audio)} bytes"
                )
            
            # self.logger.info(
            #     f"[{conversation_id}] [AUDIO_CONVERT] {from_rate}Hz {from_encoding} -> {to_rate}Hz {to_encoding} | "
            #     f"{len(audio_data)} -> {len(converted_audio)} bytes"
            # )
            
            return converted_audio
            
        except Exception as e:
            self.logger.error(f"[{conversation_id}] [CONVERT_ERROR] Audio conversion failed: {e}")
            # Return original audio if conversion fails
            return audio_data

    def end_conversation(self, conversation_id: str, message_data: Optional[Dict[str, Any]] = None):
        """
        End the conversation and cleanup resources.
        
        Args:
            conversation_id: Unique conversation identifier
            message_data: Optional end message data
        """
        self.logger.info(f"[END] Ending Dialogflow CX conversation: {conversation_id}")
        
        try:
            # Remove session from active sessions
            with self.sessions_lock:
                if conversation_id in self.active_sessions:
                    session_info = self.active_sessions.pop(conversation_id)
                    self.logger.info(
                        f"[CLEANUP] Cleaned up session {session_info['session_id']} "
                        f"for conversation {conversation_id}"
                    )
                    self.logger.info(
                        f"[SESSIONS] Remaining active sessions: {len(self.active_sessions)}"
                    )
                else:
                    self.logger.warning(
                        f"[WARNING] No active session found for conversation: {conversation_id} (already cleaned up?)"
                    )
                
                # Clean up audio queue
                if conversation_id in self.audio_queues:
                    del self.audio_queues[conversation_id]
                    self.logger.info(f"[CLEANUP] Cleaned up audio queue for {conversation_id}")
                
                # Clean up detected format
                if conversation_id in self.detected_formats:
                    del self.detected_formats[conversation_id]
                    self.logger.debug(f"[CLEANUP] Cleaned up detected format for {conversation_id}")
                    
        except Exception as e:
            self.logger.error(f"Error ending conversation {conversation_id}: {e}", exc_info=True)

    def convert_wxcc_to_vendor(self, grpc_data: Any) -> Dict[str, Any]:
        """
        Convert WxCC gRPC data to Dialogflow CX format.
        
        Args:
            grpc_data: gRPC data from WxCC
            
        Returns:
            Dictionary in Dialogflow CX format
        """
        # This can be extended based on specific conversion needs
        return {
            "data": grpc_data,
            "converted_for": "dialogflow_cx"
        }

    def convert_vendor_to_wxcc(self, vendor_data: Any) -> Any:
        """
        Convert Dialogflow CX data to WxCC format.
        
        Args:
            vendor_data: Data from Dialogflow CX
            
        Returns:
            Data in WxCC gRPC format
        """
        # This can be extended based on specific conversion needs
        return vendor_data

