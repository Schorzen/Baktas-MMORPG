# Baktas MMORPG

A 3D fantasy MMORPG prototype that runs in the browser. Made for phones, best played in landscape.

## Play
Open the GitHub Pages link on your phone, turn it sideways and tap **Enter World**.

## Classes
- **Warrior** – Slash, Whirlwind, Charge, Battle Cry
- **Mage** – Fire Bolt, Frost Nova, Meteor, Blink
- **Marksman** – Aimed Shot, Volley, Piercing Arrow, Evasive Roll
- **Assassin** – Shadow Stab (teleports to enemies up to 9 m away), Shadowstep, Fan of Knives, Vanish

## Controls
- Left stick: move
- Drag the screen: look around · pinch: zoom
- Tap an enemy: target and auto-attack
- Skill buttons (bottom right): use skills
- Target button: lock on to the nearest enemy · Heart button: drink a potion
- Gear icon: settings (graphics, sound, music, camera speed, return to town)

## Models
The four heroes are built in Blender from `models/heroes.py` the monsters (slime, wolf, rune golem, Ancient Warden) from `models/mobs.py`, and the world props (trees, rocks, cottages, lamps, crystal, runestones, crypt pillars, portal, chest) from `models/world.py`.
Each script builds smooth meshes, a skeleton, outfits and weapons, and exports rigged `.glb` files into `models/`. The models are embedded in `index.html`, so the game is still a single file. To rebuild after editing the script:

```
pip install bpy
python models/heroes.py -- models
python models/mobs.py -- models
python models/world.py -- models
```

## Features
- **Quests:** Elder Maren by the town crystal gives a five-part quest chain that ends with the Ancient Warden.
- **Loot and gear:** monsters drop weapons, armor and trinkets in five rarities (Common to Legendary). Open the bag to compare, equip or sell. Better weapons glow in their rarity colour.
- **Sound and music:** combat sounds and calm generated music that turns darker in Duskwood and the Barrens. Mute with the ♫ button.
- **Animations:** keyframed attacks for every skill, 3-hit combos for Warrior and Assassin, a real bow draw for the Marksman, staff casting for the Mage, class-specific idle and run styles, hit flinches, kneeling death and respawn, and a level-up pose. Monsters wind up before attacking (golems show a red warning zone), flinch when hit, and each type has its own death.
- **Graphics:** shader sky with drifting clouds and sun glow, wind-swept grass and swaying trees, animated water ponds, textured ground, rim-lit characters, filmic color with bloom, zone fog (purple mist in Duskwood, dust in the Barrens), and trees that fade when they block your view. Tap **HQ/LQ** to switch quality; it drops to LQ by itself if the phone struggles.
- **Saving:** progress saves automatically on the phone, one hero per class.

## Sunken Crypt (dungeon)
A portal arch in Duskwood leads to the Sunken Crypt: three waves (wolves, then wolves and golems, then the Crypt Warden). Clear it to open a treasure chest with gear and silver, then take the exit portal back. Recommended level 4+; repeat it as often as you like.

## Frostpeak and the Glacier Hollow
A portal north-west of the Barrens leads up to Frostpeak (level 11-14): a snowy zone with frost wolves, ice golems, a frozen lake and falling snow. At its far end a second dungeon, the Glacier Hollow, has four waves and the Glacier King.

## Shop and potions
Trader Bram in Emberhollow sells gear for your level and health potions. Potions heal 40% (10 second cooldown) from the heart button; monsters sometimes drop them.

## Visible gear
Weapons and armor change shape with the rarity you equip: Common/Uncommon use the base look, Rare/Epic add a tier 2 weapon model and steel shoulder, chest and leg plates, and Legendary gives crystal weapons and dark spiked armor.

## Install on your phone
Open the game in Chrome on Android, then use the menu and choose Add to Home screen (or the Install button in Settings). It opens full screen in landscape and still starts when you are offline.

## World
Emberhollow (town) → Mossmere Fields (Lv 1–2) → Duskwood (Lv 3–5) → Rune Barrens (Lv 6–10), with the Ancient Warden boss to the north.

Built with [three.js](https://threejs.org) r128 in a single `index.html`. Other players in the world are simulated for now.
