"""Round-trip and fit checks for a generated native FreeCAD model."""
import argparse
import json
from pathlib import Path
import FreeCAD as App
import Part
import numpy as np
import trimesh
from common import ROOT, BUILD, SOURCE, config, output_dir, read_panels
from geometry import construct
from validation import validate
import mesh_backend as k


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=BUILD/'cad')
    parser.add_argument('--edit-check', action='store_true', help='Also recompute after changing all five spreadsheet dimensions')
    args = parser.parse_args()
    out = output_dir(args.directory)
    doc = App.openDocument(str(out/'enclosure.FCStd'))
    objects = {o.Label: o for g in (doc.PrintedParts, doc.AcrylicPanels) for o in g.Group}
    report = {'parts': {}, 'physical_fit_verified': False}
    solids = {}
    for name, obj in objects.items():
        shape = obj.Shape
        assert shape.isValid() and len(shape.Solids) == 1 and shape.Volume > 0, name
        step = Part.Shape()
        step.read(str(out/'step'/f'{name}.step'))
        assert step.isValid() and len(step.Solids) == 1, name
        step_delta = abs(step.Volume-shape.Volume)
        assert step_delta < .001, (name, step_delta)
        mesh = trimesh.load_mesh(out/'assembly'/f'{name}.stl')
        assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split()) == 1, name
        solid = k.load(out/'assembly'/f'{name}.stl')
        assert solid.status() == k.mf.Error.NoError, name
        reference = name+'_assembly' if name.endswith('_acrylic') else name
        ref = k.load(ROOT/'assembly'/f'{reference}.stl')
        delta = abs((solid-ref).volume())+abs((ref-solid).volume())
        entry = {'valid': True, 'solids': 1, 'volume_mm3': shape.Volume,
                 'step_volume_difference_mm3': step_delta,
                 'baseline_symmetric_difference_mm3': delta,
                 'baseline_difference_fraction': delta/ref.volume()}
        report['parts'][name] = entry
        print(name, entry, flush=True)
        solids[name] = solid
    assembly = Part.Shape()
    assembly.read(str(out/'step'/'enclosure.step'))
    assert assembly.isValid() and len(assembly.Solids) == 8
    for name in ('body', 'lid', 'glazing_bar'):
        mesh = trimesh.load_mesh(out/'print'/f'{name}_print.stl')
        assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split()) == 1, name
        assert abs(mesh.bounds[0, 2]) < 1e-4 and np.all(np.isfinite(mesh.bounds)) and np.all(mesh.extents > 0), name
    (out/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    assert all(p['baseline_difference_fraction'] < .001 for p in report['parts'].values()), report
    _, hardware = construct(k, config(), [k.load(SOURCE/f'Corpus_paz_{n}.stl') for n in ('foot', 'top')], read_panels())
    report['fit'] = validate(solids, hardware, config(), read_panels())
    if args.edit_check:
        before = {n: o.Shape.Volume for n, o in objects.items()}
        for cell, value in [('B2', '2.80'), ('B3', '3.05'), ('B4', '1.75'), ('B5', '0.95'), ('B6', '1.35')]:
            doc.Parameters.set(cell, value)
        print('Recomputing edited spreadsheet', flush=True)
        doc.recompute()
        edited = {}
        for name, obj in objects.items():
            assert obj.Shape.isValid() and len(obj.Shape.Solids) == 1, name
            assert abs(obj.Shape.Volume-before[name]) > .01, name
            edited[name] = obj.Shape.Volume
        assert not [o.Name for o in doc.Objects if 'Invalid' in o.State]
        report['spreadsheet_edit_volumes_mm3'] = edited
    App.closeDocument(doc.Name)  # Test edits never overwrite the published model.
    (out/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print('CAD checks passed', flush=True)


if __name__ == '__main__':
    main()
