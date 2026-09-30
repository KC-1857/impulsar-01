import json
from pathlib import Path
import ezdxf
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'
SOURCE = ROOT / 'source'


def config(path=None):
    cfg = json.loads(Path(path or ROOT / 'design.json').read_text())
    if not 2.8 <= cfg['groove_width_mm'] <= 3.2:
        raise ValueError('Groove width must be in [2.8, 3.2] mm')
    if not 2.5 <= cfg['acrylic_thickness_mm'] < cfg['groove_width_mm']:
        raise ValueError('Acrylic must be >=2.5 mm and thinner than its groove')
    for key, low, high in [('through_hole_radius_mm', 1.5, 1.9),
                           ('bar_pilot_radius_mm', .7, 1.0),
                           ('bar_clearance_radius_mm', 1.15, 1.5)]:
        if not low <= cfg[key] <= high:
            raise ValueError(f'{key} must be in [{low}, {high}]')
    return cfg


def read_panels():
    panels = {}
    for name in ('front', 'rear', 'left', 'right', 'top'):
        doc = ezdxf.readfile(ROOT / 'laser' / f'{name}_2p85.dxf')
        if doc.units != 4:
            raise ValueError(f'{name}: expected millimetres')
        contours = {}
        for layer in ('CUT_OUTER', 'CUT_INNER'):
            entities = list(doc.modelspace().query(f'LWPOLYLINE[layer=="{layer}"]'))
            if any(not e.closed or any(p[4] for p in e.get_points()) for e in entities):
                raise ValueError(f'{name}: open or curved polyline')
            contours[layer] = [[tuple(p[:2]) for p in e.get_points()] for e in entities]
        if len(contours['CUT_OUTER']) != 1:
            raise ValueError(f'{name}: expected one outline')
        panels[name] = Polygon(contours['CUT_OUTER'][0], contours['CUT_INNER'])
        if not panels[name].is_valid:
            raise ValueError(f'{name}: invalid contour')
    return panels


def output_dir(path):
    out = Path(path).resolve()
    if out == ROOT or out in ROOT.parents or (ROOT in out.parents and out != BUILD and BUILD not in out.parents):
        raise ValueError('Build into a separate directory, never into published assets')
    out.mkdir(parents=True, exist_ok=True)
    return out
