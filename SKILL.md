---
name: chem-figure-to-json
description: Extract strict JSON from chemical reaction images, schemes, tables, supporting-information figures, or scanned chemical diagrams. Use when Codex needs to convert visual chemistry into structured reactants, products, reagents, catalysts, solvents, temperatures, times, yields, stereochemistry, R-group definitions, or reaction metadata.
---

# Chem Figure to JSON Extraction

Convert visual chemical information into a strict JSON object. Use this skill for reaction scheme images, synthetic route figures, chemical table screenshots, literature reaction-condition images, and molecule/reaction images that need JSON or JSONL training data.

Do not use this skill for general chemistry explanation unless the user asks for structured extraction.

## Core Rules

1. Process multiple images one by one. Return one top-level JSON object per requested output unless the user specifies JSONL or another wrapper.
2. Return only valid JSON unless the user explicitly asks for explanation.
3. Represent each example product or substrate row as one entry in `reactions`.
4. Use `relations` as the only relationship field. Do not emit `relation`.
5. Put visible R-group definitions from the generalized reaction template only in the first reaction entry's first reactant `relations`.
6. Convert structural formulas to standard SMILES before writing final JSON.
7. Use concrete standard SMILES in `text` for reactants, products, solvents, catalysts, and reagents.
8. Preserve yield, ee, dr, loading, equivalents, time, and other visible metadata as strings in `relations` only when that exact text appears in the image.
9. Do not process reaction mechanism content.
10. Never copy E-SMILES, generalized formulas, or placeholder structures into final JSON `text`. Final `text` values must not contain `*`, `<sep>`, `<a>`, `</a>`, `R[`, `R1`, `R2`, or other R-group placeholders.
11. Treat OCSR output from `general_reactant_*.png` as reaction-template evidence only. Do not use it directly as any final `reactants.text`.
12. For each example reaction, set `reactants.text` to a concrete standard SMILES. If a concrete substrate/reactant structure is visible, use its normalized OCSR result. If only concrete products are visible, infer the corresponding concrete reactant SMILES from the product structure and the generalized reaction template. If the concrete reactant cannot be inferred reliably, do not fall back to E-SMILES or placeholders.
13. Put only information explicitly written in the image into `relations`, such as visible R-group definitions, yield, ee, dr, er, loading, equivalents, time, pressure, stereochemical notes, step labels, and other printed metadata. Do not add inferred, explanatory, summarized, file, crop, box, OCSR, or example-number content. Use `[]` when no visible relation text is present.
14. Put generalized R-group definitions such as `R = alkyl, aryl`, `R1 = Alk`, or `R2 = Ar` only in `reactions[0]` on the first object whose `type` is `reactants`, and only if that definition is visibly printed in the image. Do not repeat these definitions in later reactions or on products/reagents.
15. Normalize all Celsius temperatures in final JSON and cached normalized condition text to the literal Unicode degree-symbol format `°C`, for example `80 °C` or `110 °C`. Do not write corrupted or alternative encodings such as `80 掳C`, `80 deg C`, `80 ℃`, `80C`, or `80 C`.
16. For multi-step synthetic routes, treat each visible arrow or step as its own reaction entry in `reactions`.
17. For each multi-step entry, include only that step's reactants, products or intermediates, reagents, catalysts, solvents, temperatures, times, pressures, yields, and other visible conditions.
18. Do not merge conditions across steps. Do not copy a step-specific condition to another step unless the figure explicitly shows that the condition applies to both.
19. An intermediate can be the previous step's `products` and the next step's `reactants`, but each step still keeps its own conditions.
20. If a visible step marker such as `1`, `2`, `step 1`, `step 2`, `a`, `b`, `i`, or `ii` is printed, copy the exact visible marker into `relations` for objects belonging to that step, for example `["1", "10 mol%"]` or `["2", "85% yield"]`. If no marker is visibly printed, do not invent one; keep step assignment only in the cache.


## Workflow

1. Create a `.txt` cache file with the same base name as each source image. Record every MolDet v2 result, selected box, cropped structure, OCSR result, reagent, condition, relation, and uncertainty there before composing JSON.
2. Create `tmp/<sample-name>/` under the working directory for temporary cropped structure images.
3. Run MolDet v2 from this skill directory on the original source PNG before any structure crop:

```powershell
conda run -n base python scripts/moldetv2.py <source-png> --output tmp/<sample-name>/<sample-name>.boxes.png
```

4. Cache the MolDet v2 stdout JSON. Record `count`, every `detections[].box`, and the human semantic label assigned to each used box, such as `general reactant`, `general product`, `ligand`, or `example product 1`.
5. Determine whether the image is a single-step scheme/examples figure or a multi-step synthetic route. Use visible arrows, layout, and printed step markers as evidence.
6. For a multi-step synthetic route, record each arrow or step boundary in the cache before composing JSON. For each step, cache the visible step marker if present, participating structures, and only the conditions visibly assigned to that step.
7. For a single-step reaction scheme or examples figure, use the existing generalized-template and examples workflow below.
8. Inspect `tmp/<sample-name>/<sample-name>.boxes.png` before cropping. The annotation image should contain only blue boxes and no text labels. Confirm each target chemical structure is covered by an appropriate box.
9. Crop chemical structures from the original source image, not from the box-annotated image. Use MolDet v2 coordinates as `box: [x1, y1, x2, y2]` in original-image pixels.
10. If a model box is missing, incomplete, merged with another molecule, or includes too much non-structure text, manually adjust the crop bounds and record the original box, adjusted crop, and reason in the cache file.
11. Name every cropped PNG by its semantic role so the filename distinguishes generalized-scheme structures from examples and multi-step-route structures:

```text
tmp/<sample-name>/general_reactant_01.png
tmp/<sample-name>/general_product_01.png
tmp/<sample-name>/general_reagent_01.png
tmp/<sample-name>/general_catalyst_01.png
tmp/<sample-name>/general_ligand_01.png
tmp/<sample-name>/example_01_substrate.png
tmp/<sample-name>/example_01_product.png
tmp/<sample-name>/example_02_product.png
tmp/<sample-name>/step_01_reactant_01.png
tmp/<sample-name>/step_01_product_01.png
tmp/<sample-name>/step_02_intermediate_01.png
```

12. Use lowercase ASCII filenames with underscores. Use two-digit example and step numbers in visual reading order. Add a numeric suffix for multiple structures with the same role, such as `general_reactant_02.png`, `example_03_product_02.png`, or `step_02_reagent_02.png`.
13. Record the same filename in the cache entry for each selected or adjusted box, together with its semantic label and OCSR output.
14. Identify the generalized reaction scheme, usually at the top of the image. Crop the general reactant, product, and reagent(catalyst or ligand) structures into separately named PNG files in `tmp/<sample-name>/`.
15. Identify the examples section. Crop each product or substrate/product example structure into `tmp/<sample-name>/` using the selected or adjusted MolDet v2 boxes and the `example_<nn>_<role>.png` naming pattern.
16. For multi-step synthetic routes, crop each step's structures with the `step_<nn>_<role>_<mm>.png` naming pattern and keep the step assignment in the cache even when no visible step marker is printed.
17. Run the bundled OCSR client from this skill directory for each cropped PNG:

```powershell
conda run -n base python scripts/ocsr.py <cropped-png>
```

18. Treat stdout as the raw OCSR recognition result. It may already be a standard SMILES string, or it may be an E-SMILES-style result containing markers such as `<sep>`.
19. Treat stderr as diagnostics only. If the command fails, report the failure concisely and include the relevant stderr message.
20. Cache the raw OCSR output with its source filename and label, such as `general_reactant_01.png`, `general_product_01.png`, `example_01_product.png`, or `step_01_product_01.png`.
21. Parse generalized-scheme OCSR outputs as templates only. Cache the raw template output, but do not copy `general_reactant_*.png` E-SMILES or placeholder SMILES into final JSON.
22. Build each example reaction's concrete `reactants.text` before composing final JSON. Prefer visible concrete substrate/reactant crops; otherwise infer the concrete reactant standard SMILES from the concrete example product and the generalized reaction template. Cache the inference basis, but do not put inference notes in final `relations`.
23. For multi-step synthetic routes, assemble `reactions` by step, not by the whole image. Each arrow or step becomes one entry with only that step's visible conditions.
24. Extract visible text conditions and relations, including catalysts, solvents, temperatures, times, pressures, yields, ee, dr, step markers, and R-group definitions.
25. Normalize visible Celsius text to the literal `°C` form in final JSON, even if OCR or terminal output shows corrupted degree-symbol text.
26. Convert cached raw OCSR output into standard SMILES before final JSON. If a raw result contains `<sep>` or R-group/abbreviation syntax, parse and normalize it manually instead of copying it into final JSON.
27. Before returning final JSON, check that no `text` contains `*`, `<sep>`, `<a>`, `R[`, or R-group placeholders; only `reactions[0]` first reactant has visible R-group definitions in `relations`; all relation-free objects use `[]`; every Celsius temperature uses `°C`; every multi-step arrow or step is a separate `reactions` entry; step-specific conditions appear only on their visible step; visible step markers are copied exactly into that step's `relations`; and invisible markers are not invented.
28. When abbreviations such as `Me`, `Ph`, `Boc`, solvents, or reagent shorthand need expansion, read `references/group_abbreviation.tsv`.

## Script Behavior

- `scripts/moldetv2.py` must be run with `conda run -n base python`.
- `scripts/moldetv2.py` accepts one PNG path and defaults to `scripts/moldet_v2_yolo11n_640_general.pt`.
- `scripts/moldetv2.py` prints detection JSON to stdout and saves a box-only annotated PNG to the `--output` path, or to `<input>.moldetv2.png` when `--output` is omitted.
- `scripts/moldetv2.py` JSON contains `count`, `detections`, and `detections[].box` coordinates as `[x1, y1, x2, y2]` in original-image pixels.
- `scripts/moldetv2.py` exits with code `1` on missing files, non-PNG inputs, model-load failures, prediction failures, or annotation save failures.
- `scripts/ocsr.py` accepts exactly one cropped PNG path after MolDet-guided cropping.
- `scripts/ocsr.py` requires Python with the `requests` package available.
- `scripts/ocsr.py` sends a JSON payload with a base64-encoded image to `https://ocsr.dp.tech/mol/img2mol`.
- `scripts/ocsr.py` uses Chrome-like request headers and includes a built-in 2-second delay before each request.
- `scripts/ocsr.py` prints the raw OCSR result to stdout.
- `scripts/ocsr.py` exits with code `1` on missing files, non-PNG inputs, request failures, non-JSON responses, or API errors.

## Constraints

- Do not call `/mol/draw_mol`, generate SVG, render molecules, or create image previews unless the user explicitly asks for those tasks.
- Do not perform live API recognition tests unless the user explicitly asks for validation with an image.
- If Python cannot import `requests`, tell the user that the local Python environment needs `requests` installed.
- If network or sandbox permissions block the request, tell the user that the OCSR API call could not be reached and that network permission may be required.
- Do not use E-SMILES, generalized reactant templates, or R-group placeholder structures directly in the final JSON output.
- Escape backslashes in SMILES according to JSON syntax. For example, write `\\` inside JSON strings.

## Required Output Contract

The top-level object must contain `reactions`, an array of reaction entries. Each reaction entry is an array of objects with exactly these fields:

- `text`: a string containing concrete standard SMILES, source text for unreliably converted non-structural reagents, or a condition value such as `80 °C` or `rt`. Do not include E-SMILES, `<sep>`, `*`, `<a>`, `R[`, or R-group placeholders.
- `type`: one of `reactants`, `products`, `reagent`, `temperature`, `pressure`, `time`, or another concise lowercase condition type when needed.
- `relations`: an array of strings copied from visible image text, with only whitespace and Celsius-unit normalization allowed. Use an empty array when no visible relation text is present. Put generalized R-group definitions only on the first reaction's first reactant. For multi-step routes, include visible step markers only on entries belonging to that step and never invent missing markers.

Use this shape:

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
