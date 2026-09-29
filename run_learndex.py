import sys


def verify_asr(model_path, device, result_path):
    """Exercise the packaged speech runtime without opening the desktop UI."""
    import json
    import os
    import tempfile
    import wave
    from pathlib import Path

    from faster_whisper import WhisperModel

    audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.close()
    try:
        with wave.open(audio.name, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(bytes(32000))
        model = WhisperModel(model_path, device=device,
                             compute_type="float16" if device == "cuda" else "int8")
        segments, _ = model.transcribe(audio.name, language="zh", vad_filter=True)
        list(segments)
        result = {"ok": True, "device": device}
    except Exception as error:
        result = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    finally:
        os.remove(audio.name)
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--verify-asr":
        verify_asr(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        from app.main import main
        main()
