"""One-shot exterior material pass for Jelena scene A.

Refuses unless the open file is v003 or v004, scene and camera A match, scene B
still has 308 objects, camera A is within 0.0001 of the measured transform, the
new materials are absent, and collection ``06b • Terasa • scéna A`` is absent.
Selects façade targets by scene-A membership. Does not render or save.
"""

import json

import bpy

SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"
CAM_A = "A • Chata pri lese"
COL_06 = "06 • Terasa"
COL_06B = "06b • Terasa • scéna A"
COL_02 = "02 • Strecha a štíty"
MAT_FACADE = "Fasáda • termodrevo"
MAT_TERRACE = "Terasa • smrekovec"
MAT_GLASS = "Sklo • priehľadné"
MAT_ROOF = "Strecha • falcovaný plech"
MAT_BATTEN = "Fasáda • lata • A"
MAT_BACKING = "Fasáda • podklad • A"
MAT_GLASS_A = "Sklo • exteriér A"
MAT_TERRACE_A = "Terasa • smrekovec • A"
NEW_MATERIALS = (MAT_BATTEN, MAT_BACKING, MAT_GLASS_A, MAT_TERRACE_A)
GLASS_NAMES = (
    "Terrace_glazing.006",
    "Terrace_glazing.007",
    "Terrace_glazing.008",
    "Bedroom_window.004",
    "Kitchen_window.005",
    "Kitchen_window.006",
    "Living_window.005",
    "Living_window.006",
    "Bathroom_window.004",
)
CAM_LOC = (13.9, -16.4, 6.35)
CAM_ROT = (1.390952, 0.0, 0.477129)
SHORT_AXIS = 90.0
LONG_AXIS = 0.45
RANDOM_AMPLITUDE = 17.0
BUMP_DISTANCE = 0.002
BATTEN_BUMP = 0.12
BACKING_BUMP = 0.04
ROOF_NOISE_SCALE = 0.4


def fail(message):
    raise RuntimeError(message)


def in_scene(obj, scene):
    return obj.name in scene.objects


def slot_material(obj):
    if len(obj.material_slots) != 1 or obj.material_slots[0].material is None:
        fail(f"{obj.name} does not have exactly one material")
    return obj.material_slots[0].material


def uses(obj, material_name):
    return any(slot.material and slot.material.name == material_name for slot in obj.material_slots)


def assign(obj, material):
    slot_material(obj)
    obj.material_slots[0].material = material


def local_extents(mesh):
    xs = [vertex.co.x for vertex in mesh.vertices]
    ys = [vertex.co.y for vertex in mesh.vertices]
    zs = [vertex.co.z for vertex in mesh.vertices]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def grain_mul_for(obj):
    extents = local_extents(obj.data)
    long_index = max(range(3), key=lambda index: extents[index])
    scale = [SHORT_AXIS, SHORT_AXIS, SHORT_AXIS]
    scale[long_index] = LONG_AXIS
    return scale


def layer_collection(root, name):
    if root.collection.name == name:
        return root
    for child in root.children:
        found = layer_collection(child, name)
        if found is not None:
            return found
    return None


def node_signature(material):
    tree = material.node_tree
    return {
        "types": sorted(node.type for node in tree.nodes),
        "links": len(tree.links),
    }


def light_signature():
    return [
        (obj.name, round(float(obj.data.energy), 5))
        for obj in bpy.data.objects
        if obj.type == "LIGHT"
    ]


def world_signature():
    rows = []
    for world in bpy.data.worlds:
        strength = None
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                strength = round(float(node.inputs["Strength"].default_value), 5)
        rows.append((world.name, strength))
    return rows


def output_node(tree):
    node = next(node for node in tree.nodes if node.type == "OUTPUT_MATERIAL")
    return node


def principled(tree):
    return next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")


def new_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    return material


def add_grain_shader(material, dark, light):
    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "OBJECT"
    attr.attribute_name = "grain_mul"
    multiply = nodes.new("ShaderNodeVectorMath")
    multiply.operation = "MULTIPLY"
    info = nodes.new("ShaderNodeObjectInfo")
    scale = nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = RANDOM_AMPLITUDE
    combine = nodes.new("ShaderNodeCombineXYZ")
    add = nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "3D"
    noise.noise_type = "FBM"
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 3.4
    noise.inputs["Roughness"].default_value = 0.5
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.19
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].position = 0.79
    ramp.color_ramp.elements[1].color = light
    roughness = nodes.new("ShaderNodeMapRange")
    if hasattr(roughness, "data_type"):
        roughness.data_type = "FLOAT"
    roughness.inputs["From Min"].default_value = 0.0
    roughness.inputs["From Max"].default_value = 1.0
    roughness.inputs["To Min"].default_value = 0.42
    roughness.inputs["To Max"].default_value = 0.70
    if hasattr(roughness, "clamp"):
        roughness.clamp = True
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = BATTEN_BUMP
    bump.inputs["Distance"].default_value = BUMP_DISTANCE
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Metallic"].default_value = 0.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Object"], multiply.inputs[0])
    links.new(attr.outputs["Vector"], multiply.inputs[1])
    links.new(info.outputs["Random"], scale.inputs[0])
    links.new(scale.outputs["Value"], combine.inputs["X"])
    links.new(scale.outputs["Value"], combine.inputs["Y"])
    links.new(scale.outputs["Value"], combine.inputs["Z"])
    links.new(multiply.outputs["Vector"], add.inputs[0])
    links.new(combine.outputs["Vector"], add.inputs[1])
    links.new(add.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Factor"], ramp.inputs["Factor"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(noise.outputs["Factor"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(noise.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def add_backing_shader(material):
    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "3D"
    noise.noise_type = "FBM"
    noise.inputs["Scale"].default_value = 0.8
    noise.inputs["Detail"].default_value = 2.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = BACKING_BUMP
    bump.inputs["Distance"].default_value = BUMP_DISTANCE
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.09, 0.035, 0.015, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.72
    bsdf.inputs["Metallic"].default_value = 0.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Factor"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def add_glass_shader(material):
    tree = material.node_tree
    nodes = tree.nodes
    links = tree.links
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 0.90, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.04
    bsdf.inputs["IOR"].default_value = 1.5
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    bsdf.inputs["Coat Weight"].default_value = 0.0
    if "Thin Wall" in bsdf.inputs:
        bsdf.inputs["Thin Wall"].default_value = False
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def edit_roof(material):
    tree = material.node_tree
    bsdf = principled(tree)
    color = tuple(round(value, 3) for value in bsdf.inputs["Base Color"].default_value)
    if color != (0.033, 0.045, 0.046, 1.0):
        fail(f"roof base color changed before edit: {color}")
    if bsdf.inputs["Base Color"].is_linked or bsdf.inputs["Roughness"].is_linked:
        fail("roof principled already has linked color or roughness")
    bsdf.inputs["Metallic"].default_value = 0.72
    nodes = tree.nodes
    links = tree.links
    tex = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "3D"
    noise.noise_type = "FBM"
    noise.inputs["Scale"].default_value = ROOF_NOISE_SCALE
    noise.inputs["Detail"].default_value = 2.0
    mapped = nodes.new("ShaderNodeMapRange")
    if hasattr(mapped, "data_type"):
        mapped.data_type = "FLOAT"
    mapped.inputs["From Min"].default_value = 0.0
    mapped.inputs["From Max"].default_value = 1.0
    mapped.inputs["To Min"].default_value = 0.32
    mapped.inputs["To Max"].default_value = 0.48
    if hasattr(mapped, "clamp"):
        mapped.clamp = True
    links.new(tex.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Factor"], mapped.inputs["Value"])
    links.new(mapped.outputs["Result"], bsdf.inputs["Roughness"])


def scene_users(material, scene):
    return sum(1 for obj in scene.objects if uses(obj, material.name))


def validate():
    path = bpy.data.filepath
    if not (path.endswith("Jelena_Realistic_v003.blend") or path.endswith("Jelena_Realistic_v004.blend")):
        fail(f"unexpected file: {path}")
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
            fail(f"camera location {tuple(camera.location)}")
    for actual, expected in zip(camera.rotation_euler, CAM_ROT):
        if abs(actual - expected) > 0.0001:
            fail(f"camera rotation {tuple(camera.rotation_euler)}")
    for name in NEW_MATERIALS:
        if name in bpy.data.materials:
            fail(f"material already exists: {name}")
    if COL_06B in bpy.data.collections:
        fail("06b already exists")
    if len(bpy.data.collections[COL_06].objects) != 51:
        fail("collection 06 is not 51 objects")
    battens = [
        obj
        for obj in scene_a.objects
        if obj.type == "MESH" and obj.name.startswith("Fasádna lata") and uses(obj, MAT_FACADE)
    ]
    if len(battens) != 312 or any(in_scene(obj, scene_b) for obj in battens):
        fail(f"scene-A batten count {len(battens)}")
    backing = [
        obj
        for obj in scene_a.objects
        if obj.type == "MESH" and uses(obj, MAT_FACADE) and not obj.name.startswith("Fasádna lata")
    ]
    if len(backing) != 23 or any(in_scene(obj, scene_b) for obj in backing):
        fail(f"scene-A backing count {len(backing)}")
    glass = []
    for name in GLASS_NAMES:
        obj = bpy.data.objects.get(name)
        if obj is None or not in_scene(obj, scene_a) or in_scene(obj, scene_b) or not uses(obj, MAT_GLASS):
            fail(f"exterior glass missing or shared: {name}")
        glass.append(obj)
    shower = bpy.data.objects["Sprchová zástena"]
    if not uses(shower, MAT_GLASS) or not in_scene(shower, scene_b):
        fail("shower glass is not on the original shared material")
    roof_objects = [obj for obj in bpy.data.objects if uses(obj, MAT_ROOF)]
    if len(roof_objects) != 45 or any(in_scene(obj, scene_b) for obj in roof_objects):
        fail(f"roof users {len(roof_objects)}")
    if any(COL_02 not in [col.name for col in obj.users_collection] for obj in roof_objects):
        fail("a roof user is outside collection 02")
    terrace = list(bpy.data.collections[COL_06].objects)
    if any(len(obj.users_collection) != 1 for obj in terrace):
        fail("a terrace object is in more than one collection")
    if any(not (in_scene(obj, scene_a) and in_scene(obj, scene_b)) for obj in terrace):
        fail("a terrace object is not in both scenes")
    terrace_wood = [obj for obj in terrace if uses(obj, MAT_TERRACE)]
    if len(terrace_wood) != 25:
        fail(f"terrace wood count {len(terrace_wood)}")
    return scene_a, scene_b, battens, backing, glass, terrace, terrace_wood


def main():
    scene_a, scene_b, battens, backing, glass, terrace, terrace_wood = validate()
    protected = [
        bpy.data.materials[name]
        for name in (MAT_FACADE, MAT_TERRACE, MAT_GLASS, "Antracit", "Interiér • prírodný dub")
    ]
    before = {material.name: node_signature(material) for material in protected}
    lights_before = light_signature()
    worlds_before = world_signature()
    camera_before = (
        tuple(round(value, 6) for value in scene_a.camera.location),
        tuple(round(value, 6) for value in scene_a.camera.rotation_euler),
        scene_a.camera.data.lens,
    )
    original_names = [obj.name for obj in terrace]
    original_materials = {obj.name: slot_material(obj).name for obj in terrace}
    vegetation = len(bpy.data.collections["10 • Vegetácia scéna A"].objects)

    batten_mat = new_material(MAT_BATTEN)
    add_grain_shader(
        batten_mat,
        (0.115, 0.043, 0.018, 1.0),
        (0.37, 0.177, 0.074, 1.0),
    )
    backing_mat = new_material(MAT_BACKING)
    add_backing_shader(backing_mat)
    glass_mat = new_material(MAT_GLASS_A)
    add_glass_shader(glass_mat)
    terrace_mat = new_material(MAT_TERRACE_A)
    add_grain_shader(
        terrace_mat,
        (0.19, 0.088, 0.036, 1.0),
        (0.46, 0.247, 0.106, 1.0),
    )

    axis_counts = [0, 0, 0]
    for obj in battens:
        scale = grain_mul_for(obj)
        obj["grain_mul"] = scale
        axis_counts[scale.index(LONG_AXIS)] += 1
        assign(obj, batten_mat)
    for obj in backing:
        assign(obj, backing_mat)
    for obj in glass:
        assign(obj, glass_mat)

    new_col = bpy.data.collections.new(COL_06B)
    scene_a.collection.children.link(new_col)
    if any(child.name == COL_06B for child in scene_b.collection.children):
        fail("06b was linked to scene B")
    wood_ids = {obj.name for obj in terrace_wood}
    duplicates = []
    for src in terrace:
        dup = src.copy()
        dup.data = src.data.copy()
        new_col.objects.link(dup)
        duplicates.append((src, dup))
        if src.name in wood_ids:
            scale = grain_mul_for(dup)
            dup["grain_mul"] = scale
            assign(dup, terrace_mat)

    layer_a = layer_collection(scene_a.view_layers[0].layer_collection, COL_06)
    layer_b = layer_collection(scene_b.view_layers[0].layer_collection, COL_06)
    if layer_a is None or layer_b is None:
        fail("could not find collection 06 in a view layer")
    layer_a.exclude = True
    if layer_b.exclude:
        fail("scene B collection 06 is excluded")
    if layer_collection(scene_b.view_layers[0].layer_collection, COL_06B) is not None:
        fail("06b is visible to scene B")

    edit_roof(bpy.data.materials[MAT_ROOF])

    if [obj.name for obj in bpy.data.collections[COL_06].objects] != original_names:
        fail("an original terrace object was renamed")
    for obj in bpy.data.collections[COL_06].objects:
        if slot_material(obj).name != original_materials[obj.name]:
            fail(f"original terrace material changed: {obj.name}")
        if obj.hide_render:
            fail(f"hide_render set on {obj.name}")
    leaked = [dup.name for _src, dup in duplicates if in_scene(dup, scene_b)]
    if leaked:
        fail(f"duplicates leaked into scene B: {leaked[:5]}")
    if len(new_col.objects) != 51:
        fail(f"06b count {len(new_col.objects)}")
    if any(len(obj.users_collection) != 1 or obj.users_collection[0].name != COL_06B for obj in new_col.objects):
        fail("a duplicate is not exclusively in 06b")
    if len(scene_b.objects) != 308:
        fail(f"scene B count after duplication {len(scene_b.objects)}")
    if scene_users(batten_mat, scene_b) or scene_users(backing_mat, scene_b) or scene_users(terrace_mat, scene_b) or scene_users(glass_mat, scene_b):
        fail("a new material has a scene-B user")
    facade = bpy.data.materials[MAT_FACADE]
    if scene_users(facade, scene_a) != 0 or scene_users(facade, scene_b) != 156:
        fail(f"facade users A {scene_users(facade, scene_a)} B {scene_users(facade, scene_b)}")
    if scene_users(batten_mat, scene_a) != 312 or scene_users(backing_mat, scene_a) != 23:
        fail("new facade user counts")
    if scene_users(glass_mat, scene_a) != 9 or slot_material(bpy.data.objects["Sprchová zástena"]).name != MAT_GLASS:
        fail("glass assignment")
    if scene_users(terrace_mat, scene_a) != 25 or scene_users(bpy.data.materials[MAT_TERRACE], scene_b) != 25:
        fail("terrace assignment")
    roof = bpy.data.materials[MAT_ROOF]
    if scene_users(roof, scene_a) != 45 or scene_users(roof, scene_b) != 0:
        fail("roof users after edit")
    if slot_material(bpy.data.objects["Slab_027"]).name != "Kameň":
        fail("slab material changed")
    if {material.name: node_signature(material) for material in protected} != before:
        fail("a protected material node tree changed")
    if light_signature() != lights_before or world_signature() != worlds_before:
        fail("lights or worlds changed")
    camera_after = (
        tuple(round(value, 6) for value in scene_a.camera.location),
        tuple(round(value, 6) for value in scene_a.camera.rotation_euler),
        scene_a.camera.data.lens,
    )
    if camera_after != camera_before:
        fail("camera A changed")
    if len(bpy.data.collections["10 • Vegetácia scéna A"].objects) != vegetation:
        fail("vegetation count changed")
    if len(bpy.data.images) != 1 or bpy.data.images[0].name != "Render Result":
        fail("an image datablock was created")
    if bpy.data.libraries:
        fail("a library link was created")
    summary = {
        "status": "applied",
        "battens": 312,
        "backing": 23,
        "glass": 9,
        "terrace_wood_duplicates": 25,
        "duplicates": 51,
        "batten_axes_xyz": axis_counts,
        "scene_a_objects": len(scene_a.objects),
        "scene_b_objects": len(scene_b.objects),
        "scene_a_excludes_06": layer_a.exclude,
        "scene_b_includes_06": not layer_b.exclude,
        "roof_metallic": principled(roof.node_tree).inputs["Metallic"].default_value,
    }
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main()
