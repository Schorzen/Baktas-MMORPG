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
        'hips': ((0, 1.08, 0), (0, 1.28, 0), 'root'),
        'spine': ((0, 1.28, 0), (0, 1.5, 0), 'hips'),
        'chest': ((0, 1.5, 0), (0, 1.78, 0), 'spine'),
        'neck': ((0, 1.78, 0), (0, 1.92, .005), 'chest'),
        'head': ((0, 1.92, .005), (0, 2.2, .005), 'neck'),
    }
    for s, k in SIDE.items():
        B['upperarm_' + s] = ((.215 * k, 1.765, 0), (.25 * k, 1.43, -.01), 'chest')
        B['forearm_' + s] = ((.25 * k, 1.43, -.01), (.27 * k, 1.12, .02), 'upperarm_' + s)
        B['hand_' + s] = ((.27 * k, 1.12, .02), (.265 * k, .96, .03), 'forearm_' + s)
        B['fingers_' + s] = ((.268 * k, 1.005, .03), (.255 * k, .95, .03), 'hand_' + s)
        B['thigh_' + s] = ((.1 * k, 1.1, 0), (.11 * k, .6, .015), 'hips')
        B['shin_' + s] = ((.11 * k, .6, .015), (.115 * k, .1, -.01), 'thigh_' + s)
        B['foot_' + s] = ((.115 * k, .1, -.01), (.115 * k, .03, .15), 'shin_' + s)
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
    t = max(0., min(1., (abs(v[0]) - .15) / .12)) * .22
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

def hand(k, m, s):
    """Palm + four curled fingers + thumb, shaped to close around a grip."""
    x = .268 * k
    part(ell((x, 1.05, .03), (.022, .048, .042), 10, 8), m, 'hand_' + s, name='palm')
    for i, (z, ln) in enumerate(((.058, 1.0), (.038, 1.05), (.018, 1.0), (-.001, .85))):
        y0 = 1.005
        pts = [(x, y0, z), (x - .004 * k, y0 - .03 * ln, z), (x - .018 * k, y0 - .052 * ln, z), (x - .034 * k, y0 - .05 * ln, z + .002), (x - .042 * k, y0 - .036 * ln, z + .002)]
        def fw(v, z=z):
            t = max(0., min(1., math.hypot(v[0] - x, v[1] - 1.012) / .045))
            return {'hand_' + s: 1 - t, 'fingers_' + s: t} if t > 0 else {'hand_' + s: 1.}
        part(tube(pts, [.0115, .011, .0105, .0098, .008], 6), m, fw, name='finger')
    part(tube([(x - .006 * k, 1.07, .062), (x - .016 * k, 1.04, .076), (x - .03 * k, 1.015, .07), (x - .038 * k, 1.0, .058)], [.013, .012, .011, .009], 6), m, 'hand_' + s, name='thumb')

def body(look, arm_mat, leg_mat, hand_mat, foot_mat=None, head_mat=None, ears=True, torso_mat=None):
    skin = mat('Skin', look['skin'], .62)
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        arm = tube([(.215 * k, 1.775, 0), (.232 * k, 1.6, -.005), (.25 * k, 1.43, -.01), (.262 * k, 1.27, .005), (.27 * k, 1.13, .02)],
                   [.058, .053, .043, .039, .031], 14)
        part(arm, arm_mat, ('auto', ['chest', 'upperarm_' + s, 'forearm_' + s, 'hand_' + s]), name='arm')
        hand(k, hand_mat, s)
        leg = tube([(.1 * k, 1.12, 0), (.105 * k, .86, .008), (.11 * k, .6, .015), (.113 * k, .35, .0), (.115 * k, .12, -.01)],
                   [.084, .07, .053, .049, .038], 14)
        part(leg, leg_mat, ('auto', ['hips', 'thigh_' + s, 'shin_' + s]), name='leg')
        part(ell((.115 * k, .05, .045), (.046, .05, .11), 12, 8), foot_mat or leg_mat, ('auto', ['shin_' + s, 'foot_' + s]), name='foot')
        part(ell((.2 * k, 1.75, 0), (.072, .068, .072), 12, 8), arm_mat, ('auto', ['chest', 'upperarm_' + s]), name='shoulder')
    part(lathe([(0, 1.05), (.12, 1.06), (.162, 1.12), (.158, 1.22), (.142, 1.34), (.148, 1.44), (.172, 1.56), (.186, 1.66), (.182, 1.73), (.148, 1.79), (.07, 1.83), (0, 1.84)],
               sz=.66, seg=22), torso_mat or arm_mat, ('auto', ['hips', 'spine', 'chest']), name='trunk')
    hm = head_mat or skin
    part(ell((0, 2.065, .005), (.108, .132, .122), 22, 14), hm, 'head', name='head')
    part(ell((0, 1.975, .03), (.09, .072, .098), 16, 10), hm, 'head', name='jaw')
    part(tube([(0, 1.77, 0), (0, 1.94, .012)], [.048, .044], 12), hm if head_mat else skin, ('auto', ['neck', 'head', 'chest']), name='neck')
    if not head_mat:
        part(ell((0, 2.095, .098), (.088, .02, .032), 12, 6), skin, 'head', name='brow')
        part(tube([(0, 2.065, .118), (0, 2.03, .143), (0, 2.015, .138)], [.016, .017, .01], 8), skin, 'head', name='nose')
        part(ell((0, 1.985, .113), (.032, .01, .012), 8, 5), mat('Lip', 0xa8645a, .6), 'head', name='mouth')
        if ears:
            for k in (1, -1):
                part(ell((.108 * k, 2.055, -.01), (.016, .034, .024), 8, 6), skin, 'head', name='ear')

def eyes(m, brow=None, y=2.066, z=.104):
    for k in (1, -1):
        part(ell((.04 * k, y, z), (.019, .011, .009), 10, 6), m, 'head', name='eye')
        if brow is not None:
            part(xf(ell((0, 0, 0), (.026, .007, .009), 8, 5), rot=(0, 0, -.12 * k), t=(.043 * k, y + .029, z + .008)), brow, 'head', name='brow')

def torso(prof, m, sz=.7, name='torso', a0=0., a1=TAU, wfun=None):
    part(lathe(prof, sz=sz, seg=24, a0=a0, a1=a1), m, wfun or ('auto', ['hips', 'spine', 'chest']), name=name)

# ---------------------------------------------------------------- weapon objects
WEAPONS = []
def wpart(group, VF, m, smooth=True):
    WEAPONS.append((group, VF, m, smooth))

# ---------------------------------------------------------------- classes
def build_warrior():
    L = dict(skin=0xc98f6c, main=0x8d96a1, trim=0xb8924e, dark=0x34383f, cape=0x7e2a25)
    steel = mat('Main', L['main'], .32, .75); trim = mat('Trim', L['trim'], .35, .8); dark = mat('Dark', L['dark'], .85)
    leather = mat('Leather', 0x4a3424, .75); cape = mat('Cape', L['cape'], .85, cull=False); hair = mat('Hair', 0x4a3020, .9)
    eye = mat('Eye', 0x1d1a18, .4)
    body(L, dark, dark, leather, foot_mat=leather)
    eyes(eye, hair)
    part(lathe([(.172, 1.13), (.176, 1.24), (.164, 1.36), (.18, 1.46), (.205, 1.58), (.214, 1.68), (.203, 1.75), (.152, 1.81), (.08, 1.845)], sz=.72, seg=26), steel,
         ('auto', ['hips', 'spine', 'chest']), name='plate')
    for (r, y) in ((.18, 1.17), (.212, 1.74)):
        part(lathe([(r, y - .018), (r + .008, y), (r, y + .018)], sz=.73, seg=26), trim, ('auto', ['hips', 'spine', 'chest']), name='band')
    part(lathe([(.2, 1.5), (.208, 1.52), (.2, 1.54)], sz=.73, seg=26), trim, ('auto', ['spine', 'chest']), name='band2')
    part(lathe([(.172, 1.06), (.181, 1.11), (.173, 1.15)], sz=.75, seg=24), leather, 'hips', name='belt')
    part(cube((0, 1.105, .132), (.07, .06, .02)), trim, 'hips', smooth=False, name='buckle')
    def skirt_w(v):
        s = side_of(v); t = max(0., min(1., (1.08 - v[1]) / .28)) * .55
        return {'hips': 1 - t, 'thigh_' + s: t}
    for i in range(8):
        a0 = i / 8 * TAU + .1; a1 = a0 + TAU / 8 - .12
        part(lathe([(.18, 1.08), (.2, .96), (.215, .84)], sz=.8, seg=3, a0=a0, a1=a1), steel, skirt_w, name='tasset')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        for j, (r, dy) in enumerate(((.115, 0), (.1, -.06), (.088, -.11))):
            part(xf(lathe([(0, .07), (r * .7, .06), (r, .02), (r * 1.02, 0), (r, -.02)], sz=1.0, seg=16), rot=(0, 0, -.45 * k), t=(.235 * k + .015 * j * k, 1.775 + dy, 0)),
                 steel if j == 0 else dark, ('auto', ['chest', 'upperarm_' + s]), name='pauldron')
        part(xf(lathe([(.117, -.02), (.123, -.03), (.117, -.04)], seg=16), rot=(0, 0, -.45 * k), t=(.235 * k, 1.775, 0)), trim, ('auto', ['chest', 'upperarm_' + s]), name='rim')
        part(tube([(.256 * k, 1.3, .0), (.264 * k, 1.21, .01), (.27 * k, 1.13, .02)], [.044, .046, .04], 12), steel, ('auto', ['forearm_' + s, 'hand_' + s]), name='vambrace')
        part(tube([(.24 * k, 1.58, -.008), (.246 * k, 1.47, -.01)], [.056, .05], 12), steel, 'upperarm_' + s, name='rerebrace')
        part(tube([(.113 * k, .42, 0), (.115 * k, .26, -.004), (.115 * k, .11, -.01)], [.058, .056, .05], 12), leather, ('auto', ['shin_' + s, 'foot_' + s]), name='boot')
        part(ell((.115 * k, .05, .05), (.055, .055, .125), 12, 8), leather, ('auto', ['shin_' + s, 'foot_' + s]), name='bootfoot')
        part(lathe([(.06, .41), (.066, .43), (.06, .45)], c=(.113 * k, 0, 0), seg=12), trim, 'shin_' + s, name='cuff')
        part(xf(lathe([(0, .04), (.045, .034), (.064, 0), (.045, -.03)], seg=12), t=(.11 * k, .6, .055)), steel, 'shin_' + s, name='knee')
        part(tube([(.105 * k, .98, .02), (.108 * k, .76, .03)], [.075, .062], 12), steel, 'thigh_' + s, name='cuisse')
    part(lathe([(0, 2.225), (.07, 2.218), (.118, 2.17), (.135, 2.1), (.136, 2.04)], sz=1.08, seg=24), steel, 'head', name='helm')
    part(lathe([(.138, 2.025), (.144, 2.04), (.138, 2.055)], sz=1.08, seg=24), trim, 'head', name='helm_rim')
    part(lathe([(.006, .02), (.0, -.0)], c=(0, 2.22, 0), seg=4), trim, 'head', name='crest')
    part(cube((0, 2.035, .143), (.022, .085, .02)), steel, 'head', smooth=False, name='nasal')
    for k in (1, -1):
        part(cube((.118 * k, 1.985, .055), (.022, .11, .08), (0, .35 * k, 0)), steel, 'head', smooth=False, name='cheek')
        part(tube([(.13 * k, 2.13, 0), (.19 * k, 2.16, .01), (.245 * k, 2.22, .02), (.265 * k, 2.31, .03)], [.03, .024, .015, .003], 10),
             mat('Horn', 0xe3d8c0, .5), 'head', name='horn')
    part(ell((0, 1.945, .075), (.082, .05, .058), 14, 8), hair, 'head', name='beard')
    part(tube([(-.035, 1.99, .118), (0, 1.995, .124), (.035, 1.99, .118)], [.009, .011, .009], 6), hair, 'head', name='moustache')
    V = []; F = []; cols, rows = 7, 10
    for i in range(rows):
        t = i / (rows - 1)
        for j in range(cols):
            u = j / (cols - 1) - .5
            w = .42 + .2 * t
            V.append((u * w, 1.78 - t * 1.05, -.155 - .06 * t - .025 * math.cos(u * math.pi) - .015 * math.sin(t * 3 + u * 2)))
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            F.append((a, a + 1, a + cols + 1, a + cols))
    def cape_w(v):
        t = (1.78 - v[1]) / 1.05
        if t < .3: return {'chest': 1.}
        if t < .65: return {'chest': 1 - (t - .3) / .35 * .6, 'spine': (t - .3) / .35 * .6}
        return {'spine': .45, 'hips': .55}
    part((V, F), cape, cape_w, name='cape')
    for k in (1, -1):
        part(ell((.17 * k, 1.765, -.05), (.03, .03, .02), 8, 6), trim, 'chest', name='clasp')
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
    L = dict(skin=0xd9a587, main=0x2b4485, trim=0xc9a95c, dark=0x1c2039, glow=0x7fd8ff)
    robe = mat('Main', L['main'], .85); trim = mat('Trim', L['trim'], .35, .75); dark = mat('Dark', L['dark'], .85)
    beardm = mat('Hair', 0xd8d3c8, .95); eye = mat('Eye', 0x1d1a18, .4); wood = mat('Wood', 0x5b3b24, .8)
    glow = mat('Glow', L['glow'], .3, 0, L['glow'])
    body(L, robe, dark, mat('Skin', L['skin'], .62), foot_mat=dark)
    eyes(eye, beardm)
    def robe_w(v):
        if v[1] > 1.2: return auto_weights([v], ['hips', 'spine', 'chest'])[0]
        s = side_of(v); t = max(0., min(1., (1.12 - v[1]) / .85)) * .5 * min(1., abs(v[0]) / .09)
        return {'hips': 1 - t, 'thigh_' + s: t}
    part(lathe([(.08, 1.845), (.15, 1.8), (.198, 1.72), (.2, 1.56), (.168, 1.4), (.172, 1.22), (.212, .98), (.27, .66), (.325, .32), (.35, .05)], sz=.82, seg=30),
         robe, robe_w, name='robe')
    for i in range(6):
        a = i / 6 * TAU + .3
        part(tube([(math.sin(a) * .17, 1.15, math.cos(a) * .17 * .82), (math.sin(a) * .3, .5, math.cos(a) * .3 * .82), (math.sin(a) * .345, .07, math.cos(a) * .345 * .82)],
                  [.006, .01, .012], 5), dark, robe_w, name='fold')
    part(lathe([(.348, .09), (.36, .065), (.355, .03), (.343, .045)], sz=.82, seg=30), trim, robe_w, name='hem')
    part(lathe([(.168, 1.25), (.178, 1.29), (.168, 1.33)], sz=.83, seg=24), trim, ('auto', ['hips', 'spine']), name='sash')
    part(tube([(.06, 1.27, .14), (.08, 1.12, .155), (.09, .98, .16)], [.018, .016, .012], 6, flat=.4), trim, robe_w, name='sashtail')
    part(xf(lathe([(0, .03), (.03, 0), (0, -.03)], seg=6), t=(0, 1.29, .147)), glow, 'spine', name='gem')
    part(lathe([(.14, 1.82), (.22, 1.75), (.25, 1.64), (.245, 1.59)], sz=.82, seg=26), dark, mantle_w, name='mantle')
    part(lathe([(.247, 1.595), (.255, 1.61), (.247, 1.625)], sz=.82, seg=26), trim, mantle_w, name='mantle_rim')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(tube([(.25 * k, 1.44, -.01), (.258 * k, 1.32, .0), (.266 * k, 1.19, .012), (.27 * k, 1.13, .02)], [.048, .054, .068, .076], 14, cap=False), robe,
             ('auto', ['upperarm_' + s, 'forearm_' + s]), name='sleeve')
        part(lathe([(.074, -.012), (.08, 0), (.074, .012)], c=(.27 * k, 1.13, .02), seg=14), trim, 'forearm_' + s, name='cuff')
    part(lathe([(0, 2.185), (.2, 2.18), (.305, 2.155), (.312, 2.142), (.2, 2.16), (0, 2.165)], seg=30), dark, 'head', name='brim')
    part(tube([(0, 2.17, -.01), (-.005, 2.34, -.02), (-.025, 2.5, -.05), (-.07, 2.63, -.11), (-.13, 2.69, -.17)], [.135, .1, .062, .03, .003], 18), robe, 'head', name='hat')
    part(lathe([(.134, 2.18), (.137, 2.205), (.128, 2.23)], seg=24), trim, 'head', name='hatband')
    part(tube([(0, 1.965, .1), (0, 1.88, .122), (0, 1.79, .118), (0, 1.7, .096), (0, 1.63, .078)], [.068, .064, .048, .025, .002], 14, flat=.6), beardm,
         ('auto', ['head', 'neck']), name='beard')
    for k in (1, -1):
        part(tube([(0, 1.995, .126), (.04 * k, 1.988, .122), (.075 * k, 1.965, .1)], [.012, .011, .004], 8), beardm, 'head', name='moustache')
        part(ell((.07 * k, 2.1, -.02), (.04, .045, .07), 8, 6), beardm, 'head', name='sidehair')
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
    L = dict(skin=0xc99474, main=0x3a6332, trim=0x8c6b3c, dark=0x2a2922, glow=0xc8ff8a)
    tunic = mat('Main', L['main'], .88); trim = mat('Trim', L['trim'], .75); dark = mat('Dark', L['dark'], .88)
    cloak = mat('Cape', 0x2a4d25, .92, cull=False); eye = mat('Eye', 0x1d1a18, .4); hair = mat('Hair', 0x5a3c22, .9)
    glow = mat('Glow', L['glow'], .4, 0, L['glow'])
    body(L, tunic, dark, mat('Glove', 0x5a4128, .8), foot_mat=trim)
    eyes(eye, hair)
    part(ell((0, 2.1, -.015), (.114, .1, .125), 14, 8), hair, 'head', name='hair')
    def tunic_w(v):
        if v[1] > 1.12: return auto_weights([v], ['hips', 'spine', 'chest'])[0]
        s = side_of(v); t = max(0., min(1., (1.1 - v[1]) / .22)) * .55
        return {'hips': 1 - t, 'thigh_' + s: t}
    part(lathe([(.19, .9), (.182, 1.02), (.168, 1.15), (.162, 1.3), (.17, 1.44), (.194, 1.58), (.2, 1.7), (.158, 1.79), (.08, 1.845)], sz=.72, seg=26), tunic, tunic_w, name='tunic')
    part(lathe([(.17, 1.09), (.178, 1.13), (.17, 1.17)], sz=.74, seg=24), trim, 'hips', name='belt')
    part(cube((.13, 1.08, .07), (.07, .085, .05), (0, .55, 0)), trim, 'hips', smooth=False, name='pouch')
    part(cube((-.12, 1.07, .08), (.06, .07, .045), (0, -.55, 0)), trim, 'hips', smooth=False, name='pouch2')
    part(tube([(-.16, 1.18, .1), (-.04, 1.38, .132), (.08, 1.58, .13), (.17, 1.76, .07)], [.016] * 4, 8, flat=.4), trim, ('auto', ['spine', 'chest']), name='strap')
    part(lathe([(0, 2.235), (.1, 2.225), (.152, 2.15), (.162, 2.04), (.158, 1.93), (.15, 1.85)], seg=26, a0=math.radians(52), a1=math.radians(308)), cloak, 'head', name='hood')
    part(tube([(0, 2.2, -.1), (0, 2.18, -.18), (0, 2.08, -.22)], [.07, .05, .02], 10), cloak, 'head', name='hoodtail')
    part(lathe([(.15, 1.86), (.235, 1.77), (.265, 1.62), (.27, 1.55)], sz=.85, seg=28), cloak, mantle_w, name='mantle')
    part(lathe([(.122, 2.005), (.118, 1.96), (.1, 1.9), (.085, 1.86)], seg=16, a0=math.radians(-80), a1=math.radians(80)), dark, 'head', name='mask')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(tube([(.256 * k, 1.32, 0), (.264 * k, 1.22, .01), (.27 * k, 1.135, .02)], [.04, .042, .036], 12), trim, ('auto', ['forearm_' + s, 'hand_' + s]), name='bracer')
        for y in (1.2, 1.26):
            part(lathe([(.043, -.006), (.047, 0), (.043, .006)], c=(.264 * k, y, .01), seg=10), dark, 'forearm_' + s, name='lace')
        part(tube([(.113 * k, .44, 0), (.115 * k, .27, -.004), (.115 * k, .11, -.01)], [.056, .053, .048], 12), trim, ('auto', ['shin_' + s, 'foot_' + s]), name='boot')
        part(lathe([(.058, .43), (.07, .47), (.064, .5)], c=(.113 * k, 0, 0), seg=12), trim, 'shin_' + s, name='bootfold')
    qa, qb = Vector((.08, 1.32, -.165)), Vector((.18, 1.86, -.195))
    part(tube([qa, qb], [.062, .07], 12), trim, 'chest', name='quiver')
    part(lathe([(.072, -.01), (.076, 0), (.072, .01)], c=tuple(qb - (qb - qa).normalized() * .03), seg=12), dark, 'chest', name='quiverrim')
    for i in range(5):
        o = Vector(((i % 3 - 1) * .022, 0, (i // 3 - .5) * .026))
        top = qb + (qb - qa).normalized() * .13 + o
        part(tube([qb - (qb - qa).normalized() * .05 + o, top], [.006, .006], 5), mat('Shaft', 0x8a6a44, .7), 'chest', name='arrow')
        part(xf(cube((0, 0, 0), (.035, .07, .004)), rot=(0, i * .6, .25), t=tuple(top)), glow, 'chest', smooth=False, name='fletch')
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
    L = dict(skin=0xb98468, main=0x35284a, trim=0x8c62cc, dark=0x1b1622, glow=0xd59bff)
    suit = mat('Main', L['main'], .82); trim = mat('Trim', L['trim'], .5, .35); dark = mat('Dark', L['dark'], .88)
    glow = mat('Glow', L['glow'], .3, 0, L['glow']); mask = mat('Mask', 0x1c1822, .75)
    body(L, suit, dark, dark, foot_mat=dark, head_mat=mask, ears=False)
    eyes(glow, None, 2.066, .108)
    part(lathe([(.17, .98), (.16, 1.12), (.152, 1.3), (.162, 1.44), (.186, 1.58), (.19, 1.7), (.15, 1.79), (.07, 1.845)], sz=.7, seg=26), suit, ('auto', ['hips', 'spine', 'chest']), name='suit')
    for y in (1.18, 1.25, 1.32):
        r = .152 + (y - 1.18) * .02
        part(lathe([(r, y - .016), (r + .008, y), (r, y + .016)], sz=.72, seg=24), dark, ('auto', ['hips', 'spine']), name='wrap')
    part(cube((-.13, 1.1, .07), (.06, .07, .04), (0, -.55, 0)), trim, 'hips', smooth=False, name='pouch')
    part(cube((.15, 1.06, .02), (.032, .14, .05), (0, 0, .15)), dark, 'hips', smooth=False, name='sheath')
    def flap_w(v):
        s = side_of(v); t = max(0., min(1., (1.08 - v[1]) / .25)) * .5
        return {'hips': 1 - t, 'thigh_' + s: t}
    for a0 in (math.radians(-35), math.radians(145)):
        part(lathe([(.165, 1.12), (.18, .98), (.19, .8)], sz=.8, seg=4, a0=a0, a1=a0 + math.radians(70)), suit, flap_w, name='flap')
    part(lathe([(0, 2.24), (.1, 2.23), (.155, 2.15), (.165, 2.04), (.16, 1.93), (.15, 1.85)], seg=26, a0=math.radians(46), a1=math.radians(314)), suit, 'head', name='hood')
    part(tube([(0, 2.2, -.08), (0, 2.22, -.17), (0, 2.17, -.26), (0, 2.08, -.32)], [.08, .055, .028, .003], 12), suit, 'head', name='hoodtip')
    part(lathe([(.14, 1.88), (.2, 1.8), (.225, 1.74)], sz=.85, seg=26), suit, ('auto', ['chest', 'neck']), name='cowl')
    part(lathe([(.07, 1.78), (.098, 1.81), (.088, 1.87), (.07, 1.9)], seg=20), trim, ('auto', ['neck', 'chest']), name='scarf')
    part(tube([(.03, 1.84, -.08), (.07, 1.74, -.18), (.1, 1.58, -.23), (.12, 1.4, -.26), (.135, 1.24, -.27)], [.04, .037, .033, .027, .014], 10, flat=.32), trim,
         ('auto', ['chest', 'spine']), name='tail')
    for k in (1, -1):
        s = 'R' if k > 0 else 'L'
        part(xf(lathe([(0, .1), (.03, 0)], seg=6), rot=(0, 0, -.6 * k), t=(.24 * k, 1.8, 0)), trim, 'upperarm_' + s, name='spike')
        part(xf(lathe([(0, .07), (.024, 0)], seg=6), rot=(0, 0, -.9 * k), t=(.2 * k, 1.81, -.045)), trim, 'upperarm_' + s, name='spike2')
        for y in (1.19, 1.26, 1.33):
            part(lathe([(.04, -.01), (.045, 0), (.04, .01)], c=(.262 * k, y, .008), seg=12), dark, 'forearm_' + s, name='band')
        for y in (.3, .38, .46):
            part(lathe([(.052, -.01), (.058, 0), (.052, .01)], c=(.114 * k, y, 0), seg=12), trim, 'shin_' + s, name='legwrap')
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

def armor_tiers():
    """Extra armor pieces shown when rare/epic (tier 2) or legendary (tier 3) armor is equipped."""
    for tier, pre in ((2, 'A2_'), (3, 'A3_')):
        if tier == 2:
            plate = mat('Armor2', 0xcfd6e0, .28, .85); edge = mat('Armor2Trim', 0xe0b860, .3, .85); gem = mat('Armor2Gem', 0x55a8ff, .3, 0, 0x3d8fff)
            pr, spikes = .125, 0
        else:
            plate = mat('Armor3', 0x2a2438, .25, .7); edge = mat('Armor3Trim', 0xe0b860, .3, .85); gem = mat('Armor3Gem', 0xffae42, .3, 0, 0xff9a1f)
            pr, spikes = .15, 3
        cw = ('auto', ['spine', 'chest'])
        part(lathe([(.215, 1.5), (.238, 1.6), (.24, 1.7), (.2, 1.775)], sz=.8, seg=14, a0=math.radians(-78), a1=math.radians(78)), plate, cw, name=pre + 'chest')
        part(lathe([(.218, 1.49), (.228, 1.5), (.218, 1.51)], sz=.8, seg=14, a0=math.radians(-78), a1=math.radians(78)), edge, cw, name=pre + 'chestrim')
        part(ell((0, 1.64, .19), (.04, .05, .02), 8, 6), gem, 'chest', name=pre + 'gem')
        if tier == 3:
            for k in (1, -1):
                part(tube([(.03 * k, 1.66, .192), (.12 * k, 1.72, .17)], [.008, .008], 5), gem, 'chest', name=pre + 'rune')
                part(tube([(.03 * k, 1.62, .192), (.11 * k, 1.56, .175)], [.008, .008], 5), gem, 'chest', name=pre + 'rune')
            part(lathe([(.12, 1.8), (.175, 1.9), (.165, 1.95)], seg=12, a0=math.radians(95), a1=math.radians(265)), plate, 'chest', name=pre + 'collar')
            part(lathe([(.168, 1.945), (.176, 1.955), (.168, 1.965)], seg=12, a0=math.radians(95), a1=math.radians(265)), edge, 'chest', name=pre + 'collarrim')
        else:
            part(lathe([(.1, 1.8), (.13, 1.84), (.11, 1.875)], seg=16), plate, ('auto', ['neck', 'chest']), name=pre + 'gorget')
        part(cube((0, 1.11, .14), (.11, .09, .03)), plate, 'hips', smooth=False, name=pre + 'beltplate')
        part(ell((0, 1.11, .158), (.022, .022, .012), 6, 4), gem, 'hips', name=pre + 'beltgem')
        for k in (1, -1):
            s = 'R' if k > 0 else 'L'
            sw = ('auto', ['chest', 'upperarm_' + s])
            T = dict(rot=(0, 0, -.5 * k), t=(.25 * k, 1.8, 0))
            part(xf(lathe([(0, .085), (pr * .65, .07), (pr, .02), (pr * 1.03, -.01), (pr * .98, -.035)], seg=14), **T), plate, sw, name=pre + 'pauldron')
            part(xf(lathe([(pr * 1.0, -.03), (pr * 1.06, -.04), (pr * 1.0, -.05)], seg=14), **T), edge, sw, name=pre + 'pauldronrim')
            part(xf(lathe([(0, -.04), (pr * .8, -.06), (pr * .86, -.1), (pr * .8, -.13)], seg=14), rot=(0, 0, -.5 * k), t=(.27 * k, 1.78, 0)), plate, sw, name=pre + 'pauldron2')
            for j in range(spikes):
                part(xf(lathe([(0, .2 - j * .04), (.03, .04), (0, 0)], seg=5), rot=(-.5 + j * .5, 0, -.75 * k), t=((.3 + .02 * j) * k, 1.84, -.07 + j * .07)), gem, sw, name=pre + 'spike')
            part(tube([(.255 * k, 1.31, 0), (.264 * k, 1.21, .01), (.27 * k, 1.14, .02)], [.05, .052, .046], 10), plate, ('auto', ['forearm_' + s, 'hand_' + s]), name=pre + 'bracer')
            part(lathe([(.054, -.012), (.06, 0), (.054, .012)], c=(.258 * k, 1.29, .003), seg=10), edge, 'forearm_' + s, name=pre + 'bracerrim')
            part(tube([(.112 * k, .46, .01), (.114 * k, .3, .0), (.115 * k, .16, -.008)], [.066, .064, .056], 10), plate, ('auto', ['shin_' + s, 'foot_' + s]), name=pre + 'greave')
            part(xf(lathe([(0, .05), (.05, .04), (.07, 0), (.05, -.035)], seg=10), t=(.11 * k, .6, .06)), edge if tier == 2 else gem, 'shin_' + s, name=pre + 'knee')

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
    if key in ('warrior', 'mage', 'marksman', 'assassin'):
        armor_tiers()
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
        obs.append((name, ob))
    sets = {}
    for name, ob in obs:
        sets.setdefault('Armor2' if name.startswith('A2_') else 'Armor3' if name.startswith('A3_') else 'Hero', []).append(ob)
    for gname, lst in sets.items():
        if len(lst) > 1:
            with bpy.context.temp_override(active_object=lst[0], selected_editable_objects=lst, selected_objects=lst):
                bpy.ops.object.join()
        o = lst[0]; o.name = gname; o.parent = rig
        mod = o.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
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
