"""Local CPU/GPU comparison using the same model and decoding options. Never downloads."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from subloom.hardware import detect
from subloom.media import probe
from subloom.models import ModelManager
from subloom.process import Cancellation
from subloom.whisper_engine import WhisperEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("--models", type=Path, default=Path(".test-data/models"))
    parser.add_argument("--model", choices=["base", "small", "medium"], default="small")
    parser.add_argument("--report", type=Path, default=Path(".test-data/benchmark.json"))
    parser.add_argument("--fast", action="store_true", help="Explicitly compare faster greedy decoding; may reduce recognition accuracy")
    parser.add_argument("--devices", nargs="+", choices=["CPU", "GPU"], default=["CPU", "GPU"])
    parser.add_argument("--profile", choices=["Eco", "Balanced", "Performance"], default="Balanced")
    args = parser.parse_args()
    token = Cancellation()
    media = probe(args.sample, token)
    report = {"hardware": asdict(detect()), "model": args.model, "profile": args.profile,
              "decoding": "fast" if args.fast else "standard", "sample_seconds": media.duration_ms / 1000, "results": {}}
    for device in args.devices:
        engine = WhisperEngine(ModelManager(args.models), args.report.parent / "benchmark-cache", fast_decode=args.fast)
        started = time.perf_counter()
        captions = engine.infer(media, media.default_track, args.model, args.profile, device, "hi", False,
                                token, lambda *_: None)
        elapsed = time.perf_counter() - started
        result = {"elapsed_seconds": round(elapsed, 3), "backend": engine.last_backend,
                  "real_time_factor": round(elapsed / (media.duration_ms / 1000), 4), "segments": len(captions)}
        report["results"][device] = result
        print(device, json.dumps(result), flush=True)
    if {"CPU", "GPU"}.issubset(report["results"]):
        cpu, gpu = report["results"]["CPU"], report["results"]["GPU"]
        report["measured_sample_speedup"] = round(cpu["elapsed_seconds"] / gpu["elapsed_seconds"], 2)
    report["warning"] = "This sample measurement is not a guarantee for long/noisy/other-language videos. Startup and disk work are included."
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Report:", args.report)


if __name__ == "__main__":
    main()
