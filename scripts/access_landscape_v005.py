"""Scene-A access landscape for Jelena_Realistic_v005.

Builds the road, gravel pull-off and two paved paths. Hides exactly three
vegetation objects by collection exclusion. Does not render or save.
"""

import json

import bpy
import numpy as np
from mathutils import Vector

SCENE_A = "A • Chata pri lese"
SCENE_B = "B • Zariadená dispozícia"
CAM_A = "A • Chata pri lese"
HIDE = ("Smrek • stredný.021", "Smrek • vysoký.015", "Ker.003")
COL_HIDE = "05c • Vegetácia • odstránená pre prístup"
COL_STONES = "05b • Nášľap • ponechané"
COL_ACCESS = "11 • Prístup • A"
COL_HELP = "11a • Pomocné • A"
COL_PLANTS = "10a • Vegetácia • mimo prístup"
COL_CAM = "07d • Kamera prístup • A"
PATH_B = ((6.20, -2.63), (6.20, -5.70), (6.75, -6.60), (6.40, -8.20), (5.40, -9.20))
ROAD = ((-6.3, -10.0), (-3.0, -13.1), (1.0, -13.3), (15.0, -13.3), (17.0, -10.5))
STONES_A = (
    (8.65, 1.22), (9.04, 0.985), (9.43, 0.75), (9.82, 0.515),
    (10.21, 0.28), (10.6, 0.045), (10.99, -0.19), (11.38, -0.425),
    (11.77, -0.66), (12.16, -0.895), (12.55, -1.13),
)
ROCK_MIN = (5.128, -6.855)
ROCK_MAX = (5.731, -6.226)


def fail(message):
    raise RuntimeError(message)


def sock(node, *names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
        if name in node.outputs:
            return node.outputs[name]
    raise KeyError((node.bl_idname, names, [s.name for s in node.inputs], [s.name for s in node.outputs]))


class Poly:
    def __init__(self, points):
        self.pts = [np.array(p, dtype=np.float64) for p in points]
        self.seg = []
        self.cum = [0.0]
        for a, b in zip(self.pts[:-1], self.pts[1:]):
            length = float(np.linalg.norm(b - a))
            if length <= 0:
                fail("degenerate polyline")
            self.seg.append((a, b, length))
            self.cum.append(self.cum[-1] + length)
        self.length = self.cum[-1]

    def frame(self, distance):
        distance = min(max(float(distance), 0.0), self.length)
        for index, (start, end, length) in enumerate(self.seg):
            if distance <= self.cum[index + 1] or index == len(self.seg) - 1:
                along = distance - self.cum[index]
                tangent = (end - start) / length
                normal = np.array((-tangent[1], tangent[0]))
                return start + tangent * along, tangent, normal
        fail("frame")

    def point(self, distance, offset):
        origin, _tangent, normal = self.frame(distance)
        return origin + normal * offset

    def distance(self, points):
        points = np.asarray(points, dtype=np.float64)
        if points.ndim == 1:
            points = points.reshape(1, 2)
        best = np.full(len(points), 1e9)
        for start, end, _length in self.seg:
            edge = end - start
            scale = float(np.dot(edge, edge))
            t = np.clip(((points - start) @ edge) / scale, 0.0, 1.0)
            best = np.minimum(best, np.linalg.norm(points - (start + t[:, None] * edge), axis=1))
        return best


def terrain_z(terrain, x, y):
    origin = terrain.matrix_world.inverted() @ Vector((float(x), float(y), 40.0))
    direction = (terrain.matrix_world.inverted().to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    hit, loc, _normal, _index = terrain.ray_cast(origin, direction)
    if not hit:
        return None
    return float((terrain.matrix_world @ loc).z)


def layer_collection(view_layer, name):
    def walk(layer):
        if layer.collection.name == name:
            return layer
        for child in layer.children:
            found = walk(child)
            if found is not None:
                return found
        return None

    view_layer.update()
    return walk(view_layer.layer_collection)


def link_scene_a(name):
    collection = bpy.data.collections.new(name)
    bpy.data.scenes[SCENE_A].collection.children.link(collection)
    if layer_collection(bpy.data.scenes[SCENE_B].view_layers[0], name) is not None:
        fail(f"{name} leaked into scene B")
    return collection


def relink(obj, collection):
    matrix = obj.matrix_world.copy()
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    obj.matrix_world = matrix


def hash01(index):
    return ((index * 1103515245 + 12345) & 0x7FFFFFFF) % 10000 / 10000.0


def new_mesh(name, verts, faces, float_attr=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    if float_attr is not None:
        attribute = mesh.attributes.new(float_attr[0], "FLOAT", "POINT")
        attribute.data.foreach_set("value", float_attr[1])
    return mesh


def paver_block(poly, half, courses, reveal_at, vary_z=True):
    step = 0.10
    first = -half + step * 0.5
    offsets = [first + step * i for i in range(courses)]
    verts = []
    faces = []
    values = []
    count = 0
    row = 0
    distance = 0.099
    while distance < poly.length - 0.05:
        stagger = 0.10 if row % 2 else 0.0
        for offset in offsets:
            corners = []
            for ds, dn in ((-0.099, -0.049), (0.099, -0.049), (0.099, 0.049), (-0.099, 0.049)):
                along = min(max(distance + stagger + ds, 0.0), poly.length)
                side = min(max(offset + dn, -half + 0.001), half - 0.001)
                corners.append((along, side))
            world = []
            tops = []
            for along, side in corners:
                xy = poly.point(along, side)
                ground = terrain_z(bpy.data.objects["Lesná čistina"], xy[0], xy[1])
                if ground is None:
                    fail(f"terrain miss {xy}")
                jitter = 0.0
                if vary_z and 0.25 < along < poly.length - 0.70:
                    jitter = (hash01(count + 17) - 0.5) * 0.002
                tops.append(ground + reveal_at(along, poly.length) + jitter)
                world.append(xy)
            top = sum(tops) / 4.0
            center = sum(world) / 4.0
            top_xy = []
            for xy in world:
                inward = center - xy
                norm = float(np.linalg.norm(inward))
                if norm > 1e-8:
                    xy = xy + inward / norm * 0.0015
                top_xy.append(xy)
            base = len(verts)
            shade = hash01(count)
            for xy, _z in zip(world, tops):
                verts.append((float(xy[0]), float(xy[1]), top - 0.060))
                values.append(shade)
            for xy in top_xy:
                verts.append((float(xy[0]), float(xy[1]), top))
                values.append(shade)
            faces.append((base, base + 1, base + 2, base + 3))
            faces.append((base + 4, base + 7, base + 6, base + 5))
            for i in range(4):
                j = (i + 1) % 4
                faces.append((base + i, base + j, base + 4 + j, base + 4 + i))
            count += 1
        row += 1
        distance += 0.20
    return verts, faces, values, count


def bed_strip(poly, half, reveal_at):
    samples = max(2, int(poly.length / 0.20) + 1)
    stations = [poly.length * i / (samples - 1) for i in range(samples)]
    stations = [-0.006] + stations + [poly.length + 0.006]
    rows = []
    for distance in stations:
        clamped = min(max(distance, 0.0), poly.length)
        ground_points = []
        for side in (-(half + 0.004), -(half - 0.001), half - 0.001, half + 0.004):
            xy = poly.point(clamped, side if abs(distance - clamped) < 1e-6 else side)
            if distance < 0 or distance > poly.length:
                origin, tangent, normal = poly.frame(clamped)
                xy = origin + tangent * (distance - clamped) + normal * side
            ground = terrain_z(bpy.data.objects["Lesná čistina"], xy[0], xy[1])
            if ground is None:
                ground = terrain_z(bpy.data.objects["Lesná čistina"], poly.point(clamped, 0)[0], poly.point(clamped, 0)[1])
            top = (ground if ground is not None else -0.4) + reveal_at(clamped, poly.length)
            ground_points.append((float(xy[0]), float(xy[1]), top))
        rows.append(ground_points)
    verts = []
    faces = []
    for row in rows:
        # Outer border is flush. The inner bed sits 1 mm lower so joints read.
        verts.append(row[0])
        verts.append((row[1][0], row[1][1], row[1][2] - 0.001))
        verts.append((row[2][0], row[2][1], row[2][2] - 0.001))
        verts.append(row[3])
    width = 4
    for row_index in range(len(rows) - 1):
        for column in range(3):
            a = row_index * width + column
            b = a + width
            faces.append((a, b, b + 1, a + 1))
    return verts, faces


def reveal_b(distance, length):
    if distance >= length - 0.60:
        t = (distance - (length - 0.60)) / 0.60
        t = t * t * (3.0 - 2.0 * t)
        return 0.070 * (1.0 - t) + 0.012 * t
    return 0.070


def reveal_a(_distance, _length):
    return 0.070


def road_half(distance, straight0, straight1, length):
    if distance <= straight0:
        t = 0.0 if straight0 == 0 else distance / straight0
        return 0.50 + t * 1.00
    if distance >= straight1:
        span = max(length - straight1, 1e-6)
        t = (distance - straight1) / span
        return 1.50 - t * 1.00
    return 1.50


def crust(distance, offset, half, length, x, straight0, straight1):
    if offset > 0 and (half - offset) < 0.30 and straight0 <= distance <= straight1 and 3.2 <= x <= 13.0:
        lateral = 1.0
    else:
        lateral = min(1.0, max(0.0, (half - abs(offset)) / 0.25))
    longitudinal = min(1.0, distance / 3.0, (length - distance) / 3.0)
    return 0.012 * min(lateral, longitudinal)


def wear_road(distance, offset, length):
    track = min(abs(offset - 0.75), abs(offset + 0.75))
    if track > 0.14:
        return 0.0
    fade = min(1.0, distance / 3.0, (length - distance) / 3.0)
    return 0.35 * fade


def dist_point_aabb(point, bmin, bmax):
    delta = 0.0
    for axis in range(2):
        if point[axis] < bmin[axis]:
            delta += (bmin[axis] - point[axis]) ** 2
        elif point[axis] > bmax[axis]:
            delta += (point[axis] - bmax[axis]) ** 2
    return delta ** 0.5


def path_a_points():
    direction = np.array((3.9, -2.35), dtype=np.float64)
    direction /= np.linalg.norm(direction)
    left = np.array((-direction[1], direction[0]))
    shift = -0.15 * left
    points = []
    for index, point in enumerate(STONES_A):
        xy = np.array(point, dtype=np.float64)
        if 6 <= index <= 9:
            xy = xy + shift
        points.append((float(xy[0]), float(xy[1])))
    return points, shift


def assert_path_a_clear(poly):
    """Fail on a fourth visible obstacle. Stones, steps, cabin contact, ground and the three hides are not fourth objects."""
    half = 0.45
    pad = half + 0.10
    xs = [p[0] for p in poly.pts]
    ys = [p[1] for p in poly.pts]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    terrain = bpy.data.objects["Lesná čistina"]
    surface = []
    for point in poly.pts:
        ground = terrain_z(terrain, point[0], point[1])
        surface.append((ground if ground is not None else -0.4) + 0.07)
    surface = np.array(surface)
    allowed_prefix = ("Nášľap", "Vstupný schod", "Exterior_", "Schod", "Terasová")
    allowed_names = {"Zrubové drevo", "Lesná čistina", "Tráva • čistina", "Pôda • pokryv"}
    cache = {}
    scene = bpy.data.scenes[SCENE_A]
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name in HIDE:
            continue
        if obj.name in allowed_names or obj.name.startswith(allowed_prefix):
            continue
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        if max(p.x for p in corners) < x0 or min(p.x for p in corners) > x1:
            continue
        if max(p.y for p in corners) < y0 or min(p.y for p in corners) > y1:
            continue
        if max(p.z for p in corners) < -0.8 or min(p.z for p in corners) > 0.8:
            continue
        if len(obj.data.vertices) == 0:
            continue
        key = obj.data.name
        if key not in cache:
            coords = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
            obj.data.vertices.foreach_get("co", coords)
            cache[key] = coords.reshape(-1, 3)
        coords = cache[key]
        matrix = np.array(obj.matrix_world, dtype=np.float64)
        world = np.concatenate([coords, np.ones((len(coords), 1))], 1) @ matrix.T
        xy = world[:, :2]
        zz = world[:, 2]
        box = (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)
        if not np.any(box):
            continue
        chosen = np.nonzero(box)[0]
        dist = poly.distance(xy[chosen])
        nearest = np.argmin(np.linalg.norm(xy[chosen][:, None, :] - np.array(poly.pts)[None, :, :], axis=2), axis=1)
        band = (zz[chosen] >= surface[nearest]) & (zz[chosen] <= surface[nearest] + 0.30)
        if not np.any(band):
            continue
        edge = dist[band] - half
        if int(np.sum(dist[band] < half)) or float(edge.min()) < 0.10:
            order = int(np.argmin(edge))
            vertex = int(chosen[np.nonzero(band)[0][order]])
            point = world[vertex]
            fail(
                f"path A blocked by {obj.name} vertex {vertex} "
                f"at ({point[0]:.4f}, {point[1]:.4f}, {point[2]:.4f}) edge {float(edge.min()):.4f}"
            )


def validate():
    if not bpy.data.filepath.endswith("Jelena_Realistic_v005.blend"):
        fail(bpy.data.filepath)
    scene = bpy.context.scene
    if scene.name != SCENE_A or scene.camera is None or scene.camera.name != CAM_A:
        fail("scene or camera")
    if len(bpy.data.scenes[SCENE_B].objects) != 308:
        fail("scene B count")
    camera = scene.camera
    for actual, expected in zip(camera.location, (13.9, -16.4, 6.35)):
        if abs(actual - expected) > 0.0001:
            fail("camera location")
    for actual, expected in zip(camera.rotation_euler, (1.390952, 0.0, 0.477129)):
        if abs(actual - expected) > 0.0001:
            fail("camera rotation")
    if abs(camera.data.lens - 46.0) > 0.0001:
        fail("camera lens")
    for name in (COL_HIDE, COL_STONES, COL_ACCESS, COL_HELP, COL_PLANTS, COL_CAM):
        if name in bpy.data.collections:
            fail(f"collection exists {name}")


def snapshot_trees():
    found = {}
    for obj in bpy.data.objects:
        if obj.name.startswith("Smrek") or obj.name.startswith("Ker"):
            found[obj.name] = (
                tuple(round(v, 6) for v in obj.location),
                tuple(round(v, 6) for v in obj.rotation_euler),
                tuple(round(v, 6) for v in obj.scale),
            )
    return found


def same_transform(before, obj):
    loc, rot, scale = before
    for actual, expected in zip(obj.location, loc):
        if abs(actual - expected) > 0.0001:
            return False
    for actual, expected in zip(obj.rotation_euler, rot):
        if abs(actual - expected) > 0.0001:
            return False
    for actual, expected in zip(obj.scale, scale):
        if abs(actual - expected) > 0.0001:
            return False
    return True


def make_material_paver():
    mat = bpy.data.materials.new("Dlažba • betón")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    attr = tree.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "paver_var"
    attr.attribute_type = "GEOMETRY"
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.18, 0.18, 0.17, 1)
    ramp.color_ramp.elements[1].color = (0.32, 0.32, 0.30, 1)
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 35.0
    noise.inputs["Detail"].default_value = 3.0
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["From Min"].default_value = 0.0
    rough.inputs["From Max"].default_value = 1.0
    rough.inputs["To Min"].default_value = 0.78
    rough.inputs["To Max"].default_value = 0.90
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.002
    tree.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(noise.outputs["Fac"], rough.inputs["Value"])
    tree.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_material_edge():
    mat = bpy.data.materials.new("Obruba • betón")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.12, 0.12, 0.11, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_material_gravel():
    mat = bpy.data.materials.new("Štrk • prístup")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    coord = tree.nodes.new("ShaderNodeTexCoord")
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 4.0
    voro = tree.nodes.new("ShaderNodeTexVoronoi")
    voro.inputs["Scale"].default_value = 18.0
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.22, 0.20, 0.16, 1)
    mix.inputs["B"].default_value = (0.38, 0.35, 0.28, 1)
    dark = tree.nodes.new("ShaderNodeMix")
    dark.data_type = "RGBA"
    dark.inputs["B"].default_value = (0.14, 0.13, 0.11, 1)
    wear = tree.nodes.new("ShaderNodeAttribute")
    wear.attribute_name = "wear"
    wear.attribute_type = "GEOMETRY"
    rough = tree.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.82
    rough.inputs["To Max"].default_value = 0.62
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    bump.inputs["Distance"].default_value = 0.012
    tree.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    tree.links.new(coord.outputs["Object"], voro.inputs["Vector"])
    tree.links.new(voro.outputs["Distance"], mix.inputs["Factor"])
    tree.links.new(mix.outputs["Result"], dark.inputs["A"])
    tree.links.new(wear.outputs["Fac"], dark.inputs["Factor"])
    tree.links.new(dark.outputs["Result"], bsdf.inputs["Base Color"])
    tree.links.new(wear.outputs["Fac"], rough.inputs["Value"])
    tree.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mask_geometry(paths, road, straight0, straight1):
    verts = []
    faces = []

    def add_ribbon(poly, half_at):
        count = max(2, int(poly.length / 0.30) + 1)
        rows = []
        for index in range(count):
            distance = poly.length * index / (count - 1)
            half = half_at(distance) + 0.12
            left = poly.point(distance, half)
            right = poly.point(distance, -half)
            rows.append((right, left))
        base = len(verts)
        for right, left in rows:
            verts.append((float(right[0]), float(right[1]), 10.0))
            verts.append((float(left[0]), float(left[1]), 10.0))
        for index in range(count - 1):
            a = base + index * 2
            faces.append((a, a + 2, a + 3, a + 1))

    for poly, half in paths:
        add_ribbon(poly, lambda _d, h=half: h)
    add_ribbon(road, lambda d: road_half(d, straight0, straight1, road.length))
    # Parking, expanded 0.12 m.
    outline = [(3.08, -11.92), (5.48, -11.92), (5.48, -9.08), (10.72, -9.08), (10.72, -11.92), (13.12, -11.92), (13.12, -11.68), (3.08, -11.68)]
    base = len(verts)
    for x, y in outline:
        verts.append((x, y, 10.0))
    # Fan from the first vertex is not reliable for a concave taper. Use a triangle strip of the bbox plus the taper quads.
    verts[:] = verts[:base]
    quads = [
        (3.08, -11.92, 5.60, -9.08),
        (5.48, -11.92, 10.72, -9.08),
        (10.60, -11.92, 13.12, -9.08),
    ]
    for x0, y0, x1, y1 in quads:
        i = len(verts)
        verts.extend(((x0, y0, 10.0), (x1, y0, 10.0), (x1, y1, 10.0), (x0, y1, 10.0)))
        faces.append((i, i + 1, i + 2, i + 3))
    faces.extend(tuple(reversed(face)) for face in list(faces))
    return verts, faces


def install_mask(mask_obj):
    cover = bpy.data.objects["Pôda • pokryv"]
    group = cover.modifiers["Pokryv lesa"].node_group
    distribute = next(node for node in group.nodes if node.type == "DISTRIBUTE_POINTS_ON_FACES")
    selection = distribute.inputs["Selection"]
    if not selection.is_linked:
        fail("grass selection")
    previous = selection.links[0].from_socket
    group.links.remove(selection.links[0])
    info = group.nodes.new("GeometryNodeObjectInfo")
    info.transform_space = "RELATIVE"
    info.inputs["Object"].default_value = mask_obj
    ray = group.nodes.new("GeometryNodeRaycast")
    ray.inputs["Ray Direction"].default_value = (0.0, 0.0, 1.0)
    ray.inputs["Ray Length"].default_value = 30.0
    position = group.nodes.new("GeometryNodeInputPosition")
    absent = group.nodes.new("FunctionNodeBooleanMath")
    absent.operation = "NOT"
    both = group.nodes.new("FunctionNodeBooleanMath")
    both.operation = "AND"
    group.links.new(info.outputs["Geometry"], ray.inputs["Target Geometry"])
    group.links.new(position.outputs["Position"], ray.inputs["Source Position"])
    def boolean_out(node):
        for socket in node.outputs:
            if socket.type == "BOOLEAN":
                return socket
        return node.outputs[0]

    group.links.new(ray.outputs["Is Hit"], absent.inputs[0])
    group.links.new(previous, both.inputs[0])
    group.links.new(boolean_out(absent), both.inputs[1])
    group.links.new(boolean_out(both), selection)


def move_plants(paths, road, straight0, straight1):
    moved = []
    scene = bpy.data.scenes[SCENE_A]
    collection = bpy.data.collections[COL_PLANTS]
    for obj in list(scene.objects):
        if obj.type != "MESH" or obj.name.startswith("Smrek") or obj.name in HIDE:
            continue
        if "10 • Vegetácia scéna A" not in [c.name for c in obj.users_collection]:
            continue
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        bmin = (min(p.x for p in corners), min(p.y for p in corners))
        bmax = (max(p.x for p in corners), max(p.y for p in corners))
        hit = False
        for poly, half in paths:
            for index in range(24):
                origin = poly.point(poly.length * index / 23.0, 0.0)
                if dist_point_aabb(origin, bmin, bmax) <= half + 0.12:
                    hit = True
                    break
        for index in range(40):
            distance = road.length * index / 39.0
            origin = road.point(distance, 0.0)
            half = road_half(distance, straight0, straight1, road.length)
            if dist_point_aabb(origin, bmin, bmax) <= half + 0.12:
                hit = True
        if  bmin[0] <= 13.2 and bmax[0] >= 3.0 and bmin[1] <= -9.0 and bmax[1] >= -12.0:
            # Broad parking/taper test refined by corner distance.
            for corner in corners:
                if 3.0 <= corner.x <= 13.2 and -12.0 <= corner.y <= -9.0:
                    hit = True
        if hit:
            relink(obj, collection)
            moved.append(obj.name)
    return moved


def trunk_clearance(road, path_b, straight0, straight1):
    worst = []
    for obj in bpy.data.objects:
        if not obj.name.startswith("Smrek") or obj.name in HIDE:
            continue
        point = np.array((obj.location.x, obj.location.y))
        road_dist = float(road.distance(point)[0])
        samples = []
        for index in range(80):
            distance = road.length * index / 79.0
            samples.append((road.point(distance, 0.0), road_half(distance, straight0, straight1, road.length)))
        edge_r = min(float(np.linalg.norm(point - origin) - half) for origin, half in samples)
        edge_b = float(path_b.distance(point)[0]) - 0.60
        dx = max(3.2 - point[0], point[0] - 13.0, 0.0)
        dy = max(-11.8 - point[1], point[1] + 9.2, 0.0)
        edge_p = (dx * dx + dy * dy) ** 0.5
        if min(edge_r, edge_b, edge_p) < 0.70:
            worst.append((obj.name, round(edge_r, 3), round(edge_b, 3), round(edge_p, 3)))
    if worst:
        fail(f"trunk clearance {worst[:6]}")


def build():
    validate()
    points_a, shift = path_a_points()
    path_a = Poly(points_a)
    path_b = Poly(PATH_B)
    road = Poly(ROAD)
    straight0 = road.cum[2]
    straight1 = road.cum[3]
    assert_path_a_clear(path_a)
    rock = path_b.distance(np.array([
        [ROCK_MIN[0], ROCK_MIN[1]], [ROCK_MAX[0], ROCK_MIN[1]],
        [ROCK_MIN[0], ROCK_MAX[1]], [ROCK_MAX[0], ROCK_MAX[1]],
    ]))
    if float(rock.min()) < 0.35:
        fail(f"rock clearance {float(rock.min()):.3f}")
    trunk_clearance(road, path_b, straight0, straight1)

    trees_before = snapshot_trees()
    hidden_before = {}
    for name in HIDE:
        obj = bpy.data.objects[name]
        hidden_before[name] = {
            "collection": [c.name for c in obj.users_collection],
            "location": [round(v, 6) for v in obj.location],
            "rotation": [round(v, 6) for v in obj.rotation_euler],
            "scale": [round(v, 6) for v in obj.scale],
            "mesh": obj.data.name,
        }
    stone_before = {
        obj.name: [round(v, 6) for v in obj.location]
        for obj in bpy.data.objects if obj.name.startswith("Nášľap")
    }
    kamen = bpy.data.materials["Kameň"]
    kamen_nodes = len(kamen.node_tree.nodes)
    kamen_links = len(kamen.node_tree.links)
    scene_b_names = {obj.name for obj in bpy.data.scenes[SCENE_B].objects}

    col_hide = link_scene_a(COL_HIDE)
    col_stones = link_scene_a(COL_STONES)
    col_access = link_scene_a(COL_ACCESS)
    col_help = link_scene_a(COL_HELP)
    col_plants = link_scene_a(COL_PLANTS)
    col_cam = link_scene_a(COL_CAM)
    for collection in (col_hide, col_stones, col_plants):
        layer = layer_collection(bpy.context.view_layer, collection.name)
        if layer is None:
            fail(f"missing layer {collection.name}")
        layer.exclude = True

    for name in HIDE:
        relink(bpy.data.objects[name], col_hide)
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Nášľap"):
            relink(obj, col_stones)

    ground0 = terrain_z(bpy.data.objects["Lesná čistina"], 6.20, -2.63)
    terrace_delta = -0.295 - ((ground0 or -0.365) + 0.070)

    def reveal_terrace(distance, length):
        base = reveal_b(distance, length)
        if distance < 0.50:
            return base + terrace_delta * (1.0 - distance / 0.50)
        return base

    paver_mat = make_material_paver()
    edge_mat = make_material_edge()
    gravel_mat = make_material_gravel()

    def add_path(name, poly, half, courses, reveal):
        verts, faces, values, count = paver_block(poly, half, courses, reveal)
        mesh = new_mesh("Dlažba • kus" if "terasa" in name else "Dlažba • vstup", verts, faces, ("paver_var", values))
        obj = bpy.data.objects.new(name, mesh)
        col_access.objects.link(obj)
        obj.data.materials.append(paver_mat)
        bed_v, bed_f = bed_strip(poly, half, reveal)
        return obj, count, bed_v, bed_f

    path_b_obj, count_b, bed_b_v, bed_b_f = add_path("Chodník • terasa", path_b, 0.60, 12, reveal_terrace)
    path_a_obj, count_a, bed_a_v, bed_a_f = add_path("Chodník • vstup", path_a, 0.45, 9, reveal_a)
    bed_verts = bed_b_v + bed_a_v
    bed_faces = bed_b_f + [(i + len(bed_b_v), j + len(bed_b_v), k + len(bed_b_v), m + len(bed_b_v)) for i, j, k, m in bed_a_f]
    bed = bpy.data.objects.new("Lôžko • chodník", new_mesh("Lôžko • chodník", bed_verts, bed_faces))
    col_access.objects.link(bed)
    bed.data.materials.append(edge_mat)

    across = 12
    stations = max(2, int(road.length / 0.25) + 1)
    road_rows = []
    wear_values = []
    for index in range(stations):
        distance = road.length * index / (stations - 1)
        half = road_half(distance, straight0, straight1, road.length)
        row = []
        for column in range(across + 1):
            offset = -half + 2 * half * column / across
            xy = road.point(distance, offset)
            ground = terrain_z(bpy.data.objects["Lesná čistina"], xy[0], xy[1])
            if ground is None:
                fail(f"road terrain {xy}")
            lift = crust(distance, offset, half, road.length, float(xy[0]), straight0, straight1)
            row.append((float(xy[0]), float(xy[1]), ground + lift))
            wear_values.append(wear_road(distance, offset, road.length))
        road_rows.append(row)
    road_verts = [v for row in road_rows for v in row]
    road_faces = []
    stride = across + 1
    for row_index in range(stations - 1):
        for column in range(across):
            a = row_index * stride + column
            b = a + stride
            road_faces.append((a, a + 1, b + 1, b))
    road_obj = bpy.data.objects.new("Cesta • les", new_mesh("Cesta • les", road_verts, road_faces, ("wear", wear_values)))
    col_access.objects.link(road_obj)
    road_obj.data.materials.append(gravel_mat)
    for poly in road_obj.data.polygons:
        poly.use_smooth = True

    park_verts = []
    park_faces = []
    park_wear = []
    xs = np.linspace(3.20, 13.00, 40)
    for x_index, x in enumerate(xs):
        if x < 5.60:
            y_north = -11.80 + (x - 3.20) / 2.40 * 2.60
        elif x > 10.60:
            y_north = -11.80 + (13.00 - x) / 2.40 * 2.60
        else:
            y_north = -9.20
        ys = np.linspace(-11.80, y_north, 12)
        for y in ys:
            ground = terrain_z(bpy.data.objects["Lesná čistina"], float(x), float(y))
            if ground is None:
                fail(f"parking terrain {x} {y}")
            park_verts.append((float(x), float(y), ground + 0.012))
            track = min(abs(y + 11.40), abs(y + 9.90))
            park_wear.append(0.50 if track <= 0.14 and 5.60 <= x <= 10.60 else 0.0)
        if x_index:
            for y_index in range(11):
                a = (x_index - 1) * 12 + y_index
                b = x_index * 12 + y_index
                park_faces.append((a, b, b + 1, a + 1))
    park = bpy.data.objects.new("Parkovanie • štrk", new_mesh("Parkovanie • štrk", park_verts, park_faces, ("wear", park_wear)))
    col_access.objects.link(park)
    park.data.materials.append(gravel_mat)

    mask_v, mask_f = mask_geometry(((path_a, 0.45), (path_b, 0.60)), road, straight0, straight1)
    mask = bpy.data.objects.new("Maska prístupu", new_mesh("Maska prístupu", mask_v, mask_f))
    col_help.objects.link(mask)
    mask.hide_render = True
    install_mask(mask)

    proxy_z = terrain_z(bpy.data.objects["Lesná čistina"], 8.30, -10.65)
    proxy_mesh = bpy.data.meshes.new("Proxy • auto")
    proxy_mesh.from_pydata(
        [((sx * 4.5), (sy * 1.8), (sz * 1.5)) for sx in (-0.5, 0.5) for sy in (-0.5, 0.5) for sz in (-0.5, 0.5)],
        [],
        [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)],
    )
    proxy = bpy.data.objects.new("Proxy • auto", proxy_mesh)
    col_help.objects.link(proxy)
    proxy.location = (8.30, -10.65, (proxy_z or -0.4) + 0.012 + 0.75)
    proxy.hide_render = True

    camera = bpy.data.cameras.new("D • Prístup zhora")
    camera.lens = 28.0
    camera.sensor_width = 36.0
    camera.sensor_height = 24.0
    camera.clip_end = 1000.0
    cam_obj = bpy.data.objects.new("D • Prístup zhora", camera)
    col_cam.objects.link(cam_obj)
    cam_obj.location = (7.0, -23.5, 15.5)
    target = Vector((6.5, -8.0, -0.4))
    cam_obj.rotation_euler = (target - cam_obj.location).normalized().to_track_quat("-Z", "Y").to_euler()

    moved = move_plants(((path_a, 0.45), (path_b, 0.60)), road, straight0, straight1)

    for name, before in trees_before.items():
        if not same_transform(before, bpy.data.objects[name]):
            fail(f"transform changed {name}")
    for name, loc in stone_before.items():
        for actual, expected in zip(bpy.data.objects[name].location, loc):
            if abs(actual - expected) > 0.0001:
                fail(f"stone moved {name}")
    if len(kamen.node_tree.nodes) != kamen_nodes or len(kamen.node_tree.links) != kamen_links:
        fail("Kameň changed")
    if sum(1 for obj in bpy.data.objects if any(slot.material == kamen for slot in obj.material_slots)) != 25:
        fail("Kameň users")
    if {obj.name for obj in bpy.data.scenes[SCENE_B].objects} != scene_b_names:
        fail("scene B membership")
    if len(bpy.data.scenes[SCENE_B].objects) != 308:
        fail("scene B count after")
    for name in (COL_HIDE, COL_STONES, COL_ACCESS, COL_HELP, COL_PLANTS, COL_CAM):
        if layer_collection(bpy.data.scenes[SCENE_B].view_layers[0], name) is not None:
            fail(f"{name} in scene B")
    if not proxy.hide_render or not mask.hide_render:
        fail("helpers visible to render")
    if bpy.context.scene.camera.name != CAM_A:
        fail("active camera")

    print(json.dumps({
        "pavers_b": count_b,
        "pavers_a": count_a,
        "path_a_length": round(path_a.length, 3),
        "path_b_length": round(path_b.length, 3),
        "road_length": round(road.length, 3),
        "shift": [round(float(v), 4) for v in shift],
        "terrace_ground": None if ground0 is None else round(ground0, 4),
        "terrace_delta": round(terrace_delta, 4),
        "rock_m": round(float(rock.min()), 3),
        "moved_plants": moved,
        "hidden": hidden_before,
        "camera_d": [round(v, 4) for v in cam_obj.location],
        "lens_d": camera.lens,
        "scene_b": len(bpy.data.scenes[SCENE_B].objects),
        "kamen_users": 25,
    }, ensure_ascii=False))


build()
