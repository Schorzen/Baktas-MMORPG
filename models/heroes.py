"""Build the four Baktas heroes in Blender and export rigged GLBs.
All geometry is authored in GAME coordinates (x right, y up, z forward) and converted
to Blender (x, -z, y) so the glTF exporter's Y-up conversion lands it back in game space."""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix, Euler

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 1 else '/tmp/claude-0/glb'
os.makedirs(OUT, exist_ok=True)
TAU = math.pi * 2

def g2b(v):
    return (v[0], -v[2], v[1])

# ---------------------------------------------------------------- materials
MATS = {}
def hexc(h):
    return ((h >> 16 & 255) / 255, (h >> 8 & 255) / 255, (h & 255) / 255, 1)

def mat(name, color, rough=.7, metal=0., emis=None, cull=True):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexc(color)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emis is not None:
        b.inputs['Emission Color'].default_value = hexc(emis)
        b.inputs['Emission Strength'].default_value = 1.0
    m.use_backface_culling = cull
    MATS[name] = m
    return m

# ---------------------------------------------------------------- generators (game coords)
def ell(c, r, seg=18, ring=12):
    V = [(c[0], c[1] + r[1], c[2])]
    for i in range(1, ring):
        th = math.pi * i / ring
        y, s = math.cos(th), math.sin(th)
        for j in range(seg):
            ph = TAU * j / seg
            V.append((c[0] + r[0] * s * math.sin(ph), c[1] + r[1] * y, c[2] + r[2] * s * math.cos(ph)))
    V.append((c[0], c[1] - r[1], c[2]))
    F = []
    for j in range(seg):
        F.append((0, 1 + j, 1 + (j + 1) % seg))
    for i in range(ring - 2):
        for j in range(seg):
            a = 1 + i * seg + j; b = 1 + i * seg + (j + 1) % seg
            F.append((a, a + seg, b + seg, b))
    last = len(V) - 1; base = 1 + (ring - 2) * seg
    for j in range(seg):
        F.append((base + j, last, base + (j + 1) % seg))
    return V, F

def lathe(prof, c=(0, 0, 0), seg=20, sx=1., sz=1., a0=0., a1=TAU, cap0=False, cap1=False):
    """Revolve [(r, y)] around the vertical axis. Angles measured from +z (front) toward +x."""
    full = abs((a1 - a0) - TAU) < 1e-6
    n = seg if full else seg + 1
    V = []; F = []; rows = []
    for (r, y) in prof:
        if r < 1e-5:
            rows.append([len(V)]); V.append((c[0], c[1] + y, c[2])); continue
        row = []
        for j in range(n):
            a = a0 + (a1 - a0) * j / seg
            row.append(len(V)); V.append((c[0] + r * sx * math.sin(a), c[1] + y, c[2] + r * sz * math.cos(a)))
        rows.append(row)
    for i in range(len(rows) - 1):
        A, B = rows[i], rows[i + 1]
        m = seg if full else seg
        for j in range(m):
            j1 = (j + 1) % n if full else j + 1
            if len(A) == 1:
                F.append((A[0], B[j], B[j1]))
            elif len(B) == 1:
                F.append((A[j], B[0], A[j1]))
            else:
                F.append((A[j], B[j], B[j1], A[j1]))
    if cap0 and len(rows[0]) > 1 and full:
        F.append(tuple(reversed(rows[0])))
    if cap1 and len(rows[-1]) > 1 and full:
        F.append(tuple(rows[-1]))
    return V, F

def tube(pts, rad, seg=12, cap=True, flat=1.):
    pts = [Vector(p) for p in pts]
    n = len(pts)
    T = []
    for i in range(n):
        if i == 0: t = pts[1] - pts[0]
        elif i == n - 1: t = pts[-1] - pts[-2]
        else: t = pts[i + 1] - pts[i - 1]
        T.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(T[0].z) < .9 else Vector((1, 0, 0))
    N = T[0].cross(ref).normalized()
    V = []; F = []
    for i in range(n):
        if i > 0:
            axis = T[i - 1].cross(T[i])
            if axis.length > 1e-6:
                ang = T[i - 1].angle(T[i])
                N = (Matrix.Rotation(ang, 3, axis.normalized()) @ N).normalized()
        Bv = T[i].cross(N).normalized()
        r = rad[i]
        for j in range(seg):
            a = TAU * j / seg
            off = N * (math.cos(a) * r) + Bv * (math.sin(a) * r * flat)
            V.append(tuple(pts[i] + off))
    for i in range(n - 1):
        for j in range(seg):
            a = i * seg + j; b = i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    if cap:
        if rad[0] > 1e-4:
            ci = len(V); V.append(tuple(pts[0] - T[0] * rad[0] * .5))
            for j in range(seg): F.append((ci, (j + 1) % seg, j))
        if rad[-1] > 1e-4:
            ci = len(V); V.append(tuple(pts[-1] + T[-1] * rad[-1] * .5)); base = (n - 1) * seg
            for j in range(seg): F.append((ci, base + j, base + (j + 1) % seg))
    return V, F

def blade(stations, M=Matrix.Identity(4)):
    """Diamond cross-section blade. stations: [(along, halfwidth, halfthick, sideOffset, upOffset)] along +z."""
    V = []; F = []
    for (z, w, t, sx, sy) in stations:
        base = len(V)
        V += [(sx - w, sy, z), (sx, sy + t, z), (sx + w, sy, z), (sx, sy - t, z)]
    k = len(stations)
    for i in range(k - 1):
        a = i * 4; b = a + 4
        for e in range(4):
            F.append((a + e, a + (e + 1) % 4, b + (e + 1) % 4, b + e))
    F.append((3, 2, 1, 0))
    F.append(tuple(range((k - 1) * 4, k * 4)))
    V = [tuple(M @ Vector(v)) for v in V]
    return V, F

def cube(c, s, rot=(0, 0, 0)):
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    R = Euler(rot, 'XYZ').to_matrix()
    P = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    V = [tuple(Vector(c) + R @ Vector(p)) for p in P]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
    return V, F

def xf(VF, rot=(0, 0, 0), t=(0, 0, 0), s=(1, 1, 1), pivot=(0, 0, 0)):
    V, F = VF
    R = Euler(rot, 'XYZ').to_matrix()
    out = []
    for v in V:
        p = Vector(v) - Vector(pivot)
        p = Vector((p.x * s[0], p.y * s[1], p.z * s[2]))
        p = R @ p + Vector(pivot) + Vector(t)
        out.append(tuple(p))
    return out, F

def mirror_x(VF):
    V, F = VF
    return [(-v[0], v[1], v[2]) for v in V], [tuple(reversed(f)) for f in F]

# ---------------------------------------------------------------- skeleton (game coords)
SIDE = {'R': 1, 'L': -1}
def bones_def():
    B = {
        'root': ((0, 0, 0), (0, .3, 0), None),
        'hips': ((0, .93, 0), (0, 1.15, 0), 'root'),
        'spine': ((0, 1.15, 0), (0, 1.42, 0), 'hips'),
        'chest': ((0, 1.42, 0), (0, 1.76, 0), 'spine'),
        'neck': ((0, 1.76, 0), (0, 1.9, 0), 'chest'),
        'head': ((0, 1.9, 0), (0, 2.3, 0), 'neck'),
    }
    for s, k in SIDE.items():
        B['upperarm_' + s] = ((.33 * k, 1.7, 0), (.37 * k, 1.41, 0), 'chest')
        B['forearm_' + s] = ((.37 * k, 1.41, 0), (.4 * k, 1.12, .01), 'upperarm_' + s)
        B['hand_' + s] = ((.4 * k, 1.12, .01), (.41 * k, 1.0, .015), 'forearm_' + s)
        B['thigh_' + s] = ((.13 * k, .93, 0), (.145 * k, .55, .02), 'hips')
        B['shin_' + s] = ((.145 * k, .55, .02), (.15 * k, .14, -.01), 'thigh_' + s)
        B['foot_' + s] = ((.15 * k, .14, -.01), (.15 * k, .05, .16), 'shin_' + s)
    return B
BONES = bones_def()
DEFORM = [b for b in BONES if b != 'root']

def seg_dist(p, a, b):
    p, a, b = Vector(p), Vector(a), Vector(b)
    ab = b - a; t = max(0., min(1., (p - a).dot(ab) / max(ab.dot(ab), 1e-9)))
    return (p - (a + ab * t)).length

def auto_weights(V, allowed, power=4, k=2):
    W = []
    for v in V:
        ds = sorted(((seg_dist(v, BONES[b][0], BONES[b][1]), b) for b in allowed))[:k]
        ws = [(1. / max(d, 1e-3) ** power, b) for d, b in ds]
        tot = sum(w for w, _ in ws)
        W.append({b: w / tot for w, b in ws})
    return W

def side_of(v):
    return 'R' if v[0] >= 0 else 'L'

def mantle_w(v):
    t = max(0., min(1., (abs(v[0]) - .2) / .15)) * .22
    return {'chest': 1 - t, 'upperarm_' + side_of(v): t} if t > 0 else {'chest': 1.}

# ---------------------------------------------------------------- part registry
PARTS = []
def part(VF, m, weights, smooth=True, name='part'):
    """weights: 'bone' | ('auto', [bones]) | callable(v)->{bone:w}"""
    V, F = VF
    if isinstance(weights, str):
        W = [{weights: 1.} for _ in V]
    elif isinstance(weights, tuple):
        allowed = weights[1]
        if weights[0] == 'autoside':
            W = []
            for v in V:
                s = side_of(v)
                W.append(auto_weights([v], [b.replace('#', s) for b in allowed])[0])
        else:
            W = auto_weights(V, allowed)
    else:
        W = [weights(v) for v in V]
    PARTS.append((name, V, F, m, W, smooth))

LIMB_R = ['upperarm_#', 'forearm_#', 'hand_#']
LEG_R = ['thigh_#', 'shin_#', 'foot_#']

def body(look, arm_mat, leg_mat, hand_mat, foot_mat=None, head_mat=None, ears=True):
    skin = mat('Skin', look['skin'], .62)
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        arm = tube([(.33 * k, 1.72, 0), (.35 * k, 1.56, 0), (.37 * k, 1.41, 0), (.385 * k, 1.27, .005), (.4 * k, 1.14, .01)],
                   [.074, .068, .058, .054, .046], 12)
        part(arm, arm_mat, ('auto', ['chest', 'upperarm_' + s, 'forearm_' + s, 'hand_' + s]), name='arm')
        hand = ell((.405 * k, 1.065, .02), (.048, .066, .05), 12, 8)
        part(hand, hand_mat, 'hand_' + s, name='hand')
        thumb = ell((.38 * k, 1.07, .055), (.022, .035, .022), 8, 6)
        part(thumb, hand_mat, 'hand_' + s, name='thumb')
        leg = tube([(.125 * k, .97, 0), (.135 * k, .76, .01), (.145 * k, .55, .02), (.148 * k, .36, .005), (.15 * k, .17, -.01)],
                   [.105, .093, .074, .068, .054], 12)
        part(leg, leg_mat, ('auto', ['hips', 'thigh_' + s, 'shin_' + s]), name='leg')
        foot = ell((.15 * k, .075, .045), (.068, .07, .14), 12, 8)
        part(foot, foot_mat or leg_mat, ('auto', ['shin_' + s, 'foot_' + s]), name='foot')
        sh = ell((.3 * k, 1.69, 0), (.09, .085, .09), 12, 8)
        part(sh, arm_mat, ('auto', ['chest', 'upperarm_' + s]), name='shoulder')
    hm = head_mat or skin
    part(ell((0, 2.04, 0), (.185, .205, .19), 22, 14), hm, 'head', name='head')
    part(ell((0, 1.965, .035), (.145, .115, .14), 18, 10), hm, 'head', name='jaw')
    part(tube([(0, 1.74, 0), (0, 1.93, .01)], [.068, .062], 12), hm if head_mat else skin, ('auto', ['neck', 'head', 'chest']), name='neck')
    if not head_mat:
        part(tube([(0, 2.04, .17), (0, 1.995, .215)], [.032, .012], 8), skin, 'head', name='nose')
        if ears:
            for k in (1, -1):
                part(ell((.185 * k, 2.03, -.01), (.03, .055, .04), 8, 6), skin, 'head', name='ear')

def eyes(m, brow=None, y=2.06, z=.168):
    for k in (1, -1):
        part(ell((.068 * k, y, z), (.034, .03, .02), 10, 6), m, 'head', name='eye')
        if brow is not None:
            part(cube((.07 * k, y + .055, z + .01), (.085, .022, .03), (0, 0, -.18 * k)), brow, 'head', smooth=False, name='brow')

def torso(prof, m, sz=.7, name='torso', a0=0., a1=TAU, wfun=None):
    part(lathe(prof, sz=sz, seg=24, a0=a0, a1=a1), m, wfun or ('auto', ['hips', 'spine', 'chest']), name=name)

# ---------------------------------------------------------------- weapon objects
WEAPONS = []
def wpart(group, VF, m, smooth=True):
    WEAPONS.append((group, VF, m, smooth))

# ---------------------------------------------------------------- classes
def build_warrior():
    L = dict(skin=0xd9a07a, main=0x8a939e, trim=0xc9a15a, dark=0x3a3f46, cape=0x8e2f29)
    steel = mat('Main', L['main'], .38, .7); trim = mat('Trim', L['trim'], .35, .8); dark = mat('Dark', L['dark'], .8)
    leather = mat('Leather', 0x4a3424, .75); cape = mat('Cape', L['cape'], .85, cull=False); hair = mat('Hair', 0x5a3a22, .9)
    eye = mat('Eye', 0x1d1a18, .4)
    body(L, dark, dark, leather, foot_mat=leather)
    eyes(eye, hair)
    torso([(.215, 1.08), (.225, 1.2), (.25, 1.36), (.26, 1.5), (.255, 1.62), (.21, 1.73), (.13, 1.79)], steel, .74, 'plate')
    for y in (1.1, 1.73):
        part(lathe([(.232 if y < 1.5 else .215, y - .025), (.24 if y < 1.5 else .222, y), (.232 if y < 1.5 else .215, y + .025)], sz=.75, seg=24), trim,
             ('auto', ['hips', 'spine', 'chest']), name='band')
    part(cube((0, 1.5, .19), (.1, .18, .04)), trim, 'chest', smooth=False, name='emblem')
    part(lathe([(.225, .96), (.235, 1.04), (.226, 1.1)], sz=.76, seg=24), leather, 'hips', name='belt')
    part(cube((0, 1.03, .175), (.09, .08, .03)), trim, 'hips', smooth=False, name='buckle')
    def skirt_w(v):
        s = side_of(v); t = max(0., min(1., (1.0 - v[1]) / .3)) * .45
        return {'hips': 1 - t, 'thigh_' + s: t}
    part(lathe([(.23, 1.0), (.26, .86), (.29, .7)], sz=.78, seg=24), steel, skirt_w, name='tassets')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(xf(lathe([(0, .1), (.1, .085), (.15, .04), (.16, 0), (.15, -.03)], sz=1.0, seg=16), rot=(0, 0, -.35 * k), t=(.36 * k, 1.69, 0)), steel,
             ('auto', ['chest', 'upperarm_' + s]), name='pauldron')
        part(xf(lathe([(.165, -.03), (.172, -.045), (.165, -.06)], seg=16), rot=(0, 0, -.35 * k), t=(.36 * k, 1.69, 0)), trim,
             ('auto', ['chest', 'upperarm_' + s]), name='pauldron_rim')
        part(tube([(.383 * k, 1.3, .005), (.392 * k, 1.21, .008), (.4 * k, 1.12, .01)], [.064, .066, .06], 12), steel,
             ('auto', ['forearm_' + s, 'hand_' + s]), name='gauntlet')
        part(tube([(.149 * k, .4, .0), (.15 * k, .24, -.005), (.15 * k, .12, -.01)], [.078, .074, .07], 12), leather,
             ('auto', ['shin_' + s, 'foot_' + s]), name='boot')
        part(lathe([(.08, .37), (.088, .4), (.08, .43)], c=(.149 * k, 0, .0), seg=12), trim, 'shin_' + s, name='cuff')
        part(xf(lathe([(0, .05), (.06, .045), (.09, 0), (.06, -.04)], seg=12), t=(.145 * k, .56, .085)), steel, 'shin_' + s, name='knee')
    # helmet
    part(lathe([(0, 2.31), (.12, 2.29), (.2, 2.21), (.228, 2.1), (.228, 2.05)], sz=1.02, seg=24), steel, 'head', name='helm')
    part(lathe([(.23, 2.03), (.238, 2.06), (.23, 2.09)], sz=1.02, seg=24), trim, 'head', name='helm_rim')
    part(cube((0, 2.01, .215), (.04, .13, .035)), steel, 'head', smooth=False, name='nasal')
    for k in (1, -1):
        part(cube((.195 * k, 1.97, .07), (.04, .16, .12), (0, .3 * k, 0)), steel, 'head', smooth=False, name='cheek')
        part(tube([(.2 * k, 2.17, 0), (.31 * k, 2.21, .02), (.39 * k, 2.32, .04), (.42 * k, 2.46, .05)], [.052, .043, .028, .004], 10),
             mat('Horn', 0xeee4cf, .5), 'head', name='horn')
    part(ell((0, 1.9, .1), (.135, .1, .09), 14, 8), hair, 'head', name='beard')
    # cape
    V = []; F = []; cols, rows = 7, 9
    for i in range(rows):
        t = i / (rows - 1)
        for j in range(cols):
            u = j / (cols - 1) - .5
            w = .56 + .2 * t
            V.append((u * w, 1.74 - t * 1.05, -.23 - .07 * t - .03 * math.cos(u * math.pi) - .02 * math.sin(t * 3)))
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            F.append((a, a + 1, a + cols + 1, a + cols))
    def cape_w(v):
        t = (1.74 - v[1]) / 1.05
        if t < .35: return {'chest': 1.}
        if t < .7: return {'chest': 1 - (t - .35) / .35 * .6, 'spine': (t - .35) / .35 * .6}
        return {'spine': .5, 'hips': .5}
    part((V, F), cape, cape_w, name='cape')
    part(lathe([(.21, 1.71), (.25, 1.76), (.21, 1.8)], sz=.7, seg=20, a0=math.pi * .55, a1=math.pi * 1.45), trim, 'chest', name='clasp')
    # sword (grip at origin, blade along +z)
    metal = mat('Metal', 0xe3e9f0, .2, .9)
    wpart('W_main', tube([(0, 0, -.15), (0, 0, .15)], [.03, .03], 10), leather)
    wpart('W_main', ell((0, 0, -.18), (.045, .045, .045), 10, 8), trim)
    wpart('W_main', tube([(-.2, 0, .17), (-.1, 0, .175), (0, 0, .175), (.1, 0, .175), (.2, 0, .17)], [.018, .03, .035, .03, .018], 8), trim)
    wpart('W_main', blade([(.19, .07, .022, 0, 0), (.4, .064, .02, 0, 0), (1.1, .056, .018, 0, 0), (1.3, .04, .014, 0, 0), (1.42, 0, .004, 0, 0)]), metal, False)
    wpart('W_main', blade([(.22, .012, .024, 0, 0), (1.05, .008, .021, 0, 0), (1.2, 0, .016, 0, 0)]), mat('Fuller', 0xb8c2cc, .3, .9), False)
    # shield (faces outward on the left hand)
    shield = lambda VF: xf(VF, rot=(0, 0, math.pi / 2), t=(-.13, .08, .06))
    wpart('W_off', shield(lathe([(0, .07), (.2, .065), (.36, .045), (.44, .015), (.45, -.01), (.43, -.03), (0, -.03)], seg=28)), cape)
    wpart('W_off', shield(lathe([(.43, .03), (.46, .005), (.45, -.025), (.42, -.01)], seg=28)), trim)
    wpart('W_off', shield(lathe([(0, .14), (.07, .12), (.11, .07), (.12, .05)], seg=16)), trim)
    for a in range(8):
        ang = a / 8 * TAU
        wpart('W_off', shield(ell((math.sin(ang) * .33, .062, math.cos(ang) * .33), (.025, .02, .025), 8, 5)), metal)
    # ---- tier 2: winged broadsword + spiked steel shield
    silver = mat('Silver', 0xd8dde6, .25, .9); ruby = mat('Glow2', 0xff5a4a, .3, 0, 0xff4a3a)
    wpart('W_main2', tube([(0, 0, -.17), (0, 0, .15)], [.032, .032], 10), leather)
    wpart('W_main2', ell((0, 0, -.21), (.05, .05, .05), 10, 8), silver)
    wpart('W_main2', tube([(-.3, .06, .1), (-.15, .0, .17), (0, 0, .18), (.15, 0, .17), (.3, .06, .1)], [.012, .03, .04, .03, .012], 8), silver)
    wpart('W_main2', ell((0, 0, .19), (.045, .045, .03), 8, 6), ruby)
    wpart('W_main2', blade([(.2, .09, .024, 0, 0), (.5, .085, .022, 0, 0), (1.25, .07, .02, 0, 0), (1.45, .05, .016, 0, 0), (1.58, 0, .004, 0, 0)]), metal, False)
    wpart('W_main2', blade([(.22, .014, .026, 0, 0), (1.3, .01, .023, 0, 0), (1.45, 0, .018, 0, 0)]), ruby, False)
    wpart('W_off2', shield(lathe([(0, .07), (.2, .065), (.36, .045), (.46, .015), (.47, -.01), (.45, -.03), (0, -.03)], seg=28)), silver)
    wpart('W_off2', shield(lathe([(.45, .03), (.49, .005), (.48, -.025), (.44, -.01)], seg=28)), trim)
    wpart('W_off2', shield(lathe([(0, .32), (.05, .14), (.12, .07), (.13, .05)], seg=10)), trim)
    wpart('W_off2', shield(lathe([(.25, .068), (.28, .072), (.25, .076)], seg=24)), ruby)
    # ---- tier 3: Warden greatsword + crystal kite shield
    void = mat('Glow3', 0xd88bff, .3, 0, 0xc070ff); obsid = mat('Obsidian', 0x2a2438, .25, .6)
    wpart('W_main3', tube([(0, 0, -.22), (0, 0, .15)], [.034, .034], 10), obsid)
    wpart('W_main3', ell((0, 0, -.27), (.06, .06, .07), 8, 6), void)
    for k in (1, -1):
        wpart('W_main3', tube([(0, 0, .18), (.18 * k, .03, .14), (.32 * k, .1, .2), (.38 * k, .16, .3)], [.045, .035, .022, .004], 8), obsid)
    wpart('W_main3', blade([(.2, .11, .03, 0, 0), (.55, .1, .028, 0, 0), (1.35, .085, .024, 0, 0), (1.62, .055, .018, 0, 0), (1.78, 0, .005, 0, 0)]), obsid, False)
    wpart('W_main3', blade([(.24, .045, .034, 0, 0), (1.4, .035, .03, 0, 0), (1.66, 0, .02, 0, 0)]), void, False)
    kite = lambda VF: xf(VF, rot=(0, 0, math.pi / 2), t=(-.13, .02, .06))
    wpart('W_off3', kite(xf(lathe([(0, .07), (.2, .065), (.38, .045), (.47, .015), (.48, -.01), (0, -.03)], seg=4), s=(.85, 1, 1.45))), obsid)
    wpart('W_off3', kite(xf(lathe([(0, .14), (.12, .1), (.2, .06)], seg=4), s=(.85, 1, 1.45))), void)
    wpart('W_off3', kite(xf(lathe([(.46, .03), (.5, .0), (.46, -.03)], seg=4), s=(.85, 1, 1.45))), trim)
    return 'warrior'

def build_mage():
    L = dict(skin=0xe2b08c, main=0x2f4a8f, trim=0xd4b46a, dark=0x1f2440, glow=0x7fd8ff)
    robe = mat('Main', L['main'], .8); trim = mat('Trim', L['trim'], .35, .75); dark = mat('Dark', L['dark'], .85)
    beardm = mat('Hair', 0xdcd6cc, .9); eye = mat('Eye', 0x1d1a18, .4); wood = mat('Wood', 0x5b3b24, .8)
    glow = mat('Glow', L['glow'], .3, 0, L['glow'])
    body(L, robe, dark, mat('Skin', L['skin'], .62), foot_mat=dark)
    eyes(eye, beardm)
    def robe_w(v):
        if v[1] > 1.15: return auto_weights([v], ['hips', 'spine', 'chest'])[0]
        s = side_of(v); t = max(0., min(1., (1.05 - v[1]) / .8)) * .5 * min(1., abs(v[0]) / .12)
        return {'hips': 1 - t, 'thigh_' + s: t}
    part(lathe([(.11, 1.8), (.2, 1.73), (.245, 1.6), (.235, 1.42), (.22, 1.2), (.245, 1.0), (.3, .76), (.37, .46), (.43, .17), (.455, .05)], sz=.84, seg=28),
         robe, robe_w, name='robe')
    part(lathe([(.452, .1), (.465, .07), (.458, .035), (.445, .05)], sz=.84, seg=28), trim, robe_w, name='hem')
    part(lathe([(.23, 1.05), (.245, 1.1), (.23, 1.15)], sz=.85, seg=24), trim, 'hips', name='sash')
    part(cube((0, 1.1, .2), (.07, .07, .03)), glow, 'hips', smooth=False, name='gem')
    part(lathe([(.2, 1.78), (.3, 1.68), (.34, 1.55), (.33, 1.5)], sz=.82, seg=24), dark, mantle_w, name='mantle')
    part(lathe([(.335, 1.505), (.345, 1.53), (.335, 1.555)], sz=.82, seg=24), trim, mantle_w, name='mantle_rim')
    part(cube((0, 1.62, .2), (.06, .2, .03)), trim, 'chest', smooth=False, name='stole')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(tube([(.37 * k, 1.42, 0), (.385 * k, 1.28, .005), (.4 * k, 1.17, .01), (.405 * k, 1.13, .012)], [.068, .075, .098, .108], 14, cap=False), robe,
             ('auto', ['upperarm_' + s, 'forearm_' + s]), name='sleeve')
        part(lathe([(.105, -.02), (.112, 0), (.105, .02)], c=(.405 * k, 1.13, .012), seg=14), trim, 'forearm_' + s, name='cuff')
    # hat: brim + bent cone
    part(lathe([(0, 2.205), (.3, 2.2), (.46, 2.17), (.47, 2.155), (.3, 2.175), (0, 2.18)], seg=28), dark, 'head', name='brim')
    part(tube([(0, 2.19, -.01), (-.01, 2.45, -.03), (-.04, 2.68, -.08), (-.1, 2.86, -.16), (-.18, 2.93, -.24)], [.25, .17, .1, .045, .004], 18), robe, 'head', name='hat')
    part(lathe([(.245, 2.2), (.25, 2.24), (.235, 2.28)], seg=24), trim, 'head', name='hatband')
    part(tube([(0, 1.98, .15), (0, 1.86, .19), (0, 1.73, .18), (0, 1.6, .14), (0, 1.52, .11)], [.105, .1, .075, .04, .002], 14, flat=.6), beardm,
         ('auto', ['head', 'neck']), name='beard')
    for k in (1, -1):
        part(tube([(.0, 2.0, .2), (.07 * k, 1.985, .195), (.13 * k, 1.95, .17)], [.025, .022, .008], 8), beardm, 'head', name='moustache')
    # staff (grip at origin, vertical)
    wpart('W_main', tube([(0, -.72, 0), (.01, -.2, .005), (-.008, .4, 0), (.01, 1.0, -.005), (0, 1.3, 0)], [.038, .042, .044, .048, .05], 10), wood)
    for y in (-.05, .1, 1.22):
        wpart('W_main', lathe([(.05, y - .02), (.058, y), (.05, y + .02)], seg=12), trim)
    pts = [(math.sin(a) * .23, 1.48 + math.cos(a) * .23, 0) for a in [math.radians(d) for d in range(-150, 151, 25)]]
    wpart('W_main', tube(pts, [.03 if i not in (0, len(pts) - 1) else .012 for i in range(len(pts))], 8), trim)
    wpart('W_main', tube([(0, 1.3, 0), (0, 1.34, 0)], [.05, .06], 10), trim)
    wpart('W_mainOrb', ell((0, 1.48, 0), (.135, .135, .135), 16, 10), glow)
    # ---- tier 2: forked silver staff with a floating ring
    silver = mat('Silver', 0xd8dde6, .25, .9); ebony = mat('Ebony', 0x2c1f1a, .7)
    wpart('W_main2', tube([(0, -.75, 0), (0, .3, 0), (0, 1.05, 0), (0, 1.22, 0)], [.036, .042, .046, .05], 10), ebony)
    for k in (1, -1):
        wpart('W_main2', tube([(0, 1.2, 0), (.12 * k, 1.32, 0), (.2 * k, 1.5, 0), (.14 * k, 1.68, 0), (.04 * k, 1.74, 0)], [.035, .03, .026, .02, .006], 8), silver)
    ring = [(math.cos(a) * .27, 1.48, math.sin(a) * .27) for a in [TAU * i / 24 for i in range(25)]]
    wpart('W_main2', tube(ring, [.014] * 25, 6, cap=False), silver)
    for y in (-.1, .5, 1.1):
        wpart('W_main2', lathe([(.05, y - .025), (.06, y), (.05, y + .025)], seg=12), silver)
    # ---- tier 3: crystal staff with a crown of shards
    crys = mat('Glow3', 0xb8f4ff, .2, 0, 0x8fe8ff); gold = mat('Gold', 0xe0b860, .3, .85)
    wpart('W_main3', tube([(0, -.8, 0), (0, .4, 0), (0, 1.25, 0)], [.04, .046, .052], 10), gold)
    for y in (-.4, .0, .4, .8):
        wpart('W_main3', xf(lathe([(0, .14), (.05, .07), (0, 0)], seg=5), t=(0, y, 0)), crys)
    for i in range(6):
        a = TAU * i / 6
        wpart('W_main3', xf(lathe([(0, .5), (.05, .16), (0, 0)], seg=5), rot=(math.sin(a) * .5, 0, -math.cos(a) * .5), t=(math.cos(a) * .12, 1.3, math.sin(a) * .12)), crys)
    wpart('W_main3', lathe([(.07, 1.24), (.16, 1.3), (.07, 1.36)], seg=12), gold)
    return 'mage'

def build_marksman():
    L = dict(skin=0xd8a27e, main=0x3f6b35, trim=0x9c7a45, dark=0x2b2a22, glow=0xc8ff8a)
    tunic = mat('Main', L['main'], .85); trim = mat('Trim', L['trim'], .7); dark = mat('Dark', L['dark'], .85)
    cloak = mat('Cape', 0x2f5528, .9, cull=False); eye = mat('Eye', 0x1d1a18, .4); hair = mat('Hair', 0x6b4a2a, .9)
    glow = mat('Glow', L['glow'], .4, 0, L['glow'])
    body(L, tunic, dark, mat('Glove', 0x5a4128, .8), foot_mat=trim)
    eyes(eye, hair)
    def tunic_w(v):
        if v[1] > 1.0: return auto_weights([v], ['hips', 'spine', 'chest'])[0]
        s = side_of(v); t = max(0., min(1., (1.0 - v[1]) / .25)) * .5
        return {'hips': 1 - t, 'thigh_' + s: t}
    part(lathe([(.25, .76), (.235, .9), (.215, 1.1), (.228, 1.34), (.24, 1.5), (.235, 1.64), (.18, 1.74), (.1, 1.8)], sz=.72, seg=24), tunic, tunic_w, name='tunic')
    part(lathe([(.225, .98), (.236, 1.04), (.226, 1.1)], sz=.74, seg=24), trim, 'hips', name='belt')
    part(cube((.17, .98, .09), (.09, .1, .06), (0, .5, 0)), trim, 'hips', smooth=False, name='pouch')
    part(tube([(-.2, 1.08, .14), (-.05, 1.3, .18), (.1, 1.52, .175), (.21, 1.7, .1)], [.022] * 4, 8, flat=.4), trim, ('auto', ['spine', 'chest']), name='strap')
    # hood (open at the front) + mantle + mask
    part(lathe([(0, 2.29), (.15, 2.27), (.235, 2.15), (.252, 2.0), (.245, 1.88), (.23, 1.8)], seg=24, a0=math.radians(48), a1=math.radians(312)), cloak, 'head', name='hood')
    part(lathe([(.21, 1.84), (.31, 1.7), (.36, 1.5), (.37, 1.42)], sz=.85, seg=26), cloak, mantle_w, name='mantle')
    part(lathe([(.203, 2.0), (.198, 1.93), (.16, 1.85)], seg=16, a0=math.radians(-75), a1=math.radians(75)), dark, 'head', name='mask')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(tube([(.383 * k, 1.32, .005), (.392 * k, 1.22, .008), (.4 * k, 1.13, .01)], [.06, .062, .056], 12), trim, ('auto', ['forearm_' + s, 'hand_' + s]), name='bracer')
        part(tube([(.149 * k, .42, .0), (.15 * k, .26, -.005), (.15 * k, .12, -.01)], [.076, .072, .068], 12), trim, ('auto', ['shin_' + s, 'foot_' + s]), name='boot')
    # quiver on the back
    qa, qb = Vector((.12, 1.12, -.25)), Vector((.26, 1.74, -.28))
    part(tube([qa, qb], [.085, .095], 12), trim, 'chest', name='quiver')
    for i in range(5):
        o = Vector(((i % 3 - 1) * .03, 0, (i // 3 - .5) * .035))
        top = qb + (qb - qa).normalized() * .14 + o
        part(tube([qb - (qb - qa).normalized() * .05 + o, top], [.008, .008], 5), mat('Shaft', 0x8a6a44, .7), 'chest', name='arrow')
        part(xf(cube((0, 0, 0), (.05, .09, .005)), rot=(0, i * .6, .25), t=tuple(top)), glow, 'chest', smooth=False, name='fletch')
    # recurve bow (left hand): tips at y = +-0.64, belly bulges forward (+z)
    pts = []; rad = []
    for i in range(23):
        t = -1 + 2 * i / 22
        z = .2 * (1 - t * t) - .07 * max(0., abs(t) - .78) / .22
        pts.append((0, .64 * t, z)); rad.append(.045 - .03 * abs(t) ** 1.4)
    wpart('W_off', tube(pts, rad, 8, flat=.7), mat('BowWood', 0x6b4423, .6))
    wpart('W_off', tube([(0, -.09, .2), (0, .09, .2)], [.05, .05], 10), dark)
    for sgn in (1, -1):
        wpart('W_off', ell((0, .64 * sgn, 0), (.022, .022, .022), 6, 4), trim)
    # ---- tier 2: longbow with silver tips; tier 3: crystal-limbed bow (tips stay at y = +-0.64)
    silver = mat('Silver', 0xd8dde6, .25, .9); dwood = mat('DarkWood', 0x3e2414, .6); crys = mat('Glow3', 0xb8ff9a, .2, 0, 0x9cff7a); gold = mat('Gold', 0xe0b860, .3, .85)
    for tier, limbm, tipm in ((2, dwood, silver), (3, crys, gold)):
        pts = []; rad = []
        for i in range(23):
            t = -1 + 2 * i / 22
            z = (.24 if tier == 3 else .16) * (1 - t * t) - (.1 if tier == 3 else .04) * max(0., abs(t) - .7) / .3
            pts.append((0, .64 * t, z)); rad.append((.05 if tier == 3 else .042) - .032 * abs(t) ** 1.3)
        wpart('W_off%d' % tier, tube(pts, rad, 8, flat=.7), limbm)
        wpart('W_off%d' % tier, tube([(0, -.1, pts[11][2]), (0, .1, pts[11][2])], [.052, .052], 10), dark if tier == 2 else gold)
        for sgn in (1, -1):
            wpart('W_off%d' % tier, xf(lathe([(0, .12), (.03, 0)], seg=5), rot=(0 if sgn > 0 else math.pi, 0, 0), t=(0, .62 * sgn, 0)), tipm)
        if tier == 3:
            for sgn in (1, -1):
                wpart('W_off3', xf(lathe([(0, .22), (.04, .08), (0, 0)], seg=5), rot=(-.6 * sgn, 0, 0), t=(0, .3 * sgn, .2)), crys)
    return 'marksman'

def build_assassin():
    L = dict(skin=0xc99372, main=0x3a2a4f, trim=0x9c6be0, dark=0x1d1824, glow=0xd59bff)
    suit = mat('Main', L['main'], .8); trim = mat('Trim', L['trim'], .45, .4); dark = mat('Dark', L['dark'], .85)
    glow = mat('Glow', L['glow'], .3, 0, L['glow']); mask = mat('Mask', 0x1e1a24, .7)
    body(L, suit, dark, dark, foot_mat=dark, head_mat=mask, ears=False)
    eyes(glow, None, 2.055, .175)
    part(lathe([(.21, .9), (.2, 1.1), (.215, 1.34), (.232, 1.5), (.228, 1.64), (.17, 1.74), (.09, 1.8)], sz=.7, seg=24), suit, ('auto', ['hips', 'spine', 'chest']), name='suit')
    for y in (1.0, 1.1, 1.2):
        part(lathe([(.205 + (y - 1) * .05, y - .02), (.215 + (y - 1) * .05, y), (.205 + (y - 1) * .05, y + .02)], sz=.72, seg=24), dark, ('auto', ['hips', 'spine']), name='wrap')
    part(cube((-.17, 1.02, .1), (.08, .09, .05), (0, -.5, 0)), trim, 'hips', smooth=False, name='pouch')
    part(cube((.2, 1.0, .03), (.04, .16, .06)), dark, 'hips', smooth=False, name='sheath')
    # hood with a swept-back point
    part(lathe([(0, 2.3), (.16, 2.28), (.24, 2.15), (.255, 2.0), (.25, 1.88), (.23, 1.8)], seg=24, a0=math.radians(42), a1=math.radians(318)), suit, 'head', name='hood')
    part(tube([(0, 2.25, -.1), (0, 2.27, -.22), (0, 2.22, -.34), (0, 2.12, -.42)], [.12, .08, .04, .004], 12), suit, 'head', name='hoodtip')
    part(lathe([(.2, 1.86), (.28, 1.76), (.3, 1.7)], sz=.85, seg=24), suit, ('auto', ['chest', 'neck']), name='cowl')
    # scarf + trailing tail
    part(lathe([(.11, 1.76), (.15, 1.8), (.13, 1.87), (.1, 1.9)], seg=20), trim, ('auto', ['neck', 'chest']), name='scarf')
    part(tube([(.04, 1.82, -.12), (.1, 1.72, -.26), (.15, 1.55, -.33), (.18, 1.35, -.37), (.2, 1.18, -.38)], [.06, .055, .05, .04, .02], 10, flat=.35), trim,
         ('auto', ['chest', 'spine']), name='tail')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(xf(lathe([(0, .14), (.045, 0)], seg=6), rot=(0, 0, -.6 * k), t=(.36 * k, 1.75, 0)), trim, 'upperarm_' + s, name='spike')
        part(xf(lathe([(0, .1), (.035, 0)], seg=6), rot=(0, 0, -.9 * k), t=(.3 * k, 1.77, -.06)), trim, 'upperarm_' + s, name='spike2')
        for y in (1.18, 1.26):
            part(lathe([(.055, -.015), (.062, 0), (.055, .015)], c=(.393 * k, y, .007), seg=12), dark, 'forearm_' + s, name='band')
        for y in (.3, .4):
            part(lathe([(.075, -.015), (.082, 0), (.075, .015)], c=(.149 * k, y, 0), seg=12), trim, 'shin_' + s, name='legwrap')
    # curved daggers
    steel = mat('Metal', 0xdde3ee, .2, .85)
    for g in ('W_main', 'W_off'):
        st = []
        for i in range(9):
            t = i / 8
            st.append((.1 + t * .66, .055 * (1 - t ** 2.2) + .004, .014 * (1 - t) + .003, 0, .07 * t * t))
        wpart(g, blade(st), steel, False)
        wpart(g, blade([(.12, .006, .018, 0, 0), (.6, .004, .016, 0, .05)]), glow, False)
        wpart(g, tube([(-.13, 0, .07), (-.04, 0, .075), (.04, 0, .075), (.13, 0, .07)], [.012, .02, .02, .012], 8), trim)
        for k in (1, -1):
            wpart(g, tube([(.13 * k, 0, .07), (.15 * k, 0, .13)], [.012, .002], 6), trim)
        wpart(g, tube([(0, 0, -.12), (0, 0, .06)], [.034, .036], 10), dark)
        wpart(g, ell((0, 0, -.15), (.04, .04, .045), 8, 6), glow)
    # ---- tier 2: serrated long daggers; tier 3: crystal fangs
    blood = mat('Glow2', 0xff4a5a, .3, 0, 0xff3a4a); crys = mat('Glow3', 0xe0b0ff, .2, 0, 0xc890ff); gold = mat('Gold', 0xe0b860, .3, .85)
    for g in ('W_main2', 'W_off2'):
        st = []
        for i in range(13):
            t = i / 12
            st.append((.1 + t * .82, (.062 * (1 - t ** 2) + .004) * (1.15 if i % 2 else .9), .015 * (1 - t) + .003, 0, .05 * t * t))
        wpart(g, blade(st), steel, False)
        wpart(g, blade([(.12, .007, .019, 0, 0), (.72, .004, .016, 0, .04)]), blood, False)
        wpart(g, tube([(-.15, 0, .07), (0, 0, .08), (.15, 0, .07)], [.014, .022, .014], 8), dark)
        wpart(g, tube([(0, 0, -.13), (0, 0, .06)], [.034, .036], 10), dark)
        wpart(g, ell((0, 0, -.16), (.042, .042, .045), 8, 6), blood)
    for g in ('W_main3', 'W_off3'):
        st = []
        for i in range(9):
            t = i / 8
            st.append((.1 + t * .78, .07 * (1 - t ** 1.8) + .005, .02 * (1 - t) + .004, 0, .09 * t * t))
        wpart(g, blade(st), crys, False)
        wpart(g, tube([(-.17, .02, .05), (-.06, 0, .08), (.06, 0, .08), (.17, .02, .05)], [.01, .022, .022, .01], 8), gold)
        wpart(g, tube([(0, 0, -.13), (0, 0, .06)], [.034, .036], 10), mat('Obsidian', 0x2a2438, .25, .6))
        wpart(g, xf(lathe([(0, .1), (.04, .04), (0, 0)], seg=5), rot=(math.pi / 2, 0, 0), t=(0, 0, -.13)), crys)
    return 'assassin'

# ---------------------------------------------------------------- assembly + export
def make_object(name, V, F, m, smooth):
    me = bpy.data.meshes.new(name)
    me.from_pydata([g2b(v) for v in V], [], [tuple(f) for f in F])
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob

def build(fn):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear(); PARTS.clear(); WEAPONS.clear()
    key = fn()
    # armature
    arm = bpy.data.armatures.new('Rig'); rig = bpy.data.objects.new('Rig', arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (h, t, par) in BONES.items():
        eb = arm.edit_bones.new(name); eb.head = g2b(h); eb.tail = g2b(t)
    for name, (h, t, par) in BONES.items():
        if par: arm.edit_bones[name].parent = arm.edit_bones[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    # skinned parts
    obs = []
    for (name, V, F, m, W, smooth) in PARTS:
        ob = make_object(name, V, F, m, smooth)
        # vertex order is preserved by remove_doubles only when no doubles; rebuild weights by nearest original vertex
        groups = {b: ob.vertex_groups.new(name=b) for b in DEFORM}
        orig = [Vector(g2b(v)) for v in V]
        for vi, v in enumerate(ob.data.vertices):
            best = min(range(len(orig)), key=lambda i: (orig[i] - v.co).length_squared) if vi >= len(orig) or (orig[vi] - v.co).length > 1e-5 else vi
            for b, w in W[best].items():
                if w > .002: groups[b].add([vi], w, 'REPLACE')
        obs.append(ob)
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, selected_objects=obs):
        bpy.ops.object.join()
    hero = obs[0]; hero.name = 'Hero'
    hero.parent = rig
    mod = hero.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
    # weapons (unskinned, at origin)
    wobs = {}
    for (g, VF, m, smooth) in WEAPONS:
        ob = make_object(g + '_p', VF[0], VF[1], m, smooth)
        wobs.setdefault(g, []).append(ob)
    for g, lst in wobs.items():
        if len(lst) > 1:
            with bpy.context.temp_override(active_object=lst[0], selected_editable_objects=lst, selected_objects=lst):
                bpy.ops.object.join()
        lst[0].name = g
    path = os.path.join(OUT, key + '.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_skins=True, export_animations=False,
                              export_apply=False, export_yup=True, export_normals=True, export_texcoords=False,
                              export_materials='EXPORT')
    tris = sum(len(p.vertices) - 2 for o in bpy.data.objects if o.type == 'MESH' for p in o.data.polygons)
    print('BUILT', key, os.path.getsize(path), 'bytes', tris, 'tris')

if __name__ == '__main__':
    which = sys.argv[sys.argv.index('--') + 2:] if '--' in sys.argv else []
    for fn in (build_warrior, build_mage, build_marksman, build_assassin):
        if not which or fn.__name__[6:] in which:
            build(fn)
