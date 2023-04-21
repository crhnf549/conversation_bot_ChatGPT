# conversation_bot_ChatGPT

This is a voice chat bot using ChatGPT and Whisper's API.
It can accept input from the user even in the middle of a response.
You can switch modes with the keyboard's 1, 2, 3.
- Mode 1: Voice input
- Mode 2: Text input
- Mode 3: For debugging

If you want to end the conversation, press key 8 or pronaunce "会話終了" in Japanese.

Required libraries
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
from pydub import AudioSegment
from pydub.silence import split_on_silence
from win32com.client import constants
import win32com.client
import pythoncom
import openai
import pyaudio
import keyboard
import time
import winsound
