# Chem Figure to JSON

Convert chemical reaction figures into strict JSON for downstream curation, model training, or literature data extraction.

This repository is packaged as a Codex skill. It guides an agent through molecule detection, structure cropping, OCSR recognition, condition extraction, and final JSON normalization for reaction schemes, synthetic routes, reaction tables, and supporting-information figures.

## What It Does

- Detects chemical structures in PNG figures with a bundled MolDet v2 YOLO model.
- Produces box-only molecule annotations to help select reliable crops.
- Recognizes cropped molecule images as SMILES through an OCSR API client.
- Converts visible reaction schemes, examples, routes, reagents, catalysts, solvents, temperatures, times, yields, ee, dr, and R-group definitions into a strict JSON schema.
- Handles both single-step reaction/example figures and multi-step synthetic routes.
- Enforces concrete standard SMILES in final JSON instead of placeholders, E-SMILES, or generalized R-group templates.
- Provides an abbreviation reference table for common chemistry shorthand such as Me, Ph, Boc, and related groups.

## Repository Layout

```text
.
|-- SKILL.md                                # Codex skill instructions and extraction contract
|-- README.md                               # Project overview and usage guide
|-- agents/
|   `-- openai.yaml                         # Optional agent configuration
|-- examples/
|   `-- example.json                        # Example output matching the required schema
|-- references/
|   `-- group_abbreviation.tsv              # Common group abbreviations and SMILES expansions
`-- scripts/
    |-- moldetv2.py                         # MolDet v2 molecule detector wrapper
    |-- moldet_v2_yolo11n_640_general.pt    # Bundled YOLO weights
    `-- ocsr.py                             # OCSR API client for cropped PNG structures
```

## Requirements

The workflow assumes:

- Python 3.10 or later.
- A Conda environment named `base` for the MolDet v2 command shown in `SKILL.md`.
- Python packages needed by `scripts/moldetv2.py`, including `ultralytics` and `opencv-python`.
- Python package `requests` for `scripts/ocsr.py`.
- RDKit for SMILES validation and normalization.
- PNG input images. The helper scripts intentionally reject non-PNG files.
- Network access for OCSR recognition, because `scripts/ocsr.py` calls `https://ocsr.dp.tech/mol/img2mol`.

Install RDKit with Conda:

```powershell
conda install -c conda-forge rdkit
```

The development `base` environment currently uses `rdkit==2024.03.5`, `ultralytics==8.4.62`, `torch==2.8.0+cu126`, and `torchvision==0.23.0+cu126`. If you need CUDA-enabled PyTorch, install the matching PyTorch build for your machine first.

Then install the remaining pip dependencies:

```powershell
pip install -r requirements.txt
```

If you use the exact commands from the skill, make sure those packages are available inside the Conda `base` environment.

## Usage

1. Install this repository as a Codex skill by placing the whole `ChemFigureToJson` directory in your Codex skills directory.

Windows:

```text
%USERPROFILE%\.codex\skills\ChemFigureToJson
```

macOS/Linux:

```text
~/.codex/skills/ChemFigureToJson
```

2. In Codex, ask the skill to convert the target figures:

```text
Please convert the Figure xxxx.png - xxxx.png to json, save in json dir.
```

The `json dir` means a `json/` directory under the current working directory. Codex will follow `SKILL.md` to detect structures, run OCSR, normalize SMILES, extract visible conditions, and save the final JSON files.

## Output Schema

The final output is one top-level JSON object with a `reactions` array. Each reaction entry is an array of objects with exactly these fields:

- `text`: concrete standard SMILES, source text for unreliably converted non-structural reagents, or a condition value such as `80 °C` or `rt`.
- `type`: `reactants`, `products`, `reagent`, `temperature`, `pressure`, `time`, or another concise lowercase condition type when needed.
- `relations`: visible relation text copied from the image, such as yield, ee, dr, equivalents, loading, R-group definitions, or step labels. Use `[]` when no relation text is visible.

Example:

```json
{
  "reactions": [
    [
      {
        "text": "O=C(CC#CC1CC1)c1ccccc1",
        "type": "reactants",
        "relations": [
          "R1 = Ph, p-BrC6H4, p-ClC6H4, (CH2)4",
          "R2 = H, (CH2)4",
          "R3 = p-MeC6H4, c-C3H5, p-t-BuC6H4, MeOCH2, Me(CH2)2"
        ]
      },
      {
        "text": "[Zn+2].[Cl-].[Cl-]",
        "type": "reagent",
        "relations": [
          "10 mol%"
        ]
      },
      {
        "text": "ClCCl",
        "type": "reagent",
        "relations": []
      },
      {
        "text": "rt",
        "type": "temperature",
        "relations": []
      },
      {
        "text": "c1ccc(-c2ccc(C3CC3)o2)cc1",
        "type": "products",
        "relations": [
          "85% yield"
        ]
      }
    ]
  ]
}
```

See `examples/example.json` for a longer example.

## Extraction Rules

The complete rules live in `SKILL.md`. The most important constraints are:

- Return valid JSON only when producing extraction results.
- Use `relations`, never `relation`.
- Use concrete standard SMILES in final `text` values.
- Do not copy E-SMILES, `<sep>`, `<a>`, `</a>`, `*`, `R1`, `R2`, or placeholder structures into final JSON.
- Treat generalized reactant OCSR results as template evidence only.
- Put visible generalized R-group definitions only on the first reaction entry's first reactant.
- Preserve visible metadata such as yield, ee, dr, loading, equivalents, time, pressure, and step labels in `relations`.
- Do not invent invisible metadata, inferred notes, crop names, file names, box coordinates, or OCSR diagnostics in final JSON.
- For multi-step synthetic routes, represent each visible arrow or step as a separate entry in `reactions`.
- Keep step-specific conditions attached only to the step where they visibly appear.
- Normalize Celsius temperatures to the exact `°C` form required by the skill contract.

## Script Reference

### `scripts/moldetv2.py`

Detects molecules in a PNG image and optionally saves an annotated PNG.

```powershell
conda run -n base python scripts/moldetv2.py <source-png> --output tmp\<sample>\<sample>.boxes.png
```

Useful options:

- `--model`: path to a custom YOLO weights file.
- `--output`: path for the annotated PNG.
- `--imgsz`: YOLO inference image size. Defaults to `640`.
- `--conf`: confidence threshold. Defaults to `0.5`.
- `--device`: optional YOLO device, such as `cpu` or `0`.
- `--no-save`: print detections without writing an annotation image.

Stdout contains JSON with `count`, `detections`, and `detections[].box` coordinates in original-image pixels.

### `scripts/ocsr.py`

Recognizes one cropped PNG chemical structure as a raw OCSR string.

```powershell
conda run -n base python scripts/ocsr.py <cropped-png>
```

The script prints the raw OCSR result to stdout. It requires the `requests` package and network access to the remote OCSR endpoint.

## Recommended Workflow for Agents

1. Read `SKILL.md` before processing images.
2. Create `tmp/<sample-name>/` for crops and annotation images.
3. Create a same-basename `.txt` cache for detections, selected boxes, crops, OCSR output, condition text, and uncertainties.
4. Run MolDet v2 on the original PNG.
5. Inspect the annotation image and crop target structures from the original PNG.
6. Run OCSR on each crop.
7. Normalize raw OCSR output to concrete standard SMILES.
8. Extract only visible conditions and relation text.
9. Build the final JSON object.
10. Validate the final JSON against the required contract before returning it.

## Limitations

- The OCSR helper depends on a live third-party API and may fail without network access.
- MolDet boxes can be incomplete, merged, or too broad; manual crop adjustment is expected.
- Generalized templates and R-group structures require chemical judgment before conversion to concrete SMILES.
- The skill is designed for structured extraction, not for general chemistry explanation or mechanism analysis.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](./LICENSE) file for details.

## Contributors

- [@zhaixiaoyi001](https://github.com/zhaixiaoyi001)
- [@jenniett](https://github.com/jenniett)
- [@xuhan323](https://github.com/xuhan323)
