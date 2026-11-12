"""Build the Baktas monsters (slime, wolf, rune golem, Ancient Warden) in Blender.
Reuses the generators and exporter from heroes.py; each monster swaps in its own skeleton."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heroes as H
from mathutils import Vector

H.OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 1 else '/tmp/claude-0/glb'
os.makedirs(H.OUT, exist_ok=True)
ell, lathe, tube, xf, cube, part, mat = H.ell, H.lathe, H.tube, H.xf, H.cube, H.part, H.mat

def use_bones(B):
    H.BONES.clear(); H.BONES.update(B)
    H.DEFORM[:] = [b for b in B if b != 'root']

def hsh(x, y, z, seed):
    v = math.sin(x * 12.9898 + y * 78.233 + z * 37.719 + seed * 4.1) * 43758.5453
    return v - math.floor(v)

def rock(c, r, seed=1, amt=.12, seg=10, ring=7):
    V, F = ell(c, r, seg, ring)
    out = []
    for v in V:
        d = Vector(v) - Vector(c)
        n = d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))
        q = (round(n.x * 3) / 3, round(n.y * 3) / 3, round(n.z * 3) / 3)
        k = 1 + (hsh(*q, seed) - .5) * 2 * amt + (hsh(n.x, n.y, n.z, seed + 7) - .5) * amt * .6
        out.append(tuple(Vector(c) + d * k))
    return out, F

# ------------------------------------------------------------------ slime
def build_slime():
    use_bones({'root': ((0, 0, 0), (0, .3, 0), None), 'body': ((0, .05, 0), (0, 1.1, 0), 'root')})
    gel = mat('Slime', 0x7cc46a, .15)
    part(lathe([(0, 1.22), (.2, 1.18), (.44, 1.0), (.63, .76), (.74, .5), (.72, .25), (.6, .07), (.32, 0), (0, 0)], seg=26), gel, 'body', name='gel')
    part(ell((0, .5, -.05), (.27, .25, .27), 12, 8), mat('Core', 0x2f5a28, .6), 'body', name='core')
    for (x, y, z, r) in ((.3, .35, .2, .07), (-.25, .7, -.1, .05), (.05, .25, -.35, .06), (-.35, .3, .25, .045)):
        part(ell((x, y, z), (r, r, r), 8, 6), mat('Bubble', 0xc8f0b0, .1), 'body', name='bubble')
    white = mat('EyeWhite', 0xf4f1e6, .3); black = mat('Pupil', 0x15130f, .3)
    for k in (1, -1):
        part(ell((.21 * k, .8, .53), (.12, .15, .07), 12, 8), white, 'body', name='eye')
        part(ell((.2 * k, .78, .59), (.055, .07, .03), 10, 6), black, 'body', name='pupil')
        part(ell((.18 * k, .83, .615), (.018, .02, .01), 6, 4), white, 'body', name='glint')
    part(ell((0, .55, .64), (.12, .045, .04), 10, 6), black, 'body', name='mouth')
    leaf = mat('Leaf', 0x5c9e3a, .7)
    part(tube([(0, 1.18, 0), (.03, 1.32, 0), (.08, 1.42, 0)], [.03, .025, .02], 6), leaf, 'body', name='stem')
    part(xf(ell((0, 0, 0), (.16, .025, .07), 10, 6), rot=(0, 0, .5), t=(.2, 1.45, 0)), leaf, 'body', name='leaf')
    part(xf(ell((0, 0, 0), (.12, .022, .055), 10, 6), rot=(0, 0, -.4), t=(-.05, 1.44, 0)), leaf, 'body', name='leaf2')
    return 'slime'

# ------------------------------------------------------------------ wolf
def build_wolf():
    B = {'root': ((0, 0, 0), (0, .3, 0), None),
         'spine': ((0, .92, -.55), (0, .98, .45), 'root'),
         'neck': ((0, .98, .45), (0, 1.15, .75), 'spine'),
         'head': ((0, 1.15, .75), (0, 1.12, 1.25), 'neck'),
         'tail': ((0, 1.0, -.62), (0, .9, -1.3), 'spine')}
    for nm, x, z, z2 in (('FL', -.2, .45, .5), ('FR', .2, .45, .5), ('BL', -.2, -.45, -.45), ('BR', .2, -.45, -.45)):
        B['leg' + nm] = ((x, .88, z), (x * 1.05, .46, (z + z2) / 2), 'spine')
        B['paw' + nm] = ((x * 1.05, .46, (z + z2) / 2), (x * 1.05, .06, z2), 'leg' + nm)
    use_bones(B)
    fur = mat('Fur', 0x4a4658, .95); dark = mat('FurDark', 0x2e2b38, .95); belly = mat('Belly', 0x77718a, .95)
    glow = mat('Glow', 0xffb04a, .3, 0, 0xffb04a); nose = mat('Nose', 0x141216, .4); fang = mat('Fang', 0xeee8d8, .4)
    part(tube([(0, .9, -.66), (0, .97, -.35), (0, 1.0, .05), (0, 1.03, .38), (0, 1.06, .55)], [.2, .27, .29, .31, .26], 16, flat=.82), fur,
         ('auto', ['spine', 'neck', 'tail']), name='torso')
    part(ell((0, .9, .38), (.27, .3, .24), 14, 10), belly, ('auto', ['spine', 'neck']), name='ruff')
    for i in range(5):
        z = -.45 + i * .22
        part(xf(lathe([(0, .16), (.06, 0)], seg=5), rot=(-.5, 0, 0), t=(0, 1.22 + .02 * math.sin(i), z)), dark, 'spine', name='tuft')
    part(tube([(0, 1.0, .45), (0, 1.12, .66), (0, 1.17, .8)], [.2, .18, .16], 14), fur, ('auto', ['neck', 'head', 'spine']), name='neck')
    part(ell((0, 1.17, .86), (.19, .18, .21), 16, 10), fur, 'head', name='skull')
    part(tube([(0, 1.12, .95), (0, 1.08, 1.15), (0, 1.05, 1.3)], [.12, .095, .065], 12), fur, 'head', name='snout')
    part(tube([(0, 1.02, .95), (0, .99, 1.15), (0, .99, 1.26)], [.09, .07, .045], 10, flat=.6), belly, 'head', name='jaw')
    part(ell((0, 1.075, 1.32), (.045, .038, .035), 8, 6), nose, 'head', name='nose')
    for k in (1, -1):
        part(xf(lathe([(0, .2), (.075, 0)], seg=6, sz=.5), rot=(.25, 0, -.25 * k), t=(.11 * k, 1.29, .8)), dark, 'head', name='ear')
        part(ell((.095 * k, 1.21, 1.03), (.04, .026, .02), 8, 5), glow, 'head', name='eye')
        part(xf(lathe([(0, -.06), (.015, 0)], seg=5), t=(.045 * k, 1.0, 1.25)), fang, 'head', name='fang')
    for nm, x, z, z2, back in (('FL', -.2, .45, .5, 0), ('FR', .2, .45, .5, 0), ('BL', -.2, -.45, -.45, 1), ('BR', .2, -.45, -.45, 1)):
        xm = x * 1.05
        if back:
            pts = [(x, .95, z), (xm, .7, z - .08), (xm, .46, z - .08), (xm, .27, z - .02), (xm, .09, z2)]
            rad = [.15, .11, .075, .058, .05]
        else:
            pts = [(x, .9, z), (xm, .66, z + .02), (xm, .46, z + .03), (xm, .27, z + .04), (xm, .09, z2)]
            rad = [.11, .085, .066, .056, .05]
        part(tube(pts, rad, 12), fur, ('auto', ['spine', 'leg' + nm, 'paw' + nm]), name='leg')
        part(ell((xm, .06, z2 + .04), (.07, .055, .1), 10, 6), dark, 'paw' + nm, name='paw')
    part(tube([(0, 1.0, -.6), (0, 1.06, -.84), (0, .99, -1.08), (0, .86, -1.3)], [.08, .1, .085, .02], 12), dark, ('auto', ['tail', 'spine']), name='tail')
    return 'wolf'

# ------------------------------------------------------------------ golems
def golem_bones():
    B = {'root': ((0, 0, 0), (0, .3, 0), None),
         'torso': ((0, 1.2, 0), (0, 2.6, 0), 'root'),
         'head': ((0, 2.6, 0), (0, 3.2, .1), 'torso')}
    for s, k in (('L', -1), ('R', 1)):
        B['arm_' + s] = ((1.0 * k, 2.4, 0), (1.04 * k, 1.0, 0), 'torso')
        B['leg_' + s] = ((.38 * k, 1.2, 0), (.4 * k, .1, 0), 'root')
    return B

def build_golem_variant(boss):
    use_bones(golem_bones())
    stone = mat('Stone', 0x4a4560 if boss else 0x7a7c74, .95)
    stone2 = mat('Stone2', 0x37324a if boss else 0x5c5e57, .95)
    glow = mat('Glow', 0xd88bff if boss else 0x6ff2ff, .3, 0, 0xd88bff if boss else 0x6ff2ff)
    moss = mat('Moss', 0x3c2f52 if boss else 0x5f8a3e, .95)
    sm = False
    part(rock((0, 2.02, 0), (.8, .72, .54), 1), stone, ('auto', ['torso']), smooth=sm, name='chest')
    part(rock((0, 1.32, 0), (.56, .32, .42), 2), stone2, 'torso', smooth=sm, name='pelvis')
    part(rock((0, 2.9, .12), (.33, .28, .31), 3, .1), stone, 'head', smooth=sm, name='head')
    part(rock((0, 3.02, .3), (.3, .08, .1), 4, .15), stone2, 'head', smooth=sm, name='brow')
    for k in (1, -1):
        part(cube((.12 * k, 2.93, .41), (.12, .05, .03), (0, 0, -.15 * k)), glow, 'head', smooth=False, name='eye')
    # glowing rune crystal + rune lines on the chest
    part(rock((0, 2.08, .5), (.17, .22, .1), 5, .05, 6, 4), glow, 'torso', smooth=False, name='core')
    for (a, b) in (((-.38, 2.4, .42), (-.12, 2.18, .5)), ((.38, 2.4, .42), (.12, 2.18, .5)), ((-.32, 1.72, .44), (-.1, 1.92, .5)), ((.32, 1.72, .44), (.1, 1.92, .5))):
        part(tube([a, b], [.022, .022], 5), glow, 'torso', name='rune')
    for s, k in (('L', -1), ('R', 1)):
        part(rock((1.0 * k, 2.42, 0), (.4, .36, .38), 10 + k), stone2, ('auto', ['torso', 'arm_' + s]), smooth=sm, name='shoulder')
        part(rock((1.0 * k, 1.95, 0), (.28, .38, .3), 12 + k), stone, 'arm_' + s, smooth=sm, name='upper')
        part(rock((1.02 * k, 1.47, .02), (.3, .34, .31), 14 + k), stone, 'arm_' + s, smooth=sm, name='fore')
        part(rock((1.04 * k, 1.04, .04), (.38, .33, .38), 16 + k), stone2, 'arm_' + s, smooth=sm, name='fist')
        part(rock((.38 * k, .92, 0), (.31, .36, .33), 18 + k), stone, 'leg_' + s, smooth=sm, name='thigh')
        part(rock((.4 * k, .32, .06), (.33, .34, .4), 20 + k), stone2, 'leg_' + s, smooth=sm, name='foot')
        part(xf(ell((0, 0, 0), (.3, .07, .26), 10, 6), t=(1.0 * k, 2.74, 0)), moss, 'arm_' + s, name='moss')
        part(tube([(1.0 * k, 1.6, .3), (1.02 * k, 1.3, .32)], [.02, .02], 5), glow, 'arm_' + s, name='armrune')
    part(xf(ell((0, 0, 0), (.25, .06, .22), 10, 6), t=(0, 3.15, .05)), moss, 'head', name='headmoss')
    if boss:
        for i, (x, y, z, h, tilt) in enumerate(((0, 3.15, .02, .55, 0), (-.18, 3.1, 0, .4, .35), (.18, 3.1, 0, .4, -.35), (-.3, 3.0, -.05, .28, .7), (.3, 3.0, -.05, .28, -.7))):
            part(xf(lathe([(0, h), (.07, .1), (.06, 0)], seg=5), rot=(0, 0, tilt), t=(x, y, z)), glow, 'head', smooth=False, name='crown')
        for k in (1, -1):
            s = 'L' if k < 0 else 'R'
            for j in range(3):
                part(xf(lathe([(0, .38 - j * .08), (.07, 0)], seg=5), rot=(-.3 + j * .3, 0, -.6 * k), t=((1.0 + .05 * j) * k, 2.72, -.15 + j * .15)), glow, 'arm_' + s, smooth=False, name='spike')
    return 'warden' if boss else 'golem'

def build_golem():
    return build_golem_variant(False)

def build_warden():
    return build_golem_variant(True)

if __name__ == '__main__':
    which = sys.argv[sys.argv.index('--') + 2:] if '--' in sys.argv else []
    for fn in (build_slime, build_wolf, build_golem, build_warden):
        if not which or fn.__name__[6:] in which:
            H.build(fn)
