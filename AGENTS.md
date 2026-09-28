# Repository guidance

## Current state

- This checkout contains specifications, diagrams, and mechanical assets with Python/FreeCAD generators under `mechanical/impulsar-01-rev06/`; no station application or CI exists. Mechanical dependencies and build commands are local to that variant's README.
- README features and backlog statuses describe the intended product and project progress, not runnable code in this checkout. SRS §5 lists hardware acceptance scenarios, not automated tests.
- OpenSpec references in `CHANGELOG.md` and the SRS are stale for this checkout: there is no `openspec/` directory or configured OpenSpec workflow.

## Requirements and scope

- Read `docs/vision-ru.md` for MVP boundaries and `docs/srs-ru.md` for detailed requirements, subsystem IDs (П1–П7), and acceptance criteria. `docs/hardware-ru.md` is a hardware reference, not the requirements authority.
- The target is Orange Pi CM4/RK3566 (aarch64), ALT Linux with kernel 6.18, ReSpeaker 2-Mic HAT/WM8960, and a USB Zigbee coordinator. Vendor BSP kernel versions in the hardware reference are not the project target.
- MVP speech recognition runs locally on CPU and maps a fixed Russian command vocabulary to Zigbee actions. The vision explicitly excludes Internet dependence, a web UI, audio output/TTS, and an LLM.
- Requirements are still inconsistent: SRS UC-03 assumes SSH access while NFR-2.6 forbids it; the LED table in §4.1 and NFR-3.1 name different phases. Surface relevant conflicts when changing these behaviors rather than silently treating one statement as settled.

## Documentation and assets

- Keep Russian in `docs/*-ru.md` and `README-RU.md`; `README.md` is the English counterpart. Reflect shared README changes in both languages.
- Backlog IDs (`US-1.1`, etc.) differ from story-map IDs (`US-01`, etc.); match stories by meaning rather than assuming identical numbering. The backlog's completion rule requires acceptance criteria to be met, a `CHANGELOG.md` entry, and consistency with the SRS.
- Diagram sources are `docs/diagrams/diag-*.uml`; the SRS embeds corresponding PNGs from `docs/images/`. Keep source and rendered images aligned when changing diagrams; no rendering command is configured in the repo.
- Hardware diagnostics are documented in `docs/hardware-ru.md` §2.4 and run on the station. Firmware and proprietary binaries are supplied by OS images/packages and must not be added to this repository.
- Preserve original mechanical assets. Rev06 is self-contained: use its local `source/` inputs and ignored `build/` output, with commands run from the variant directory. Keep generation printer-independent, verify geometry before publishing exports, and keep baseline parameters/checksums in `reference/` distinct from validation reports. `design.json` is input; generated parameter reports are not. Native CAD and baseline mesh exports are separate representations. Digital fit checks do not close SRS physical acceptance.
