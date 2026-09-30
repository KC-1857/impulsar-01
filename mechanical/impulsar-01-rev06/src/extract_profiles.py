"""Reproduce the measured planar profiles used to reconstruct the native CAD blanks."""
import argparse
import json
import numpy as np
from shapely.geometry import LineString
from common import BUILD, SOURCE, output_dir
from mesh_backend import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(BUILD/'profiles'))
    out = output_dir(parser.parse_args().output)
    profiles = {}
    for name, heights in [('foot', [.5, 2.25, 2.75, 3.75, 7.55, 25, 43.5]),
                          ('top', [43.5, 50.5, 54])]:
        solid = load(SOURCE/f'Corpus_paz_{name}.stl')
        for z in heights:
            rings = []
            for ring in solid.slice(z).to_polygons():
                points = LineString([*ring, ring[0]]).simplify(.00001).coords
                rings.append(np.round(points, 6).tolist())
            profiles[f'{name}_{z}'] = rings
    (out/'source_profiles.json').write_text(json.dumps(profiles, indent=2)+'\n')


if __name__ == '__main__':
    main()
