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

## Features
- **Quests:** Elder Maren by the town crystal gives a five-part quest chain that ends with the Ancient Warden.
- **Loot and gear:** monsters drop weapons, armor and trinkets in five rarities (Common to Legendary). Open the bag to compare, equip or sell. Better weapons glow in their rarity colour.
- **Sound and music:** combat sounds and calm generated music that turns darker in Duskwood and the Barrens. Mute with the ♫ button.
- **Animations:** keyframed attacks for every skill, 3-hit combos for Warrior and Assassin, a real bow draw for the Marksman, staff casting for the Mage, class-specific idle and run styles, hit flinches, kneeling death and respawn, and a level-up pose. Monsters wind up before attacking (golems show a red warning zone), flinch when hit, and each type has its own death.
- **Graphics:** shader sky with drifting clouds and sun glow, wind-swept grass and swaying trees, animated water ponds, textured ground, rim-lit characters, filmic color with bloom, zone fog (purple mist in Duskwood, dust in the Barrens), and trees that fade when they block your view. Tap **HQ/LQ** to switch quality; it drops to LQ by itself if the phone struggles.
- **Saving:** progress saves automatically on the phone, one hero per class.

## World
Emberhollow (town) → Mossmere Fields (Lv 1–2) → Duskwood (Lv 3–5) → Rune Barrens (Lv 6–10), with the Ancient Warden boss to the north.

Built with [three.js](https://threejs.org) r128 in a single `index.html`. Other players in the world are simulated for now.
