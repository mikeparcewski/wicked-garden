#!/usr/bin/env python3
"""Multi-provider image generation abstraction.

Provides a unified CLI for image generation across providers:
  - cstudio: Creative Studio CLI binary
  - vertex-curl: Google Vertex AI Imagen via gcloud + urllib
  - openai: OpenAI Images API (DALL-E 3 / gpt-image-1)
  - stability: Stability AI (Stable Diffusion 3.5)
  - replicate: Replicate (Flux models)

Usage:
    python3 provider.py generate --prompt "..." --output ./out.png [--provider auto]
    python3 provider.py edit --image ./in.png --prompt "..." --output ./out.png
    python3 provider.py inpaint --image ./in.png --mask ./mask.png --prompt "..." --output ./out.png
    python3 provider.py detect
    python3 provider.py list-providers
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# Provider base
# ---------------------------------------------------------------------------

class BaseProvider:
    """Interface that every provider must implement."""

    name: str = ""

    def detect(self) -> bool:
        """Return True if this provider is available in the current env."""
        raise NotImplementedError

    def generate(self, prompt: str, output: str, **opts) -> dict:
        raise NotImplementedError

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        raise NotImplementedError

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        raise NotImplementedError

    # helpers ---------------------------------------------------------------

    def _ok(self, operation: str, output_path: str, **metadata) -> dict:
        return {
            "ok": True,
            "provider": self.name,
            "operation": operation,
            "output_path": output_path,
            "metadata": metadata,
        }

    def _fail(self, error: str) -> dict:
        return {"ok": False, "provider": self.name, "error": error}

    @staticmethod
    def _ensure_parent(path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_image_b64(path: str) -> str:
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()

    @staticmethod
    def _write_image_b64(b64data: str, path: str) -> None:
        BaseProvider._ensure_parent(path)
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64data))

    @staticmethod
    def _write_image_bytes(data: bytes, path: str) -> None:
        BaseProvider._ensure_parent(path)
        with open(path, "wb") as fh:
            fh.write(data)

    @staticmethod
    def _http_json(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
        """POST JSON and return parsed response."""
        data = json.dumps(body).encode()
        hdrs = {"Content-Type": "application/json", **headers}
        req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"API returned {exc.code}: {body_text}") from exc

    @staticmethod
    def _http_download(url: str, path: str, timeout: int = 60) -> None:
        """Download a URL to a file path."""
        BaseProvider._ensure_parent(path)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(path, "wb") as fh:
                fh.write(resp.read())


# ---------------------------------------------------------------------------
# cstudio provider
# ---------------------------------------------------------------------------

class CStudioProvider(BaseProvider):
    """Creative Studio CLI wrapper."""

    name = "cstudio"

    def _bin(self) -> str:
        return os.environ.get("CSTUDIO_PATH", "cstudio")

    def detect(self) -> bool:
        custom = os.environ.get("CSTUDIO_PATH")
        if custom:
            return os.path.isfile(custom) and os.access(custom, os.X_OK)
        return shutil.which("cstudio") is not None

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=120
        )

    def generate(self, prompt: str, output: str, **opts) -> dict:
        self._ensure_parent(output)
        cmd = [self._bin(), "generate", "image", "--prompt", prompt, "--output", output]
        try:
            result = self._run(cmd)
            if result.returncode != 0:
                return self._fail(f"cstudio exited {result.returncode}: {result.stderr.strip()}")
            return self._ok("generate", output, prompt=prompt)
        except FileNotFoundError:
            return self._fail("cstudio binary not found")
        except subprocess.TimeoutExpired:
            return self._fail("cstudio timed out after 120s")
        except Exception as exc:
            return self._fail(str(exc))

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        self._ensure_parent(output)
        cmd = [self._bin(), "edit", "image", "--image", image, "--prompt", prompt, "--output", output]
        try:
            result = self._run(cmd)
            if result.returncode != 0:
                return self._fail(f"cstudio exited {result.returncode}: {result.stderr.strip()}")
            return self._ok("edit", output, prompt=prompt, source_image=image)
        except FileNotFoundError:
            return self._fail("cstudio binary not found")
        except subprocess.TimeoutExpired:
            return self._fail("cstudio timed out after 120s")
        except Exception as exc:
            return self._fail(str(exc))

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        self._ensure_parent(output)
        cmd = [
            self._bin(), "inpaint", "image",
            "--image", image, "--mask", mask,
            "--prompt", prompt, "--output", output,
        ]
        try:
            result = self._run(cmd)
            if result.returncode != 0:
                return self._fail(f"cstudio exited {result.returncode}: {result.stderr.strip()}")
            return self._ok("inpaint", output, prompt=prompt, source_image=image, mask=mask)
        except FileNotFoundError:
            return self._fail("cstudio binary not found")
        except subprocess.TimeoutExpired:
            return self._fail("cstudio timed out after 120s")
        except Exception as exc:
            return self._fail(str(exc))


# ---------------------------------------------------------------------------
# vertex-curl provider
# ---------------------------------------------------------------------------

class VertexCurlProvider(BaseProvider):
    """Google Vertex AI Imagen via gcloud auth + urllib.request."""

    name = "vertex-curl"

    GENERATE_MODEL = "imagen-3.0-generate-001"
    EDIT_MODEL = "imagen-3.0-capability-001"

    def detect(self) -> bool:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            return False
        return shutil.which("gcloud") is not None

    # internals -------------------------------------------------------------

    def _project(self) -> str:
        return os.environ["GOOGLE_CLOUD_PROJECT"]

    def _location(self) -> str:
        return os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    def _token(self) -> str:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gcloud auth failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _endpoint(self, model: str) -> str:
        loc = self._location()
        proj = self._project()
        return (
            f"https://{loc}-aiplatform.googleapis.com/v1/"
            f"projects/{proj}/locations/{loc}/"
            f"publishers/google/models/{model}:predict"
        )

    def _vertex_post(self, url: str, body: dict, token: str) -> dict:
        return self._http_json(url, body, {"Authorization": f"Bearer {token}"})

    # operations ------------------------------------------------------------

    def generate(self, prompt: str, output: str, **opts) -> dict:
        try:
            token = self._token()
            url = self._endpoint(self.GENERATE_MODEL)
            body = {
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1},
            }
            resp = self._vertex_post(url, body, token)
            preds = resp.get("predictions") or []
            if not preds or "bytesBase64Encoded" not in preds[0]:
                return self._fail("API returned no predictions — check quota, project ID, or prompt safety filters")
            self._write_image_b64(preds[0]["bytesBase64Encoded"], output)
            return self._ok(
                "generate", output,
                model=self.GENERATE_MODEL, prompt=prompt,
            )
        except Exception as exc:
            return self._fail(str(exc))

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        try:
            token = self._token()
            url = self._endpoint(self.EDIT_MODEL)
            b64src = self._read_image_b64(image)
            body = {
                "instances": [{
                    "prompt": prompt,
                    "image": {"bytesBase64Encoded": b64src},
                }],
                "parameters": {"sampleCount": 1},
            }
            resp = self._vertex_post(url, body, token)
            preds = resp.get("predictions") or []
            if not preds or "bytesBase64Encoded" not in preds[0]:
                return self._fail("API returned no predictions — check quota, project ID, or prompt safety filters")
            self._write_image_b64(preds[0]["bytesBase64Encoded"], output)
            return self._ok(
                "edit", output,
                model=self.EDIT_MODEL, prompt=prompt, source_image=image,
            )
        except Exception as exc:
            return self._fail(str(exc))

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        try:
            token = self._token()
            url = self._endpoint(self.EDIT_MODEL)
            b64src = self._read_image_b64(image)
            b64mask = self._read_image_b64(mask)
            body = {
                "instances": [{
                    "prompt": prompt,
                    "image": {"bytesBase64Encoded": b64src},
                    "mask": {"image": {"bytesBase64Encoded": b64mask}},
                }],
                "parameters": {"sampleCount": 1},
            }
            resp = self._vertex_post(url, body, token)
            preds = resp.get("predictions") or []
            if not preds or "bytesBase64Encoded" not in preds[0]:
                return self._fail("API returned no predictions — check quota, project ID, or prompt safety filters")
            self._write_image_b64(preds[0]["bytesBase64Encoded"], output)
            return self._ok(
                "inpaint", output,
                model=self.EDIT_MODEL, prompt=prompt,
                source_image=image, mask=mask,
            )
        except Exception as exc:
            return self._fail(str(exc))


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseProvider):
    """OpenAI Images API (gpt-image-1 / DALL-E 3)."""

    name = "openai"

    GENERATE_MODEL = "gpt-image-1"
    EDIT_MODEL = "gpt-image-1"
    API_BASE = "https://api.openai.com/v1"

    def detect(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}

    def generate(self, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/images/generations"
            body = {
                "model": self.GENERATE_MODEL,
                "prompt": prompt,
                "n": 1,
                "size": opts.get("size", "1024x1024"),
                "response_format": "b64_json",
            }
            resp = self._http_json(url, body, self._headers())
            data = resp.get("data") or []
            if not data:
                return self._fail("API returned no images — check prompt or billing")
            b64 = data[0].get("b64_json")
            if not b64:
                # Fallback: download from URL
                img_url = data[0].get("url")
                if img_url:
                    self._http_download(img_url, output)
                else:
                    return self._fail("API returned no image data")
            else:
                self._write_image_b64(b64, output)
            return self._ok("generate", output, model=self.GENERATE_MODEL, prompt=prompt)
        except Exception as exc:
            return self._fail(str(exc))

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/images/edits"
            boundary = "----WickedGardenBoundary"
            img_data = Path(image).read_bytes()
            img_name = Path(image).name
            import io
            buf = io.BytesIO()
            for part_text in [("model", self.EDIT_MODEL), ("prompt", prompt), ("response_format", "b64_json")]:
                buf.write(f"--{boundary}\r\n".encode())
                buf.write(f'Content-Disposition: form-data; name="{part_text[0]}"\r\n\r\n'.encode())
                buf.write(f"{part_text[1]}\r\n".encode())
            # image file part
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(f'Content-Disposition: form-data; name="image"; filename="{img_name}"\r\n'.encode())
            buf.write(b"Content-Type: image/png\r\n\r\n")
            buf.write(img_data)
            buf.write(b"\r\n")
            buf.write(f"--{boundary}--\r\n".encode())

            req = urllib.request.Request(
                url, data=buf.getvalue(), method="POST",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
            data = result.get("data") or []
            if not data:
                return self._fail("API returned no images from edit")
            b64 = data[0].get("b64_json")
            if b64:
                self._write_image_b64(b64, output)
            else:
                img_url = data[0].get("url")
                if img_url:
                    self._http_download(img_url, output)
                else:
                    return self._fail("API returned no image data from edit")
            return self._ok("edit", output, model=self.EDIT_MODEL, prompt=prompt, source_image=image)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            return self._fail(f"API returned {exc.code}: {body_text}")
        except Exception as exc:
            return self._fail(str(exc))

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/images/edits"
            boundary = "----WickedGardenBoundary"
            img_data = Path(image).read_bytes()
            mask_data = Path(mask).read_bytes()
            import io
            buf = io.BytesIO()
            for field, value in [("model", self.EDIT_MODEL), ("prompt", prompt), ("response_format", "b64_json")]:
                buf.write(f"--{boundary}\r\n".encode())
                buf.write(f'Content-Disposition: form-data; name="{field}"\r\n\r\n'.encode())
                buf.write(f"{value}\r\n".encode())
            for field, data, fname in [("image", img_data, Path(image).name), ("mask", mask_data, Path(mask).name)]:
                buf.write(f"--{boundary}\r\n".encode())
                buf.write(f'Content-Disposition: form-data; name="{field}"; filename="{fname}"\r\n'.encode())
                buf.write(b"Content-Type: image/png\r\n\r\n")
                buf.write(data)
                buf.write(b"\r\n")
            buf.write(f"--{boundary}--\r\n".encode())

            req = urllib.request.Request(
                url, data=buf.getvalue(), method="POST",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
            data = result.get("data") or []
            if not data:
                return self._fail("API returned no images from inpaint")
            b64 = data[0].get("b64_json")
            if b64:
                self._write_image_b64(b64, output)
            else:
                img_url = data[0].get("url")
                if img_url:
                    self._http_download(img_url, output)
                else:
                    return self._fail("API returned no image data from inpaint")
            return self._ok("inpaint", output, model=self.EDIT_MODEL, prompt=prompt, source_image=image, mask=mask)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            return self._fail(f"API returned {exc.code}: {body_text}")
        except Exception as exc:
            return self._fail(str(exc))


# ---------------------------------------------------------------------------
# Stability AI provider
# ---------------------------------------------------------------------------

class StabilityProvider(BaseProvider):
    """Stability AI (Stable Diffusion 3.5) via REST API."""

    name = "stability"
    API_BASE = "https://api.stability.ai/v2beta/stable-image"

    def detect(self) -> bool:
        return bool(os.environ.get("STABILITY_API_KEY"))

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['STABILITY_API_KEY']}",
            "Accept": "application/json",
        }

    def _multipart_post(self, url: str, fields: list, files: list) -> dict:
        """POST multipart/form-data with text fields and file uploads."""
        boundary = "----WickedGardenBoundary"
        import io
        buf = io.BytesIO()
        for name, value in fields:
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            buf.write(f"{value}\r\n".encode())
        for name, data, filename, content_type in files:
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            buf.write(f"Content-Type: {content_type}\r\n\r\n".encode())
            buf.write(data)
            buf.write(b"\r\n")
        buf.write(f"--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            url, data=buf.getvalue(), method="POST",
            headers={
                "Authorization": f"Bearer {os.environ['STABILITY_API_KEY']}",
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"API returned {exc.code}: {body_text}") from exc

    def generate(self, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/generate/sd3"
            fields = [
                ("prompt", prompt),
                ("output_format", "png"),
                ("model", opts.get("model", "sd3.5-large")),
            ]
            if opts.get("negative_prompt"):
                fields.append(("negative_prompt", opts["negative_prompt"]))
            resp = self._multipart_post(url, fields, [])
            b64 = resp.get("image")
            if not b64:
                return self._fail("API returned no image data")
            self._write_image_b64(b64, output)
            return self._ok("generate", output, model="sd3.5-large", prompt=prompt)
        except Exception as exc:
            return self._fail(str(exc))

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/generate/sd3"
            img_data = Path(image).read_bytes()
            fields = [
                ("prompt", prompt),
                ("output_format", "png"),
                ("model", opts.get("model", "sd3.5-large")),
                ("mode", "image-to-image"),
                ("strength", str(opts.get("strength", 0.7))),
            ]
            files = [("image", img_data, Path(image).name, "image/png")]
            resp = self._multipart_post(url, fields, files)
            b64 = resp.get("image")
            if not b64:
                return self._fail("API returned no image data from edit")
            self._write_image_b64(b64, output)
            return self._ok("edit", output, model="sd3.5-large", prompt=prompt, source_image=image)
        except Exception as exc:
            return self._fail(str(exc))

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        try:
            url = f"{self.API_BASE}/edit/inpaint"
            img_data = Path(image).read_bytes()
            mask_data = Path(mask).read_bytes()
            fields = [
                ("prompt", prompt),
                ("output_format", "png"),
            ]
            files = [
                ("image", img_data, Path(image).name, "image/png"),
                ("mask", mask_data, Path(mask).name, "image/png"),
            ]
            resp = self._multipart_post(url, fields, files)
            b64 = resp.get("image")
            if not b64:
                return self._fail("API returned no image data from inpaint")
            self._write_image_b64(b64, output)
            return self._ok("inpaint", output, model="sd3.5-large", prompt=prompt, source_image=image, mask=mask)
        except Exception as exc:
            return self._fail(str(exc))


# ---------------------------------------------------------------------------
# Replicate provider
# ---------------------------------------------------------------------------

class ReplicateProvider(BaseProvider):
    """Replicate API (Flux models)."""

    name = "replicate"

    GENERATE_MODEL = "black-forest-labs/flux-1.1-pro"
    EDIT_MODEL = "black-forest-labs/flux-fill-pro"
    API_BASE = "https://api.replicate.com/v1"

    def detect(self) -> bool:
        return bool(os.environ.get("REPLICATE_API_TOKEN"))

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['REPLICATE_API_TOKEN']}",
            "Prefer": "wait",
        }

    def _predict(self, model: str, input_data: dict) -> dict:
        """Create a prediction and wait for result (sync mode)."""
        url = f"{self.API_BASE}/models/{model}/predictions"
        body = {"input": input_data}
        hdrs = {**self._headers(), "Content-Type": "application/json"}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST", headers=hdrs,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"API returned {exc.code}: {body_text}") from exc

    def _download_output(self, result: dict, output: str) -> str | None:
        """Extract image URL from prediction output and download it."""
        out = result.get("output")
        if not out:
            return "API returned no output — check model and input"
        # Output can be a URL string or a list of URLs
        img_url = out[0] if isinstance(out, list) else out
        if not isinstance(img_url, str) or not img_url.startswith("http"):
            return f"Unexpected output format: {type(out)}"
        self._http_download(img_url, output)
        return None

    def generate(self, prompt: str, output: str, **opts) -> dict:
        try:
            input_data = {"prompt": prompt}
            if opts.get("aspect_ratio"):
                input_data["aspect_ratio"] = opts["aspect_ratio"]
            result = self._predict(self.GENERATE_MODEL, input_data)
            if result.get("status") == "failed":
                return self._fail(f"Prediction failed: {result.get('error', 'unknown')}")
            err = self._download_output(result, output)
            if err:
                return self._fail(err)
            return self._ok("generate", output, model=self.GENERATE_MODEL, prompt=prompt)
        except Exception as exc:
            return self._fail(str(exc))

    def edit(self, image: str, prompt: str, output: str, **opts) -> dict:
        try:
            b64src = self._read_image_b64(image)
            input_data = {
                "prompt": prompt,
                "image": f"data:image/png;base64,{b64src}",
            }
            result = self._predict(self.EDIT_MODEL, input_data)
            if result.get("status") == "failed":
                return self._fail(f"Prediction failed: {result.get('error', 'unknown')}")
            err = self._download_output(result, output)
            if err:
                return self._fail(err)
            return self._ok("edit", output, model=self.EDIT_MODEL, prompt=prompt, source_image=image)
        except Exception as exc:
            return self._fail(str(exc))

    def inpaint(self, image: str, mask: str, prompt: str, output: str, **opts) -> dict:
        try:
            b64src = self._read_image_b64(image)
            b64mask = self._read_image_b64(mask)
            input_data = {
                "prompt": prompt,
                "image": f"data:image/png;base64,{b64src}",
                "mask": f"data:image/png;base64,{b64mask}",
            }
            result = self._predict(self.EDIT_MODEL, input_data)
            if result.get("status") == "failed":
                return self._fail(f"Prediction failed: {result.get('error', 'unknown')}")
            err = self._download_output(result, output)
            if err:
                return self._fail(err)
            return self._ok("inpaint", output, model=self.EDIT_MODEL, prompt=prompt, source_image=image, mask=mask)
        except Exception as exc:
            return self._fail(str(exc))


# ---------------------------------------------------------------------------
# Registry & detection
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, BaseProvider] = {
    "cstudio": CStudioProvider(),
    "vertex-curl": VertexCurlProvider(),
    "openai": OpenAIProvider(),
    "stability": StabilityProvider(),
    "replicate": ReplicateProvider(),
}

PRIORITY_ORDER = ["cstudio", "vertex-curl", "openai", "stability", "replicate"]


def detect_providers() -> list[str]:
    """Return names of available providers in priority order."""
    return [name for name in PRIORITY_ORDER if PROVIDERS[name].detect()]


def select_provider(requested: str) -> BaseProvider:
    """Resolve a provider by name or auto-detect the best available one."""
    if requested and requested != "auto":
        if requested not in PROVIDERS:
            raise ValueError(f"Unknown provider: {requested}")
        prov = PROVIDERS[requested]
        if not prov.detect():
            raise RuntimeError(f"Provider '{requested}' is not available in this environment")
        return prov

    available = detect_providers()
    if not available:
        raise RuntimeError(
            "No image providers detected. Options: "
            "cstudio CLI, gcloud + GOOGLE_CLOUD_PROJECT, "
            "OPENAI_API_KEY, STABILITY_API_KEY, or REPLICATE_API_TOKEN."
        )
    return PROVIDERS[available[0]]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-provider image generation CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate an image from a text prompt")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("--output", required=True)
    gen.add_argument("--provider", default="auto")

    # edit
    ed = sub.add_parser("edit", help="Edit an existing image with a prompt")
    ed.add_argument("--image", required=True)
    ed.add_argument("--prompt", required=True)
    ed.add_argument("--output", required=True)
    ed.add_argument("--provider", default="auto")

    # inpaint
    inp = sub.add_parser("inpaint", help="Inpaint a masked region of an image")
    inp.add_argument("--image", required=True)
    inp.add_argument("--mask", required=True)
    inp.add_argument("--prompt", required=True)
    inp.add_argument("--output", required=True)
    inp.add_argument("--provider", default="auto")

    # detect
    sub.add_parser("detect", help="List available providers in this environment")

    # list-providers
    sub.add_parser("list-providers", help="List all supported providers")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "detect":
            available = detect_providers()
            print(json.dumps({
                "ok": True,
                "available": available,
                "default": available[0] if available else None,
            }))
            return

        if args.command == "list-providers":
            print(json.dumps({
                "ok": True,
                "providers": [
                    {"name": name, "available": PROVIDERS[name].detect()}
                    for name in PRIORITY_ORDER
                ],
            }))
            return

        provider = select_provider(args.provider)

        if args.command == "generate":
            result = provider.generate(args.prompt, args.output)
        elif args.command == "edit":
            result = provider.edit(args.image, args.prompt, args.output)
        elif args.command == "inpaint":
            result = provider.inpaint(args.image, args.mask, args.prompt, args.output)
        else:
            result = {"ok": False, "provider": "", "error": f"Unknown command: {args.command}"}

        print(json.dumps(result))
        sys.exit(0 if result.get("ok") else 1)

    except Exception as exc:
        print(json.dumps({"ok": False, "provider": "", "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
