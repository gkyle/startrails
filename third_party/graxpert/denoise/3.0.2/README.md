# GraXpert Denoising Model 3.0.2

Unmodified model by the **GraXpert Development Team**.
Upstream: https://github.com/Steffenhir/GraXpert/

This model is licensed under **CC BY-NC-SA 4.0**, independently of StarTrails'
MIT-licensed code. See the original attribution and contributor notice in
[LICENSE.html](LICENSE.html), and the full license in [LICENSE.txt](LICENSE.txt).
License URL: https://creativecommons.org/licenses/by-nc-sa/4.0/

StarTrails redistributes these unchanged weights for noncommercial distribution.
Retain these notices when redistributing the model. Commercial redistribution
requires separate permission from the rights holder. No endorsement is implied.

## Preparing a release

Obtain denoising model **3.0.2** through the official GraXpert application's model
download function. Copy its `model.onnx` into `models/graxpert/denoise/3.0.2/` without conversion,
quantization or other modification. The original `LICENSE.html` is retained here.
The model must be 477,703,971 bytes with SHA-256:

```text
e61c880e7fb955917e91141660e66801c9de5c4f3d9946dc449e5a7dd7346563
```

The large weight file is excluded from Git. `python build/models.py` verifies
its pinned identity, copies these notices beside it, and includes them in the existing versioned model
archive alongside the application's other models. Users receive it through the
normal installer model download; they do not need a separate GraXpert install.
No GraXpert Python application code or S3 credentials are bundled.
