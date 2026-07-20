#
# snapWONDERS API — Python SDK example
#
# Copyright (c) 2026 Kenneth Springer @ snapWONDERS. MIT Licensed — see LICENSE.
# Author: Kenneth Springer @ snapWONDERS <kenneth@snapwonders.com> (https://kennethbspringer.au)
#
# Media conversion: convert an image to another format (here JPEG → WebP).
# Run:  SNAPWONDERS_API_KEY=sw_... python examples/convert.py
#

import os
from pathlib import Path

from snapwonders import Client

HERE = Path(__file__).parent
OUT = HERE / "out" / "convert"


def main() -> None:
    key = os.environ.get("SNAPWONDERS_API_KEY")
    if not key:
        raise SystemExit("Set SNAPWONDERS_API_KEY (get one at https://snapwonders.com/sign-up)")

    source = HERE / "assets" / "sample.png"
    client = Client(api_key=key)

    # `image_format`: jpeg | png | webp | avif | heic | jxl. (Video uses `video_format`.)
    print(f"Converting {source.name} → webp …")
    job = client.convert.run([str(source)], image_format="webp")
    print(f"  status: {job.status}")

    for result in job.results():
        path = result.download(str(OUT) + "/")
        print(f"  output → {path}  ({result.mime_type})")

    print("Done. See", OUT)


if __name__ == "__main__":
    main()
