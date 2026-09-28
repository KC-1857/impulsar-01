"""Impulsar-01 rev06 enclosure construction, mm.

The shared geometry backend protocol uses
CSG solids, planar polygons, ruled lofts and rigid/reflection transforms.
"""
import itertools
import math


def construct(k, cfg, originals, panels):
    box, section, cylinder = k.box, k.section, k.cylinder
    width = cfg['groove_width_mm']
    thick = cfg['acrylic_thickness_mm']
    floor = 58 - width
    top_z = 58 - (width + thick) / 2

    def mirror(s, x=False, y=False):
        if x:
            s = s.mirror([1, 0, 0]).translate([102, 0, 0])
        if y:
            s = s.mirror([0, 1, 0]).translate([0, 95, 0])
        return s

    def opposite(s):
        return mirror(s, True, True)

    def yz(points, x0, x1):
        return section(points).extrude(x1-x0).transform(
            [[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])

    def taper(rect, z0, z1, e0, e1):
        x0, y0, x1, y1 = rect
        return k.loft([(z, section([(x0-e, y0-e), (x1+e, y0-e),
                                    (x1+e, y1+e), (x0-e, y1+e)]))
                       for z, e in ((z0, e0), (z1, e1))])

    slots = [(10.8, 4.15-width/2, 91.2, 4.15+width/2, 7.8, 53.2),
             (10.8, 90.85-width/2, 91.2, 90.85+width/2, 7.8, 53.2),
             (4.15-width/2, 11.3, 4.15+width/2, 83.7, 9.3, 51.7),
             (97.85-width/2, 11.3, 97.85+width/2, 83.7, 9.3, 51.7)]
    result = []
    for top, source in enumerate(originals):
        shape = source
        for fx, fy in itertools.product((False, True), repeat=2):
            shape += mirror(box([8.5, 0, 43 if top else 5.8], [14, 8.3, 55 if top else 43]), fx, fy)
            shape += mirror(box([0, 9, 43 if top else 7.3], [8.3, 15, 55 if top else 43]), fx, fy)
        for flip in (False, True):
            shape += mirror(box([8.5, 0, 50.2 if top else 5.8], [93.5, 8.3, 55 if top else 10.8]), y=flip)
            shape += mirror(box([0, 9, 48.7 if top else 7.3], [8.3, 86, 55 if top else 12.3]), x=flip)
            shape -= mirror(box([14, -1, 10.8], [88, 8.31, 50.2]), y=flip)
            shape -= mirror(box([-1, 15, 12.3], [8.31, 80, 48.7]), x=flip)
        if not top:
            for flip in (False, True):
                front = yz([(3.31, 2.5), (7, 2.5), (8.31, 5.81), (0, 5.81)], 8.5, 93.5)
                side = yz([(4.81, 2.5), (7, 2.5), (8.31, 7.31), (0, 7.31)], 9, 86)
                side = side.transform([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0]])
                shape += mirror(front, y=flip)
                shape += mirror(side, x=flip)
            shape -= (shape-source) ^ box([-.1, 37, 2.4], [8, 58, 7.6])
        shape = k.stage(shape, 'LidRails' if top else 'BodyRails')
        for x0, y0, x1, y1, low, high in slots:
            shape -= box([x0, y0, low], [x1, y1, high])
            shape -= taper((x0, y0, x1, y1), 43 if top else 42.4,
                           43.6 if top else 43, .4 if top else 0, 0 if top else .4)
        if top:
            shape += box([8.3, 12.3, 51], [93.7, 82.7, 60])
            shape -= box([10.8, 14.8, 42], [91.2, 80.2, 58])
            aperture = section(panels['top'].exterior.coords).translate([51, 47.5]).offset(-1.8)
            shape -= aperture.extrude(3).translate([0, 0, 58])
            shape -= k.loft([(59.4, aperture), (60.01, aperture.offset(.61))])
        # Preserve the original boolean sequence as well as the final envelope:
        # float32 STL tessellation is sensitive to coincident seam boundaries.
        old_profile = k.outline({'corner_chamfer_mm': 3, 'corner_blend_mm': .6})
        old_inset = old_profile.offset(-.6)
        old_envelope = k.loft([(43 if top else 0, old_inset),
                               (43.6 if top else .6, old_profile),
                               (59.4 if top else 42.4, old_profile),
                               (60 if top else 43, old_inset)])
        if not top:
            for x, y in itertools.product((6, 96), (6, 89)):
                old_envelope += box([x-2.3, y-2.3, 42.9], [x+2.3, y+2.3, 46.1])
        shape ^= old_envelope
        for flip in (False, True):
            for outer in (True, False):
                a, c = (-.01, .6) if outer else (7.7, 8.31)
                e, f = (.61, 0) if outer else (0, .61)
                tool = taper((14, 10.8, 88, 50.2), a, c, e, f)
                tool = tool.transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]])
                shape -= mirror(tool, y=flip)
                tool = taper((15, 12.3, 80, 48.7), a, c, e, f)
                tool = tool.transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
                shape -= mirror(tool, x=flip)
        result.append(k.stage(shape, 'LidGrooves' if top else 'BodyGrooves'))
    foot, lid = result
    window = (12.8, 16.8, 89.2, 78.2)
    lid -= box([12.8, 16.8, 58], [89.2, 78.2, 61])
    lid -= taper(window, 59.4, 60.01, 0, .61)
    profile = k.outline(cfg)
    edge, seam = cfg['outer_edge_mm'], cfg['seam_inset_mm']
    for top, shape in enumerate((foot, lid)):
        levels = ([(43, profile.offset(-seam)), (43+1.1*seam, profile),
                   (60-1.1*edge, profile), (60, profile.offset(-edge))] if top else
                  [(0, profile.offset(-edge)), (1.1*edge, profile),
                   (43-1.1*seam, profile), (43, profile.offset(-seam))])
        envelope = k.loft(levels)
        if not top:
            for x, y in itertools.product((6, 96), (6, 89)):
                envelope += box([x-2.3, y-2.3, 42.9], [x+2.3, y+2.3, 46.1])
        result[top] = shape ^ envelope
    foot, lid = result
    depth = cfg['base_reveal_depth_mm']
    z0, z1 = 9.4-1.1*depth, 9.4+1.1*depth
    retained = k.loft([(z0, profile), (9.4, profile.offset(-depth))])
    retained += k.loft([(9.4, profile.offset(-depth)), (z1, profile)])
    foot -= box([-1, -1, z0], [103, 96, z1]) - retained
    foot, lid = k.stage(foot, 'BodyChamfers'), k.stage(lid, 'LidChamfers')
    bore = cfg['through_hole_radius_mm']
    for transform in (lambda s: s, opposite):
        foot += transform(cylinder(10, 10, 2, 5, 4.4))
        foot += transform(k.cone(10, 10, 5, 6, 4.4, 3.4))
        foot += transform(cylinder(10, 10, 2, 43, 3.4))
        foot -= transform(cylinder(10, 10, -1, 44, bore))
        foot -= transform(cylinder(10, 10, -1, 3.3, 3))
        boss = box([6.5, 6.5, 43], [15.3, 13.5, 55.5])
        boss -= cylinder(10, 10, 42, 54.3, bore)
        slot = box([6.7, 7.15, 46.6], [16, 12.85, 49.2])
        boss -= slot
        for low, high in ((7.15, 7.3), (12.7, 12.85)):
            nib = box([14.7, low, 46.6], [15.3, high, 49.2])
            boss += nib
            slot -= nib
        lid += transform(boss)
        lid -= transform(slot + cylinder(10, 10, 42, 54.3, bore))
    strips = [box([7.8, 9, 2.5], [8.3, 86, 43]), box([93.7, 9, 2.5], [94.2, 86, 43]),
              box([8.5, 7.8, 2.5], [93.5, 8.3, 43]), box([8.5, 86.7, 2.5], [93.5, 87.2, 43])]
    support = cylinder(10, 10, 2, 6, 4.4) + cylinder(10, 10, 6, 43, 3.4)
    foot -= k.union(strips) - (support + opposite(support))
    foot, lid = k.stage(foot, 'BodyFasteners'), k.stage(lid, 'LidNutPockets')
    lid += yz([(13, 53.5), (15.8, 53.5), (16.5, 54.2), (16.5, floor),
               (14.8, floor), (14.8, 58.1), (13, 58.1)], 24, 78)
    lid -= box([23.8, 80.2, 42], [78.2, 86.8, 55.2])
    lid -= box([10.8, 80.2, 42], [91.2, 82.2, 58])
    bar = yz([(78.5, 52.9), (78.9, 52.5), (86.6, 52.5), (86.6, 55.2),
              (80.25, 55.2), (80.25, floor), (78.5, floor)], 24, 78)
    for x in (28, 74):
        lid += box([x-3, 82, 55.2], [x+3, 87, 59.4])
        lid -= cylinder(x, 84.1, 54.9, 59.2, cfg['bar_pilot_radius_mm'])
        bar -= cylinder(x, 84.1, 52, 56, cfg['bar_clearance_radius_mm'])
    regions = k.union([box([x-2.3, y-2.3, 42.9], [x+2.3, y+2.3, 46.3])
                       for x, y in itertools.product((6, 96), (6, 89))])
    foot = (foot-regions) + (originals[0] ^ regions)
    lid = (lid-regions) + (originals[1] ^ regions)
    solids = {'body': k.stage(foot, 'Body'), 'lid': k.stage(lid, 'Lid'),
              'glazing_bar': k.stage(bar, 'GlazingBar')}
    for name, poly in panels.items():
        solids[name+'_acrylic'] = place(section(poly).extrude(thick), name, thick, top_z)
    bolt = cylinder(10, 10, .3, 3.3, 2.75) + cylinder(10, 10, 3.3, 53.3, 1.5)
    bolt -= cylinder(10, 10, .2, 1.6, 1.25/math.cos(math.pi/6), 6)
    nut = cylinder(10, 10, 46.6, 49, 2.75/math.cos(math.pi/6), 6) - cylinder(10, 10, 46.5, 49.1, 1.5)
    hardware = {'bolt_A': bolt, 'bolt_B': opposite(bolt), 'nut_A': nut, 'nut_B': opposite(nut)}
    for i, x in enumerate((28, 74)):
        hardware['bar_screw_'+str(i)] = cylinder(x, 84.1, 50.9, 52.5, 2.1) + cylinder(x, 84.1, 52.5, 59, 1.1)
    return solids, hardware


def place(s, name, thick, top_z):
    shift = (2.9-thick)/2
    matrices = {
        'front': [[1, 0, 0, 51], [0, 0, 1, 2.7+shift], [0, 1, 0, 30.5]],
        'rear': [[-1, 0, 0, 51], [0, 0, -1, 92.3-shift], [0, 1, 0, 30.5]],
        'left': [[0, 0, 1, 2.7+shift], [-1, 0, 0, 47.5], [0, 1, 0, 30.5]],
        'right': [[0, 0, -1, 99.3-shift], [1, 0, 0, 47.5], [0, 1, 0, 30.5]],
        'top': [[1, 0, 0, 51], [0, 1, 0, 47.5], [0, 0, 1, top_z]],
    }
    return s.transform(matrices[name])
