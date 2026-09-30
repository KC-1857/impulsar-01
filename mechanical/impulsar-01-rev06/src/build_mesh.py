"""Build the Impulsar-01 rev06 enclosure meshes from project sources."""
import argparse
import json
from common import ROOT, BUILD, SOURCE, config, output_dir, read_panels
from geometry import construct
import mesh_backend as k
from manufacturing import export
from validation import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(BUILD / 'mesh'))
    parser.add_argument('--config')
    args = parser.parse_args()
    out = output_dir(args.output)
    cfg = config(args.config)
    originals = [k.load(SOURCE / f'Corpus_paz_{n}.stl') for n in ('foot', 'top')]
    panels = read_panels()
    solids, hardware = construct(k, cfg, originals, panels)
    checks = {}
    for name, solid in solids.items():
        mesh = k.as_mesh(solid)
        assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split()) == 1, name
        folder = out / 'assembly'
        folder.mkdir(exist_ok=True)
        mesh.export(folder / f'{name}.stl')
        reference_name = name + '_assembly' if name.endswith('_acrylic') else name
        ref = k.load(ROOT / 'assembly' / f'{reference_name}.stl')
        delta = abs((solid-ref).volume()) + abs((ref-solid).volume())
        checks[name] = {'symmetric_difference_mm3': delta, 'volume_mm3': mesh.volume}
        print(name, checks[name], flush=True)
    for name in ('body', 'lid', 'glazing_bar'):
        mesh = k.as_mesh(solids[name])
        if name == 'lid':
            mesh.apply_transform([ [1, 0, 0, 0], [0, -1, 0, 95], [0, 0, -1, 60], [0, 0, 0, 1] ])
        elif name == 'glazing_bar':
            mesh.apply_translation(-mesh.bounds[0])
        (out / 'print').mkdir(exist_ok=True)
        mesh.export(out / 'print' / f'{name}_print.stl')
    (out / 'parameters.json').write_text(json.dumps(cfg, indent=2) + '\n')
    (out / 'comparison.json').write_text(json.dumps(checks, indent=2) + '\n')
    if cfg == config():
        assert all(c['symmetric_difference_mm3'] < .01 for c in checks.values()), checks
    export(out, solids, panels, cfg)
    report = validate(solids, hardware, cfg, panels)
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Verified', len(report['clearance_checks_mm3']), 'clearance checks; saved', out)


if __name__ == '__main__':
    main()
