"""Downloads the model weights into the image at build time (TORCH_HOME),
so a scaled-from-zero instance doesn't fetch them on its first job."""
from demucs.pretrained import get_model

for name in ("htdemucs_6s", ):
    get_model(name)
    print(f"Downloaded {name}")
