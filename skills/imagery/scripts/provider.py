#!/usr/bin/env python3
"""Multi-provider image generation abstraction.

Provides a unified CLI for image generation across providers:
  - cstudio: Creative Studio CLI binary
  - vertex-curl: Google Vertex AI Imagen via gcloud + urllib

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

    def _post(self, url: str, body: dict, token: str) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"API returned {exc.code}: {body_text}") from exc

    def _read_image_b64(self, path: str) -> str:
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()

    def _write_image_b64(self, b64data: str, path: str) -> None:
        self._ensure_parent(path)
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64data))

    # operations ------------------------------------------------------------

    def generate(self, prompt: str, output: str, **opts) -> dict:
        try:
            token = self._token()
            url = self._endpoint(self.GENERATE_MODEL)
            body = {
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1},
            }
            resp = self._post(url, body, token)
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
            resp = self._post(url, body, token)
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
            resp = self._post(url, body, token)
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
# Registry & detection
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, BaseProvider] = {
    "cstudio": CStudioProvider(),
    "vertex-curl": VertexCurlProvider(),
}

PRIORITY_ORDER = ["cstudio", "vertex-curl"]


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
            "No image providers detected. "
            "Install cstudio CLI or set GOOGLE_CLOUD_PROJECT + gcloud."
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
