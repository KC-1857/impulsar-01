"""Manifold backend; original meshes retained as the rev06 reference."""
import functools
import numpy as np
import manifold3d as mf
import trimesh


def box(lo, hi):
    return mf.Manifold.cube(np.subtract(hi, lo)).translate(lo)


def section(poly):
    if hasattr(poly, 'exterior'):
        rings = [list(poly.exterior.coords), *[list(r.coords) for r in poly.interiors]]
    else:
        rings = [list(poly)]
    return mf.CrossSection(rings, mf.FillRule.EvenOdd)


def cylinder(x, y, low, high, radius, segments=64):
    return mf.Manifold.cylinder(high-low, radius, radius, segments).translate([x, y, low])


def cone(x, y, low, high, r0, r1):
    return mf.Manifold.cylinder(high-low, r0, r1, 64).translate([x, y, low])


def loft(levels):
    return mf.Manifold.hull_points([(x, y, z) for z, s in levels for p in s.to_polygons() for x, y in p])


def outline(cfg):
    c, r = cfg['corner_chamfer_mm'], cfg['corner_blend_mm']
    return section([(c, 0), (102-c, 0), (102, c), (102, 95-c),
                    (102-c, 95), (c, 95), (0, 95-c), (0, c)]).offset(-r).offset(r, circular_segments=64)


def union(solids):
    return functools.reduce(lambda a, b: a+b, solids)


def stage(solid, name):
    return solid


def load(path):
    mesh = trimesh.load_mesh(path)
    return mf.Manifold(mf.Mesh(np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.uint32)))


def as_mesh(solid):
    data = solid.simplify(1e-5).to_mesh()
    mesh = trimesh.Trimesh(data.vert_properties[:, :3], data.tri_verts, process=True)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    # Float32 STL can collapse coplanar sliver triangles along boolean edges.
    # Split the resulting T junctions without moving any surface vertices.
    for _ in range(3):
        if mesh.is_watertight:
            break
        edges, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
        boundary = edges[counts == 1]
        candidates = np.unique(boundary)
        replacements = {}
        for a, b in boundary:
            start, end = mesh.vertices[[a, b]]
            direction = end-start
            length2 = np.dot(direction, direction)
            t = (mesh.vertices[candidates]-start) @ direction / length2
            distances = np.linalg.norm(mesh.vertices[candidates] - start - t[:, None]*direction, axis=1)
            mask = (t > 1e-7) & (t < 1-1e-7) & (distances < 1e-5)
            points = candidates[mask][np.argsort(t[mask])]
            if not len(points):
                continue
            matches = np.flatnonzero(np.any(mesh.faces == a, axis=1) & np.any(mesh.faces == b, axis=1))
            assert len(matches) == 1
            fi = int(matches[0])
            face = mesh.faces[fi]
            ia = int(np.flatnonzero(face == a)[0])
            if face[(ia+1) % 3] != b:
                a, b, points = b, a, points[::-1]
            third = int(next(v for v in face if v not in (a, b)))
            chain = [a, *points.tolist(), b]
            assert fi not in replacements, 'Multiple collapsed edges on one triangle'
            replacements[fi] = [[u, v, third] for u, v in zip(chain, chain[1:])]
        if not replacements:
            break
        faces = [f for i, f in enumerate(mesh.faces) if i not in replacements]
        faces.extend(f for triangles in replacements.values() for f in triangles)
        mesh = trimesh.Trimesh(mesh.vertices, faces, process=False)
    return mesh
