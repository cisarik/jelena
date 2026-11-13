"""One-shot horizontal timber cladding for the main walls of Jelena v004.

Hides the 210 scene-A vertical wall battens without deleting them, and adds a
lightweight horizontal log layer over the 21 Exterior wall panels. The 102
gable battens stay visible. Does not render or save.
"""

import hashlib
import json

import bpy
from mathutils import Vector

SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"
CAM_LOC = (13.9, -16.4, 6.35)
CAM_ROT = (1.390952, 0.0, 0.477129)
EXPECTED_V004 = "24927e9ae55ba45287578ff1cb3e999ea6f45da806fcb3ccdec5b98c64500095"
MAT_BATTEN = "Fasáda • lata • A"
MAT_BACKING = "Fasáda • podklad • A"
MAT_LOG = "Fasáda • zrub • A"
MAT_SHADOW = "Fasáda • zrub • tieň • A"
COL_01 = "01 • Import 3D | pôvodná geometria"
COL_01A = "01a • Fasáda • pôvodné latky"
COL_01B = "01b • Fasáda • zrub • A"
PITCH = 0.18
BOARD_H = 0.142
# Profile fraction from the bottom of the board, proud distance in metres.
PROFILE = ((0.0, 0.006), (0.2, 0.03), (0.62, 0.046), (1.0, 0.01))


def fail(message):
    raise RuntimeError(message)


def in_scene(obj, scene):
    return obj.name in scene.objects


def uses(obj, name):
    return any(slot.material and slot.material.name == name for slot in obj.material_slots)


def scene_users(name, scene):
    return sum(1 for obj in scene.objects if uses(obj, name))


def node_signature(material):
    tree = material.node_tree
    return {"types": sorted(node.type for node in tree.nodes), "links": len(tree.links)}


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
        fail(path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != EXPECTED_V004:
        fail(f"hash {digest}")
    scene = bpy.context.scene
    if scene.name != SCENE_A or scene.camera is None or scene.camera.name != SCENE_A:
        fail("scene or camera")
    for actual, expected in zip(scene.camera.location, CAM_LOC):
        if abs(actual - expected) > 0.0001:
            fail("camera location")
    for actual, expected in zip(scene.camera.rotation_euler, CAM_ROT):
        if abs(actual - expected) > 0.0001:
            fail("camera rotation")
    scene_a = bpy.data.scenes[SCENE_A]
    scene_b = bpy.data.scenes[SCENE_B]
    if len(scene_b.objects) != 308:
        fail("scene B")
    if len(bpy.data.collections["06b • Terasa • scéna A"].objects) != 51:
        fail("terrace duplicates")
    if len(bpy.data.objects["Šindeľ strechy"].data.polygons) != 740:
        fail("shingles")
    if len(bpy.data.collections["02a • Strecha • pôvodné falce"].objects) != 38:
        fail("ribs")
    for name in (MAT_LOG, MAT_SHADOW, COL_01A, COL_01B):
        if name in bpy.data.materials or name in bpy.data.collections:
            fail(f"already present {name}")
    panels = []
    for obj in scene_a.objects:
        if obj.type == "MESH" and obj.name.startswith("Exterior_") and uses(obj, MAT_BACKING):
            if in_scene(obj, scene_b):
                fail(f"panel in scene B {obj.name}")
            panels.append(obj)
    if len(panels) != 21:
        fail(f"panels {len(panels)}")
    wall = []
    gable = []
    for obj in scene_a.objects:
        if not (obj.type == "MESH" and obj.name.startswith("Fasádna lata") and uses(obj, MAT_BATTEN)):
            continue
        cols = [col.name for col in obj.users_collection]
        if cols == [COL_01]:
            wall.append(obj)
        elif any(name.startswith("02") for name in cols):
            gable.append(obj)
        else:
            fail(f"batten collection {obj.name} {cols}")
    if len(wall) != 210 or len(gable) != 102:
        fail(f"battens wall {len(wall)} gable {len(gable)}")
    if any(in_scene(obj, scene_b) for obj in wall + gable + panels):
        fail("facade object in scene B")
    return scene_a, scene_b, panels, wall


def hide_wall_battens(scene_a, wall):
    collection = bpy.data.collections.new(COL_01A)
    scene_a.collection.children.link(collection)
    source = bpy.data.collections[COL_01]
    for obj in wall:
        source.objects.unlink(obj)
        collection.objects.link(obj)
    bpy.context.view_layer.update()
    layer = layer_collection(scene_a.view_layers[0].layer_collection, COL_01A)
    if layer is None:
        fail("01a missing from view layer")
    layer.exclude = True
    if layer_collection(bpy.data.scenes[SCENE_B].view_layers[0].layer_collection, COL_01A) is not None:
        fail("01a leaked into scene B")


def panel_spec(obj):
    world = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    xs = [point.x for point in world]
    ys = [point.y for point in world]
    zs = [point.z for point in world]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    extents = (max_x - min_x, max_y - min_y, max_z - min_z)
    thin = extents.index(min(extents))
    if thin == 2 or extents[2] < 0.12:
        return None
    if thin == 1 and min_y < 1.0:
        outward = Vector((0.0, -1.0, 0.0))
        along = Vector((1.0, 0.0, 0.0))
        origin = Vector((0.0, min_y, 0.0))
        a0, a1 = min_x, max_x
    elif thin == 1:
        outward = Vector((0.0, 1.0, 0.0))
        along = Vector((-1.0, 0.0, 0.0))
        origin = Vector((0.0, max_y, 0.0))
        a0, a1 = -max_x, -min_x
    elif thin == 0 and max_x > 4.0:
        outward = Vector((1.0, 0.0, 0.0))
        along = Vector((0.0, 1.0, 0.0))
        origin = Vector((max_x, 0.0, 0.0))
        a0, a1 = min_y, max_y
    elif thin == 0:
        outward = Vector((-1.0, 0.0, 0.0))
        along = Vector((0.0, -1.0, 0.0))
        origin = Vector((min_x, 0.0, 0.0))
        a0, a1 = -max_y, -min_y
    else:
        return None
    if along.cross(Vector((0.0, 0.0, 1.0))).dot(outward) < 0.5:
        fail(f"frame {obj.name}")
    return {
        "name": obj.name,
        "origin": origin,
        "along": along,
        "outward": outward,
        "a0": a0 + 0.004,
        "a1": a1 - 0.004,
        "z0": min_z,
        "z1": max_z,
    }


def add_face(verts, faces, uvs, tones, corners, uv_corners, tone, expected_normal):
    start = len(verts)
    verts.extend(corners)
    indexes = (start, start + 1, start + 2, start + 3)
    normal = (corners[1] - corners[0]).cross(corners[2] - corners[0])
    if normal.dot(expected_normal) < 0.0:
        indexes = (start, start + 3, start + 2, start + 1)
        uv_corners = (uv_corners[0], uv_corners[3], uv_corners[2], uv_corners[1])
    faces.append(indexes)
    uvs.extend(uv_corners)
    tones.extend((tone, tone, tone, tone))


def build_logs(scene_a, panels):
    verts = []
    faces = []
    uvs = []
    tones = []
    skipped = []
    for panel in panels:
        spec = panel_spec(panel)
        if spec is None or spec["a1"] - spec["a0"] < 0.08:
            skipped.append(panel.name)
            continue
        z = spec["z0"] - (spec["z0"] % PITCH)
        salt = sum(ord(char) for char in spec["name"])
        while z < spec["z1"] - 0.05:
            board_z0 = max(z, spec["z0"])
            board_z1 = min(z + BOARD_H, spec["z1"])
            if board_z1 - board_z0 >= 0.06:
                tone_key = int(round(z / PITCH))
                mixed = (tone_key * 374761393 + salt * 668265263) & 0xFFFFFF
                tone = mixed / 0xFFFFFF
                rings = []
                for fraction, proud in PROFILE:
                    height = board_z0 + (board_z1 - board_z0) * fraction
                    start = spec["origin"] + spec["along"] * spec["a0"] + Vector((0.0, 0.0, height)) + spec["outward"] * proud
                    end = spec["origin"] + spec["along"] * spec["a1"] + Vector((0.0, 0.0, height)) + spec["outward"] * proud
                    rings.append((start, end, fraction))
                for index in range(len(rings) - 1):
                    low = rings[index]
                    high = rings[index + 1]
                    add_face(
                        verts, faces, uvs, tones,
                        (low[0], low[1], high[1], high[0]),
                        ((0.0, low[2]), (1.0, low[2]), (1.0, high[2]), (0.0, high[2])),
                        tone, spec["outward"],
                    )
                cap_start = [ring[0] for ring in rings]
                cap_end = [ring[1] for ring in rings]
                add_face(
                    verts, faces, uvs, tones,
                    tuple(cap_start),
                    tuple((0.0, ring[2]) for ring in rings),
                    tone, -spec["along"],
                )
                add_face(
                    verts, faces, uvs, tones,
                    tuple(reversed(cap_end)),
                    tuple((1.0, ring[2]) for ring in reversed(rings)),
                    tone, spec["along"],
                )
            z += PITCH
    mesh = bpy.data.meshes.new("Zrubové drevo")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    if len(mesh.polygons) > 3000:
        fail(f"faces {len(mesh.polygons)}")
    mesh.calc_loop_triangles()
    if len(mesh.loop_triangles) > 6000:
        fail(f"triangles {len(mesh.loop_triangles)}")
    uv_layer = mesh.uv_layers.new(name="UVMap")
    tone_layer = mesh.color_attributes.new(name="tone", type="FLOAT_COLOR", domain="CORNER")
    for index, loop in enumerate(mesh.loops):
        uv_layer.data[index].uv = uvs[index]
        tone_layer.data[index].color = (tones[index], tones[index], tones[index], 1.0)
    return mesh, skipped


def make_log_material():
    material = bpy.data.materials.new(MAT_LOG)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    nodes = tree.nodes
    links = tree.links
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    separate = nodes.new("ShaderNodeSeparateXYZ")
    tone = nodes.new("ShaderNodeAttribute")
    tone.attribute_type = "GEOMETRY"
    tone.attribute_name = "tone"
    tone_split = nodes.new("ShaderNodeSeparateXYZ")
    tone_map = nodes.new("ShaderNodeMapRange")
    tone_map.data_type = "FLOAT"
    tone_map.clamp = True
    board = nodes.new("ShaderNodeValToRGB")
    board.color_ramp.elements[0].position = 0.0
    board.color_ramp.elements[0].color = (0.09, 0.038, 0.015, 1.0)
    board.color_ramp.elements[1].position = 1.0
    board.color_ramp.elements[1].color = (0.40, 0.20, 0.075, 1.0)
    middle = board.color_ramp.elements.new(0.5)
    middle.color = (0.24, 0.115, 0.045, 1.0)
    grain = nodes.new("ShaderNodeTexNoise")
    grain.noise_dimensions = "3D"
    grain.noise_type = "FBM"
    grain.inputs["Scale"].default_value = 18.0
    grain.inputs["Detail"].default_value = 5.0
    grain_gain = nodes.new("ShaderNodeMapRange")
    grain_gain.data_type = "FLOAT"
    grain_gain.inputs["To Min"].default_value = 0.86
    grain_gain.inputs["To Max"].default_value = 1.08
    grain_gain.clamp = True
    seam = nodes.new("ShaderNodeMath")
    seam.operation = "MULTIPLY"
    # Darken the upper and lower shoulders so the joint reads.
    low = nodes.new("ShaderNodeMapRange")
    low.data_type = "FLOAT"
    low.inputs["From Min"].default_value = 0.0
    low.inputs["From Max"].default_value = 0.18
    low.inputs["To Min"].default_value = 0.55
    low.inputs["To Max"].default_value = 1.0
    low.clamp = True
    high = nodes.new("ShaderNodeMapRange")
    high.data_type = "FLOAT"
    high.inputs["From Min"].default_value = 0.82
    high.inputs["From Max"].default_value = 1.0
    high.inputs["To Min"].default_value = 1.0
    high.inputs["To Max"].default_value = 0.62
    high.clamp = True
    tint = nodes.new("ShaderNodeVectorMath")
    tint.operation = "SCALE"
    shade = nodes.new("ShaderNodeVectorMath")
    shade.operation = "SCALE"
    grain_tint = nodes.new("ShaderNodeVectorMath")
    grain_tint.operation = "SCALE"
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.data_type = "FLOAT"
    roughness.inputs["To Min"].default_value = 0.52
    roughness.inputs["To Max"].default_value = 0.76
    roughness.clamp = True
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.002
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.28
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tone.outputs["Color"], tone_split.inputs["Vector"])
    links.new(tone_split.outputs["X"], tone_map.inputs["Value"])
    links.new(tone_map.outputs["Result"], board.inputs["Factor"])
    links.new(uv.outputs["UV"], separate.inputs["Vector"])
    links.new(separate.outputs["Y"], low.inputs["Value"])
    links.new(separate.outputs["Y"], high.inputs["Value"])
    links.new(low.outputs["Result"], seam.inputs[0])
    links.new(high.outputs["Result"], seam.inputs[1])
    links.new(board.outputs["Color"], tint.inputs[0])
    links.new(seam.outputs["Value"], tint.inputs["Scale"])
    links.new(uv.outputs["UV"], grain.inputs["Vector"])
    links.new(grain.outputs["Factor"], grain_gain.inputs["Value"])
    links.new(tint.outputs["Vector"], grain_tint.inputs[0])
    links.new(grain_gain.outputs["Result"], grain_tint.inputs["Scale"])
    links.new(grain_tint.outputs["Vector"], bsdf.inputs["Base Color"])
    links.new(grain.outputs["Factor"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(grain.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return material


def make_shadow_material():
    material = bpy.data.materials.new(MAT_SHADOW)
    material.use_nodes = True
    tree = material.node_tree
    principled = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    principled.inputs["Base Color"].default_value = (0.035, 0.016, 0.008, 1.0)
    principled.inputs["Roughness"].default_value = 0.82
    principled.inputs["Metallic"].default_value = 0.0
    return material


def main():
    scene_a, scene_b, panels, wall = validate()
    protected = [
        "Fasáda • termodrevo",
        MAT_BATTEN,
        MAT_BACKING,
        "Sklo • exteriér A",
        "Sklo • priehľadné",
        "Terasa • smrekovec",
        "Terasa • smrekovec • A",
        "Strecha • falcovaný plech",
        "Strecha • šindeľ • antracit",
        "Antracit",
    ]
    before = {name: node_signature(bpy.data.materials[name]) for name in protected}
    hide_wall_battens(scene_a, wall)
    mesh, skipped = build_logs(scene_a, panels)
    log_material = make_log_material()
    shadow = make_shadow_material()
    for panel in panels:
        panel.material_slots[0].material = shadow
    obj = bpy.data.objects.new("Zrubové drevo", mesh)
    collection = bpy.data.collections.new(COL_01B)
    scene_a.collection.children.link(collection)
    collection.objects.link(obj)
    obj.data.materials.append(log_material)
    if layer_collection(scene_b.view_layers[0].layer_collection, COL_01B) is not None:
        fail("01b leaked into scene B")
    for name in protected:
        if node_signature(bpy.data.materials[name]) != before[name]:
            fail(f"protected material {name}")
    if len(scene_b.objects) != 308:
        fail("scene B changed")
    if scene_users(MAT_BACKING, scene_a) != 2 or scene_users(MAT_LOG, scene_b) or scene_users(MAT_SHADOW, scene_b):
        fail("material users")
    if scene_users(MAT_BATTEN, scene_a) != 312:
        fail("gable or hidden batten material")
    summary = {
        "status": "applied",
        "hidden_wall_battens": len(bpy.data.collections[COL_01A].objects),
        "wall_battens_excluded": layer_collection(scene_a.view_layers[0].layer_collection, COL_01A).exclude,
        "log_faces": len(mesh.polygons),
        "log_triangles": len(mesh.loop_triangles),
        "skipped_panels": skipped,
        "shadow_panels": scene_users(MAT_SHADOW, scene_a),
        "log_material_users": scene_users(MAT_LOG, scene_a),
        "backing_scene_a": scene_users(MAT_BACKING, scene_a),
        "scene_a": len(scene_a.objects),
        "scene_b": len(scene_b.objects),
    }
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main()
