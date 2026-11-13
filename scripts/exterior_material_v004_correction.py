"""One-shot façade and roof correction for the first-pass Jelena v004.

Rebuilds the scene-A batten and backing shaders so boards differ at ordinary
viewing size, hides the standing-seam ribs without deleting them, and adds a
lightweight dark shingle layer on the existing roof planes. Does not render
or save.
"""

import hashlib
import json

import bpy
from mathutils import Vector

SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"
CAM_A = "A • Chata pri lese"
CAM_LOC = (13.9, -16.4, 6.35)
CAM_ROT = (1.390952, 0.0, 0.477129)
EXPECTED_V004 = "f02ad73ce879cd30ced6ab88dda01c6a4ecbfc7b03333b74b9036190712d5272"
MAT_BATTEN = "Fasáda • lata • A"
MAT_BACKING = "Fasáda • podklad • A"
MAT_GLASS = "Sklo • exteriér A"
MAT_GLASS_OLD = "Sklo • priehľadné"
MAT_ROOF = "Strecha • falcovaný plech"
MAT_SHINGLE = "Strecha • šindeľ • antracit"
COL_02 = "02 • Strecha a štíty"
COL_02A = "02a • Strecha • pôvodné falce"
COL_02B = "02b • Strecha • šindeľ"
COL_06B = "06b • Terasa • scéna A"

# Measured top faces of the two roof sheets. s increases downslope from the ridge.
SLOPES = {
    "west": {
        "origin": Vector((4.2, -0.38, 5.068)),
        "down": Vector((-0.8979, 0.0, -0.4401)),
        "normal": Vector((-0.44, 0.0, 0.898)),
        "y_dir": Vector((0.0, 1.0, 0.0)),
        "length": 5.056,
    },
    "east": {
        "origin": Vector((4.2, -0.38, 5.068)),
        "down": Vector((0.8979, 0.0, -0.4401)),
        "normal": Vector((0.44, 0.0, 0.898)),
        "y_dir": Vector((0.0, 1.0, 0.0)),
        "length": 5.056,
    },
}
S_START = 0.18
S_END = 4.98
ROW_STEP = 0.20
SHINGLE_LENGTH = 0.30
Y0 = -0.32
Y1 = 6.10
PITCH = 0.40
# Chimney footprint on the east slope, expanded slightly, in (s0, s1, y0, y1).
CHIMNEY_HOLE = (3.58, 4.05, 5.06, 5.43)


def fail(message):
    raise RuntimeError(message)


def in_scene(obj, scene):
    return obj.name in scene.objects


def uses(obj, material_name):
    return any(slot.material and slot.material.name == material_name for slot in obj.material_slots)


def scene_users(material_name, scene):
    return sum(1 for obj in scene.objects if uses(obj, material_name))


def node_signature(material):
    tree = material.node_tree
    return {
        "types": sorted(node.type for node in tree.nodes),
        "links": len(tree.links),
    }


def layer_collection(root, name):
    if root.collection.name == name:
        return root
    for child in root.children:
        found = layer_collection(child, name)
        if found is not None:
            return found
    return None


def validate():
    path = bpy.data.filepath
    if not path.endswith("Jelena_Realistic_v004.blend"):
        fail(f"unexpected file: {path}")
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != EXPECTED_V004:
        fail(f"v004 hash {digest}")
    scene = bpy.context.scene
    if scene.name != SCENE_A or scene.camera is None or scene.camera.name != CAM_A:
        fail("active scene or camera is not A")
    scene_a = bpy.data.scenes[SCENE_A]
    scene_b = bpy.data.scenes[SCENE_B]
    if len(scene_b.objects) != 308:
        fail(f"scene B count {len(scene_b.objects)}")
    camera = scene_a.camera
    for actual, expected in zip(camera.location, CAM_LOC):
        if abs(actual - expected) > 0.0001:
            fail("camera location")
    for actual, expected in zip(camera.rotation_euler, CAM_ROT):
        if abs(actual - expected) > 0.0001:
            fail("camera rotation")
    for name in (MAT_BATTEN, MAT_BACKING, MAT_GLASS, MAT_ROOF):
        if name not in bpy.data.materials:
            fail(f"missing material {name}")
    if MAT_SHINGLE in bpy.data.materials or COL_02A in bpy.data.collections or COL_02B in bpy.data.collections:
        fail("correction already exists")
    if COL_06B not in bpy.data.collections or len(bpy.data.collections[COL_06B].objects) != 51:
        fail("terrace duplicate set is not 51")
    battens = [
        obj
        for obj in scene_a.objects
        if obj.name.startswith("Fasádna lata") and uses(obj, MAT_BATTEN) and not in_scene(obj, scene_b)
    ]
    backing = [
        obj
        for obj in scene_a.objects
        if uses(obj, MAT_BACKING) and not in_scene(obj, scene_b)
    ]
    if len(battens) != 312 or len(backing) != 23:
        fail(f"facade users battens {len(battens)} backing {len(backing)}")
    if any("grain_mul" not in obj.keys() for obj in battens):
        fail("a batten is missing grain_mul")
    ribs = [obj for obj in bpy.data.objects if obj.name.startswith("Strešný falc")]
    if len(ribs) != 38 or any(in_scene(obj, scene_b) for obj in ribs):
        fail(f"rib count {len(ribs)}")
    if scene_users(MAT_ROOF, scene_a) != 45 or scene_users(MAT_ROOF, scene_b) != 0:
        fail("roof material users")
    return scene_a, scene_b, battens, backing, ribs


def clear_tree(material):
    material.use_nodes = True
    material.node_tree.nodes.clear()
    return material.node_tree


def new_color_ramp(nodes, stops):
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = stops[0][0]
    ramp.color_ramp.elements[0].color = stops[0][1]
    ramp.color_ramp.elements[1].position = stops[-1][0]
    ramp.color_ramp.elements[1].color = stops[-1][1]
    for position, color in stops[1:-1]:
        element = ramp.color_ramp.elements.new(position)
        element.color = color
    return ramp


def rebuild_batten(material):
    tree = clear_tree(material)
    nodes = tree.nodes
    links = tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "OBJECT"
    attr.attribute_name = "grain_mul"
    mapped = nodes.new("ShaderNodeVectorMath")
    mapped.operation = "MULTIPLY"
    info = nodes.new("ShaderNodeObjectInfo")
    phase = nodes.new("ShaderNodeMath")
    phase.operation = "MULTIPLY"
    phase.inputs[1].default_value = 8.0
    phase_vec = nodes.new("ShaderNodeCombineXYZ")
    positioned = nodes.new("ShaderNodeVectorMath")
    positioned.operation = "ADD"
    fine_scale = nodes.new("ShaderNodeVectorMath")
    fine_scale.operation = "SCALE"
    fine_scale.inputs["Scale"].default_value = 4.0
    coarse = nodes.new("ShaderNodeTexNoise")
    coarse.noise_dimensions = "3D"
    coarse.noise_type = "FBM"
    coarse.inputs["Scale"].default_value = 1.4
    coarse.inputs["Detail"].default_value = 2.0
    fine = nodes.new("ShaderNodeTexNoise")
    fine.noise_dimensions = "3D"
    fine.noise_type = "FBM"
    fine.inputs["Scale"].default_value = 1.0
    fine.inputs["Detail"].default_value = 6.0
    board = new_color_ramp(
        nodes,
        (
            (0.0, (0.07, 0.028, 0.012, 1.0)),
            (0.5, (0.26, 0.12, 0.05, 1.0)),
            (1.0, (0.44, 0.22, 0.10, 1.0)),
        ),
    )
    coarse_gain = nodes.new("ShaderNodeMapRange")
    coarse_gain.data_type = "FLOAT"
    coarse_gain.inputs["To Min"].default_value = 0.86
    coarse_gain.inputs["To Max"].default_value = 1.08
    coarse_gain.clamp = True
    fine_gain = nodes.new("ShaderNodeMapRange")
    fine_gain.data_type = "FLOAT"
    fine_gain.inputs["To Min"].default_value = 0.93
    fine_gain.inputs["To Max"].default_value = 1.05
    fine_gain.clamp = True
    gain = nodes.new("ShaderNodeMath")
    gain.operation = "MULTIPLY"
    tint = nodes.new("ShaderNodeVectorMath")
    tint.operation = "SCALE"
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.data_type = "FLOAT"
    roughness.inputs["To Min"].default_value = 0.50
    roughness.inputs["To Max"].default_value = 0.78
    roughness.clamp = True
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    bump.inputs["Distance"].default_value = 0.0025
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Object"], mapped.inputs[0])
    links.new(attr.outputs["Vector"], mapped.inputs[1])
    links.new(info.outputs["Random"], phase.inputs[0])
    links.new(phase.outputs["Value"], phase_vec.inputs["X"])
    links.new(phase.outputs["Value"], phase_vec.inputs["Y"])
    links.new(phase.outputs["Value"], phase_vec.inputs["Z"])
    links.new(mapped.outputs["Vector"], positioned.inputs[0])
    links.new(phase_vec.outputs["Vector"], positioned.inputs[1])
    links.new(positioned.outputs["Vector"], coarse.inputs["Vector"])
    links.new(positioned.outputs["Vector"], fine_scale.inputs[0])
    links.new(fine_scale.outputs["Vector"], fine.inputs["Vector"])
    links.new(info.outputs["Random"], board.inputs["Factor"])
    links.new(coarse.outputs["Factor"], coarse_gain.inputs["Value"])
    links.new(fine.outputs["Factor"], fine_gain.inputs["Value"])
    links.new(coarse_gain.outputs["Result"], gain.inputs[0])
    links.new(fine_gain.outputs["Result"], gain.inputs[1])
    links.new(board.outputs["Color"], tint.inputs[0])
    links.new(gain.outputs["Value"], tint.inputs["Scale"])
    links.new(tint.outputs["Vector"], bsdf.inputs["Base Color"])
    links.new(fine.outputs["Factor"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(fine.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def rebuild_backing(material):
    tree = clear_tree(material)
    nodes = tree.nodes
    links = tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "3D"
    noise.noise_type = "FBM"
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["Detail"].default_value = 2.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.05
    bump.inputs["Distance"].default_value = 0.002
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.055, 0.022, 0.009, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Metallic"].default_value = 0.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def hide_ribs(scene_a, ribs):
    collection = bpy.data.collections.new(COL_02A)
    scene_a.collection.children.link(collection)
    source = bpy.data.collections[COL_02]
    for obj in ribs:
        if source not in obj.users_collection or len(obj.users_collection) != 1:
            fail(f"rib {obj.name} is not exclusively in collection 02")
        source.objects.unlink(obj)
        collection.objects.link(obj)
    bpy.context.view_layer.update()
    layer = layer_collection(scene_a.view_layers[0].layer_collection, COL_02A)
    if layer is None:
        fail("could not exclude the preserved ribs")
    layer.exclude = True
    if layer_collection(bpy.data.scenes[SCENE_B].view_layers[0].layer_collection, COL_02A) is not None:
        fail("rib collection leaked into scene B")
    return collection


def subtract_hole(rect):
    s0, s1, y0, y1 = rect
    h0, h1, k0, k1 = CHIMNEY_HOLE
    if s1 <= h0 or s0 >= h1 or y1 <= k0 or y0 >= k1:
        return [rect]
    pieces = []
    if s0 < h0:
        pieces.append((s0, min(s1, h0), y0, y1))
    if s1 > h1:
        pieces.append((max(s0, h1), s1, y0, y1))
    overlap_s0 = max(s0, h0)
    overlap_s1 = min(s1, h1)
    if y0 < k0:
        pieces.append((overlap_s0, overlap_s1, y0, min(y1, k0)))
    if y1 > k1:
        pieces.append((overlap_s0, overlap_s1, max(y0, k1), y1))
    return [piece for piece in pieces if piece[1] - piece[0] > 0.03 and piece[3] - piece[2] > 0.03]


def shingle_rects(side):
    rects = []
    row = 0
    butt = S_END
    while butt - SHINGLE_LENGTH >= S_START - 0.001:
        top = butt - SHINGLE_LENGTH
        shift = 0.0 if row % 2 == 0 else PITCH * 0.5
        y = Y0 + shift
        while y < Y1 - 0.03:
            y_b = min(y + PITCH, Y1)
            if y_b - y >= 0.12:
                rect = (top, butt, y, y_b)
                if side == "east":
                    rects.extend(subtract_hole(rect))
                else:
                    rects.append(rect)
            y += PITCH
        butt -= ROW_STEP
        row += 1
    return rects, row


def add_quad(verts, faces, uvs, tones, corners, tone):
    start = len(verts)
    verts.extend(corners)
    s_values = [index for index in range(4)]
    # Corners are (top-south, butt-south, butt-north, top-north) before any side reversal.
    faces.append((start, start + 1, start + 2, start + 3))
    y0 = min(corner[1] for corner in corners)
    y1 = max(corner[1] for corner in corners)
    # UV is filled by the caller in corner order: U across, V 0 at the butt.
    uvs.extend(corners)
    tones.append(tone)
    return s_values


def build_shingles(scene_a):
    material = bpy.data.materials.new(MAT_SHINGLE)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    nodes = tree.nodes
    links = tree.links
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    separate = nodes.new("ShaderNodeSeparateXYZ")
    tone_attr = nodes.new("ShaderNodeAttribute")
    tone_attr.attribute_type = "GEOMETRY"
    tone_attr.attribute_name = "tone"
    tone_split = nodes.new("ShaderNodeSeparateXYZ")
    tone_gain = nodes.new("ShaderNodeMapRange")
    tone_gain.data_type = "FLOAT"
    tone_gain.inputs["To Min"].default_value = 0.72
    tone_gain.inputs["To Max"].default_value = 1.28
    tone_gain.clamp = True
    butt = nodes.new("ShaderNodeMapRange")
    butt.data_type = "FLOAT"
    butt.inputs["From Min"].default_value = 0.0
    butt.inputs["From Max"].default_value = 0.22
    butt.inputs["To Min"].default_value = 0.48
    butt.inputs["To Max"].default_value = 1.0
    butt.clamp = True
    grain = nodes.new("ShaderNodeTexNoise")
    grain.noise_dimensions = "3D"
    grain.noise_type = "FBM"
    grain.inputs["Scale"].default_value = 9.0
    grain.inputs["Detail"].default_value = 4.0
    grain_gain = nodes.new("ShaderNodeMapRange")
    grain_gain.data_type = "FLOAT"
    grain_gain.inputs["To Min"].default_value = 0.90
    grain_gain.inputs["To Max"].default_value = 1.06
    grain_gain.clamp = True
    base = nodes.new("ShaderNodeCombineXYZ")
    base.inputs["X"].default_value = 0.033
    base.inputs["Y"].default_value = 0.045
    base.inputs["Z"].default_value = 0.046
    tint = nodes.new("ShaderNodeVectorMath")
    tint.operation = "SCALE"
    shade = nodes.new("ShaderNodeVectorMath")
    shade.operation = "SCALE"
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.data_type = "FLOAT"
    roughness.inputs["To Min"].default_value = 0.48
    roughness.inputs["To Max"].default_value = 0.64
    roughness.clamp = True
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.0015
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.25
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tone_attr.outputs["Color"], tone_split.inputs["Vector"])
    links.new(tone_split.outputs["X"], tone_gain.inputs["Value"])
    links.new(base.outputs["Vector"], tint.inputs[0])
    links.new(tone_gain.outputs["Result"], tint.inputs["Scale"])
    links.new(uv.outputs["UV"], separate.inputs["Vector"])
    links.new(separate.outputs["Y"], butt.inputs["Value"])
    links.new(tint.outputs["Vector"], shade.inputs[0])
    links.new(butt.outputs["Result"], shade.inputs["Scale"])
    # Grain multiplies the already shaded color.
    grain_tint = nodes.new("ShaderNodeVectorMath")
    grain_tint.operation = "SCALE"
    links.new(uv.outputs["UV"], grain.inputs["Vector"])
    links.new(grain.outputs["Factor"], grain_gain.inputs["Value"])
    links.new(shade.outputs["Vector"], grain_tint.inputs[0])
    links.new(grain_gain.outputs["Result"], grain_tint.inputs["Scale"])
    links.new(grain_tint.outputs["Vector"], bsdf.inputs["Base Color"])
    links.new(grain.outputs["Factor"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(grain.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    verts = []
    faces = []
    loop_uvs = []
    loop_tones = []
    for side, spec in SLOPES.items():
        origin = spec["origin"]
        down = spec["down"]
        normal = spec["normal"]
        y_dir = spec["y_dir"]
        rects, _rows = shingle_rects(side)
        for index, (top, butt_s, y_a, y_b) in enumerate(rects):
            lift = 0.008 + ((S_END - butt_s) / ROW_STEP) * 0.0025

            def point(s_value, y_value, extra=0.0):
                return origin + down * s_value + y_dir * (y_value + 0.38) + normal * (lift + extra)

            corners = (
                point(top, y_a),
                point(butt_s, y_a),
                point(butt_s, y_b),
                point(top, y_b),
            )
            if side == "west":
                corners = (corners[0], corners[3], corners[2], corners[1])
            start = len(verts)
            verts.extend(corners)
            faces.append((start, start + 1, start + 2, start + 3))
            span_s = max(butt_s - top, 1e-6)
            span_y = max(y_b - y_a, 1e-6)
            ordered = ((top, y_a), (butt_s, y_a), (butt_s, y_b), (top, y_b))
            if side == "west":
                ordered = (ordered[0], ordered[3], ordered[2], ordered[1])
            tone = ((index * 374761393 + (0 if side == "west" else 17) * 668265263) & 0xFFFFFF) / 0xFFFFFF
            for s_value, y_value in ordered:
                loop_uvs.append(((y_value - y_a) / span_y, (butt_s - s_value) / span_s))
                loop_tones.append(tone)

    mesh = bpy.data.meshes.new("Šindeľ strechy")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    min_z = min(polygon.normal.z for polygon in mesh.polygons)
    if min_z < 0.5:
        fail(f"shingle normals point downward: {min_z}")
    uv_layer = mesh.uv_layers.new(name="UVMap")
    tone_layer = mesh.color_attributes.new(name="tone", type="FLOAT_COLOR", domain="CORNER")
    for loop_index, loop in enumerate(mesh.loops):
        uv_layer.data[loop_index].uv = loop_uvs[loop_index]
        tone_layer.data[loop_index].color = (loop_tones[loop_index],) * 3 + (1.0,)
    if len(mesh.polygons) > 2000:
        fail(f"shingle faces {len(mesh.polygons)}")
    mesh.calc_loop_triangles()
    if len(mesh.loop_triangles) > 5000:
        fail(f"shingle triangles {len(mesh.loop_triangles)}")
    obj = bpy.data.objects.new("Šindeľ strechy", mesh)
    collection = bpy.data.collections.new(COL_02B)
    scene_a.collection.children.link(collection)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    if layer_collection(bpy.data.scenes[SCENE_B].view_layers[0].layer_collection, COL_02B) is not None:
        fail("shingle collection leaked into scene B")
    return len(mesh.polygons), len(mesh.loop_triangles)


def main():
    scene_a, scene_b, battens, backing, ribs = validate()
    protected_names = (
        "Fasáda • termodrevo",
        "Terasa • smrekovec",
        "Terasa • smrekovec • A",
        MAT_GLASS,
        MAT_GLASS_OLD,
        "Antracit",
        "Interiér • prírodný dub",
        MAT_ROOF,
    )
    before = {name: node_signature(bpy.data.materials[name]) for name in protected_names}
    roof_positions = {}
    for name in ("Roof_031", "Roof_032", "Hrebenáč"):
        obj = bpy.data.objects[name]
        world = obj.matrix_world
        roof_positions[name] = [tuple(round(value, 4) for value in (world @ vertex.co)) for vertex in obj.data.vertices]
    rebuild_batten(bpy.data.materials[MAT_BATTEN])
    rebuild_backing(bpy.data.materials[MAT_BACKING])
    hide_ribs(scene_a, ribs)
    faces, triangles = build_shingles(scene_a)
    for name in protected_names:
        if node_signature(bpy.data.materials[name]) != before[name]:
            fail(f"protected material changed: {name}")
    for name, coords in roof_positions.items():
        obj = bpy.data.objects[name]
        world = obj.matrix_world
        now = [tuple(round(value, 4) for value in (world @ vertex.co)) for vertex in obj.data.vertices]
        if now != coords:
            fail(f"roof geometry changed: {name}")
    if len(scene_b.objects) != 308:
        fail("scene B count changed")
    if scene_users(MAT_BATTEN, scene_a) != 312 or scene_users(MAT_BACKING, scene_a) != 23:
        fail("facade assignment changed")
    if scene_users(MAT_BATTEN, scene_b) or scene_users(MAT_BACKING, scene_b) or scene_users(MAT_SHINGLE, scene_b):
        fail("a corrected material reached scene B")
    if scene_users(MAT_ROOF, scene_a) != 45:
        fail("roof metal users changed")
    summary = {
        "status": "applied",
        "battens": 312,
        "backing": 23,
        "ribs_preserved": len(bpy.data.collections[COL_02A].objects),
        "ribs_excluded": layer_collection(scene_a.view_layers[0].layer_collection, COL_02A).exclude,
        "shingle_faces": faces,
        "shingle_triangles": triangles,
        "scene_a_objects": len(scene_a.objects),
        "scene_b_objects": len(scene_b.objects),
    }
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main()
