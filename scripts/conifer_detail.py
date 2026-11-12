"""Denser conifers around the cabin for Jelena_Realistic_v003.

Spruce, fir and pine: curved trunks, two branch orders, needles along the wood.
Does not save, delete, or edit scene B.
"""

import json
import math
import random

import bmesh
import bpy
from mathutils import Vector

SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"


def ortho(direction):
    up = Vector((0.0, 0.0, 1.0))
    side = direction.cross(up)
    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    return side, direction.cross(side).normalized()


def tube(bm, origin, direction, length, bend, r0, r1, sides, segs):
    direction = direction.normalized()
    points = []
    for i in range(segs + 1):
        t = i / segs
        points.append(origin + direction * (length * t) + bend * (length * t * t))
    rings = []
    for i, point in enumerate(points):
        if i < segs:
            tangent = (points[i + 1] - point).normalized()
        else:
            tangent = (point - points[i - 1]).normalized()
        side, binorm = ortho(tangent)
        radius = r0 + (r1 - r0) * (i / segs)
        ring = []
        for k in range(sides):
            ang = 2.0 * math.pi * k / sides
            ring.append(bm.verts.new(point + (side * math.cos(ang) + binorm * math.sin(ang)) * radius))
        rings.append(ring)
    for i in range(segs):
        for k in range(sides):
            j = (k + 1) % sides
            face = bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
            face.material_index = 0
            face.smooth = True
    return points


def needles(bm, origin, axis, length, count, droop, spread):
    axis = axis.normalized()
    side, binorm = ortho(axis)
    for i in range(count):
        ang = 2.0 * math.pi * i / count + (i % 3) * 0.17
        outward = side * math.cos(ang) + binorm * math.sin(ang)
        direction = (outward * spread + axis * 0.55 + Vector((0.0, 0.0, droop))).normalized()
        tip = origin + direction * length
        width = length * 0.045
        bit = direction.cross(outward)
        if bit.length < 1e-6:
            bit = binorm
        bit.normalize()
        face = bm.faces.new((
            bm.verts.new(origin + bit * width),
            bm.verts.new(origin - bit * width),
            bm.verts.new(tip),
        ))
        face.material_index = 1
        face.smooth = False


def dress_branch(bm, points, needle_len, per_step, droop, spread):
    for i in range(len(points) - 1):
        start = points[i]
        axis = points[i + 1] - start
        for step in (0.18, 0.42, 0.66, 0.9):
            needles(bm, start + axis * step, axis, needle_len, per_step, droop, spread)


def build_tree(kind):
    """Three spruce sizes. Every kind droops and carries short needles."""
    rng = random.Random({"smrek": 3, "jedla": 11, "borovica": 19}[kind])
    bm = bmesh.new()
    if kind == "smrek":
        height, clear, whorls, per, needle = 8.2, 1.05, 9, 7, 0.22
        reach_base = 2.35
    elif kind == "jedla":
        height, clear, whorls, per, needle = 6.6, 0.85, 8, 7, 0.2
        reach_base = 1.85
    else:
        height, clear, whorls, per, needle = 4.8, 0.7, 7, 6, 0.18
        reach_base = 1.35
    droop, spread = -0.62, 1.0
    bend = Vector((rng.uniform(-0.16, 0.16), rng.uniform(-0.1, 0.1), 0.0))
    tube(bm, Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)), height, bend, 0.2, 0.03, 8, 12)
    for w in range(whorls):
        t = w / max(1, whorls - 1)
        z = clear + (height - clear - 0.3) * t
        reach = reach_base * (1.0 - t) ** 0.78 + 0.22
        rise = 0.22 - 0.5 * t
        base_ang = rng.random() * 0.6
        for b in range(per):
            if rng.random() < 0.08 + 0.16 * t:
                continue
            ang = base_ang + 2.0 * math.pi * (b + 0.13 * w) / per
            direction = Vector((math.cos(ang), math.sin(ang), rise + rng.uniform(-0.04, 0.06)))
            branch_bend = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), -0.38))
            radius = 0.042 * (1.0 - 0.4 * t)
            pts = tube(bm, Vector((0.0, 0.0, z)), direction, reach, branch_bend, radius, radius * 0.28, 5, 4)
            dress_branch(bm, pts, needle, 18, droop, spread)
            side, binorm = ortho(direction)
            for s in range(40):
                along = 0.12 + 0.84 * ((s + 0.5) / 40.0)
                origin = pts[0] + (pts[-1] - pts[0]) * along
                spin = s * 2.399
                outward = side * math.cos(spin) + binorm * math.sin(spin)
                twig_dir = (direction * 0.28 + outward + Vector((0.0, 0.0, -0.22 + rng.uniform(-0.05, 0.05)))).normalized()
                twig_len = reach * (0.16 + 0.22 * (1.0 - along)) * rng.uniform(0.85, 1.1)
                twig = tube(bm, origin, twig_dir, twig_len, Vector((0.0, 0.0, -0.1)), radius * 0.38, 0.007, 4, 2)
                dress_branch(bm, twig, needle * 0.82, 16, droop, spread)
    for _cone in range(10):
        ang = rng.random() * math.tau
        z = rng.uniform(clear + 0.6, height - 0.35)
        center = Vector((math.cos(ang) * rng.uniform(0.12, 0.55), math.sin(ang) * rng.uniform(0.12, 0.55), z))
        tube(bm, center, Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), -1.0)), 0.08, Vector((0, 0, 0)), 0.022, 0.004, 5, 1)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return bm


def material(name, color_a, color_b):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(node for node in nt.nodes if node.type == "BSDF_PRINCIPLED")
    info = next((node for node in nt.nodes if node.type == "OBJECT_INFO"), None)
    if info is None:
        info = nt.nodes.new("ShaderNodeObjectInfo")
    mix = next((node for node in nt.nodes if node.name == "Ihlicie mix"), None)
    if mix is None:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.name = "Ihlicie mix"
        mix.data_type = "RGBA"
    for socket, value in (("A", (*color_a, 1.0)), ("B", (*color_b, 1.0))):
        for candidate in mix.inputs:
            if candidate.name == socket and hasattr(candidate, "default_value"):
                try:
                    if len(candidate.default_value) == 4:
                        candidate.default_value = value
                except TypeError:
                    pass
    if not any(link.to_node == mix and link.to_socket.name == "Factor" for link in nt.links):
        nt.links.new(info.outputs["Random"], mix.inputs["Factor"])
    for link in list(nt.links):
        if link.to_node == bsdf and link.to_socket.name == "Base Color":
            nt.links.remove(link)
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.74
    return mat


def store(kind, obj_name, bark, foliage):
    bm = build_tree(kind)
    obj = bpy.data.objects[obj_name]
    mesh = obj.data
    mesh.materials.clear()
    mesh.materials.append(bark)
    mesh.materials.append(foliage)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    leaves = sum(1 for poly in mesh.polygons if poly.material_index == 1)
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles), leaves


def forbidden(x, y):
    if -1.1 <= x <= 9.5 and -1.2 <= y <= 7.0:
        return True
    if 2.2 <= x <= 11.0 and y < 1.6:
        return True
    if 3.2 <= x <= 9.4 and -3.2 <= y <= 2.2:
        return True
    return False


def place_ring(prototypes):
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    col = bpy.data.collections["10 • Vegetácia scéna A"]
    center = Vector((4.2, 2.6, 0.0))
    made = 0
    radii = (7.2, 8.4, 9.6, 11.0, 12.6, 14.2)
    kinds = ("smrek", "jedla", "borovica")
    for ring, radius in enumerate(radii):
        count = 7 if radius < 11 else 6
        for i in range(count):
            ang = 2.0 * math.pi * (i + 0.17 * ring) / count + 0.4
            x = center.x + math.cos(ang) * radius
            y = center.y + math.sin(ang) * radius
            if forbidden(x, y):
                x += math.cos(ang) * 2.4
                y += math.sin(ang) * 2.4
            if forbidden(x, y):
                continue
            hit, loc, _n, _i, hit_obj, _m = scene.ray_cast(
                depsgraph, Vector((x, y, 40.0)), Vector((0.0, 0.0, -1.0)), distance=80.0
            )
            if not hit or hit_obj is None or hit_obj.name != "Lesná čistina":
                continue
            kind = kinds[(i + ring) % 3]
            src = prototypes[kind]
            inst = src.copy()
            inst.data = src.data
            inst.name = src.name
            scale = 0.72 + ((i * 3 + ring) % 6) * 0.08
            inst.location = (x, y, loc.z - 0.02)
            inst.rotation_euler = (0.0, 0.0, ang + ring)
            inst.scale = (scale, scale, scale)
            inst.hide_render = False
            inst.hide_viewport = False
            col.objects.link(inst)
            inst["jelena_proto"] = kind
            made += 1
    return made


def apply_conifers():
    if not bpy.data.filepath.endswith("Jelena_Realistic_v003.blend"):
        raise RuntimeError(bpy.data.filepath)
    if bpy.context.scene.name != SCENE_A:
        raise RuntimeError(bpy.context.scene.name)
    bark = bpy.data.materials["Kôra • smrek"]
    spruce = material("Ihličie • smrek", (0.012, 0.07, 0.02), (0.04, 0.16, 0.035))
    fir = material("Ihličie • jedľa", (0.015, 0.09, 0.04), (0.05, 0.2, 0.07))
    pine = material("Ihličie • borovica", (0.06, 0.14, 0.025), (0.12, 0.24, 0.04))
    mapping = (
        ("smrek", "Smrek • vysoký", spruce),
        ("jedla", "Smrek • stredný", fir),
        ("borovica", "Smrek • mladý", pine),
    )
    stats = {}
    prototypes = {}
    for kind, name, foliage in mapping:
        tris, leaves = store(kind, name, bark, foliage)
        stats[name] = {"tris": tris, "leaf_faces": leaves}
        prototypes[kind] = bpy.data.objects[name]
    added = place_ring(prototypes)
    bpy.context.view_layer.update()
    scene_b = bpy.data.scenes[SCENE_B]
    sun = bpy.data.objects["Popoludňajšie slnko"].data.energy
    print(json.dumps({
        "stats": stats,
        "added": added,
        "scene_a": len(bpy.context.scene.objects),
        "scene_b": len(scene_b.objects),
        "sun_b": round(float(sun), 3),
        "camera": [round(v, 5) for v in bpy.context.scene.camera.location],
    }, ensure_ascii=False))


if __name__ == "__main__":
    apply_conifers()
