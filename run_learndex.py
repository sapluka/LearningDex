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


def verify_llm(result_path):
    """Check note generation inside the packaged executable with synthetic text."""
    import json
    from pathlib import Path

    from app import agents, config, llm

    try:
        settings = config.load()
        info = {"title": "测试", "duration": 600,
                "subtitle": "先解释概念，再结合步骤和实例说明。" * 150}
        note = agents.summarize(settings, info)
        result = {"ok": bool(note and note.strip()), "characters": len(note or "")}
    except Exception as error:
        result = {"ok": False, "error_type": type(error).__name__,
                  "connection_error": llm.is_connection_error(error)}
    Path(result_path).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--verify-asr":
        verify_asr(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 3 and sys.argv[1] == "--verify-llm":
        verify_llm(sys.argv[2])
    else:
        from app.main import main
        main()
