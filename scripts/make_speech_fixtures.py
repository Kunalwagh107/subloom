"""Generate redistributable synthetic test speech entirely locally with eSpeak NG.

Usage: python scripts/make_speech_fixtures.py --espeak PATH/TO/espeak-ng.exe
Generated audio is synthetic, not a substitute for native-speaker quality review.
"""
import argparse
import json
from pathlib import Path
import subprocess
import shutil

CORPUS = {
    "english": {"voice": "en-us", "reference": "Hello everyone. Today we will learn about neural networks. This recording stays on this computer."},
    "hindi": {"voice": "hi", "reference": "नमस्ते दोस्तों। आज हम पढ़ाई करेंगे। यह एक छोटी हिंदी रिकॉर्डिंग है। आपका स्वागत है।"},
    "hinglish": {"voice": "hi", "reference": "नमस्ते दोस्तों। आज हम neural networks समझेंगे। यह machine learning का एक example है। हम Python में code लिखेंगे।"},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--espeak", type=Path, default=shutil.which("espeak-ng"), help="Installed or portable eSpeak NG executable")
    parser.add_argument("--output", type=Path, default=Path(".test-data/corpus"))
    args = parser.parse_args()
    if args.espeak is None:
        parser.error("Install eSpeak NG or pass --espeak with its executable path.")
    args.output.mkdir(parents=True, exist_ok=True)
    for key, item in CORPUS.items():
        text = args.output / (key + ".txt")
        text.write_text(item["reference"], encoding="utf-8")
        data_root = args.espeak.resolve().parent
        data_args = ["--path=" + str(data_root)] if (data_root / "espeak-ng-data").is_dir() else []
        subprocess.run([str(args.espeak.resolve()), *data_args, "-v", item["voice"], "-s", "135", "-f", str(text.resolve()),
                        "-w", str((args.output / (key + ".wav")).resolve())], check=True)
    (args.output / "references.json").write_text(json.dumps(CORPUS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated English, Hindi and Hinglish speech in {args.output}")


if __name__ == "__main__":
    main()
