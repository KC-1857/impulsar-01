"""Run with Python matching FreeCAD's ABI, with its lib directory on PYTHONPATH."""
import argparse
import json
import time
import FreeCAD as App
import MeshPart
import Part
from common import BUILD, config, output_dir, read_panels
from geometry import construct
from cad_backend import Backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(BUILD / 'cad'))
    parser.add_argument('--config')
    args = parser.parse_args()
    out = output_dir(args.output)
    cfg = config(args.config)
    doc = App.newDocument('ImpulsarRev06')
    doc.Label = 'Импульсар-01 / rev06'
    k = Backend(doc, cfg)
    solids, hardware = construct(k, k.config, k.originals(), read_panels())
    print('Recomputing', len(doc.Objects), 'native objects', flush=True)
    for i, obj in enumerate(doc.Objects):
        start = time.monotonic()
        doc.recompute([obj])
        print('Recompute', i, obj.Name, round(time.monotonic()-start, 2), flush=True)
        if hasattr(obj, 'Shape') and obj.Shape.isNull():
            doc.saveAs(str(out / 'failed.FCStd'))
            raise RuntimeError(f'Null shape: {obj.Name}, {obj.State}')
    checks = {}
    for name, solid in {**solids, **hardware}.items():
        shape = solid.obj.Shape
        checks[name] = {'valid': shape.isValid(), 'solids': len(shape.Solids), 'volume_mm3': shape.Volume}
        print(name, checks[name], flush=True)
        assert shape.isValid() and len(shape.Solids) == 1 and shape.Volume > 0, name
        solid.obj.Label = name
    for obj in doc.Objects:
        if hasattr(obj, 'Visibility'):
            obj.Visibility = False
    for solid in solids.values():
        solid.obj.Visibility = True
    for name, objects in [('PrintedParts', {n: solids[n] for n in ('body', 'lid', 'glazing_bar')}),
                          ('AcrylicPanels', {n: s for n, s in solids.items() if n.endswith('_acrylic')}),
                          ('HardwareEnvelopes', hardware)]:
        group = doc.addObject('App::DocumentObjectGroup', name)
        group.Group = [s.obj for s in objects.values()]
    doc.recompute()
    doc.saveAs(str(out / 'enclosure.FCStd'))
    (out / 'step').mkdir(exist_ok=True)
    (out / 'assembly').mkdir(exist_ok=True)
    (out / 'print').mkdir(exist_ok=True)
    for name, solid in solids.items():
        shape = solid.obj.Shape
        shape.exportStep(str(out / 'step' / f'{name}.step'))
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=.01, AngularDeflection=.1, Relative=False)
        mesh.write(str(out / 'assembly' / f'{name}.stl'))
        if name in ('body', 'lid', 'glazing_bar'):
            printable = shape.copy()
            if name == 'lid':
                printable.rotate(App.Vector(), App.Vector(1, 0, 0), 180)
                printable.translate(App.Vector(0, 95, 60))
            elif name == 'glazing_bar':
                bb = printable.BoundBox
                printable.translate(App.Vector(-bb.XMin, -bb.YMin, -bb.ZMin))
            MeshPart.meshFromShape(Shape=printable, LinearDeflection=.01, AngularDeflection=.1, Relative=False).write(str(out / 'print' / f'{name}_print.stl'))
    Part.makeCompound([s.obj.Shape for s in solids.values()]).exportStep(str(out / 'step' / 'enclosure.step'))
    (out / 'construction.json').write_text(json.dumps({'FreeCAD': App.Version(), 'checks': checks}, indent=2)+'\n')
    print('Saved', out, flush=True)


if __name__ == '__main__':
    main()
