#!/usr/bin/env python
"""Detect and annotate molecules in a PNG image with the MolDet v2 YOLO model."""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
from pathlib import Path
from typing import Any


DEFAULT_MODEL_PATH = Path(__file__).resolve().with_name("moldet_v2_yolo11n_640_general.pt")
DEFAULT_CONFIG_ROOT = Path(__file__).resolve().parents[1] / ".ultralytics"


class MolDetError(RuntimeError):
    """Raised when MolDet v2 annotation fails."""


def _validate_png(path: Path) -> Path:
    if not path.exists():
        raise MolDetError(f"file not found: {path}")
    if not path.is_file():
        raise MolDetError(f"not a file: {path}")
    if path.suffix.lower() != ".png":
        raise MolDetError("input file must be a PNG")

    return path


def _validate_model(path: Path) -> Path:
    if not path.exists():
        raise MolDetError(f"model file not found: {path}")
    if not path.is_file():
        raise MolDetError(f"model path is not a file: {path}")

    return path


def _default_output_path(image_path: Path) -> Path:
    return image_path.with_name(f"{image_path.stem}.moldetv2.png")


def _load_model(model_path: Path) -> Any:
    DEFAULT_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(DEFAULT_CONFIG_ROOT))
    os.environ.setdefault("YOLO_VERBOSE", "False")
    _install_matplotlib_stub()

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise MolDetError(f"failed to import ultralytics: {exc}") from exc

    try:
        return YOLO(str(model_path))
    except Exception as exc:
        raise MolDetError(f"failed to load model: {exc}") from exc


def _install_matplotlib_stub() -> None:
    """Avoid importing a broken matplotlib build on detection-only Ultralytics paths."""

    if "matplotlib" in sys.modules:
        return

    matplotlib = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    matplotlib.__path__ = []
    matplotlib.pyplot = pyplot
    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot


def _name_for_class(names: Any, class_id: int) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))
    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return str(names[class_id])
    return str(class_id)


def _result_to_detections(result: Any) -> list[dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    names = getattr(result, "names", {})
    xyxy_values = boxes.xyxy.cpu().tolist()
    confidence_values = boxes.conf.cpu().tolist()
    class_values = boxes.cls.cpu().tolist()

    detections: list[dict[str, Any]] = []
    for box, confidence, class_value in zip(xyxy_values, confidence_values, class_values):
        class_id = int(class_value)
        detections.append(
            {
                "label": _name_for_class(names, class_id),
                "class_id": class_id,
                "confidence": round(float(confidence), 6),
                "box": [round(float(value), 2) for value in box],
            }
        )

    return detections


def _save_annotation(result: Any, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cv2
    except Exception as exc:
        raise MolDetError(f"failed to import cv2: {exc}") from exc

    annotated_image = result.plot(line_width=3, labels=False, conf=False)
    if not cv2.imwrite(str(output_path), annotated_image):
        raise MolDetError(f"failed to save annotated image: {output_path}")

    return output_path


def annotate_png(
    path: str,
    model_path: str | None = None,
    output_path: str | None = None,
    imgsz: int = 640,
    conf: float = 0.5,
    save: bool = True,
    device: str | None = None,
) -> dict[str, Any]:
    """Return MolDet v2 detections for a local PNG and optionally save an annotated image."""

    image_path = _validate_png(Path(path))
    model_file = _validate_model(Path(model_path) if model_path else DEFAULT_MODEL_PATH)
    output_file = Path(output_path) if output_path else _default_output_path(image_path)

    model = _load_model(model_file)
    predict_kwargs: dict[str, Any] = {
        "source": str(image_path),
        "imgsz": imgsz,
        "conf": conf,
        "save": False,
        "verbose": False,
    }
    if device:
        predict_kwargs["device"] = device

    try:
        results = model.predict(**predict_kwargs)
    except Exception as exc:
        raise MolDetError(f"prediction failed: {exc}") from exc

    if not results:
        raise MolDetError("prediction returned no results")

    result = results[0]
    height, width = getattr(result, "orig_shape", (None, None))
    detections = _result_to_detections(result)

    annotation_path = None
    if save:
        annotation_path = _save_annotation(result, output_file)

    return {
        "image_path": str(image_path),
        "model_path": str(model_file),
        "image_size": {"width": width, "height": height},
        "count": len(detections),
        "detections": detections,
        "annotated_path": str(annotation_path) if annotation_path else None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect molecules in a PNG image and save a MolDet v2 annotation."
    )
    parser.add_argument("png_path", help="Path to a local PNG image.")
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL_PATH),
        help="Path to the MolDet v2 YOLO weights file.",
    )
    parser.add_argument(
        "--output",
        help="Path for the annotated PNG. Defaults to '<input>.moldetv2.png'.",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO inference image size.")
    parser.add_argument("--conf", type=float, default=0.5, help="YOLO confidence threshold.")
    parser.add_argument("--device", help="Optional YOLO device, for example 'cpu' or '0'.")
    parser.add_argument("--no-save", action="store_true", help="Do not save the annotated PNG.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation for stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = annotate_png(
            args.png_path,
            model_path=args.model,
            output_path=args.output,
            imgsz=args.imgsz,
            conf=args.conf,
            save=not args.no_save,
            device=args.device,
        )
    except MolDetError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
