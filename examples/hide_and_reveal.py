#
# snapWONDERS API — Python SDK example
#
# Copyright (c) 2026 Kenneth Springer @ snapWONDERS. MIT Licensed — see LICENSE.
# Author: Kenneth Springer @ snapWONDERS <kenneth@snapwonders.com> (https://kennethbspringer.au)
#
# Steganography: hide a secret file inside a cover image, then reveal it back out.
# Run:  SNAPWONDERS_API_KEY=sw_... python examples/hide_and_reveal.py
#

import os
from pathlib import Path

from snapwonders import Client

HERE = Path(__file__).parent
OUT = HERE / "out"


def main() -> None:
    key = os.environ.get("SNAPWONDERS_API_KEY")
    if not key:
        raise SystemExit("Set SNAPWONDERS_API_KEY (get one at https://snapwonders.com/sign-up)")

    client = Client(api_key=key)

    # A "secret" (any media file) and a "cover" image to hide it inside. The secret and cover must be
    # two different files, and the cover's shortest side must be at least 512px.
    secret = HERE / "assets" / "secret.png"
    cover = HERE / "assets" / "sample.png"

    print("Hiding — the SDK creates a session, uploads both files, runs the job, and waits …")
    job = client.stego.hide([str(secret), str(cover)], password="Str0ng!Pass")
    print(f"  status: {job.status}")

    stego = None
    for result in job.results():
        stego = result.download(str(OUT) + "/")   # a trailing "/" writes into the directory
        print(f"  stego image → {stego}")

    print("Revealing the hidden file back out …")
    revealed = client.stego.reveal(str(stego), password="Str0ng!Pass")
    for result in revealed.results():
        path = result.download(str(OUT / "recovered") + "/")
        print(f"  recovered → {path}")

    print("Done. See", OUT)


if __name__ == "__main__":
    main()
