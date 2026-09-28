"""Fit-coupon and material-part exports for the Impulsar-01 rev06 enclosure."""
import shutil
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from shapely.geometry import box
from common import ROOT
import mesh_backend as k


def save_3mf(path, solids, colors):
    ns = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
    ET.register_namespace('', ns)
    def element(tag, **attrs):
        return ET.Element('{'+ns+'}'+tag, {key: str(value) for key, value in attrs.items()})
    model = element('model', unit='millimeter')
    resources = element('resources')
    model.append(resources)
    materials = element('basematerials', id=10)
    for i, color in enumerate(colors):
        materials.append(element('base', name=f'color_{i}', displaycolor=color+'FF'))
    resources.append(materials)
    for i, (name, solid) in enumerate(solids.items(), 1):
        m = k.as_mesh(solid)
        obj = element('object', id=i, type='model', name=name, pid=10, pindex=i-1)
        mesh, verts, tris = element('mesh'), element('vertices'), element('triangles')
        for v in m.vertices:
            verts.append(element('vertex', x=f'{v[0]:.7f}', y=f'{v[1]:.7f}', z=f'{v[2]:.7f}'))
        for f in m.faces:
            tris.append(element('triangle', v1=int(f[0]), v2=int(f[1]), v3=int(f[2])))
        mesh.extend([verts, tris]); obj.append(mesh); resources.append(obj)
    group = element('object', id=20, type='model', name='Импульсар-01')
    children = element('components')
    for i in range(1, len(solids)+1):
        children.append(element('component', objectid=i))
    group.append(children); resources.append(group)
    build = element('build'); build.append(element('item', objectid=20)); model.append(build)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        archive.writestr('3D/3dmodel.model', ET.tostring(model, encoding='utf-8', xml_declaration=True))
    loaded = trimesh.load(path, force='scene')
    assert len(loaded.geometry) == len(solids)
    assert all(m.is_watertight and m.is_winding_consistent for m in loaded.geometry.values())
    np.testing.assert_allclose(sorted(m.volume for m in loaded.geometry.values()),
                               sorted(k.as_mesh(s).volume for s in solids.values()), atol=1e-4)


def export(out, solids, panels, cfg):
    foot, lid, bar = (solids[n] for n in ('body', 'lid', 'glazing_bar'))
    flip = lambda s: s.rotate([180, 0, 0])
    pose = lambda s: flip(s).translate([0, 95, 60])
    coupons = {}
    for width in (2.95, 3.0, 3.05):
        coupons[f'groove_{width:.2f}'] = k.box([0, 0, 0], [20, width+4, 9])-k.box([-1, 2, 2], [21, width+2, 10])
    for name, solid, low, high, upside_down in [
        ('nut_corner', lid, [6.4, 6.4, 43], [16, 14, 56], True),
        ('bolt_lower_corner', foot, [-.1, -.1, -.1], [17, 17, 46.1], False),
        ('bolt_upper_corner', lid, [-.1, -.1, 42.9], [17, 17, 60.1], True),
        ('actual_groove', foot, [8.51, 0, 5], [24, 8.31, 42], False),
        ('fixed_groove', lid, [24, 12.5, 52], [40, 17, 60], True),
        ('bar_mount', lid, [24, 80.3, 54], [32, 87.1, 60], True),
        ('bar_end', bar, [24, 78, 52], [32, 87, 56], False),
    ]:
        coupon = solid ^ k.box(low, high)
        coupons[name] = flip(coupon) if upside_down else coupon
    coupons['cm4_trial'] = k.section(panels['left']).extrude(cfg['acrylic_thickness_mm'])
    (out/'coupons').mkdir(exist_ok=True)
    for name, solid in coupons.items():
        mesh = k.as_mesh(solid)
        mesh.apply_translation(-mesh.bounds[0])
        assert mesh.is_watertight and mesh.is_winding_consistent and len(mesh.split()) == 1, name
        mesh.export(out/'coupons'/f'{name}_print.stl')
    accents = [k.section(box(x+.5, 6.5, x+9.5, 6.7).buffer(.5, quad_segs=8)).extrude(.4).translate([0, 0, 59.6]) for x in (18, 74)]
    gold = k.union(accents)
    assert abs((gold-lid).volume()) < .01
    lid_base = lid-gold
    assert abs((lid_base ^ gold).volume()) < .01
    assert abs((lid_base+gold).volume()-lid.volume()) < .01
    (out/'multicolor').mkdir(exist_ok=True)
    save_3mf(out/'multicolor'/'lid_multicolor.3mf', {'lid': pose(lid_base), 'gold_A': pose(accents[0]), 'gold_B': pose(accents[1])},
             [cfg['body_color'], cfg['accent_color'], cfg['accent_color']])
    shutil.copytree(ROOT/'laser', out/'laser', dirs_exist_ok=True)
