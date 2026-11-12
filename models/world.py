"""Build the Baktas world props in Blender and export one unskinned world.glb.
Each prop is a single object named P_* with its origin at the base (or pivot) in game coordinates."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heroes as H
import bpy
from mathutils import Vector
from mobs import rock

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 1 else '/tmp/claude-0/glb'
ell, lathe, tube, xf, cube, mat, blade = H.ell, H.lathe, H.tube, H.xf, H.cube, H.mat, H.blade
TAU = math.pi * 2
PROPS = {}

def add(prop, VF, m, smooth=False):
    PROPS.setdefault(prop, []).append((VF, m, smooth))

def hsh(a, b):
    v = math.sin(a * 12.9898 + b * 78.233) * 43758.5453
    return v - math.floor(v)

def jag_cone(y, h, r, seg=9, jit=.14, seed=1, droop=.18):
    """Low-poly conifer tier: jagged drooping rim, apex on top, underside closed."""
    V = [(0, y + h, 0)]
    for j in range(seg):
        a = TAU * j / seg + hsh(seed, j) * .25
        rr = r * (1 + (hsh(j, seed) - .5) * 2 * jit)
        V.append((math.sin(a) * rr, y - droop * (.6 + hsh(seed + 3, j) * .8), math.cos(a) * rr))
    V.append((0, y + .12, 0))
    F = [(0, 1 + j, 1 + (j + 1) % seg) for j in range(seg)]
    F += [(seg + 1, 1 + (j + 1) % seg, 1 + j) for j in range(seg)]
    return V, F

def blob_cluster(prop, centers, m, seed=1, amt=.1):
    for i, (c, r) in enumerate(centers):
        add(prop, rock(c, r, seed + i * 3, amt, 9, 6), m)

def build():
    bark = mat('Bark', 0x5a3d2b, .95); leaves = mat('Leaves', 0xffffff, .9); rockm = mat('Rock', 0xffffff, .95)
    # ---- conifers
    add('P_pine', tube([(0, 0, 0), (0, 1.3, 0), (0, 2.8, 0)], [.3, .22, .12], 7), bark)
    for i, (y, h, r) in enumerate(((1.35, 1.7, 1.5), (2.3, 1.6, 1.22), (3.2, 1.45, .95), (4.0, 1.15, .62))):
        add('P_pine', jag_cone(y, h, r, 9, .14, i + 1), leaves)
    add('P_pine2', tube([(0, 0, 0), (0, 1.6, 0), (0, 3.6, 0)], [.24, .17, .09], 7), bark)
    for i, (y, h, r) in enumerate(((1.6, 1.4, 1.05), (2.35, 1.35, .92), (3.05, 1.3, .78), (3.75, 1.2, .6), (4.4, 1.15, .4))):
        add('P_pine2', jag_cone(y, h, r, 8, .16, i + 11, .14), leaves)
    # ---- round leafy tree
    add('P_oak', tube([(0, 0, 0), (.08, .9, .02), (0, 1.8, -.04), (-.05, 2.4, 0)], [.34, .26, .22, .18], 8), bark)
    add('P_oak', tube([(0, 1.6, 0), (.5, 2.2, .2), (.9, 2.6, .3)], [.13, .09, .06], 6), bark)
    add('P_oak', tube([(0, 1.9, 0), (-.55, 2.5, -.25), (-.8, 2.9, -.3)], [.12, .08, .05], 6), bark)
    blob_cluster('P_oak', [((0, 3.2, 0), (1.35, 1.1, 1.3)), ((.95, 2.85, .35), (.9, .8, .9)), ((-.9, 3.0, -.3), (.95, .85, .9)),
                           ((.2, 3.9, -.2), (.95, .8, .9)), ((-.2, 2.7, .8), (.8, .7, .75))], leaves, 4)
    # ---- bush
    blob_cluster('P_bush', [((0, .45, 0), (.6, .5, .6)), ((.45, .35, .2), (.42, .38, .42)), ((-.4, .32, -.15), (.45, .36, .42)), ((.05, .3, -.45), (.38, .3, .38))], leaves, 31, .12)
    # ---- rocks
    add('P_rock1', rock((0, .25, 0), (.9, .55, .8), 41, .16), rockm)
    add('P_rock2', rock((0, .35, 0), (.7, .75, .6), 43, .2), rockm)
    add('P_rock2', rock((.6, .18, .3), (.4, .3, .35), 44, .2), rockm)
    add('P_rock3', rock((0, .2, 0), (1.1, .4, .7), 47, .14), rockm)
    # ---- cottage (door faces +z)
    stone = mat('Stone', 0x8c867a, .95); plaster = mat('Plaster', 0xe2d6bb, .9); beam = mat('Beam', 0x4a3322, .85)
    roof = mat('Roof', 0x8e3f2c, .85); roof2 = mat('Roof2', 0x6e2f22, .85); wood = mat('Wood', 0x6b4a2e, .8)
    win = mat('Window', 0xffc46b, .4, 0, 0xffc46b); gold = mat('Gold', 0xc9a15a, .35, .8)
    add('P_house', cube((0, .25, 0), (4.6, .5, 4.4)), stone)
    add('P_house', cube((0, 1.9, 0), (4.2, 2.8, 4.0)), plaster)
    for x in (-2.07, 2.07):
        for z in (-1.97, 1.97):
            add('P_house', cube((x, 1.9, z), (.24, 2.85, .24)), beam)
    for y in (.6, 3.25):
        add('P_house', cube((0, y, 2.03), (4.3, .2, .12)), beam); add('P_house', cube((0, y, -2.03), (4.3, .2, .12)), beam)
        add('P_house', cube((2.13, y, 0), (.12, .2, 4.1)), beam); add('P_house', cube((-2.13, y, 0), (.12, .2, 4.1)), beam)
    for sx in (-1, 1):
        add('P_house', cube((1.55 * sx, 1.9, -2.04), (.14, 2.6, .1), (0, 0, .62 * sx)), beam)
    th = .62
    for sz in (1, -1):
        add('P_house', cube((0, 5.0 - 1.5 * math.sin(th), 1.22 * sz), (4.9, .18, 3.0), (-th * sz, 0, 0)), roof)
        for i in range(3):
            d = .6 + i * .8
            add('P_house', cube((0, 5.0 - d * math.sin(th) + .1, d * math.cos(th) * sz), (4.95, .06, .14), (-th * sz, 0, 0)), roof2)
    for sx in (-1, 1):
        xo, xi = 2.1 * sx, 1.95 * sx
        V = [(xo, 3.3, -2.0), (xo, 3.3, 2.0), (xo, 4.95, 0), (xi, 3.3, -2.0), (xi, 3.3, 2.0), (xi, 4.95, 0)]
        F = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
        add('P_house', (V, F), plaster)
    add('P_house', cube((0, 5.0, 0), (5.0, .2, .2)), beam)
    add('P_house', cube((1.3, 4.7, -.9), (.6, 1.9, .6)), stone); add('P_house', cube((1.3, 5.7, -.9), (.75, .14, .75)), stone)
    add('P_house', cube((0, 1.15, 2.03), (1.0, 1.7, .1)), wood)
    add('P_house', cube((0, 2.05, 2.06), (1.2, .14, .14)), beam)
    add('P_house', ell((.33, 1.15, 2.1), (.045, .045, .045), 6, 4), gold, True)
    for x in (-1.35, 1.35):
        add('P_house', cube((x, 2.0, 2.04), (.72, .64, .06)), win)
        add('P_house', cube((x, 2.0, 2.09), (.8, .07, .07)), beam); add('P_house', cube((x, 2.0, 2.09), (.07, .7, .07)), beam)
        add('P_house', cube((x, 1.62, 2.12), (.84, .1, .2)), beam)
        add('P_house', rock((x, 1.75, 2.18), (.38, .12, .1), 61, .2, 8, 5), mat('Flowers', 0x5f9a3c, .9))
    for sx in (-1, 1):
        add('P_house', cube((2.12 * sx, 2.0, 0), (.06, .64, .72)), win)
    # ---- lamp post
    iron = mat('Iron', 0x2a2a2e, .5, .6); glow = mat('LampGlow', 0xffd27a, .4, 0, 0xffd27a)
    add('P_lamp', lathe([(0, .22), (.2, .2), (.24, .08), (.22, 0)], seg=8), stone)
    add('P_lamp', tube([(0, .2, 0), (0, 2.5, 0)], [.06, .045], 8), iron, True)
    add('P_lamp', tube([(0, 2.45, 0), (.15, 2.65, 0), (.4, 2.68, 0)], [.035, .03, .03], 6), iron, True)
    add('P_lamp', cube((.4, 2.42, 0), (.22, .3, .22)), glow)
    for dx in (-.11, .11):
        for dz in (-.11, .11):
            add('P_lamp', cube((.4 + dx, 2.42, dz), (.03, .32, .03)), iron)
    add('P_lamp', lathe([(0, .14), (.17, 0)], c=(.4, 2.57, 0), seg=4), iron)
    # ---- town crystal (origin at crystal centre) + carved pedestal
    crys = mat('Crystal', 0x7fe6ff, .2, 0, 0x7fe6ff)
    for (x, z, h, w, rx, rz) in ((0, 0, 2.2, .42, 0, 0), (.32, .12, 1.2, .24, .2, -.45), (-.3, -.1, 1.3, .25, -.15, .42), (.08, -.32, 1.0, .2, -.45, .1), (-.1, .3, .9, .18, .4, .2)):
        add('P_crystal', xf(lathe([(0, h), (w, h * .32), (w * .8, h * .12), (0, 0)], seg=6), rot=(rx, 0, rz), t=(x, -1.0, z)), crys)
    add('P_pedestal', lathe([(1.75, 0), (1.75, .25), (1.4, .25), (1.4, .5), (1.08, .5), (.95, 1.0), (1.15, 1.12), (1.15, 1.3), (0, 1.3)], seg=10), stone)
    add('P_pedestal', lathe([(1.17, 1.15), (1.2, 1.2), (1.17, 1.25)], seg=24), gold, True)
    for a in range(4):
        ang = a * TAU / 4 + TAU / 8
        add('P_pedestal', cube((math.sin(ang) * 1.42, .38, math.cos(ang) * 1.42), (.18, .14, .03), (0, ang, 0)), crys)
    # ---- runestone
    rr = mat('RuneRock', 0x5d5a66, .95); rune = mat('Rune', 0x6ff2ff, .3, 0, 0x6ff2ff)
    add('P_runestone', rock((0, 1.6, 0), (.55, 1.75, .34), 71, .1, 8, 7), rr)
    for (a, b) in (((-.18, 2.4, .33), (.12, 2.1, .34)), ((.12, 2.1, .34), (-.15, 1.75, .34)), ((-.15, 1.75, .34), (.15, 1.4, .33)), ((0, 1.1, .32), (0, 2.6, .32))):
        add('P_runestone', tube([a, b], [.03, .03], 5), rune, True)
    # ---- crypt pillar with torch
    cs = mat('CryptStone', 0x4d4858, .95); flame = mat('Flame', 0xff9a3c, .4, 0, 0xff8a2c)
    add('P_pillar', lathe([(.85, 0), (.85, .35), (.62, .45), (.55, .6), (.5, 5.2), (.62, 5.35), (.85, 5.5), (.85, 5.9), (0, 5.9)], seg=10), cs)
    add('P_pillar', tube([(0, 2.6, .5), (0, 2.75, .75), (0, 2.95, .85)], [.05, .045, .04], 6), iron, True)
    add('P_pillar', lathe([(0, .1), (.13, .06), (.1, 0)], c=(0, 2.95, .85), seg=6), iron)
    add('P_pillar', lathe([(0, .5), (.12, .18), (.1, 0)], c=(0, 3.04, .85), seg=7), flame)
    # ---- portal arch (opening faces +z)
    add('P_portal', cube((-1.75, .2, 0), (.9, .4, .9)), cs); add('P_portal', cube((1.75, .2, 0), (.9, .4, .9)), cs)
    for x in (-1.75, 1.75):
        add('P_portal', tube([(x, .3, 0), (x, 1.9, 0)], [.36, .32], 8), cs)
    pts = [(math.cos(a) * 1.75, 1.9 + math.sin(a) * 1.75, 0) for a in [math.pi * i / 14 for i in range(15)]]
    add('P_portal', tube(pts, [.33] * 15, 8), cs)
    add('P_portal', cube((0, 3.75, 0), (.5, .55, .7)), cs)
    add('P_portal', ell((0, 3.75, .36), (.12, .15, .04), 8, 5), mat('PortalRune', 0xb37bea, .3, 0, 0xb37bea), True)
    for x in (-1.75, 1.75):
        add('P_portal', tube([(x, .5, .34), (x, 1.8, .34)], [.025, .025], 4), mat('PortalRune', 0xb37bea, .3, 0, 0xb37bea), True)
    # ---- treasure chest (lid pivots at the back top edge)
    add('P_chest', cube((0, .3, 0), (1.1, .6, .7)), wood)
    for x in (-.4, .4):
        add('P_chest', cube((x, .3, 0), (.08, .62, .72)), gold)
    add('P_chest', cube((0, .45, .36), (.16, .2, .04)), gold)
    # half-cylinder lid along x; hinge (origin) at the back top edge, lid extends toward +z
    segs = 8; Vl = []; Fl = []
    for i in range(segs + 1):
        a = math.pi * i / segs
        for x in (-.55, .55):
            Vl.append((x, math.sin(a) * .3, .35 - math.cos(a) * .35))
    for i in range(segs):
        a = i * 2
        Fl.append((a, a + 2, a + 3, a + 1))
    Fl.append(tuple(range(0, (segs + 1) * 2, 2)))
    Fl.append(tuple(reversed(range(1, (segs + 1) * 2, 2))))
    add('P_chestLid', (Vl, Fl), wood, True)
    for x in (-.4, .4):
        add('P_chestLid', tube([(x, math.sin(math.pi * i / 8) * .315, .35 - math.cos(math.pi * i / 8) * .36) for i in range(9)], [.035] * 9, 4, cap=False), gold, True)

def export():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    H.MATS.clear()
    build()
    for name, parts in PROPS.items():
        obs = [H.make_object(name + '_p', VF[0], VF[1], m, smooth) for (VF, m, smooth) in parts]
        if len(obs) > 1:
            with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, selected_objects=obs):
                bpy.ops.object.join()
        obs[0].name = name
    path = os.path.join(OUT, 'world.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_skins=False, export_animations=False, export_yup=True,
                              export_normals=True, export_texcoords=False, export_materials='EXPORT')
    tris = sum(len(p.vertices) - 2 for o in bpy.data.objects if o.type == 'MESH' for p in o.data.polygons)
    print('BUILT world', os.path.getsize(path), 'bytes', tris, 'tris', sorted(PROPS))

if __name__ == '__main__':
    export()
