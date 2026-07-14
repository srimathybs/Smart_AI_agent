"""voice_tool.py — Text-to-speech in 14 languages using gTTS"""
import os

class TextToSpeechTool:
    name = "text_to_speech"
    description = "Convert text to speech. INPUT: text string. OUTPUT: path to .mp3 file."
    def _run(self, text: str, lang: str = "en") -> str:
        try:
            from gtts import gTTS
            os.makedirs("outputs", exist_ok=True)
            path = f"outputs/speech_{abs(hash(text[:50]))}.mp3"
            gTTS(text=text[:3000], lang=lang, slow=False).save(path)
            return f"AUDIO_SAVED:{path}"
        except ImportError: return "ERROR: pip install gTTS"
        except Exception as e: return f"TTS error: {str(e)}"

LANGUAGES = {
    "English":"en","Tamil":"ta","Hindi":"hi","Telugu":"te",
    "Kannada":"kn","Malayalam":"ml","Bengali":"bn","French":"fr",
    "Spanish":"es","German":"de","Japanese":"ja","Chinese":"zh",
    "Arabic":"ar","Portuguese":"pt",
}
