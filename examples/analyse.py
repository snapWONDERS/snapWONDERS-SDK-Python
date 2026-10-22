#
# snapWONDERS API — Python SDK example
#
# Copyright (c) 2026 Kenneth Springer @ snapWONDERS. MIT Licensed — see LICENSE.
# Author: Kenneth Springer @ snapWONDERS <kenneth@snapwonders.com> (https://kennethbspringer.au)
#
# Forensic analysis: grade an image A–F and download the overlay assets it produces.
# Run:  SNAPWONDERS_API_KEY=sw_... python examples/analyse.py [path/to/image.jpg]
#

import os
import sys
from pathlib import Path

from snapwonders import Client

HERE = Path(__file__).parent
OUT = HERE / "out" / "analyse"


def main() -> None:
    key = os.environ.get("SNAPWONDERS_API_KEY")
    if not key:
        raise SystemExit("Set SNAPWONDERS_API_KEY (get one at https://snapwonders.com/sign-up)")

    image = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "assets" / "sample.png")
    client = Client(api_key=key)

    print(f"Analysing {image} …")
    job = client.analyse.run([image], face_detection=True)
    print(f"  status: {job.status}")

    for item in job.results():
        print(f"\n  {item.filename}")
        print(f"    grade         : {item.grade}")
        print(f"    faces         : {item.face_count}")
        print(f"    text regions  : {item.text_region_count}")
        print(f"    watermark     : {item.watermark_flagged}")
        v = item.verdicts
        if v:
            print(f"    AI generation : {(v.get('ai_generation') or {}).get('verdict')}")
            print(f"    C2PA          : {(v.get('c2pa') or {}).get('verdict')}")
            print(f"    camera match  : {(v.get('camera_fingerprint') or {}).get('encoder_name')}")
            for finding in v.get("findings", []):
                print(f"    finding       : {finding.get('label')} ({finding.get('severity')})")
            # forensic / audio_splice / video_tamper carry the WHY behind the grade — the exact
            # data a thin "grade: F" response was missing (see the SDK README's "why this exists").
            forensic = v.get("forensic") or {}
            if forensic:
                ela = forensic.get("ela") or {}
                if ela:
                    print(f"    ELA           : {ela.get('high_fraction')} high-residual, {ela.get('anomaly_tile_count')} anomaly tile(s)")
                noise = forensic.get("noise_inconsistency") or {}
                if noise:
                    print(f"    noise map     : {noise.get('anomaly_tile_count')} anomaly tile(s)")
            audio_splice = v.get("audio_splice") or {}
            if audio_splice:
                print(f"    audio splice  : {audio_splice.get('verdict')} ({audio_splice.get('spike_count')} spike(s), noise CoV {audio_splice.get('noise_cov')})")
            video_tamper = v.get("video_tamper") or {}
            if video_tamper:
                tamper = video_tamper.get("inter_frame_tamper") or {}
                if tamper:
                    print(f"    inter-frame   : {tamper.get('verdict')} ({tamper.get('spike_count')} spike(s) / {tamper.get('frame_count_checked')} frames checked)")
                dup = video_tamper.get("frame_duplicate") or {}
                if dup:
                    print(f"    dup frames    : {dup.get('dup_verdict')} ({dup.get('dup_count')} duplicate(s))")
                gps = video_tamper.get("gps_triangle") or {}
                if gps.get("applicable"):
                    print(f"    GPS triangle  : {gps.get('verdict')} (Δ{gps.get('delta_secs')}s, {gps.get('timezone')})")
        for asset in item.assets:          # e.g. ELA map, face overlay
            path = asset.download(str(OUT) + "/")
            print(f"    asset         : {asset.name} → {path}")

    print("\nDone. See", OUT)


if __name__ == "__main__":
    main()
