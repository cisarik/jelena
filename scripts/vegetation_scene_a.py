"""Scene-A vegetation for Jelena_Realistic_v002.

Runs inside the live Blender session. Refuses any other filepath.
Does not save, delete, purge, or edit scene B datablocks.
"""

import json
import math
import random

import bmesh
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

PATH_SUFFIX = "Jelena_Realistic_v002.blend"
SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"
COL_07B = "07b • Svetlá exteriér"
COL_07C = "07c • Svetlá scéna A"
COL_09 = "09 • Prototypy vegetácie"
COL_10 = "10 • Vegetácia scéna A"
COL_05A = "05a • Les • nahradené"
WORLD_A = "Obloha nad lesom • A"
SUN_A = "Popoludňajšie slnko • A"
DISK_A = "Mäkké svetlo z čistiny • A"
COVER = "Pôda • pokryv"
GROUP = "Pokryv lesa"


def require_v002():
    if not bpy.data.filepath.endswith(PATH_SUFFIX):
        raise RuntimeError("refusing: filepath is not Jelena_Realistic_v002.blend")
    if bpy.context.scene.name != SCENE_A:
        raise RuntimeError("refusing: active scene is not A")


def sock(node, *names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    raise KeyError((node.bl_idname, names, [s.name for s in node.inputs]))


def out_sock(node, *names):
    for name in names:
        if name in node.outputs:
            return node.outputs[name]
    raise KeyError((node.bl_idname, names, [s.name for s in node.outputs]))


def link_to(scene, col):
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)


def find_layer(scene, name):
    def walk(lc):
        if lc.collection.name == name:
            return lc
        for child in lc.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    scene.view_layers[0].update()
    return walk(scene.view_layers[0].layer_collection)


def set_exclude(scene, name, value):
    lc = find_layer(scene, name)
    if lc is None:
        raise RuntimeError(f"missing layer collection {name} in {scene.name}")
    lc.exclude = value
    return lc.exclude


def world_strength(world):
    for node in world.node_tree.nodes:
        if node.type == "BACKGROUND":
            return float(node.inputs["Strength"].default_value)
    raise RuntimeError("world has no Background node")


def snapshot_b():
    scene_b = bpy.data.scenes[SCENE_B]
    sun = bpy.data.objects["Popoludňajšie slnko"]
    disk = bpy.data.objects["Mäkké svetlo z čistiny"]
    interior = bpy.data.objects["Svetlo v interiéri"]
    lc = find_layer(scene_b, COL_07B)
    return {
        "objects": len(scene_b.objects),
        "sun": float(sun.data.energy),
        "disk": float(disk.data.energy),
        "interior": float(interior.data.energy),
        "world": scene_b.world.name if scene_b.world else None,
        "strength": world_strength(scene_b.world),
        "exclude_07b": None if lc is None else bool(lc.exclude),
        "layer_found": lc is not None,
    }


def assert_scene_b(tag):
    got = snapshot_b()
    problems = []
    if got["objects"] != 308:
        problems.append(f"objects {got['objects']}")
    if abs(got["sun"] - 2.2) > 1e-3:
        problems.append(f"sun {got['sun']}")
    if abs(got["disk"] - 610.0) > 1e-3:
        problems.append(f"disk {got['disk']}")
    if abs(got["interior"] - 65.0) > 1e-3:
        problems.append(f"interior {got['interior']}")
    if got["world"] != "Obloha nad lesom":
        problems.append(f"world {got['world']}")
    if abs(got["strength"] - 0.48) > 1e-3:
        problems.append(f"strength {got['strength']}")
    if got["layer_found"] and got["exclude_07b"]:
        problems.append("scene B excludes 07b")
    if problems:
        raise RuntimeError(f"scene B readback failed at {tag}: {problems}; {got}")
    return got


def camera_delta():
    cam = bpy.context.scene.camera
    loc = (13.899999618530273, -16.399999618530273, 6.349999904632568)
    rot = (1.390952467918396, 1.9204376755510566e-08, 0.4771289527416229)
    deltas = [abs(cam.location[i] - loc[i]) for i in range(3)]
    deltas += [abs(cam.rotation_euler[i] - rot[i]) for i in range(3)]
    deltas.append(abs(cam.data.lens - 46.0))
    deltas.append(abs(cam.data.sensor_width - 36.0))
    deltas.append(abs(cam.data.sensor_height - 24.0))
    deltas.append(abs(cam.data.shift_x))
    deltas.append(abs(cam.data.shift_y))
    return max(deltas), cam.data.sensor_fit


def move_into(obj, col):
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    col.objects.link(obj)


def is_old_vegetation(name):
    return (
        name == "Smrek"
        or name.startswith("Smrek.")
        or name == "Kmeň smreka"
        or name.startswith("Kmeň smreka.")
        or name == "Tráva • čistina"
    )


def new_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat


def principled(mat):
    return next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")


def make_foliage(name, color_a, color_b):
    mat = new_material(name)
    bsdf = principled(mat)
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Specular IOR Level"].default_value = 0.22
    info = mat.node_tree.nodes.new("ShaderNodeObjectInfo")
    mix = mat.node_tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    sock(mix, "A").default_value = (*color_a, 1.0)
    sock(mix, "B").default_value = (*color_b, 1.0)
    mat.node_tree.links.new(out_sock(info, "Random"), sock(mix, "Factor"))
    mat.node_tree.links.new(out_sock(mix, "Result"), bsdf.inputs["Base Color"])
    return mat


def make_bark():
    mat = new_material("Kôra • smrek")
    nt = mat.node_tree
    bsdf = principled(mat)
    bsdf.inputs["Roughness"].default_value = 0.84
    coord = nt.nodes.new("ShaderNodeTexCoord")
    scale = nt.nodes.new("ShaderNodeVectorMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = (2.4, 2.4, 0.35)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.55
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = (0.035, 0.016, 0.008, 1)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (0.22, 0.11, 0.045, 1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.38
    bump.inputs["Distance"].default_value = 0.04
    nt.links.new(coord.outputs["Object"], scale.inputs[0])
    nt.links.new(scale.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_simple(name, color, roughness, bump_strength=0.0):
    mat = new_material(name)
    bsdf = principled(mat)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if bump_strength:
        nt = mat.node_tree
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 4.5
        noise.inputs["Detail"].default_value = 4.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bump_strength
        bump.inputs["Distance"].default_value = 0.03
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def assign_face(face, index):
    face.material_index = index


def add_tube(bm, origin, direction, length, r0, r1, sides, segs, droop, mat):
    direction = direction.normalized()
    up = Vector((0.0, 0.0, 1.0))
    side = direction.cross(up)
    if side.length < 1e-6:
        side = Vector((1.0, 0.0, 0.0))
    side.normalize()
    binorm = direction.cross(side).normalized()
    rings = []
    for seg in range(segs + 1):
        t = seg / segs
        center = origin + direction * (length * t) + Vector((0.0, 0.0, -droop * t * t))
        radius = r0 + (r1 - r0) * t
        ring = []
        for i in range(sides):
            ang = 2.0 * math.pi * i / sides
            point = center + (side * math.cos(ang) + binorm * math.sin(ang)) * radius
            ring.append(bm.verts.new(point))
        rings.append(ring)
    for seg in range(segs):
        for i in range(sides):
            j = (i + 1) % sides
            face = bm.faces.new((rings[seg][i], rings[seg][j], rings[seg + 1][j], rings[seg + 1][i]))
            assign_face(face, mat)


def add_band(bm, z0, z1, r0, r1, sides, phase, amp, mat):
    rings = []
    for z, radius in ((z0, r0), (z1, r1)):
        ring = []
        for i in range(sides):
            ang = 2.0 * math.pi * i / sides
            wobble = 1.0 + amp * math.sin(ang * 3.0 + phase) + 0.45 * amp * math.sin(ang * 8.0 - phase)
            point = Vector((math.cos(ang) * radius * wobble, math.sin(ang) * radius * wobble, z))
            ring.append(bm.verts.new(point))
        rings.append(ring)
    for i in range(sides):
        j = (i + 1) % sides
        face = bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
        assign_face(face, mat)


def spruce_profile(kind):
    if kind == "tall":
        return {
            "name": "Smrek • vysoký",
            "height": 9.6,
            "trunk": 3.4,
            "trunk_r": (0.2, 0.05),
            "crown_z": (2.0, 9.6),
            "crown_r": 1.15,
            "bands": 18,
            "sides": 56,
            "amp": 0.16,
            "phase": 0.3,
            "freq": 5.0,
            "pow": 1.35,
            "zjitter": 0.04,
            "whorls": 6,
            "branches": 5,
            "branch_r": 0.045,
            "reach": 1.65,
        }
    if kind == "mid":
        return {
            "name": "Smrek • stredný",
            "height": 6.6,
            "trunk": 1.7,
            "trunk_r": (0.16, 0.05),
            "crown_z": (0.9, 6.6),
            "crown_r": 2.05,
            "bands": 12,
            "sides": 48,
            "amp": 0.38,
            "phase": 1.8,
            "freq": 2.0,
            "pow": 0.72,
            "zjitter": 0.16,
            "whorls": 4,
            "branches": 8,
            "branch_r": 0.04,
            "reach": 1.22,
        }
    return {
        "name": "Smrek • mladý",
        "height": 4.3,
        "trunk": 1.7,
        "trunk_r": (0.07, 0.025),
        "crown_z": (1.35, 4.3),
        "crown_r": 0.62,
        "bands": 8,
        "sides": 36,
        "amp": 0.34,
        "phase": 2.4,
        "freq": 3.0,
        "pow": 0.9,
        "zjitter": 0.08,
        "whorls": 4,
        "branches": 3,
        "branch_r": 0.02,
        "reach": 1.85,
    }


def radius_at(spec, z):
    z0, z1 = spec["crown_z"]
    t = min(1.0, max(0.0, (z - z0) / (z1 - z0)))
    base = spec["crown_r"] * ((1.0 - t) ** spec["pow"])
    return base * (0.78 + 0.22 * math.sin(t * math.pi))


def fill_spruce(bm, spec):
    add_tube(
        bm,
        Vector((0.0, 0.0, 0.0)),
        Vector((0.0, 0.0, 1.0)),
        spec["trunk"],
        spec["trunk_r"][0],
        spec["trunk_r"][1],
        8,
        10,
        0.0,
        0,
    )
    z0, z1 = spec["crown_z"]
    bands = spec["bands"]
    sides = spec["sides"]
    rings = []
    for band in range(bands + 1):
        t = band / bands
        z = z0 + (z1 - z0) * t
        radius = radius_at(spec, z)
        ring = []
        for i in range(sides):
            ang = 2.0 * math.pi * i / sides
            wobble = 1.0 + spec["amp"] * math.sin(ang * spec["freq"] + spec["phase"])
            wobble += 0.35 * spec["amp"] * math.sin(ang * 2.0 - spec["phase"] + t * 5.0)
            zz = z + spec["zjitter"] * math.sin(ang * 3.0 + spec["phase"])
            ring.append(bm.verts.new((math.cos(ang) * radius * wobble, math.sin(ang) * radius * wobble, zz)))
        rings.append(ring)
    for band in range(bands):
        for i in range(sides):
            j = (i + 1) % sides
            face = bm.faces.new((rings[band][i], rings[band][j], rings[band + 1][j], rings[band + 1][i]))
            assign_face(face, 1)
    for whorl in range(spec["whorls"]):
        z = spec["crown_z"][0] + (spec["trunk"] * 0.15) + whorl * (spec["height"] - spec["crown_z"][0]) * 0.72 / spec["whorls"]
        reach = max(0.45, radius_at(spec, z) * spec["reach"])
        for branch in range(spec["branches"]):
            ang = 2.0 * math.pi * (branch + 0.41 * whorl) / spec["branches"] + spec["phase"]
            direction = Vector((math.cos(ang), math.sin(ang), 0.28))
            add_tube(
                bm,
                Vector((0.0, 0.0, z)),
                direction,
                reach,
                spec["branch_r"],
                spec["branch_r"] * 0.28,
                5,
                3,
                reach * 0.18,
                0,
            )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))


def build_spruce(kind, bark, foliage, col):
    spec = spruce_profile(kind)
    mesh = bpy.data.meshes.new(spec["name"])
    bm = bmesh.new()
    fill_spruce(bm, spec)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(bark)
    mesh.materials.append(foliage)
    obj = bpy.data.objects.new(spec["name"], mesh)
    obj.location = (80.0, -80.0, 0.0)
    col.objects.link(obj)
    obj["jelena_proto"] = kind
    obj["jelena_radius"] = spec["crown_r"] * spec["reach"]
    obj["jelena_height"] = spec["height"]
    return obj


def refill_live_spruces():
    for kind in ("tall", "mid", "young"):
        spec = spruce_profile(kind)
        obj = bpy.data.objects[spec["name"]]
        bm = bmesh.new()
        fill_spruce(bm, spec)
        bm.to_mesh(obj.data)
        bm.free()
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.update()
        obj["jelena_radius"] = spec["crown_r"] * spec["reach"]
        obj["jelena_height"] = spec["height"]
    for name, factor in (("Karta trávy A", 3.2), ("Karta trávy B", 2.8)):
        card = bpy.data.objects[name]
        if card.get("jelena_widened"):
            continue
        for vert in card.data.vertices:
            vert.co.x *= factor
            vert.co.y *= factor
        card.data.update()
        card["jelena_widened"] = True


def build_fern(mat, col):
    mesh = bpy.data.meshes.new("Papraď")
    bm = bmesh.new()
    for i in range(9):
        ang = 2.0 * math.pi * i / 9.0
        direction = Vector((math.cos(ang), math.sin(ang), 0.15))
        length = 0.34 if i % 2 == 0 else 0.26
        axis = direction.normalized()
        side = axis.cross(Vector((0.0, 0.0, 1.0))).normalized()
        tip = axis * length + Vector((0.0, 0.0, 0.16))
        mid = axis * (length * 0.45) + Vector((0.0, 0.0, 0.08))
        width = 0.045
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new(mid + side * width)
        v2 = bm.verts.new(tip)
        v3 = bm.verts.new(mid - side * width)
        for tri in ((v0, v1, v2), (v0, v2, v3)):
            face = bm.faces.new(tri)
            assign_face(face, 0)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("Papraď", mesh)
    obj.location = (80.0, -80.0, 0.0)
    col.objects.link(obj)
    obj["jelena_proto"] = "fern"
    obj["jelena_radius"] = 0.36
    obj["jelena_height"] = 0.28
    return obj


def build_shrub(mat, col):
    mesh = bpy.data.meshes.new("Ker")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.45)
    for vert in bm.verts:
        vert.co.z *= 0.62
        vert.co.z += 0.22
        wobble = 1.0 + 0.16 * math.sin(vert.co.x * 7.0) * math.cos(vert.co.y * 6.0)
        vert.co.x *= wobble
        vert.co.y *= wobble
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("Ker", mesh)
    obj.location = (80.0, -80.0, 0.0)
    col.objects.link(obj)
    obj["jelena_proto"] = "shrub"
    obj["jelena_radius"] = 0.55
    obj["jelena_height"] = 0.55
    return obj


def build_rock(mat, col):
    mesh = bpy.data.meshes.new("Kameň • les")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.42)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1)
    for vert in bm.verts:
        vert.co.z *= 0.55
        vert.co.z += 0.08
        vert.co *= 1.0 + 0.22 * math.sin(vert.co.x * 9.0 + vert.co.y * 4.0)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("Kameň • les", mesh)
    obj.location = (80.0, -80.0, 0.0)
    col.objects.link(obj)
    obj["jelena_proto"] = "rock"
    obj["jelena_radius"] = 0.32
    obj["jelena_height"] = 0.28
    return obj


def build_cards(mat, col):
    cards = []
    specs = (("Karta trávy A", 0.09, 0.11), ("Karta trávy B", 0.11, 0.07))
    for name, width, height in specs:
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        for turn in (0.0, math.pi * 0.5):
            c = math.cos(turn)
            s = math.sin(turn)
            verts = []
            for x, z in ((-width, 0.0), (width, 0.0), (width, height), (-width, height)):
                verts.append(bm.verts.new((x * c, x * s, z)))
            face = bm.faces.new(verts)
            assign_face(face, 0)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat)
        obj = bpy.data.objects.new(name, mesh)
        col.objects.link(obj)
        cards.append(obj)
    return cards


def tris_of(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def extend_ground():
    mat = bpy.data.materials["Lesná pôda"]
    nt = mat.node_tree
    ramp = next(node for node in nt.nodes if node.type == "VALTORGB")
    coord = next(node for node in nt.nodes if node.type == "TEX_COORD")
    bsdf = principled(mat)
    for link in list(nt.links):
        if link.from_node == ramp and link.to_socket.name == "Base Color":
            nt.links.remove(link)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.name = "Šum širší"
    noise.inputs["Scale"].default_value = 0.28
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.55
    broad = nt.nodes.new("ShaderNodeValToRGB")
    broad.name = "Pôda širšia"
    broad.color_ramp.elements[0].position = 0.30
    broad.color_ramp.elements[0].color = (0.03, 0.045, 0.018, 1)
    broad.color_ramp.elements[1].position = 0.72
    broad.color_ramp.elements[1].color = (0.11, 0.145, 0.04, 1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    sock(mix, "Factor").default_value = 0.45
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], broad.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], sock(mix, "A"))
    nt.links.new(broad.outputs["Color"], sock(mix, "B"))
    nt.links.new(out_sock(mix, "Result"), bsdf.inputs["Base Color"])


def compare(ng, operation, value_socket, threshold):
    node = ng.nodes.new("FunctionNodeCompare")
    node.data_type = "FLOAT"
    node.operation = operation
    ng.links.new(value_socket, sock(node, "A"))
    sock(node, "B").default_value = threshold
    return out_sock(node, "Result")


def bool_and(ng, a, b):
    node = ng.nodes.new("FunctionNodeBooleanMath")
    node.operation = "AND"
    ng.links.new(a, node.inputs[0])
    ng.links.new(b, node.inputs[1])
    return node.outputs[0]


def bool_not(ng, a):
    node = ng.nodes.new("FunctionNodeBooleanMath")
    node.operation = "NOT"
    ng.links.new(a, node.inputs[0])
    return node.outputs[0]


def build_cover(cards, col):
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes = ng.nodes
    links = ng.links
    ground_info = nodes.new("GeometryNodeObjectInfo")
    ground_info.transform_space = "RELATIVE"
    ground_info.inputs["Object"].default_value = bpy.data.objects["Lesná čistina"]
    position = nodes.new("GeometryNodeInputPosition")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(out_sock(position, "Position"), sock(separate, "Vector"))
    x = out_sock(separate, "X")
    y = out_sock(separate, "Y")
    inside = bool_and(ng, compare(ng, "GREATER_THAN", x, 0.0), compare(ng, "LESS_THAN", x, 18.0))
    inside = bool_and(ng, inside, compare(ng, "GREATER_THAN", y, -13.0))
    inside = bool_and(ng, inside, compare(ng, "LESS_THAN", y, 4.0))
    cabin = bool_and(ng, compare(ng, "GREATER_THAN", x, -0.5), compare(ng, "LESS_THAN", x, 9.2))
    cabin = bool_and(ng, cabin, compare(ng, "GREATER_THAN", y, -0.6))
    cabin = bool_and(ng, cabin, compare(ng, "LESS_THAN", y, 6.9))
    terrace = bool_and(ng, compare(ng, "GREATER_THAN", x, 3.2), compare(ng, "LESS_THAN", x, 9.3))
    terrace = bool_and(ng, terrace, compare(ng, "GREATER_THAN", y, -2.8))
    terrace = bool_and(ng, terrace, compare(ng, "LESS_THAN", y, 2.1))
    blocked = bool_and(ng, bool_not(ng, cabin), bool_not(ng, terrace))
    # blocked currently means NOT cabin AND NOT terrace. Combine with inside.
    selection = bool_and(ng, inside, blocked)
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.distribute_method = "RANDOM"
    sock(distribute, "Density").default_value = 45.0
    if "Distance Min" in distribute.inputs:
        distribute.inputs["Distance Min"].default_value = 0.0
    sock(distribute, "Seed").default_value = 4
    links.new(out_sock(ground_info, "Geometry"), sock(distribute, "Mesh"))
    links.new(selection, sock(distribute, "Selection"))
    infos = []
    for card in cards:
        info = nodes.new("GeometryNodeObjectInfo")
        info.transform_space = "RELATIVE"
        info.inputs["Object"].default_value = card
        infos.append(info)
    switch = nodes.new("GeometryNodeSwitch")
    if "input_type" in switch.bl_rna.properties:
        idents = [item.identifier for item in switch.bl_rna.properties["input_type"].enum_items]
        if "GEOMETRY" in idents:
            switch.input_type = "GEOMETRY"
    pick = nodes.new("FunctionNodeRandomValue")
    pick.data_type = "FLOAT"
    sock(pick, "Min").default_value = 0.0
    sock(pick, "Max").default_value = 1.0
    sock(pick, "Seed").default_value = 9
    choose = nodes.new("FunctionNodeCompare")
    choose.data_type = "FLOAT"
    choose.operation = "GREATER_THAN"
    links.new(out_sock(pick, "Value"), sock(choose, "A"))
    sock(choose, "B").default_value = 0.5
    links.new(out_sock(choose, "Result"), sock(switch, "Switch"))
    links.new(out_sock(infos[0], "Geometry"), sock(switch, "False"))
    links.new(out_sock(infos[1], "Geometry"), sock(switch, "True"))
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    links.new(out_sock(distribute, "Points"), sock(instance, "Points"))
    links.new(out_sock(switch, "Output"), sock(instance, "Instance"))
    rot = nodes.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT"
    sock(rot, "Min").default_value = 0.0
    sock(rot, "Max").default_value = math.tau
    sock(rot, "Seed").default_value = 11
    combine_r = nodes.new("ShaderNodeCombineXYZ")
    links.new(out_sock(rot, "Value"), sock(combine_r, "Z"))
    links.new(out_sock(combine_r, "Vector"), sock(instance, "Rotation"))
    scale = nodes.new("FunctionNodeRandomValue")
    scale.data_type = "FLOAT"
    sock(scale, "Min").default_value = 0.75
    sock(scale, "Max").default_value = 1.45
    sock(scale, "Seed").default_value = 13
    combine_s = nodes.new("ShaderNodeCombineXYZ")
    links.new(out_sock(scale, "Value"), sock(combine_s, "X"))
    links.new(out_sock(scale, "Value"), sock(combine_s, "Y"))
    links.new(out_sock(scale, "Value"), sock(combine_s, "Z"))
    links.new(out_sock(combine_s, "Vector"), sock(instance, "Scale"))
    output = nodes.new("NodeGroupOutput")
    links.new(out_sock(instance, "Instances"), sock(output, "Geometry"))
    mesh = bpy.data.meshes.new(COVER)
    obj = bpy.data.objects.new(COVER, mesh)
    col.objects.link(obj)
    mod = obj.modifiers.new(GROUP, "NODES")
    mod.node_group = ng
    return obj, distribute


def forbidden_trunk(x, y, stones):
    if -0.96 <= x <= 9.36 and -1.01 <= y <= 6.81:
        return True
    if 2.5 <= x <= 10.5 and y < 2.0:
        return True
    if 3.40 <= x <= 9.05 and -2.63 <= y <= 1.91:
        return True
    for bmin, bmax in stones:
        cx = min(max(x, bmin[0]), bmax[0])
        cy = min(max(y, bmin[1]), bmax[1])
        if (x - cx) ** 2 + (y - cy) ** 2 < 0.45 ** 2:
            return True
    return False


def aabb_hit(box, aabbs, pad=0.05):
    a0, a1 = box
    for b0, b1 in aabbs:
        separated = (
            a1[0] < b0[0] - pad
            or a0[0] > b1[0] + pad
            or a1[1] < b0[1] - pad
            or a0[1] > b1[1] + pad
            or a1[2] < b0[2] - pad
            or a0[2] > b1[2] + pad
        )
        if not separated:
            return True
    return False


def world_aabb(obj):
    xs, ys, zs = [], [], []
    for corner in obj.bound_box:
        world = obj.matrix_world @ Vector(corner)
        xs.append(world.x)
        ys.append(world.y)
        zs.append(world.z)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def candidate_points():
    rng = random.Random(7)
    forced = [
        (17.5, -7.5, "tall"),
        (-8.5, -2.0, "tall"),
        (-6.0, 12.0, "tall"),
        (14.0, 12.0, "tall"),
        (19.0, -4.5, "mid"),
        (-10.0, 4.0, "mid"),
        (12.5, 16.0, "mid"),
        (-2.0, 14.0, "mid"),
        (15.2, -10.6, "young"),
        (-5.2, -8.2, "young"),
        (21.0, 2.2, "young"),
        (-12.0, 14.0, "tall"),
        (22.0, 8.0, "mid"),
        (-14.0, -4.0, "mid"),
        (16.5, 18.0, "young"),
    ]
    points = [(x, y, kind) for x, y, kind in forced]
    x = -18.0
    while x <= 28.0:
        y = -12.0
        while y <= 26.0:
            points.append((x + rng.uniform(-0.7, 0.7), y + rng.uniform(-0.7, 0.7), None))
            y += 5.0
        x += 5.0
    return points


def place_instances(prototypes, col):
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    stones = []
    arch = []
    for obj in bpy.data.collections["05 • Les a okolie"].objects:
        if obj.name.startswith("Nášľap"):
            stones.append(world_aabb(obj))
    for name in ("01 • Import 3D | pôvodná geometria", "02 • Strecha a štíty", "06 • Terasa"):
        for obj in bpy.data.collections[name].objects:
            if obj.type == "MESH":
                arch.append(world_aabb(obj))
    need = {"tall": 12, "mid": 16, "young": 10}
    placed = []
    skipped = {"ray": 0, "keep": 0, "space": 0, "aabb": 0}
    for x, y, preferred in candidate_points():
        if all(value <= 0 for value in need.values()) and preferred is None:
            continue
        if forbidden_trunk(x, y, stones):
            skipped["keep"] += 1
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 3.6 ** 2 for _k, px, py, _s in placed):
            skipped["space"] += 1
            continue
        hit, loc, _normal, _index, hit_obj, _matrix = scene.ray_cast(
            depsgraph, Vector((x, y, 40.0)), Vector((0.0, 0.0, -1.0)), distance=80.0
        )
        if not hit or hit_obj is None or hit_obj.name != "Lesná čistina":
            skipped["ray"] += 1
            continue
        kind = preferred
        if kind is None or need.get(kind, 0) <= 0:
            kind = max(need, key=need.get)
        if need[kind] <= 0:
            continue
        proto = prototypes[kind]
        radius = float(proto["jelena_radius"])
        height = float(proto["jelena_height"])
        scale = 0.96 + (0.13 * ((len(placed) * 5 + ord(kind[0])) % 10) / 9.0)
        scale = min(1.15, max(0.90, scale))
        near_same = False
        for other_kind, ox, oy, other_scale in placed:
            if other_kind != kind:
                continue
            if (x - ox) ** 2 + (y - oy) ** 2 > 3.5 ** 2:
                continue
            ratio = scale / other_scale
            if 0.97 <= ratio <= 1.03:
                near_same = True
        if near_same:
            scale = min(1.15, scale + 0.08)
        box = (
            (x - radius * scale, y - radius * scale, loc.z - 0.02),
            (x + radius * scale, y + radius * scale, loc.z - 0.02 + height * scale),
        )
        if aabb_hit(box, arch):
            skipped["aabb"] += 1
            continue
        inst = proto.copy()
        inst.name = proto.name
        inst.location = (x, y, loc.z - 0.02)
        inst.rotation_mode = "XYZ"
        inst.rotation_euler = (
            ((len(placed) % 7) - 3) * 0.012,
            (((len(placed) * 3) % 7) - 3) * 0.012,
            (len(placed) * 0.73) % math.tau,
        )
        inst.scale = (scale, scale, scale)
        inst.hide_render = False
        inst.hide_viewport = False
        col.objects.link(inst)
        placed.append((kind, x, y, scale))
        need[kind] -= 1
    return placed, need, skipped


def place_small(proto, points, col, depsgraph, arch):
    scene = bpy.context.scene
    made = 0
    for x, y, scale, rot in points:
        hit, loc, _n, _i, hit_obj, _m = scene.ray_cast(
            depsgraph, Vector((x, y, 40.0)), Vector((0.0, 0.0, -1.0)), distance=80.0
        )
        if not hit or hit_obj is None or hit_obj.name != "Lesná čistina":
            continue
        radius = float(proto["jelena_radius"]) * scale
        height = float(proto["jelena_height"]) * scale
        box = (
            (x - radius, y - radius, loc.z - 0.02),
            (x + radius, y + radius, loc.z - 0.02 + height),
        )
        if aabb_hit(box, arch, pad=0.02):
            continue
        inst = proto.copy()
        inst.name = proto.name
        inst.location = (x, y, loc.z - 0.02)
        inst.rotation_mode = "XYZ"
        inst.rotation_euler = (0.0, 0.0, rot)
        inst.scale = (scale, scale, scale)
        inst.hide_render = False
        col.objects.link(inst)
        made += 1
    return made


def count_cards(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.evaluated_get(depsgraph)
    count = 0
    for inst in depsgraph.object_instances:
        if not inst.is_instance:
            continue
        parent = inst.parent
        original = getattr(parent, "original", parent) if parent is not None else None
        if original == obj or parent == obj:
            count += 1
    return count


def setup_lights_and_world():
    scene_a = bpy.data.scenes[SCENE_A]
    scene_b = bpy.data.scenes[SCENE_B]
    world = scene_a.world.copy()
    world.name = WORLD_A
    scene_a.world = world
    for node in world.node_tree.nodes:
        if node.type == "BACKGROUND":
            node.inputs["Strength"].default_value = 0.25
    col_b = bpy.data.collections.new(COL_07B)
    col_c = bpy.data.collections.new(COL_07C)
    link_to(scene_a, col_b)
    link_to(scene_b, col_b)
    link_to(scene_a, col_c)
    for name in ("Popoludňajšie slnko", "Mäkké svetlo z čistiny"):
        move_into(bpy.data.objects[name], col_b)
    sun = bpy.data.objects["Popoludňajšie slnko"]
    disk = bpy.data.objects["Mäkké svetlo z čistiny"]
    sun_a = sun.copy()
    sun_a.data = sun.data.copy()
    sun_a.name = SUN_A
    sun_a.data.energy = 4.0
    sun_a.data.angle = 0.05
    col_c.objects.link(sun_a)
    disk_a = disk.copy()
    disk_a.data = disk.data.copy()
    disk_a.name = DISK_A
    disk_a.data.energy = 120.0
    disk_a.data.size = 8.0
    col_c.objects.link(disk_a)
    set_exclude(scene_a, COL_07B, True)
    return assert_scene_b("after lights")


def main():
    require_v002()
    if COL_09 in bpy.data.collections:
        raise RuntimeError("refusing: prototypes already exist")
    scene_a = bpy.data.scenes[SCENE_A]
    before = assert_scene_b("before lights")
    if not before["layer_found"]:
        # 07b does not exist yet; the pre-check only validates energies and counts.
        pass
    light_report = setup_lights_and_world()
    if light_report["layer_found"] and light_report["exclude_07b"]:
        raise RuntimeError("excluding 07b also excluded it for scene B")
    if not light_report["layer_found"]:
        raise RuntimeError("scene B view layer has no 07b collection to verify")

    col_05 = bpy.data.collections["05 • Les a okolie"]
    col_05a = bpy.data.collections.new(COL_05A)
    link_to(scene_a, col_05a)
    moved = []
    for obj in list(col_05.objects):
        if is_old_vegetation(obj.name):
            if obj.users != 1 or obj.data.users != 1:
                raise RuntimeError(f"refusing to move shared object {obj.name}")
            move_into(obj, col_05a)
            moved.append(obj.name)
    set_exclude(scene_a, COL_05A, True)
    bpy.context.view_layer.update()

    col_09 = bpy.data.collections.new(COL_09)
    col_10 = bpy.data.collections.new(COL_10)
    link_to(scene_a, col_09)
    link_to(scene_a, col_10)
    bark = make_bark()
    foliage = make_foliage("Ihličie • koruna", (0.012, 0.045, 0.018), (0.055, 0.12, 0.028))
    fern_mat = make_foliage("Papraď • list", (0.02, 0.07, 0.02), (0.08, 0.16, 0.04))
    shrub_mat = make_foliage("Ker • list", (0.03, 0.06, 0.018), (0.09, 0.13, 0.03))
    rock_mat = make_simple("Kameň • les", (0.23, 0.22, 0.19), 0.92, 0.35)
    grass_mat = make_simple("Tráva • pokryv", (0.05, 0.11, 0.03), 0.9)
    prototypes = {
        "tall": build_spruce("tall", bark, foliage, col_09),
        "mid": build_spruce("mid", bark, foliage, col_09),
        "young": build_spruce("young", bark, foliage, col_09),
    }
    fern = build_fern(fern_mat, col_09)
    shrub = build_shrub(shrub_mat, col_09)
    rock = build_rock(rock_mat, col_09)
    cards = build_cards(grass_mat, col_09)
    counts = {key: tris_of(obj) for key, obj in prototypes.items()}
    counts["fern"] = tris_of(fern)
    counts["shrub"] = tris_of(shrub)
    counts["rock"] = tris_of(rock)
    counts["card_a"] = tris_of(cards[0])
    counts["card_b"] = tris_of(cards[1])
    unique = counts["tall"] + counts["mid"] + counts["young"] + counts["fern"] + counts["shrub"] + counts["rock"]
    if unique > 80000:
        raise RuntimeError(f"unique vegetation triangles {unique} exceed 80000")
    set_exclude(scene_a, COL_09, True)

    placed, remaining, skipped = place_instances(prototypes, col_10)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arch = []
    for name in ("01 • Import 3D | pôvodná geometria", "02 • Strecha a štíty", "06 • Terasa"):
        for obj in bpy.data.collections[name].objects:
            if obj.type == "MESH":
                arch.append(world_aabb(obj))
    fern_n = place_small(
        fern,
        [
            (4.2, -3.35, 1.0, 0.2),
            (6.4, -3.45, 0.85, 1.4),
            (8.4, -3.30, 1.15, 2.2),
            (2.55, -1.2, 0.9, 0.6),
            (2.7, 0.6, 1.05, 1.8),
            (10.0, -1.4, 0.95, 2.8),
            (10.15, 0.4, 1.1, 0.4),
            (7.2, -4.3, 0.8, 1.1),
            (11.4, -3.6, 1.0, 2.5),
            (5.0, -5.4, 0.9, 0.9),
        ],
        col_10,
        depsgraph,
        arch,
    )
    shrub_n = place_small(
        shrub,
        [
            (1.3, -4.2, 1.0, 0.3),
            (11.6, -2.2, 0.85, 1.2),
            (2.0, -6.5, 1.15, 2.0),
            (13.2, -1.0, 0.9, 0.7),
            (-1.2, -3.5, 1.05, 1.6),
            (11.0, -6.0, 0.8, 2.4),
            (4.8, -6.8, 1.0, 0.5),
            (15.5, -1.8, 0.95, 1.9),
        ],
        col_10,
        depsgraph,
        arch,
    )
    rock_n = place_small(
        rock,
        [
            (5.4, -6.55, 1.0, 0.4),
            (8.8, -4.9, 0.8, 1.3),
            (12.2, -2.6, 1.1, 2.1),
            (13.4, 0.6, 0.9, 0.8),
            (4.6, -4.7, 0.75, 1.7),
            (10.6, -5.5, 1.05, 2.6),
        ],
        col_10,
        depsgraph,
        arch,
    )
    extend_ground()
    cover, _distribute = build_cover(cards, col_10)
    for card in cards:
        card.hide_render = True
        card.hide_viewport = True
    bpy.context.view_layer.update()
    card_count = count_cards(cover)
    if card_count > 20000:
        dist = next(node for node in cover.modifiers[GROUP].node_group.nodes if node.bl_idname == "GeometryNodeDistributePointsOnFaces")
        dist.inputs["Density"].default_value = 22.0
        bpy.context.view_layer.update()
        card_count = count_cards(cover)
    if card_count > 20000:
        raise RuntimeError(f"grass cards {card_count} still above 20000 after one reduction")

    scene = bpy.context.scene
    in_frame = {"tall": 0, "mid": 0, "young": 0}
    for obj in col_10.objects:
        kind = obj.get("jelena_proto")
        if kind not in in_frame:
            continue
        point = world_to_camera_view(scene, scene.camera, obj.matrix_world.translation)
        if point.z > 0.0 and -0.05 <= point.x <= 1.05 and -0.05 <= point.y <= 1.05:
            in_frame[kind] += 1
    final_b = assert_scene_b("final")
    delta, sensor_fit = camera_delta()
    if delta > 1e-5 or sensor_fit != "AUTO":
        raise RuntimeError(f"camera changed: delta {delta} fit {sensor_fit}")
    summary = {
        "moved_old": len(moved),
        "triangles": counts,
        "unique_triangles": unique,
        "placed": {kind: sum(1 for item in placed if item[0] == kind) for kind in ("tall", "mid", "young")},
        "remaining_need": remaining,
        "skipped": skipped,
        "fern": fern_n,
        "shrub": shrub_n,
        "rock": rock_n,
        "cards": card_count,
        "in_frame": in_frame,
        "node_groups": [group.name for group in bpy.data.node_groups],
        "scene_b": final_b,
        "camera_delta": delta,
        "world_a": world_strength(scene.world),
        "sun_a": float(bpy.data.objects[SUN_A].data.energy),
        "sun_a_angle": float(bpy.data.objects[SUN_A].data.angle),
        "disk_a": float(bpy.data.objects[DISK_A].data.energy),
        "dirty": bool(bpy.data.is_dirty),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
