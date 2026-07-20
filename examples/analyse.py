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
        for asset in item.assets:          # e.g. ELA map, face overlay
            path = asset.download(str(OUT) + "/")
            print(f"    asset         : {asset.name} → {path}")

    print("\nDone. See", OUT)


if __name__ == "__main__":
    main()
