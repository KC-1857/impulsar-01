"""Native FreeCAD CSG tree: sketches, extrusions, lofts, primitives, booleans.

FCStd contains no mesh imports or Python proxy objects. Editable expressions
and construction history work after reopening without this module installed.
"""
import functools
import json
import math
from pathlib import Path
import FreeCAD as App
import Part
import Sketcher
import manifold3d as mf
import numpy as np
import mesh_backend


class Dimension(float):
    """A number carrying its FreeCAD spreadsheet expression through arithmetic."""
    def __new__(cls, value, expression):
        obj = super().__new__(cls, value)
        obj.expression = expression
        return obj

    def op(self, other, symbol, function):
        right = getattr(other, 'expression', repr(float(other)))
        return Dimension(function(float(self), float(other)), f'({self.expression}{symbol}{right})')

    def __add__(self, other): return self.op(other, '+', lambda a, b: a+b)
    __radd__ = __add__
    def __sub__(self, other): return self.op(other, '-', lambda a, b: a-b)
    def __rsub__(self, other): return (-self).__add__(other)
    def __mul__(self, other): return self.op(other, '*', lambda a, b: a*b)
    __rmul__ = __mul__
    def __truediv__(self, other): return self.op(other, '/', lambda a, b: a/b)
    def __neg__(self): return Dimension(-float(self), f'(-{self.expression})')


def assign(obj, prop, value):
    setattr(obj, prop, float(value))
    if isinstance(value, Dimension):
        obj.setExpression(prop, value.expression)


class Solid:
    def __init__(self, backend, obj):
        self.k, self.obj = backend, obj

    def boolean(self, other, kind):
        obj = self.k.doc.addObject('Part::'+kind, kind)
        obj.Base, obj.Tool = self.obj, other.obj
        obj.Refine = True
        return Solid(self.k, obj)

    def __add__(self, other): return self.boolean(other, 'Fuse')
    def __sub__(self, other): return self.boolean(other, 'Cut')
    def __xor__(self, other): return self.boolean(other, 'Common')

    def mirror(self, normal):
        obj = self.k.doc.addObject('Part::Mirroring', 'Mirror')
        obj.Source = self.obj
        obj.Normal = App.Vector(*normal)
        obj.Base = App.Vector()
        return Solid(self.k, obj)

    def translate(self, vector):
        return self.transform([[1, 0, 0, vector[0]], [0, 1, 0, vector[1]], [0, 0, 1, vector[2]]])

    def transform(self, rows):
        matrix = App.Matrix()
        for i in range(3):
            for j in range(3):
                setattr(matrix, f'A{i+1}{j+1}', float(rows[i][j]))
        source = self
        if matrix.determinant() < 0:
            source = self.mirror([1, 0, 0])
            for i in range(3):
                setattr(matrix, f'A{i+1}1', -getattr(matrix, f'A{i+1}1'))
        obj = self.k.doc.addObject('Part::Compound', 'Transform')
        obj.Links = [source.obj]
        obj.Placement = App.Placement(App.Vector(*[float(r[3]) for r in rows]), App.Rotation(matrix))
        for i, axis in enumerate('xyz'):
            if isinstance(rows[i][3], Dimension):
                obj.setExpression('Placement.Base.'+axis, rows[i][3].expression)
        return Solid(self.k, obj)


class Section:
    def __init__(self, backend, rings):
        self.k, self.rings = backend, rings

    def extrude(self, height):
        # A compound of nested closed wires is extruded using the Part face maker.
        profiles = [self.k.sketch(ring) for ring in self.rings]
        if len(profiles) == 1:
            base = profiles[0]
        else:
            base = self.k.doc.addObject('Part::Compound', 'ProfileWithHoles')
            base.Links = profiles
        obj = self.k.doc.addObject('Part::Extrusion', 'Extrusion')
        obj.Base = base
        obj.DirMode = 'Normal'
        obj.Dir = App.Vector(0, 0, 1)
        obj.Solid = True
        assign(obj, 'LengthFwd', height)
        return Solid(self.k, obj)

    def translate(self, vector):
        return Section(self.k, [[(p[0]+vector[0], p[1]+vector[1]) for p in ring] for ring in self.rings])

    def offset(self, amount):
        cs = mf.CrossSection(self.rings, mf.FillRule.EvenOdd).offset(float(amount), mf.JoinType.Miter)
        return Section(self.k, [p.tolist() for p in cs.to_polygons()])


class Backend:
    def __init__(self, doc, cfg):
        self.doc = doc
        self.stages = []
        self.sheet = doc.addObject('Spreadsheet::Sheet', 'Parameters')
        self.sheet.set('A1', 'Размеры, мм — editable dimensions')
        aliases = {'acrylic_thickness_mm': 'AcrylicThickness', 'groove_width_mm': 'GrooveWidth',
                   'through_hole_radius_mm': 'ThroughRadius', 'bar_pilot_radius_mm': 'PilotRadius',
                   'bar_clearance_radius_mm': 'BarClearanceRadius'}
        self.config = dict(cfg)
        for row, (key, alias) in enumerate(aliases.items(), 2):
            self.sheet.set(f'A{row}', key)
            self.sheet.set(f'B{row}', str(cfg[key]))
            self.sheet.setAlias(f'B{row}', alias)
            self.config[key] = Dimension(cfg[key], f'Parameters.{alias}')
        self.sheet.setColumnWidth('A', 240)
        doc.recompute()

    def sketch(self, points, z=0):
        points = list(points)
        if points[0] == points[-1]:
            points = points[:-1]
        obj = self.doc.addObject('Sketcher::SketchObject', 'Profile')
        obj.Placement.Base.z = float(z)
        if isinstance(z, Dimension):
            obj.setExpression('Placement.Base.z', z.expression)
        for i, p in enumerate(points):
            q = points[(i+1) % len(points)]
            obj.addGeometry(Part.LineSegment(App.Vector(float(p[0]), float(p[1]), 0),
                                             App.Vector(float(q[0]), float(q[1]), 0)), False)
        constraints = []
        expressions = []
        for i, p in enumerate(points):
            constraints.append(Sketcher.Constraint('Coincident', i, 2, (i+1) % len(points), 1))
            for axis, value in enumerate(p):
                if float(value) == 0 and not isinstance(value, Dimension):
                    constraints.append(Sketcher.Constraint('DistanceX' if axis == 0 else 'DistanceY', i, 1, 0.0))
                else:
                    constraints.append(Sketcher.Constraint('DistanceX' if axis == 0 else 'DistanceY', i, 1, float(value)))
                if isinstance(value, Dimension):
                    expressions.append((len(constraints)-1, value.expression))
        obj.addConstraint(constraints)
        for index, expr in expressions:
            obj.setExpression(f'Constraints[{index}]', expr)
        return obj

    def section(self, poly):
        if hasattr(poly, 'exterior'):
            rings = [list(poly.exterior.coords), *[list(r.coords) for r in poly.interiors]]
        else:
            rings = [list(poly)]
        return Section(self, rings)

    def box(self, lo, hi):
        obj = self.doc.addObject('Part::Box', 'Box')
        for prop, a, b in zip(('Length', 'Width', 'Height'), lo, hi):
            assign(obj, prop, b-a)
        obj.Placement.Base = App.Vector(*[float(v) for v in lo])
        for axis, v in zip('xyz', lo):
            if isinstance(v, Dimension):
                obj.setExpression('Placement.Base.'+axis, v.expression)
        return Solid(self, obj)

    def cylinder(self, x, y, low, high, radius, segments=64):
        if segments != 64:
            points = [(x+radius*math.cos(2*math.pi*i/segments), y+radius*math.sin(2*math.pi*i/segments)) for i in range(segments)]
            return self.section(points).extrude(high-low).translate([0, 0, low])
        obj = self.doc.addObject('Part::Cylinder', 'Cylinder')
        assign(obj, 'Radius', radius)
        assign(obj, 'Height', high-low)
        obj.Placement.Base = App.Vector(x, y, low)
        return Solid(self, obj)

    def cone(self, x, y, low, high, r0, r1):
        obj = self.doc.addObject('Part::Cone', 'Cone')
        obj.Radius1, obj.Radius2, obj.Height = r0, r1, high-low
        obj.Placement.Base = App.Vector(x, y, low)
        return Solid(self, obj)

    def loft(self, levels):
        # OCCT cannot reliably match polygonal offsets with disappearing edges.
        # Split convex profile edges on common rays; this preserves each contour
        # while giving every section the same ordered vertex correspondence.
        rings = [section.rings[0] for z, section in levels]
        if len({len(r) for r in rings}) > 1:
            center = np.mean(np.concatenate(rings), axis=0)
            angles = sorted(math.atan2(y-center[1], x-center[0]) for ring in rings for x, y in ring)
            unique = []
            for angle in angles:
                if not unique or angle-unique[-1] > 1e-6:
                    unique.append(angle)
            aligned = []
            for ring in rings:
                points = np.asarray(ring, dtype=float)
                edges = np.roll(points, -1, axis=0)-points
                starts = points-center
                sampled = []
                for angle in unique:
                    ray = np.array([math.cos(angle), math.sin(angle)])
                    cross = lambda a, b: a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]
                    denominator = cross(ray, edges)
                    mask = abs(denominator) > 1e-10
                    distances = cross(starts[mask], edges[mask])/denominator[mask]
                    fractions = cross(starts[mask], ray)/denominator[mask]
                    hits = distances[(distances > 0) & (fractions >= -1e-7) & (fractions <= 1+1e-7)]
                    sampled.append((center+ray*min(hits)).tolist())
                aligned.append(sampled)
            levels = [(z, Section(self, [ring])) for (z, _), ring in zip(levels, aligned)]
        profiles = []
        for z, section in levels:
            assert len(section.rings) == 1
            profiles.append(self.sketch(section.rings[0], z))
        obj = self.doc.addObject('Part::Loft', 'RuledLoft')
        obj.Sections, obj.Solid, obj.Ruled = profiles, True, True
        return Solid(self, obj)

    def outline(self, cfg):
        return Section(self, [p.tolist() for p in mesh_backend.outline(cfg).to_polygons()])

    def union(self, solids):
        return functools.reduce(lambda a, b: a+b, solids)

    def stage(self, solid, name):
        solid.obj.Label = name
        self.stages.append(solid.obj)
        print('CAD construction:', name, flush=True)
        return solid

    def originals(self):
        profiles = json.loads(Path(__file__).with_name('source_profiles.json').read_text())

        def slab(key, low, high):
            return Section(self, profiles[key]).extrude(high-low).translate([0, 0, low])

        foot = self.box([0, 0, 0], [102, 95, 43]) - self.box([7, 7, 2.5], [95, 88, 44])
        foot -= self.box([3, 37.5, 2.5], [7.01, 57.5, 7.5])
        for x in (8, 94):
            for y in (8, 87):
                foot -= self.cylinder(x, y, -1, 2, 5)
        for x in (11.5, 69):
            for y in (22.5, 71.5):
                foot += self.cylinder(x, y, 2.5, 7.5, 3)
                foot -= self.cylinder(x, y, 3.5, 7.6, 1.35)
        # New window rails replace the old rounded screw ears completely.
        foot += slab('foot_43.5', 42.5, 46)
        lid = slab('top_43.5', 43, 46.5)
        lid += self.box([0, 0, 46.5], [102, 95, 53]) - self.box([7, 7, 46], [95, 88, 54])
        lid += self.box([0, 0, 53], [102, 95, 60])
        return [self.stage(foot, 'OriginalBaseReconstruction'), self.stage(lid, 'OriginalLidReconstruction')]
