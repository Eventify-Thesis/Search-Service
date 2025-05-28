from fastapi import APIRouter, UploadFile, File, HTTPException
from google.cloud import speech
import os
import tempfile
from typing import Optional
from google.oauth2 import service_account
import logging
import wave
import contextlib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def validate_wav_file(file_path):
    """Validate WAV file format and return audio properties"""
    try:
        # Check file size first
        file_size = os.path.getsize(file_path)
        if file_size < 44:  # WAV header is 44 bytes
            logger.error(f"File too small: {file_size} bytes (minimum 44 bytes for WAV header)")
            return False, "File is too small to be a valid WAV file"

        with contextlib.closing(wave.open(file_path, 'rb')) as wav_file:
            # Get audio properties
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            duration = n_frames / float(frame_rate)
            
            logger.info(f"Audio properties: {n_channels} channels, {frame_rate} Hz, {duration:.2f}s")
            
            # Validate audio properties
            if frame_rate != 16000:
                logger.warning(f"Warning: Frame rate is {frame_rate} Hz, expected 16000 Hz")
            
            if n_channels != 1:
                logger.warning(f"Warning: Audio has {n_channels} channels, mono (1 channel) is recommended")
            
            return True, "Valid WAV file"
    except Exception as e:
        logger.error(f"Invalid WAV file: {str(e)}")
        return False, str(e)

@router.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language_code: Optional[str] = "vi-VN"
):
    """
    Convert speech to text using Google Cloud Speech-to-Text API.
    Accepts WAV audio files.
    Uses service account credentials.
    """
    try:
        logger.info(f"Received file: {file.filename}, content_type: {file.content_type}")
        
        # Validate file extension
        if not file.filename.lower().endswith('.wav'):
            raise HTTPException(
                status_code=400,
                detail="Only WAV files are supported. Please upload a .wav file"
            )
        
        # Create a temporary directory for audio files
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_audio")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save the uploaded file with its original name
        temp_file_path = os.path.join(temp_dir, file.filename)
        with open(temp_file_path, "wb") as temp_file:
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Empty file received"
                )
            temp_file.write(content)
            temp_file.flush()
        
        logger.info(f"Saved audio file: {os.path.getsize(temp_file_path)} bytes")
        
        # Validate the WAV file
        is_valid, message = validate_wav_file(temp_file_path)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid WAV file: {message}"
            )
        
        # Get the absolute path to the service account file
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_path = os.path.join(current_dir, "config", "gcloud", "service-account.json")
        
        # Initialize the Speech-to-Text client with service account credentials
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        client = speech.SpeechClient(credentials=credentials)
        
        # Read the audio file
        with open(temp_file_path, "rb") as audio_file:
            content = audio_file.read()
        
        # Configure the audio and recognition settings
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            enable_automatic_punctuation=True,
            model="default"
        )
        
        # Perform the transcription
        logger.info("Processing speech-to-text...")
        response = client.recognize(config=config, audio=audio)
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        if not response.results:
            logger.warning("No transcription results returned")
            return {"text": ""}
        
        # Combine all transcriptions
        transcript = " ".join([result.alternatives[0].transcript for result in response.results])
        logger.info(f"Transcription successful: '{transcript}'")
        
        return {"text": transcript}
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) 