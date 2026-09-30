"""Digital fit checks; these do not certify a physical assembly."""
import itertools
import numpy as np
from shapely.geometry import Polygon
from geometry import place
import mesh_backend as k


def validate(solids, hardware, cfg, panels):
    foot, lid, bar = (solids[n] for n in ('body', 'lid', 'glazing_bar'))
    case = foot + lid
    checks = {}

    def clear(name, a, b):
        volume = abs((a ^ b).volume())
        checks[name] = volume
        assert volume < .01, (name, volume)

    clear('halves', foot, lid)
    clear('bar_case', bar, case)
    for name, poly in panels.items():
        panel = solids[name+'_acrylic']
        clear(name+'_case', panel, case+bar)
        for hname, h in hardware.items():
            clear(name+'_'+hname, panel, h)
        if name != 'top':
            points = k.as_mesh(panel).vertices
            swept = k.mf.Manifold.hull_points(np.vstack([points, points+[0, 0, 60]]))
            clear(name+'_insertion', swept, foot)
        for i, ring in enumerate(poly.interiors):
            tool = k.section(Polygon(ring)).extrude(30).translate([0, 0, -10])
            tool = place(tool, name, cfg['acrylic_thickness_mm'],
                         58-(cfg['groove_width_mm']+cfg['acrylic_thickness_mm'])/2)
            clear(f'{name}_opening_{i}', tool, case+bar)
    for name, h in hardware.items():
        if name.startswith('bar_screw'):
            clear(name+'_bar', h, bar)
            clear(name+'_body', h, foot)
            x = 28 if name.endswith('0') else 74
            clear(name+'_driver', k.cylinder(x, 84.1, 35, 50.9, 2.5), lid+bar+solids['top_acrylic'])
        else:
            clear(name+'_case', h, case+bar)
    for (an, a), (bn, b) in itertools.combinations(hardware.items(), 2):
        clear(an+'_'+bn, a, b)
    for dz in np.linspace(0, 55, 23):
        clear(f'lid_lift_{dz:g}', lid.translate([0, 0, float(dz)]), foot)
        clear(f'bar_install_{dz:g}', bar.translate([0, 0, -float(dz)]), lid+solids['top_acrylic'])
        clear(f'bolt_insert_{dz:g}', hardware['bolt_A'].translate([0, 0, -float(dz)]), case+bar)
    for distance in np.linspace(0, 1.8, 37):
        clear(f'glass_slide_{distance:g}', solids['top_acrylic'].translate([0, float(distance), 0]), lid)
    for distance in np.linspace(0, 25, 26):
        clear(f'glass_approach_{distance:g}', solids['top_acrylic'].translate([0, 1.8, -float(distance)]), lid)
    nut_motion = max(abs((hardware[name].translate([direction*float(x), 0, 0]) ^ lid).volume())
                     for name, direction in (('nut_A', 1), ('nut_B', -1)) for x in np.linspace(0, 10, 81))
    assert nut_motion < .5, nut_motion
    retention = {n: (solids['top_acrylic'].translate([0, 0, -.2]) ^ s).volume()
                 for n, s in [('front', lid), ('rear', bar)]}
    assert all(v > .1 for v in retention.values()), retention
    interference = {n: (s ^ lid).volume() for n, s in hardware.items() if n.startswith('bar_screw')}
    assert all(0 < v < 6 for v in interference.values()), interference
    return {'clearance_checks_mm3': checks, 'retention_mm3': retention,
            'nut_entry_interference_max_mm3': nut_motion,
            'self_tapping_interference_mm3': interference, 'physical_fit_verified': False}
