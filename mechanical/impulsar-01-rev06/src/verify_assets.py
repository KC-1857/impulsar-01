"""Check the self-contained rev06 sources and manufacturing baseline."""
import argparse
import hashlib
import json
import numpy as np
import trimesh
from common import ROOT, BUILD, SOURCE, output_dir, read_panels


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def mesh_check(path, on_bed=False):
    mesh = trimesh.load_mesh(path)
    result = {'watertight': bool(mesh.is_watertight),
              'winding_consistent': bool(mesh.is_winding_consistent),
              'components': len(mesh.split()), 'volume_mm3': float(mesh.volume),
              'bounds_mm': mesh.bounds.tolist(), 'sha256': digest(path)}
    assert result['watertight'] and result['winding_consistent'], path
    assert result['components'] == 1 and result['volume_mm3'] > 0, path
    if on_bed:
        assert abs(mesh.bounds[0, 2]) < 1e-4 and np.all(np.isfinite(mesh.bounds)) and np.all(mesh.extents > 0), path
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(BUILD/'audit'))
    args = parser.parse_args()
    out = output_dir(args.output)
    hashes = json.loads((ROOT/'reference'/'assets.sha256.json').read_text())
    for name, expected in hashes.items():
        assert digest(ROOT/name) == expected, name
    source_hashes = json.loads((ROOT/'reference'/'source.sha256.json').read_text())
    for name, expected in source_hashes.items():
        assert digest(SOURCE/name) == expected, name
    checks = {str(p.relative_to(ROOT)): mesh_check(p, folder != 'assembly')
              for folder in ('assembly', 'print', 'coupons') for p in sorted((ROOT/folder).glob('*.stl'))}
    read_panels()
    scene = trimesh.load(ROOT/'multicolor'/'lid_multicolor.3mf', force='scene')
    assert len(scene.geometry) == 3
    assert all(m.is_watertight and m.is_winding_consistent for m in scene.geometry.values())
    lid = trimesh.load_mesh(ROOT/'print'/'lid_print.stl')
    assert abs(sum(m.volume for m in scene.geometry.values())-lid.volume) < .01
    report = {'baseline_assets': len(hashes), 'source_files': source_hashes, 'meshes': checks,
              'multicolor_parts': 3, 'physical_fit_verified': False}
    (out/'assets-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Verified', len(hashes), 'baseline assets and', len(checks), 'meshes')


if __name__ == '__main__':
    main()
