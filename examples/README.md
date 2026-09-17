# Examples — snapWONDERS Python SDK

Runnable, self-contained examples. Each needs an API key
([sign up free](https://snapwonders.com/sign-up)) in the `SNAPWONDERS_API_KEY` environment variable.

```bash
pip install snapwonders          # or:  pip install -e ..
export SNAPWONDERS_API_KEY=sw_your_key_here

python examples/hide_and_reveal.py     # steganography: hide a file in an image, then reveal it
python examples/analyse.py             # forensic analysis: grade an image A–F + overlay assets
python examples/convert.py             # media conversion: JPEG → WebP
```

Outputs are written to `examples/out/` (git-ignored). `assets/sample.png` is a generated placeholder
— pass your own image to `analyse.py` (`python examples/analyse.py my-photo.jpg`) or swap the file in
`assets/` for richer results.

## See it in action

[**WALKTHROUGH.md**](WALKTHROUGH.md) shows the real input/output images and a real forensic analysis JSON result from running these examples.
