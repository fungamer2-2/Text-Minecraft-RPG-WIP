import random, json, os
from enum import Enum
from termcolor import cprint, colored
#A text-based RPG game based on Minecraft

def one_in(x):
	"Returns True with a probability of 1/x, otherwise returns False"
	return x <= 1 or random.randint(1, x) == 1

def x_in_y(x, y):
	"Returns True with a probability of x/y, otherwise returns False"
	return random.uniform(0, y) < x

def choice_input(*choices, return_text=False):
	for index, choice in enumerate(choices):
		print(f"{index + 1}. {choice}")
	while True:
		try:
			choice = int(input(">> "))
		except ValueError:
			continue
		else:
			if 1 <= choice <= len(choices):
				return choices[choice - 1] if return_text else choice
	
class MobBehaviorType(Enum):
	passive = 0 #Passive; won't attack even if attacked
	neutral = 1 #Neutral; will become hostile if attacked
	hostile = 2 #Hostile; will attack on sight

file_path = os.path.dirname(__file__) + "/"
mobs_dict = json.load(open(file_path + "mobs.json"))

class MobType:
	
	def __init__(self, name, max_hp, behavior: MobBehaviorType, death_drops, night_mob, attack_strength):
		self.name = name
		self.hp = max_hp
		self.behavior = behavior
		self.death_drops = death_drops
		self.night_mob = night_mob
		self.attack_strength = attack_strength
		
	@staticmethod
	def from_dict(d):
		name = d["name"]
		HP = d["HP"]
		b = d["behavior"]
		if b == "passive":
			behavior = MobBehaviorType.passive
		elif b == "neutral":
			behavior = MobBehaviorType.neutral
		elif b == "hostile":
			behavior = MobBehaviorType.hostile
		else:
			raise ValueError(f"Invalid behavior type {b!r}")
		attack_strength = d.get("attack_strength")
		if attack_strength is None and b != "passive":
			raise ValueError("Non-passive mobs require an attack strength")
		death_drops = d.get("death_drops", {})
		night_mob = d.get("night_mob", False)
		return MobType(name, HP, behavior, death_drops, night_mob, attack_strength)

mob_types = {}

for mob_dict in mobs_dict:
	mob_types[mob_dict["name"]] = MobType.from_dict(mob_dict)
	
class Mob:
	
	def __init__(self, name, HP, behavior: MobBehaviorType, death_drops, attack_strength):
		self.name = name
		self.HP = HP
		self.behavior = behavior
		self.death_drops = death_drops
		self.attack_strength = attack_strength
		
	@staticmethod
	def new_mob(typ: str):
		typ = mob_types[typ]
		return Mob(typ.name, typ.hp, typ.behavior, typ.death_drops, typ.attack_strength)
	
	def damage(self, amount, player):
		self.HP -= amount
		if self.HP <= 0:
			print(f"The {self.name.lower()} is dead!")
			self.on_death(player)
			
	def on_death(self, player):
		if self.death_drops:
			got = {}
			for drop in self.death_drops:
				r = self.death_drops[drop]
				assert isinstance(r, dict), f"Unexpected value '{r}'"
				q = r["quantity"]
				x, y = r.get("chance", [1, 1])
				if isinstance(q, list):
					assert len(q) == 2, "A range must have exactly one start and one end"
					start, end = tuple(q)
					amount = random.randint(start, end)
				elif isinstance(q, int):
					amount = q
				else:
					raise TypeError("Amount must be an int or a 2-item list")
				if amount > 0 and x_in_y(x, y):
					if drop == "EXP":
						player.EXP += amount
					else:
						got[drop] = amount
			print("You got: ")
			for item in got:
				print(f"{got[item]}x {item}")
				player.add_item(item, got[item])

recipes = json.load(open(file_path + "recipes.json"))
				
class Time:
	
	def __init__(self):
		self.mins = 0
		self.secs = 0
		
	def is_night(self):
		return self.mins >= 20
	
	def advance(self, secs):
		was_night = self.is_night()
		last_mins = self.mins
		self.secs += secs
		while self.secs >= 60:
			self.mins += 1
			self.secs -= 60
		self.mins %= 40
		is_night = self.is_night()
		if was_night ^ is_night:
			if is_night:
				cprint("It is now nighttime", "blue")
			else:
				cprint("It is now daytime", "blue")
		elif last_mins < 18 and self.mins >= 18:
			cprint("The sun begins to set", "blue")
		elif last_mins < 38 and self.mins >= 38:
			cprint("The sun begins to come up", "blue")

class Player:
	
	def __init__(self):
		self.HP = 20
		self.hunger = 20
		self.food_exhaustion = 0
		self.saturation = 5
		self.inventory = {}
		self.tools = []
		self.curr_weapon = None
		self.EXP = 0
		self.time = Time()
		
	def damage(self, amount, death_reason=None):
		if amount <= 0:
			return
		cprint(f"You take {amount} damage!", "red")
		self.HP -= amount
		self.mod_food_exhaustion(0.1)
		if self.HP <= 0:
			self.die(death_reason)
		print(f"HP: {self.HP}/20")
		
	def die(self, death_reason=None):
		print("You died!")
		if death_reason:
			print(death_reason)
		print(f"\nScore: {self.EXP}")
		exit()
		
	def heal(self, amount):
		if amount <= 0:
			return False
		old_hp = self.HP
		self.HP = min(self.HP + amount, 20)
		healed_by = self.HP - old_hp
		if healed_by > 0:
			cprint(f"You are healed by {healed_by} HP.", "green")
			print(f"HP: {self.HP}/20")
			return True
		return False
	 
	def tick(self):
		if self.HP < 20:
			if (self.hunger == 20 or (self.hunger >= 17 and one_in(8))) and self.heal(1):
				self.mod_food_exhaustion(6)
		self.time.advance(0.5)
	
	def mod_food_exhaustion(self, amount):
		self.food_exhaustion += amount
		if self.food_exhaustion >= 4:
			if self.saturation == 0:
				self.hunger -= 1
			else:
				self.saturation -= 1
			self.print_hunger()
			self.food_exhaustion = 0		
	
	def print_hunger(self):
		if self.saturation == 0:
			cprint(f"Hunger: {self.hunger}/20", "yellow")
		else:
			print(f"Hunger: {self.hunger}/20")
	
	def add_item(self, item, amount=1):
		if item in self.inventory:
			self.inventory[item] += amount
		else:
			self.inventory[item] = amount
			
	def add_tool(self, tool):
		self.tools.append(tool)
			
	def remove_item(self, item, amount):
		if amount <= 0:
			return
		if item not in self.inventory or amount > self.inventory[item]:
			raise ValueError("Tried to remove more of item than available in inventory")
		self.inventory[item] -= amount
		if self.inventory[item] <= 0:
			del self.inventory[item]
			
	def has_item(self, item, amount=1):
		if item not in self.inventory:
			return False
		return self.inventory[item] >= amount
			
class Tool:
	
	def __init__(self, name, durability):
		self.name = name
		self.durability = durability
		self.max_durability = durability
		
class Sword(Tool):
		
	def __init__(self, name, damage, durability):
		super().__init__(name, durability)
		self.damage = damage
		
def durability_message(durability, max_durability):
	durability_msg = f"{durability}/{max_durability}"
	if durability <= max_durability // 4:
		color = "red"
	elif durability <= max_durability // 2:
		color = "yellow"
	else:
		color = "green"
	return colored(durability_msg, color)

print("MINCERAFT" if one_in(10000) else "MINECRAFT") #An extremely rare easter egg
print()
choice = choice_input("Play", "Quit")
if choice == 2:
	exit()
	
player = Player()

passive_mob_types = list(filter(lambda typ: mob_types[typ].behavior == MobBehaviorType.passive, mob_types))
night_mob_types = list(filter(lambda typ: mob_types[typ].night_mob, mob_types))

while True:
	player.tick()
	if player.time.is_night():
		print("It is currently nighttime")
	print(f"HP: {player.HP}/20")
	if player.saturation == 0:
		cprint(f"Hunger: {player.hunger}/20", "yellow")
	else:
		print(f"Hunger: {player.hunger}/20")
	if player.curr_weapon:
		print(f"Current weapon: {player.curr_weapon.name} - Durability {durability_message(weapon.durability, weapon.max_durability)}")
	choice = choice_input("Explore", "Inventory", "Craft", "Switch Weapon")
	if choice == 1:
		print("You explore for a while.")
		player.mod_food_exhaustion(0.001)
		player.time.advance(random.randint(10, 50))
		mob_chance = 3 if player.time.is_night() else 8
		if one_in(mob_chance):
			if player.time.is_night():
				choices = night_mob_types
			else:
				choices = passive_mob_types
			mob = Mob.new_mob(random.choice(choices))
			#mob = Mob.new_mob("Creeper")
			mob_name = mob.name.lower()
			print(f"You found a {mob_name} while exploring{'!' if mob.behavior == MobBehaviorType.hostile else '.'}")
			if mob.behavior == MobBehaviorType.hostile and mob_name != "creeper" and one_in(2):
				cprint(f"The {mob_name} attacks you!", "red")
				player.damage(mob.attack_strength)
			creeper_turn = 0
			choice = choice_input("Attack", "Flee" if mob.behavior == MobBehaviorType.hostile else "Ignore")
			if choice == 1:
				run = 0
				while True:
					is_unarmed = player.curr_weapon is None
					if run > 0:
						run -= 1
						if run == 0:
							print(f"The {mob_name} stops running.")
					player.mod_food_exhaustion(0.1)
					if run > 0 and one_in(3):
						print(f"You miss the {mob_name} attacking it while it was fleeing.")
					else:
						print(f"You attack the {mob_name}.") #TODO: Vary this message based on wielded weapon
						if is_unarmed:
							damage = 1
						else:
							damage = player.curr_weapon.damage
						weapon = player.curr_weapon
						if weapon:
							weapon.durability -= 1
							if weapon.durability < 0:
								cprint(f"Your {weapon.name} is destroyed!", "red")
								player.tools.remove(weapon)
								player.curr_weapon = None
							else:
								print(f"Weapon durability: {durability_message(weapon.durability, weapon.max_durability)}")
						mob.damage(damage, player) #TODO: Add different types of swords, each doing different amounts of damage
						if mob.HP <= 0:
							break
						if mob.behavior == MobBehaviorType.passive:
							if not one_in(3) and run == 0:
								print(f"The {mob_name} starts running away.")
								run += random.randint(3, 5)
					if is_unarmed:
						attack_speed = 4 #Attack speed controls the chance of being attacked by a mob when we attack
					else:
						attack_speed = 1.6
					if mob_name == "creeper":
						creeper_turn += 1
						if creeper_turn > 2 and not one_in(creeper_turn - 1): #Increasing chance to explode after the first 2 turns
							damage = max(random.randint(1, mob.attack_strength) for _ in range(4)) #attack_strength defines explosion power for creepers
							print("The creeper explodes!")
							player.damage(damage)
							break
						else:
							print("The creeper flashes...")
					elif mob.behavior != MobBehaviorType.passive and x_in_y(1, attack_speed) and not one_in(4): #I use x_in_y instead of one_in because x_in_y works with floats
						print(f"The {mob_name} attacks you!")
						player.damage(mob.attack_strength)
					player.tick()
					choice = choice_input("Attack", "Ignore" if mob.behavior == MobBehaviorType.passive else "Flee")
					if choice == 2:
						break
		elif x_in_y(3, 5):
			explore_finds = [("Grass", 8), ("Dirt", 1), ("Wood", 4)]
			choices = [val[0] for val in explore_finds]
			weights = [val[1] for val in explore_finds]
			found = random.choices(choices, weights=weights)[0]
			print(f"You found 1x {found}")
			player.add_item(found)
	elif choice == 2:
		if len(player.inventory) == 0:
			print("There is nothing in your inventory")
		else:
			print("Your inventory:")
			for item in player.inventory:
				print(f"{player.inventory[item]}x {item}")
			print("Your tools:")
			for index, tool in enumerate(player.tools):
				print(f"{index+1}. {tool.name} - Durability {tool.durability}/{tool.max_durability}")
	elif choice == 3:
		craftable = []
		for recipe in recipes:
			info = recipes[recipe]
			components = info["components"]
			for component in components:
				name = component[0]
				amount = component[1]
				if not player.has_item(name, amount):
					break
			else:
				craftable.append((recipe, recipes[recipe]))
		if len(craftable) == 0:
			print("There are no items that you have the components to craft")
		else:
			print("Items you can craft:")
			for item in craftable:
				name, info = item
				quantity = info.get("quantity", 1)
				string = f"{quantity}x {name} | Components: "
				components = info["components"]
				string += ", ".join(f"{c[1]}x {c[0]}" for c in components)
				print(string)
				print()
			print("What would you like to craft?")
			item_name = input()
			item = next((v for v in craftable if v[0] == item_name), None)
			if item is not None:
				name = item[0]
				components = item[1]["components"]
				quantity = item[1]["quantity"]
				for component in components:
					player.remove_item(*component)
				if "Sword" in name:
					player.add_tool(Sword(name, 4, 60))
				else:
					player.add_item(name, quantity)
				print(f"You have crafted {quantity}x {name}")
			else:
				print("Invalid item")
	elif choice == 4:
		if len(player.tools) > 0:
			options = [] 
			for tool in player.tools:
				options.append(f"{tool.name} - Durability {durability_message(tool.durability, tool.max_durability)}")
			options.append("Unarmed")
			print("Which weapon would you like to switch to?")
			choice = choice_input(*options)
			if choice == len(player.tools) + 1:
				print("You decide to go unarmed")
				player.curr_weapon = None
			else:
				weapon = player.tools[choice - 1]
				print(f"You switch to your {weapon.name}")
				player.curr_weapon = weapon
		else:
			print("You don't have any weapons")